from __future__ import annotations

import hashlib
import math
import threading
import time
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from fastapi import Depends, HTTPException, Request, Response, status
from redis import Redis
from redis.exceptions import RedisError

from .config import Settings, get_settings
from .db_models import LicenseTier
from .dependencies import get_optional_principal
from .licensing import AuthenticatedPrincipal, TIER_POLICIES


ANONYMOUS_QUOTAS: Mapping[str, int] = {
    "requests_per_minute": 10,
    "daily_request_units": 100,
}

ENDPOINT_COSTS: Mapping[str, int] = {
    "/api/v1/calculate": 2,
    "/api/v1/pressure-map": 5,
    "/api/v1/impulse-response": 20,
    "/api/v1/measurement/waterfall": 10,
    "/api/v1/measurement/calibrate": 10,
    "/api/v1/numerical/finite-impedance": 5,
    "/api/v1/numerical/fem2d": 25,
    "/api/v1/numerical/ray-tracing": 30,
    "/api/v1/numerical/hybrid": 50,
    "/api/v1/exports/*": 20,
}


@dataclass(frozen=True)
class WindowRequest:
    name: str
    key: str
    limit: int
    reset_at: int


@dataclass(frozen=True)
class WindowUsage:
    name: str
    limit: int
    used: int
    reset_at: int

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


@dataclass(frozen=True)
class BackendDecision:
    allowed: bool
    windows: tuple[WindowUsage, ...]


class FixedWindowBackend(Protocol):
    def consume(
        self,
        windows: Sequence[WindowRequest],
        *,
        cost: int,
        now: float,
    ) -> BackendDecision: ...


class InMemoryFixedWindowBackend:
    """Atomic fixed-window counters intended for deterministic tests and local development."""

    def __init__(self) -> None:
        self._counters: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()

    def consume(
        self,
        windows: Sequence[WindowRequest],
        *,
        cost: int,
        now: float,
    ) -> BackendDecision:
        with self._lock:
            expired = [key for key, (_, reset_at) in self._counters.items() if reset_at <= now]
            for key in expired:
                del self._counters[key]

            current = {
                window.key: self._counters.get(window.key, (0, window.reset_at))[0]
                for window in windows
            }
            allowed = all(current[window.key] + cost <= window.limit for window in windows)
            usages: list[WindowUsage] = []
            for window in windows:
                used = current[window.key]
                if allowed:
                    used += cost
                    self._counters[window.key] = (used, window.reset_at)
                usages.append(
                    WindowUsage(
                        name=window.name,
                        limit=window.limit,
                        used=used,
                        reset_at=window.reset_at,
                    )
                )
            return BackendDecision(allowed=allowed, windows=tuple(usages))


class RedisFixedWindowBackend:
    _CONSUME_SCRIPT = """
local cost = tonumber(ARGV[1])
local allowed = 1
local current = {}
for i, key in ipairs(KEYS) do
    current[i] = tonumber(redis.call('GET', key) or '0')
    local limit = tonumber(ARGV[2 * i])
    if current[i] + cost > limit then
        allowed = 0
    end
end
local result = {allowed}
for i, key in ipairs(KEYS) do
    if allowed == 1 then
        current[i] = redis.call('INCRBY', key, cost)
        redis.call('EXPIREAT', key, tonumber(ARGV[2 * i + 1]))
    end
    table.insert(result, current[i])
end
return result
"""

    def __init__(self, client: Redis) -> None:
        self.client = client

    def consume(
        self,
        windows: Sequence[WindowRequest],
        *,
        cost: int,
        now: float,
    ) -> BackendDecision:
        del now
        keys = [window.key for window in windows]
        args: list[int] = [cost]
        for window in windows:
            args.extend((window.limit, window.reset_at))
        raw = self.client.eval(self._CONSUME_SCRIPT, len(keys), *keys, *args)
        allowed = bool(int(raw[0]))
        usages = tuple(
            WindowUsage(
                name=window.name,
                limit=window.limit,
                used=int(raw[index + 1]),
                reset_at=window.reset_at,
            )
            for index, window in enumerate(windows)
        )
        return BackendDecision(allowed=allowed, windows=usages)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    tier: str
    cost: int
    limit: int
    remaining: int
    reset_at: int
    reset_after: int
    daily_limit: int
    daily_remaining: int
    daily_reset_at: int
    daily_reset_after: int
    retry_after: int | None = None

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "RateLimit-Limit": str(self.limit),
            "RateLimit-Remaining": str(self.remaining),
            "RateLimit-Reset": str(self.reset_after),
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_at),
            "X-RateLimit-Daily-Limit": str(self.daily_limit),
            "X-RateLimit-Daily-Remaining": str(self.daily_remaining),
            "X-RateLimit-Daily-Reset": str(self.daily_reset_at),
            "X-RateLimit-Cost": str(self.cost),
            "X-RateLimit-Tier": self.tier,
        }
        if self.retry_after is not None:
            headers["Retry-After"] = str(self.retry_after)
        return headers

    def raise_if_limited(self) -> None:
        if not self.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit quota exceeded",
                headers=self.headers,
            )


