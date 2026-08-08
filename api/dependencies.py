from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

TIERS: dict[str | None, dict] = {
    None: {"tier": "anonymous", "rate": 5, "features": ["basic"]},
    "free_tier": {"tier": "free", "rate": 100, "features": ["basic", "pressure_map"]},
}

FEATURE_MAP = {
    "/api/v1/calculate": ["basic"],
    "/api/v1/pressure-map": ["basic", "pressure_map"],
    "/api/v1/materials": ["basic"],
    "/api/v1/materials/categories": ["basic"],
    "/api/v1/design/ratios": ["basic"],
    "/api/v1/design/targets": ["basic"],
    "/api/v1/design/air-absorption": ["basic"],
    "/api/v1/design/audience-absorption": ["basic"],
    "/api/v1/design/inverse": ["basic"],
    "/api/v1/design/absorbers/porous": ["basic"],
    "/api/v1/design/absorbers/helmholtz": ["basic"],
    "/api/v1/design/absorbers/membrane": ["basic"],
    "/api/v1/design/diffusers/qrd": ["basic"],
    "/api/v1/design/diffusers/skyline": ["basic"],
    "/api/v1/design/isolation/single-panel": ["basic"],
    "/api/v1/design/isolation/double-panel": ["basic"],
    "/api/v1/design/isolation/nc": ["basic"],
    "/api/v1/design/isolation/nc-targets": ["basic"],
    "/api/v1/impulse-response": ["ism"],
    "/api/v1/health": ["basic"],
}


def _normalize_path(path: str) -> str:
    """Remove trailing slash and normalize"""
    path = path.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return path


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_endpoint_access(
    api_key: str = Security(api_key_header),
):
    """Retorna el tier del usuario. Los endpoints individuales verifican features específicas."""
    tier = TIERS.get(api_key, TIERS.get(None))
    return tier


def check_feature(tier: dict | None, endpoint: str) -> bool:
    if tier is None:
        tier = TIERS[None]
    required = FEATURE_MAP.get(_normalize_path(endpoint), [])
    if not required:
        return True
    user_features = tier.get("features", [])
    return any(f in user_features for f in required)
