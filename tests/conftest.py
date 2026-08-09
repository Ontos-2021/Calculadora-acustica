from __future__ import annotations

import os
from dataclasses import dataclass

# Platform modules construct some compatibility globals at import time.  Set the
# test environment before pytest imports any test module that imports api.*.
TEST_API_KEY_PEPPER = "test-pepper-that-is-long-and-never-used-in-production"
os.environ["ACOUSTIC_ENVIRONMENT"] = "test"
os.environ["ACOUSTIC_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ACOUSTIC_API_KEY_PEPPER"] = TEST_API_KEY_PEPPER
os.environ["ACOUSTIC_REDIS_URL"] = "redis://127.0.0.1:1/15"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from acoustic_core.models import Material, Surface, Room
from api.config import Settings, get_settings
from api.database import create_database_engine, get_db, init_db
from api.db_models import LicenseTier
from api.licensing import create_api_key, create_license, create_user
from api.main import create_app
from api.rate_limit import FixedWindowRateLimiter, InMemoryFixedWindowBackend, get_rate_limiter


@pytest.fixture
def mat_concreto():
    return Material(nombre="Concreto", alpha_unico=0.05)


@pytest.fixture
def mat_panel():
    return Material(
        nombre="Panel acústico",
        alphas={"125": 0.20, "250": 0.60, "500": 0.85, "1000": 0.90, "2000": 0.85, "4000": 0.80},
    )


@pytest.fixture
def sala_basica(mat_concreto):
    return Room(
        largo=5.0, ancho=4.0, alto=3.0,
        superficies=[Surface(nombre=n, area=a, material=mat_concreto)
                     for n, a in zip(
            ["Frente", "Contrafrente", "Lat Izq", "Lat Der", "Piso", "Techo"],
            [12.0, 12.0, 15.0, 15.0, 20.0, 20.0],
        )],
    )


@pytest.fixture
def sala_cubica(mat_concreto):
    return Room(
        largo=3.0, ancho=3.0, alto=3.0,
        superficies=[Surface(nombre=n, area=9.0, material=mat_concreto)
                     for n in ["Frente", "Contrafrente", "Lat Izq", "Lat Der", "Piso", "Techo"]],
    )


@dataclass
class APIContext:
    app: object
    client: TestClient
    session_factory: sessionmaker[Session]
    keys: dict[LicenseTier, str]


@pytest.fixture
def api_context():
    engine = create_database_engine("sqlite:///:memory:")
    init_db(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    settings = Settings(
        environment="test",
        database_url="sqlite:///:memory:",
        redis_url="redis://127.0.0.1:1/15",
        api_key_pepper=TEST_API_KEY_PEPPER,
        _env_file=None,
    )
    app = create_app(settings)

    def override_db():
        with factory() as database:
            try:
                yield database
                database.commit()
            except Exception:
                database.rollback()
                raise

    limiter = FixedWindowRateLimiter(InMemoryFixedWindowBackend())
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_rate_limiter] = lambda: limiter

    keys: dict[LicenseTier, str] = {}
    with factory() as database:
        for tier in LicenseTier:
            user = create_user(database, f"api-{tier.value.lower()}@example.test")
            license_record = create_license(database, user, tier)
            issued = create_api_key(
                database,
                license_record,
                pepper=TEST_API_KEY_PEPPER,
                name=f"{tier.value} test key",
            )
            keys[tier] = issued.plaintext
        database.commit()

    with TestClient(app) as test_client:
        yield APIContext(app=app, client=test_client, session_factory=factory, keys=keys)
    engine.dispose()


@pytest.fixture
def client(api_context):
    return api_context.client


@pytest.fixture
def api_session_factory(api_context):
    return api_context.session_factory


@pytest.fixture
def api_keys(api_context):
    return api_context.keys


@pytest.fixture
def free_headers(api_context):
    return {"X-API-Key": api_context.keys[LicenseTier.FREE]}


@pytest.fixture
def paid_headers(api_context):
    return {"X-API-Key": api_context.keys[LicenseTier.PAID]}


@pytest.fixture
def research_headers(api_context):
    return {"X-API-Key": api_context.keys[LicenseTier.RESEARCH]}
