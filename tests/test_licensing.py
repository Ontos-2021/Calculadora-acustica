from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, sessionmaker

from api.config import DEVELOPMENT_API_KEY_PEPPER, Settings, get_settings
from api.database import create_database_engine, get_db, init_db
from api.db_models import APIKey, AuditEvent, JobStatus, LicenseTier
from api.dependencies import check_feature, require_feature, verify_endpoint_access
from api.jobs import InMemoryJobQueue, enqueue_job, get_job_status, process_next_job
from api.licensing import (
    AuthenticatedPrincipal,
    authenticate_api_key,
    create_api_key,
    create_license,
    create_user,
    hash_api_key,
    revoke_api_key,
    revoke_license,
    rotate_api_key,
)
from api.main import create_app
from api.storage import LocalStorage, S3Storage, get_storage


PEPPER = "test-pepper-that-is-long-and-never-used-in-production"
NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def session_factory():
    engine = create_database_engine("sqlite:///:memory:")
    init_db(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def session(session_factory):
    with session_factory() as db:
        yield db


def issue_key(session: Session, tier: LicenseTier = LicenseTier.FREE):
    user = create_user(session, f"{tier.value.lower()}@example.com")
    license = create_license(session, user, tier)
    issued = create_api_key(session, license, pepper=PEPPER, now=NOW)
    session.commit()
    return user, license, issued


def test_schema_initializer_is_idempotent_and_complete(session_factory):
    engine = session_factory.kw["bind"]
    init_db(engine)
    assert set(inspect(engine).get_table_names()) == {
        "users",
        "licenses",
        "api_keys",
        "usage_events",
        "audit_events",
        "projects",
        "calculations",
        "jobs",
        "stored_assets",
    }


def test_production_settings_fail_closed_for_secrets_and_services():
    with pytest.raises(ValidationError, match="API_KEY_PEPPER"):
        Settings(
            environment="production",
            database_url="postgresql+psycopg://db/acoustic",
            redis_url="redis://redis/0",
            api_key_pepper=DEVELOPMENT_API_KEY_PEPPER,
            storage_backend="s3",
            storage_s3_bucket="exports",
            _env_file=None,
        )

    settings = Settings(
        environment="production",
        database_url="postgresql+psycopg://db/acoustic",
        redis_url="rediss://redis/0",
        api_key_pepper="x" * 32,
        storage_backend="s3",
        storage_s3_bucket="exports",
        storage_s3_endpoint_url="",
        storage_s3_access_key_id="",
        storage_s3_secret_access_key="",
        _env_file=None,
    )
    assert settings.environment == "production"
    assert settings.storage_s3_endpoint_url is None
    assert settings.storage_s3_access_key_id is None
    assert settings.storage_s3_secret_access_key is None


def test_api_key_plaintext_is_returned_once_and_never_stored(session):
    _, _, issued = issue_key(session)
    record = session.scalar(select(APIKey).where(APIKey.id == issued.api_key_id))

    assert issued.plaintext.startswith(f"ac_{issued.prefix}_")
    assert record.key_hash == hash_api_key(issued.plaintext, PEPPER)
    assert record.key_hash != issued.plaintext
    assert issued.plaintext not in repr(record.__dict__)
    assert not hasattr(record, "plaintext")
    assert session.scalar(select(AuditEvent).where(AuditEvent.action == "api_key.created"))


def test_authentication_uses_prefix_lookup_and_constant_time_hash_result(session):
    user, license, issued = issue_key(session)

    principal = authenticate_api_key(session, issued.plaintext, pepper=PEPPER, now=NOW)
    assert principal is not None
    assert principal.user_id == user.id
    assert principal.license_id == license.id
    assert principal.tier == LicenseTier.FREE
    assert principal.has_feature("basic")
    assert principal.has_feature("pressure_map")
    assert not principal.has_feature("ism")
    assert principal["tier"] == "FREE"

    replacement = "A" if issued.plaintext[-1] != "A" else "B"
    assert (
        authenticate_api_key(
            session,
            issued.plaintext[:-1] + replacement,
            pepper=PEPPER,
            now=NOW,
        )
        is None
    )
    assert authenticate_api_key(session, "free_tier", pepper=PEPPER, now=NOW) is None
    assert authenticate_api_key(session, issued.plaintext, pepper="wrong", now=NOW) is None


def test_key_license_and_user_lifecycle_all_fail_authentication(session):
    user, license, issued = issue_key(session)
    key = session.get(APIKey, issued.api_key_id)

    key.expires_at = NOW + timedelta(seconds=1)
    session.commit()
    assert authenticate_api_key(
        session, issued.plaintext, pepper=PEPPER, now=NOW + timedelta(seconds=1)
    ) is None

    key.expires_at = None
    revoke_api_key(session, key, now=NOW)
    session.commit()
    assert authenticate_api_key(session, issued.plaintext, pepper=PEPPER, now=NOW) is None

    _, other_license, other_issued = issue_key(session, LicenseTier.PAID)
    revoke_license(session, other_license, now=NOW)
    session.commit()
    assert authenticate_api_key(session, other_issued.plaintext, pepper=PEPPER, now=NOW) is None

    third_user = create_user(session, "inactive@example.com")
    third_license = create_license(session, third_user, LicenseTier.RESEARCH)
    third_issued = create_api_key(session, third_license, pepper=PEPPER, now=NOW)
    third_user.is_active = False
    session.commit()
    assert authenticate_api_key(session, third_issued.plaintext, pepper=PEPPER, now=NOW) is None


def test_rotation_revokes_old_key_and_returns_a_new_plaintext(session):
    _, _, issued = issue_key(session)
    old_key = session.get(APIKey, issued.api_key_id)
    replacement = rotate_api_key(session, old_key, pepper=PEPPER, now=NOW + timedelta(minutes=1))
    session.commit()

    assert replacement.plaintext != issued.plaintext
    assert authenticate_api_key(
        session, issued.plaintext, pepper=PEPPER, now=NOW + timedelta(minutes=1)
    ) is None
    assert authenticate_api_key(
        session, replacement.plaintext, pepper=PEPPER, now=NOW + timedelta(minutes=1)
    ) is not None


def test_tier_entitlements_and_quota_overrides_are_effective(session):
    user = create_user(session, "custom@example.com")
    license = create_license(
        session,
        user,
        LicenseTier.FREE,
        entitlements={"basic": False, "ism": True},
        quotas={"requests_per_minute": 7, "not_an_integer": "ignored"},
    )
    issued = create_api_key(session, license, pepper=PEPPER, now=NOW)
    session.commit()

    principal = authenticate_api_key(session, issued.plaintext, pepper=PEPPER, now=NOW)
    assert principal is not None
    assert principal.entitlements == frozenset({"pressure_map", "storage", "ism"})
    assert principal.quotas["requests_per_minute"] == 7
    assert principal.quotas["daily_request_units"] == 1_000
    assert check_feature(principal, "/api/v1/impulse-response")
    assert check_feature(principal, "/api/v1/objects")
    assert not check_feature(principal, "/api/v1/calculate")


def test_fastapi_dependency_distinguishes_authentication_and_authorization(session_factory):
    with session_factory() as db:
        free_user = create_user(db, "dependency-free@example.com")
        free_license = create_license(db, free_user, LicenseTier.FREE)
        free_key = create_api_key(db, free_license, pepper=PEPPER, now=NOW)
        paid_user = create_user(db, "dependency-paid@example.com")
        paid_license = create_license(db, paid_user, LicenseTier.PAID)
        paid_key = create_api_key(db, paid_license, pepper=PEPPER, now=NOW)
        db.commit()

    app = FastAPI()

    def override_db():
        with session_factory() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="test", api_key_pepper=PEPPER, _env_file=None
    )

    @app.get("/authenticated")
    def authenticated(principal: AuthenticatedPrincipal = Depends(verify_endpoint_access)):
        return {"tier": principal.tier.value}

    @app.get("/paid")
    def paid(principal: AuthenticatedPrincipal = Depends(require_feature("ism"))):
        return {"tier": principal.tier.value}

    client = TestClient(app)
    assert client.get("/authenticated").status_code == 401
    assert client.get("/authenticated", headers={"X-API-Key": "invalid"}).status_code == 401
    assert client.get("/paid", headers={"X-API-Key": free_key.plaintext}).status_code == 403
    response = client.get("/paid", headers={"X-API-Key": paid_key.plaintext})
    assert response.status_code == 200
    assert response.json() == {"tier": "PAID"}


