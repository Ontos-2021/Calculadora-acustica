from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .config import get_settings
from .db_models import APIKey, AuditEvent, License, LicenseTier, User, utc_now


@dataclass(frozen=True)
class TierPolicy:
    features: frozenset[str]
    quotas: Mapping[str, int]


_FREE_FEATURES = frozenset({"basic", "pressure_map", "storage"})
_PAID_FEATURES = _FREE_FEATURES | frozenset(
    {
        "ism",
        "iso3382",
        "materials",
        "inverse_design",
        "absorbers",
        "diffusers",
        "isolation",
        "measurement",
        "calibration",
        "numerical",
        "exports",
        "projects",
        "jobs",
        "elevated_rate_limit",
    }
)

TIER_POLICIES: Mapping[LicenseTier, TierPolicy] = MappingProxyType(
    {
        LicenseTier.FREE: TierPolicy(
            features=_FREE_FEATURES,
            quotas=MappingProxyType(
                {
                    "requests_per_minute": 30,
                    "daily_request_units": 1_000,
                    "max_concurrent_jobs": 1,
                    "max_storage_bytes": 50 * 1024 * 1024,
                }
            ),
        ),
        LicenseTier.PAID: TierPolicy(
            features=_PAID_FEATURES,
            quotas=MappingProxyType(
                {
                    "requests_per_minute": 300,
                    "daily_request_units": 50_000,
                    "max_concurrent_jobs": 5,
                    "max_storage_bytes": 5 * 1024 * 1024 * 1024,
                }
            ),
        ),
        LicenseTier.RESEARCH: TierPolicy(
            features=_PAID_FEATURES
            | frozenset({"research", "batch", "custom_materials", "priority_jobs"}),
            quotas=MappingProxyType(
                {
                    "requests_per_minute": 600,
                    "daily_request_units": 250_000,
                    "max_concurrent_jobs": 20,
                    "max_storage_bytes": 50 * 1024 * 1024 * 1024,
                }
            ),
        ),
    }
)

API_KEY_PATTERN = re.compile(r"^ac_([0-9a-f]{12})_([A-Za-z0-9_-]{40,})$")


@dataclass(frozen=True)
class IssuedAPIKey:
    api_key_id: uuid.UUID
    prefix: str
    plaintext: str
    created_at: datetime


@dataclass(frozen=True)
class AuthenticatedPrincipal(Mapping[str, Any]):
    user_id: uuid.UUID
    license_id: uuid.UUID
    api_key_id: uuid.UUID
    email: str
    tier: LicenseTier
    entitlements: frozenset[str]
    quotas: Mapping[str, int]
    key_prefix: str

    @property
    def features(self) -> frozenset[str]:
        return self.entitlements

    def has_feature(self, feature: str) -> bool:
        return feature in self.entitlements

    def _mapping(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "license_id": self.license_id,
            "api_key_id": self.api_key_id,
            "email": self.email,
            "tier": self.tier.value,
            "features": sorted(self.entitlements),
            "entitlements": sorted(self.entitlements),
            "quotas": dict(self.quotas),
            "key_prefix": self.key_prefix,
        }

    def __getitem__(self, key: str) -> Any:
        return self._mapping()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._mapping())

    def __len__(self) -> int:
        return len(self._mapping())


def normalize_email(email: str) -> str:
    normalized = email.strip().casefold()
    if not normalized or "@" not in normalized:
        raise ValueError("a valid email address is required")
    return normalized


def _pepper_value(pepper: str | SecretStr | None) -> str:
    if pepper is None:
        pepper = get_settings().api_key_pepper
    value = pepper.get_secret_value() if isinstance(pepper, SecretStr) else pepper
    if not value:
        raise ValueError("API key pepper must not be empty")
    return value


