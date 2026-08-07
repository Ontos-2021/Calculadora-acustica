from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

TIERS = {
    None: {"limit": 10, "tier": "anonymous"},
    "free_tier": {"limit": 100, "tier": "free"},
}


async def verify_tier(
    api_key: str = Security(APIKeyHeader(name="X-API-Key", auto_error=False)),
):
    tier = TIERS.get(api_key, TIERS.get(None))
    return tier
