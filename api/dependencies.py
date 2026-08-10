from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import get_db
from .licensing import AuthenticatedPrincipal, authenticate_api_key


FEATURE_MAP: dict[str, frozenset[str]] = {
    "/api/v1/calculate": frozenset({"basic"}),
    "/api/v1/pressure-map": frozenset({"pressure_map"}),
    "/api/v1/materials": frozenset({"materials"}),
    "/api/v1/materials/*": frozenset({"materials"}),
    "/api/v1/design/ratios": frozenset({"basic"}),
    "/api/v1/design/targets": frozenset({"basic"}),
    "/api/v1/design/air-absorption": frozenset({"basic"}),
    "/api/v1/design/audience-absorption": frozenset({"basic"}),
    "/api/v1/design/inverse": frozenset({"inverse_design"}),
    "/api/v1/design/absorbers/*": frozenset({"absorbers"}),
    "/api/v1/design/diffusers/*": frozenset({"diffusers"}),
    "/api/v1/design/isolation/*": frozenset({"isolation"}),
    "/api/v1/impulse-response": frozenset({"ism"}),
    "/api/v1/measurement/calibrate": frozenset({"calibration"}),
    "/api/v1/measurement/*": frozenset({"measurement"}),
    "/api/v1/numerical/*": frozenset({"numerical"}),
    "/api/v1/exports/*": frozenset({"exports"}),
    "/api/v1/jobs": frozenset({"jobs"}),
    "/api/v1/jobs/*": frozenset({"jobs"}),
}


def _normalize_path(path: str) -> str:
    normalized = path.split("?", 1)[0].rstrip("/")
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return normalized or "/"


def required_features(endpoint: str) -> frozenset[str]:
    normalized = _normalize_path(endpoint)
    exact = FEATURE_MAP.get(normalized)
    if exact is not None:
        return exact
    for pattern, features in FEATURE_MAP.items():
        if pattern.endswith("/*") and normalized.startswith(pattern[:-1]):
            return features
    return frozenset()


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_optional_principal(
    api_key: str | None = Security(api_key_header),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedPrincipal | None:
    if not api_key:
        return None
    principal = authenticate_api_key(
        db,
        api_key,
        pepper=settings.api_key_pepper,
    )
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return principal


def verify_endpoint_access(
    principal: AuthenticatedPrincipal | None = Depends(get_optional_principal),
) -> AuthenticatedPrincipal:
    """Require an API key; feature authorization remains route-specific."""
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header is required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return principal


get_authenticated_principal = verify_endpoint_access


def check_feature(
    tier: Mapping[str, Any] | AuthenticatedPrincipal | None, endpoint: str
) -> bool:
    required = required_features(endpoint)
    if not required:
        return True
    if tier is None:
        return False
    if isinstance(tier, AuthenticatedPrincipal):
        available = tier.entitlements
    else:
        available = frozenset(tier.get("features", tier.get("entitlements", ())))
    return required.issubset(available)


def ensure_feature(
    principal: AuthenticatedPrincipal, feature: str
) -> AuthenticatedPrincipal:
    if not principal.has_feature(feature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"License does not include required feature: {feature}",
        )
    return principal


class FeatureRequirement:
    def __init__(self, feature: str) -> None:
        self.feature = feature

    def __call__(
        self,
        principal: AuthenticatedPrincipal = Depends(verify_endpoint_access),
    ) -> AuthenticatedPrincipal:
        return ensure_feature(principal, self.feature)


def require_feature(feature: str) -> FeatureRequirement:
    """Build a route dependency, for example Depends(require_feature("exports"))."""
    return FeatureRequirement(feature)
