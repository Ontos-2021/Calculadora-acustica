from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from .config import get_settings
from .database import init_db, session_scope
from .db_models import APIKey, License, LicenseTier, User
from .licensing import (
    create_api_key,
    create_license,
    create_user,
    effective_entitlements,
    effective_quotas,
    license_is_active,
    normalize_email,
    revoke_api_key,
    revoke_license,
    rotate_api_key,
)


def _datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _key_values(values: list[str], *, boolean: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"expected NAME=VALUE, got: {value}")
        name, raw = value.split("=", 1)
        if not name:
            raise ValueError("setting name must not be empty")
        if boolean:
            lowered = raw.casefold()
            if lowered not in {"true", "false"}:
                raise ValueError(f"entitlement value must be true or false: {value}")
            result[name] = lowered == "true"
        else:
            parsed = int(raw)
            if parsed < 0:
                raise ValueError(f"quota must not be negative: {value}")
            result[name] = parsed
    return result


def _license_by_id(session: Any, value: str) -> License:
    license = session.scalar(
        select(License)
        .options(joinedload(License.user))
        .where(License.id == uuid.UUID(value))
    )
    if license is None:
        raise ValueError(f"license not found: {value}")
    return license


def _api_key(session: Any, *, key_id: str | None, prefix: str | None) -> APIKey:
    query = select(APIKey).options(joinedload(APIKey.license).joinedload(License.user))
    query = query.where(APIKey.id == uuid.UUID(key_id)) if key_id else query.where(APIKey.prefix == prefix)
    api_key = session.scalar(query)
    if api_key is None:
        raise ValueError("API key not found")
    return api_key


def _license_summary(license: License) -> dict[str, Any]:
    return {
        "id": str(license.id),
        "user_id": str(license.user_id),
        "email": license.user.email,
        "tier": license.tier.value,
        "active": license_is_active(license),
        "expires_at": license.expires_at.isoformat() if license.expires_at else None,
        "revoked_at": license.revoked_at.isoformat() if license.revoked_at else None,
        "entitlements": sorted(effective_entitlements(license)),
        "quotas": dict(effective_quotas(license)),
        "api_keys": [
            {
                "id": str(key.id),
                "prefix": key.prefix,
                "name": key.name,
                "revoked_at": key.revoked_at.isoformat() if key.revoked_at else None,
                "expires_at": key.expires_at.isoformat() if key.expires_at else None,
            }
            for key in license.api_keys
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage acoustic platform licenses")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init-db", help="create missing database tables")

    create_user_parser = commands.add_parser("create-user")
    create_user_parser.add_argument("--email", required=True)
    create_user_parser.add_argument("--name")

    create_license_parser = commands.add_parser("create-license")
    create_license_parser.add_argument("--email", required=True)
    create_license_parser.add_argument("--tier", choices=[tier.value for tier in LicenseTier], required=True)
    create_license_parser.add_argument("--name")
    create_license_parser.add_argument("--expires-at")
    create_license_parser.add_argument("--entitlement", action="append", default=[])
    create_license_parser.add_argument("--quota", action="append", default=[])

    create_key_parser = commands.add_parser("create-key")
    create_key_parser.add_argument("--license-id", required=True)
    create_key_parser.add_argument("--name")
    create_key_parser.add_argument("--expires-at")

    revoke_key_parser = commands.add_parser("revoke-key")
    revoke_key_target = revoke_key_parser.add_mutually_exclusive_group(required=True)
    revoke_key_target.add_argument("--key-id")
    revoke_key_target.add_argument("--prefix")

    rotate_key_parser = commands.add_parser("rotate-key")
    rotate_key_target = rotate_key_parser.add_mutually_exclusive_group(required=True)
    rotate_key_target.add_argument("--key-id")
    rotate_key_target.add_argument("--prefix")

    revoke_license_parser = commands.add_parser("revoke-license")
    revoke_license_parser.add_argument("--license-id", required=True)

    inspect_parser = commands.add_parser("inspect")
    inspect_target = inspect_parser.add_mutually_exclusive_group(required=True)
    inspect_target.add_argument("--license-id")
    inspect_target.add_argument("--key-prefix")
    inspect_target.add_argument("--email")
    return parser


def run(args: argparse.Namespace) -> None:
    if args.command == "init-db":
        init_db()
        print("Database schema initialized")
        return

    settings = get_settings()
    with session_scope() as session:
        if args.command == "create-user":
            user = create_user(session, args.email, display_name=args.name)
            print(json.dumps({"id": str(user.id), "email": user.email}))
            return

        if args.command == "create-license":
            user = session.scalar(select(User).where(User.email == normalize_email(args.email)))
            if user is None:
                raise ValueError(f"user not found: {args.email}")
            license = create_license(
                session,
                user,
                args.tier,
                name=args.name,
                expires_at=_datetime(args.expires_at),
                entitlements=_key_values(args.entitlement, boolean=True),
                quotas=_key_values(args.quota),
            )
            print(json.dumps({"id": str(license.id), "tier": license.tier.value}))
            return

        if args.command == "create-key":
            license = _license_by_id(session, args.license_id)
            issued = create_api_key(
                session,
                license,
                pepper=settings.api_key_pepper,
                name=args.name,
                expires_at=_datetime(args.expires_at),
            )
            session.commit()
            print(f"API key (shown once): {issued.plaintext}")
            return

        if args.command == "revoke-key":
            key = _api_key(session, key_id=args.key_id, prefix=args.prefix)
            revoke_api_key(session, key)
            print(json.dumps({"id": str(key.id), "prefix": key.prefix, "revoked": True}))
            return

        if args.command == "rotate-key":
            key = _api_key(session, key_id=args.key_id, prefix=args.prefix)
            issued = rotate_api_key(session, key, pepper=settings.api_key_pepper)
            session.commit()
            print(f"API key (shown once): {issued.plaintext}")
            return

        if args.command == "revoke-license":
            license = _license_by_id(session, args.license_id)
            revoke_license(session, license)
            print(json.dumps({"id": str(license.id), "revoked": True}))
            return

        if args.command == "inspect":
            if args.license_id:
                licenses = [_license_by_id(session, args.license_id)]
            elif args.key_prefix:
                key = _api_key(session, key_id=None, prefix=args.key_prefix)
                licenses = [key.license]
            else:
                user = (
                    session.execute(
                        select(User)
                        .options(joinedload(User.licenses).joinedload(License.api_keys))
                        .where(User.email == normalize_email(args.email))
                    )
                    .unique()
                    .scalar_one_or_none()
                )
                if user is None:
                    raise ValueError(f"user not found: {args.email}")
                licenses = user.licenses
            print(json.dumps([_license_summary(license) for license in licenses], indent=2))


def main() -> None:
    parser = build_parser()
    try:
        run(parser.parse_args())
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