def test_job_queue_and_worker_are_database_portable(session_factory):
    queue = InMemoryJobQueue()
    with session_factory() as db:
        job = enqueue_job(
            db,
            queue,
            "test.add",
            {"left": 2, "right": 3},
            idempotency_key="request-1",
        )
        duplicate = enqueue_job(
            db,
            queue,
            "test.add",
            {"left": 99, "right": 99},
            idempotency_key="request-1",
        )
        assert duplicate.id == job.id
        job_id = job.id

    assert process_next_job(
        session_factory,
        queue,
        {"test.add": lambda payload: {"total": payload["left"] + payload["right"]}},
        timeout=0,
    )
    with session_factory() as db:
        view = get_job_status(db, job_id)
        assert view is not None
        assert view.status == JobStatus.SUCCEEDED
        assert view.result == {"total": 5}
        assert view.attempts == 1


def test_worker_retries_failed_jobs_up_to_the_configured_limit(session_factory):
    queue = InMemoryJobQueue()
    with session_factory() as db:
        job = enqueue_job(db, queue, "test.flaky", {}, max_attempts=2)
        job_id = job.id
    calls = 0

    def flaky(_payload):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary failure")
        return {"recovered": True}

    assert process_next_job(session_factory, queue, {"test.flaky": flaky}, timeout=0)
    assert process_next_job(session_factory, queue, {"test.flaky": flaky}, timeout=0)
    with session_factory() as db:
        view = get_job_status(db, job_id)
        assert view is not None
        assert view.status == JobStatus.SUCCEEDED
        assert view.result == {"recovered": True}
        assert view.attempts == 2


