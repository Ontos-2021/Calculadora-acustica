from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

from api.config import Settings
from api.db_models import LicenseTier
from api.dependencies import get_optional_principal
from api.rate_limit import (
    FixedWindowRateLimiter,
    InMemoryFixedWindowBackend,
    RedisFixedWindowBackend,
    create_rate_limiter,
    enforce_rate_limit,
    endpoint_cost,
    get_rate_limiter,
)


class Clock:
    def __init__(self, value: float) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def test_fixed_window_is_deterministic_atomic_and_resets():
    clock = Clock(120)
    limiter = FixedWindowRateLimiter(InMemoryFixedWindowBackend(), clock=clock)
    overrides = {"requests_per_minute": 5, "daily_request_units": 100}

    first = limiter.check("key:one", LicenseTier.FREE, "/test", cost=2, quota_overrides=overrides)
    second = limiter.check("key:one", LicenseTier.FREE, "/test", cost=2, quota_overrides=overrides)
    denied = limiter.check("key:one", LicenseTier.FREE, "/test", cost=2, quota_overrides=overrides)

    assert first.allowed and first.remaining == 3
    assert second.allowed and second.remaining == 1
    assert not denied.allowed
    assert denied.remaining == 1
    assert denied.retry_after == 60
    assert denied.headers["Retry-After"] == "60"
    assert denied.headers["X-RateLimit-Daily-Remaining"] == "96"
    with pytest.raises(HTTPException) as exc_info:
        denied.raise_if_limited()
    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["X-RateLimit-Cost"] == "2"

    clock.advance(60)
    reset = limiter.check(
        "key:one", LicenseTier.FREE, "/test", cost=2, quota_overrides=overrides
    )
    assert reset.allowed
    assert reset.remaining == 3
    assert reset.daily_remaining == 94


def test_daily_quota_is_enforced_without_partially_consuming_minute_quota():
    clock = Clock(100)
    limiter = FixedWindowRateLimiter(InMemoryFixedWindowBackend(), clock=clock)
    overrides = {"requests_per_minute": 100, "daily_request_units": 3}

    assert limiter.check(
        "key:daily", "FREE", "/test", cost=2, quota_overrides=overrides
    ).allowed
    denied = limiter.check(
        "key:daily", "FREE", "/test", cost=2, quota_overrides=overrides
    )
    assert not denied.allowed
    assert denied.remaining == 98
    assert denied.daily_remaining == 1
    assert denied.retry_after == 86_300


def test_identity_counters_are_isolated_and_tiers_have_distinct_quotas():
    clock = Clock(120)
    limiter = FixedWindowRateLimiter(InMemoryFixedWindowBackend(), clock=clock)

    free = limiter.check("key:free", LicenseTier.FREE, "/test")
    paid = limiter.check("key:paid", LicenseTier.PAID, "/test")
    other_free = limiter.check("key:other", LicenseTier.FREE, "/test")

    assert free.limit == 30 and free.remaining == 29
    assert other_free.remaining == 29
    assert paid.limit == 300 and paid.remaining == 299
    assert paid.daily_limit > free.daily_limit


def test_fastapi_wrapper_uses_ip_quota_for_anonymous_routes():
    limiter = FixedWindowRateLimiter(InMemoryFixedWindowBackend(), clock=Clock(120))
    app = FastAPI()
    app.dependency_overrides[get_optional_principal] = lambda: None
    app.dependency_overrides[get_rate_limiter] = lambda: limiter

    @app.get("/api/v1/materials")
    def public_route(_result=Depends(enforce_rate_limit)):
        return {"ok": True}

    response = TestClient(app).get("/api/v1/materials")
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Tier"] == "ANONYMOUS"
    assert response.headers["X-RateLimit-Remaining"] == "9"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/api/v1/calculate", 2),
        ("/api/v1/numerical/hybrid?quality=high", 50),
        ("/api/v1/exports/project.pdf", 20),
        ("/api/v1/materials", 1),
    ],
)
def test_endpoint_costs(path, expected):
    assert endpoint_cost(path) == expected


class UnavailableRedis:
    def ping(self):
        raise RedisError("offline")


def test_development_can_warn_and_fall_back_to_memory():
    settings = Settings(environment="test", _env_file=None)
    with pytest.warns(RuntimeWarning, match="process-local"):
        limiter = create_rate_limiter(settings, redis_client=UnavailableRedis())
    assert isinstance(limiter.backend, InMemoryFixedWindowBackend)


def test_production_never_falls_back_when_redis_is_unavailable():
    settings = Settings(
        environment="production",
        database_url="postgresql+psycopg://db/acoustic",
        redis_url="redis://redis/0",
        api_key_pepper="x" * 32,
        storage_backend="s3",
        storage_s3_bucket="exports",
        _env_file=None,
    )
    with pytest.raises(RuntimeError, match="Redis is required"):
        create_rate_limiter(settings, redis_client=UnavailableRedis())


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    def ping(self):
        return True

    def eval(self, _script, key_count, *values):
        keys = values[:key_count]
        args = values[key_count:]
        cost = int(args[0])
        current = [self.values.get(key, 0) for key in keys]
        limits = [int(args[1 + index * 2]) for index in range(key_count)]
        allowed = all(used + cost <= limit for used, limit in zip(current, limits))
        if allowed:
            current = [used + cost for used in current]
            self.values.update(zip(keys, current))
        return [int(allowed), *current]


def test_healthy_redis_selects_the_shared_backend_without_network_access():
    settings = Settings(environment="test", _env_file=None)
    limiter = create_rate_limiter(settings, redis_client=FakeRedis())
    assert isinstance(limiter.backend, RedisFixedWindowBackend)
    assert limiter.check("key:redis", LicenseTier.FREE, "/test").allowed