def hash_api_key(plaintext: str, pepper: str | SecretStr | None = None) -> str:
    return hmac.new(
        _pepper_value(pepper).encode("utf-8"),
        plaintext.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def extract_api_key_prefix(plaintext: str) -> str | None:
    match = API_KEY_PATTERN.fullmatch(plaintext)
    return match.group(1) if match else None


def effective_entitlements(license: License) -> frozenset[str]:
    features = set(TIER_POLICIES[license.tier].features)
    for feature, enabled in (license.entitlements or {}).items():
        if enabled:
            features.add(feature)
        else:
            features.discard(feature)
    return frozenset(features)


def effective_quotas(license: License) -> Mapping[str, int]:
    quotas = dict(TIER_POLICIES[license.tier].quotas)
    for name, value in (license.quotas or {}).items():
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            quotas[name] = value
    return MappingProxyType(quotas)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_expired(expires_at: datetime | None, now: datetime) -> bool:
    return expires_at is not None and _as_utc(expires_at) <= _as_utc(now)


def license_is_active(license: License, *, now: datetime | None = None) -> bool:
    current = now or utc_now()
    return (
        license.revoked_at is None
        and not _is_expired(license.expires_at, current)
        and license.user.is_active
    )


def create_user(session: Session, email: str, *, display_name: str | None = None) -> User:
    normalized = normalize_email(email)
    if session.scalar(select(User).where(User.email == normalized)) is not None:
        raise ValueError(f"user already exists: {normalized}")
    user = User(email=normalized, display_name=display_name)
    session.add(user)
    session.flush()
    session.add(
        AuditEvent(
            actor_user_id=user.id,
            action="user.created",
            resource_type="user",
            resource_id=str(user.id),
        )
    )
    return user


def create_license(
    session: Session,
    user: User,
    tier: LicenseTier | str,
    *,
    name: str | None = None,
    expires_at: datetime | None = None,
    entitlements: Mapping[str, bool] | None = None,
    quotas: Mapping[str, int] | None = None,
) -> License:
    resolved_tier = tier if isinstance(tier, LicenseTier) else LicenseTier(tier.upper())
    license = License(
        user=user,
        tier=resolved_tier,
        name=name,
        expires_at=expires_at,
        entitlements=dict(entitlements or {}),
        quotas=dict(quotas or {}),
    )
    session.add(license)
    session.flush()
    session.add(
        AuditEvent(
            actor_user_id=user.id,
            action="license.created",
            resource_type="license",
            resource_id=str(license.id),
            details={"tier": resolved_tier.value},
        )
    )
    return license


def create_api_key(
    session: Session,
    license: License,
    *,
    pepper: str | SecretStr | None = None,
    name: str | None = None,
    expires_at: datetime | None = None,
    now: datetime | None = None,
) -> IssuedAPIKey:
    current = now or utc_now()
    if not license_is_active(license, now=current):
        raise ValueError("cannot create an API key for an inactive license")
    if _is_expired(expires_at, current):
        raise ValueError("API key expiration must be in the future")

    prefix = ""
    plaintext = ""
    for _ in range(5):
        prefix = secrets.token_hex(6)
        plaintext = f"ac_{prefix}_{secrets.token_urlsafe(32)}"
        if session.scalar(select(APIKey.id).where(APIKey.prefix == prefix)) is None:
            break
    else:
        raise RuntimeError("could not allocate a unique API key prefix")

    record = APIKey(
        license=license,
        prefix=prefix,
        key_hash=hash_api_key(plaintext, pepper),
        name=name,
        expires_at=expires_at,
        created_at=current,
    )
    session.add(record)
    session.flush()
    session.add(
        AuditEvent(
            actor_user_id=license.user_id,
            action="api_key.created",
            resource_type="api_key",
            resource_id=str(record.id),
            details={"prefix": prefix},
        )
    )
    return IssuedAPIKey(
        api_key_id=record.id,
        prefix=prefix,
        plaintext=plaintext,
        created_at=current,
    )


def authenticate_api_key(
    session: Session,
    plaintext: str,
    *,
    pepper: str | SecretStr | None = None,
    now: datetime | None = None,
    update_last_used: bool = True,
) -> AuthenticatedPrincipal | None:
    prefix = extract_api_key_prefix(plaintext)
    if prefix is None:
        return None

    record = session.scalar(
        select(APIKey)
        .options(joinedload(APIKey.license).joinedload(License.user))
        .where(APIKey.prefix == prefix)
    )
    if record is None:
        return None

    candidate_hash = hash_api_key(plaintext, pepper)
    if not hmac.compare_digest(candidate_hash, record.key_hash):
        return None

    current = now or utc_now()
    if record.revoked_at is not None or _is_expired(record.expires_at, current):
        return None
    if not license_is_active(record.license, now=current):
        return None

    if update_last_used:
        record.last_used_at = current

    return AuthenticatedPrincipal(
        user_id=record.license.user.id,
        license_id=record.license.id,
        api_key_id=record.id,
        email=record.license.user.email,
        tier=record.license.tier,
        entitlements=effective_entitlements(record.license),
        quotas=effective_quotas(record.license),
        key_prefix=record.prefix,
    )


def revoke_api_key(
    session: Session,
    api_key: APIKey,
    *,
    now: datetime | None = None,
) -> None:
    if api_key.revoked_at is None:
        api_key.revoked_at = now or utc_now()
        session.add(
            AuditEvent(
                actor_user_id=api_key.license.user_id,
                action="api_key.revoked",
                resource_type="api_key",
                resource_id=str(api_key.id),
                details={"prefix": api_key.prefix},
            )
        )


def rotate_api_key(
    session: Session,
    api_key: APIKey,
    *,
    pepper: str | SecretStr | None = None,
    now: datetime | None = None,
) -> IssuedAPIKey:
    current = now or utc_now()
    if api_key.revoked_at is not None:
        raise ValueError("cannot rotate a revoked API key")
    revoke_api_key(session, api_key, now=current)
    return create_api_key(
        session,
        api_key.license,
        pepper=pepper,
        name=api_key.name,
        expires_at=api_key.expires_at,
        now=current,
    )


def revoke_license(
    session: Session,
    license: License,
    *,
    now: datetime | None = None,
) -> None:
    if license.revoked_at is None:
        license.revoked_at = now or utc_now()
        session.add(
            AuditEvent(
                actor_user_id=license.user_id,
                action="license.revoked",
                resource_type="license",
                resource_id=str(license.id),
                details={"tier": license.tier.value},
            )
        )
