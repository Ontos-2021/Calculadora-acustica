"""Create the deterministic browser-test license before starting the API."""

import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.database import init_db, session_scope
from api.db_models import APIKey, License, LicenseTier, User
from api.licensing import hash_api_key


PAID_KEY = "ac_eeeeeeeeeeee_PlaywrightPaidKey_0123456789abcdefghijklmnop"
PREFIX = "eeeeeeeeeeee"
EMAIL = "playwright-paid@example.test"
RESEARCH_KEY = "ac_dddddddddddd_PlaywrightResearchKey_0123456789abcdefghijklmn"
RESEARCH_PREFIX = "dddddddddddd"
RESEARCH_EMAIL = "playwright-research@example.test"


def ensure_license(session, *, email: str, tier: LicenseTier, prefix: str, plaintext: str) -> None:
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, display_name=f"Playwright {tier.value}", is_active=True)
        session.add(user)
        session.flush()
    else:
        user.is_active = True

    license_record = session.scalar(
        select(License).where(License.user_id == user.id, License.tier == tier)
    )
    if license_record is None:
        license_record = License(user=user, tier=tier, name=f"E2E {tier.value}")
        session.add(license_record)
        session.flush()
    license_record.revoked_at = None
    license_record.expires_at = None
    license_record.entitlements = {}
    license_record.quotas = {}

    key = session.scalar(select(APIKey).where(APIKey.prefix == prefix))
    if key is None:
        key = APIKey(
            license=license_record,
            prefix=prefix,
            key_hash=hash_api_key(plaintext),
            name="E2E deterministic",
        )
        session.add(key)
    else:
        key.license = license_record
        key.key_hash = hash_api_key(plaintext)
        key.revoked_at = None
        key.expires_at = None


def main() -> None:
    init_db()
    with session_scope() as session:
        ensure_license(session, email=EMAIL, tier=LicenseTier.PAID, prefix=PREFIX, plaintext=PAID_KEY)
        ensure_license(
            session,
            email=RESEARCH_EMAIL,
            tier=LicenseTier.RESEARCH,
            prefix=RESEARCH_PREFIX,
            plaintext=RESEARCH_KEY,
        )


if __name__ == "__main__":
    main()
