"""E2E-only API app with deterministic infrastructure and non-limiting quotas."""

from api.main import create_app
from api.rate_limit import RateLimitResult, endpoint_cost, get_rate_limiter


class UnlimitedTestRateLimiter:
    def check(self, _identity, tier, endpoint, **_kwargs) -> RateLimitResult:
        del _identity
        cost = endpoint_cost(endpoint, _kwargs.get("method"))
        return RateLimitResult(
            allowed=True,
            tier=getattr(tier, "value", tier) or "ANONYMOUS",
            cost=cost,
            limit=1_000_000,
            remaining=1_000_000 - cost,
            reset_at=0,
            reset_after=0,
            daily_limit=1_000_000,
            daily_remaining=1_000_000 - cost,
            daily_reset_at=0,
            daily_reset_after=0,
        )

    def check_principal(
        self, principal, endpoint, *, client_ip=None, method=None
    ) -> RateLimitResult:
        del client_ip
        return self.check(
            "e2e",
            principal.tier if principal else None,
            endpoint,
            method=method,
        )


app = create_app()
app.dependency_overrides[get_rate_limiter] = lambda: UnlimitedTestRateLimiter()