def endpoint_cost(endpoint: str) -> int:
    normalized = endpoint.split("?", 1)[0].rstrip("/") or "/"
    exact = ENDPOINT_COSTS.get(normalized)
    if exact is not None:
        return exact
    for pattern, cost in ENDPOINT_COSTS.items():
        if pattern.endswith("/*") and normalized.startswith(pattern[:-1]):
            return cost
    return 1


def rate_limit_identity(
    principal: AuthenticatedPrincipal | None,
    client_ip: str | None,
) -> str:
    if principal is not None:
        return f"key:{principal.api_key_id}"
    return f"ip:{client_ip or 'unknown'}"


class FixedWindowRateLimiter:
    def __init__(
        self,
        backend: FixedWindowBackend,
        *,
        key_prefix: str = "acoustic:rate-limit",
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.backend = backend
        self.key_prefix = key_prefix
        self.clock = clock

    def check(
        self,
        identity: str,
        tier: LicenseTier | str | None,
        endpoint: str,
        *,
        cost: int | None = None,
        quota_overrides: Mapping[str, int] | None = None,
    ) -> RateLimitResult:
        resolved_cost = endpoint_cost(endpoint) if cost is None else cost
        if resolved_cost <= 0:
            raise ValueError("rate limit cost must be positive")

        if tier is None:
            tier_name = "ANONYMOUS"
            quotas = dict(ANONYMOUS_QUOTAS)
        else:
            resolved_tier = tier if isinstance(tier, LicenseTier) else LicenseTier(tier.upper())
            tier_name = resolved_tier.value
            quotas = dict(TIER_POLICIES[resolved_tier].quotas)
        if quota_overrides:
            quotas.update(
                {
                    name: value
                    for name, value in quota_overrides.items()
                    if isinstance(value, int) and not isinstance(value, bool) and value >= 0
                }
            )

        now = self.clock()
        minute_reset = (math.floor(now / 60) + 1) * 60
        daily_reset = (math.floor(now / 86_400) + 1) * 86_400
        identity_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        minute_limit = quotas["requests_per_minute"]
        daily_limit = quotas["daily_request_units"]
        windows = (
            WindowRequest(
                name="minute",
                key=f"{self.key_prefix}:{identity_hash}:minute:{minute_reset}",
                limit=minute_limit,
                reset_at=minute_reset,
            ),
            WindowRequest(
                name="day",
                key=f"{self.key_prefix}:{identity_hash}:day:{daily_reset}",
                limit=daily_limit,
                reset_at=daily_reset,
            ),
        )
        decision = self.backend.consume(windows, cost=resolved_cost, now=now)
        usage = {window.name: window for window in decision.windows}

        retry_after: int | None = None
        if not decision.allowed:
            violated_resets = [
                window.reset_at
                for window in decision.windows
                if window.used + resolved_cost > window.limit
            ]
            retry_after = max(1, math.ceil(max(violated_resets) - now))

        return RateLimitResult(
            allowed=decision.allowed,
            tier=tier_name,
            cost=resolved_cost,
            limit=minute_limit,
            remaining=usage["minute"].remaining,
            reset_at=minute_reset,
            reset_after=max(0, math.ceil(minute_reset - now)),
            daily_limit=daily_limit,
            daily_remaining=usage["day"].remaining,
            daily_reset_at=daily_reset,
            daily_reset_after=max(0, math.ceil(daily_reset - now)),
            retry_after=retry_after,
        )

    def check_principal(
        self,
        principal: AuthenticatedPrincipal | None,
        endpoint: str,
        *,
        client_ip: str | None = None,
    ) -> RateLimitResult:
        return self.check(
            rate_limit_identity(principal, client_ip),
            principal.tier if principal else None,
            endpoint,
            quota_overrides=principal.quotas if principal else None,
        )


def create_rate_limiter(
    settings: Settings,
    *,
    redis_client: Redis | None = None,
) -> FixedWindowRateLimiter:
    client = redis_client or Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        client.ping()
    except (RedisError, OSError) as exc:
        if settings.environment == "production":
            raise RuntimeError("Redis is required for production rate limiting") from exc
        warnings.warn(
            "Redis unavailable; using process-local rate limiting outside production",
            RuntimeWarning,
            stacklevel=2,
        )
        return FixedWindowRateLimiter(
            InMemoryFixedWindowBackend(), key_prefix=settings.rate_limit_key_prefix
        )
    return FixedWindowRateLimiter(
        RedisFixedWindowBackend(client), key_prefix=settings.rate_limit_key_prefix
    )


@lru_cache
def get_rate_limiter() -> FixedWindowRateLimiter:
    return create_rate_limiter(get_settings())


def enforce_rate_limit(
    request: Request,
    response: Response,
    principal: AuthenticatedPrincipal | None = Depends(get_optional_principal),
    limiter: FixedWindowRateLimiter = Depends(get_rate_limiter),
) -> RateLimitResult:
    client_ip = request.client.host if request.client else None
    result = limiter.check_principal(principal, request.url.path, client_ip=client_ip)
    result.raise_if_limited()
    response.headers.update(result.headers)
    return result