def test_local_storage_is_atomic_and_rejects_path_traversal(tmp_path):
    storage = LocalStorage(tmp_path / "objects")
    stored = storage.put("exports/report.pdf", b"report", content_type="application/pdf")

    assert stored.size == 6
    assert storage.exists(stored.key)
    assert storage.get(stored.key) == b"report"
    assert storage.url(stored.key).startswith("file:")
    with pytest.raises(ValueError):
        storage.put("../outside", b"unsafe")
    storage.delete(stored.key)
    assert not storage.exists(stored.key)


def test_app_initializes_injectable_local_storage(tmp_path):
    settings = Settings(
        environment="test",
        database_url="sqlite:///:memory:",
        redis_url="redis://127.0.0.1:1/15",
        api_key_pepper=PEPPER,
        storage_local_path=tmp_path / "objects",
        _env_file=None,
    )
    app = create_app(settings)
    with TestClient(app):
        backend = app.dependency_overrides[get_storage]()
        assert isinstance(backend, LocalStorage)
        assert backend.root == (tmp_path / "objects").resolve()


def test_s3_storage_uses_compatible_object_api_without_network_access():
    class Body:
        def __init__(self, value):
            self.value = value

        def read(self):
            return self.value

    class FakeS3:
        def __init__(self):
            self.objects = {}

        def put_object(self, **kwargs):
            self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs["Body"]

        def get_object(self, **kwargs):
            return {"Body": Body(self.objects[(kwargs["Bucket"], kwargs["Key"])])}

        def head_object(self, **kwargs):
            self.objects[(kwargs["Bucket"], kwargs["Key"])]

        def delete_object(self, **kwargs):
            self.objects.pop((kwargs["Bucket"], kwargs["Key"]), None)

        def generate_presigned_url(self, operation, Params, ExpiresIn):
            return f"https://objects.test/{Params['Bucket']}/{Params['Key']}?ttl={ExpiresIn}"

    client = FakeS3()
    storage = S3Storage("exports", prefix="tenant", client=client)
    storage.put("reports/one.pdf", b"pdf")

    assert storage.get("reports/one.pdf") == b"pdf"
    assert storage.exists("reports/one.pdf")
    assert storage.url("reports/one.pdf", expires_in=60).endswith("?ttl=60")
    assert ("exports", "tenant/reports/one.pdf") in client.objects
    storage.delete("reports/one.pdf")
