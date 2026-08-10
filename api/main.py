from contextlib import asynccontextmanager
from collections.abc import Generator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .database import create_database_engine, get_db, init_db
from .rate_limit import (
    FixedWindowRateLimiter,
    InMemoryFixedWindowBackend,
    create_rate_limiter,
    get_rate_limiter,
)
from .routes import router
from .storage import StorageBackend, create_storage, get_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    engine = app.state.database_engine
    try:
        if settings.environment == "production":
            try:
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
            except Exception as exc:
                raise RuntimeError(
                    "Production database is unavailable; verify DATABASE_URL and connectivity"
                ) from exc
            try:
                app.state.rate_limiter = create_rate_limiter(settings)
            except Exception as exc:
                raise RuntimeError(
                    "Production rate-limit infrastructure is unavailable; verify REDIS_URL"
                ) from exc
            try:
                app.state.storage = create_storage(settings)
            except Exception as exc:
                raise RuntimeError(
                    "Production object storage configuration is invalid"
                ) from exc
        else:
            init_db(engine)
            app.state.rate_limiter = FixedWindowRateLimiter(
                InMemoryFixedWindowBackend(),
                key_prefix=settings.rate_limit_key_prefix,
            )
            app.state.storage = create_storage(settings)
        yield
    finally:
        engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    database_engine = create_database_engine(
        settings.database_url,
        echo=settings.database_echo,
    )
    session_factory = sessionmaker(
        bind=database_engine,
        class_=Session,
        expire_on_commit=False,
    )

    app = FastAPI(
        title="Calculadora Acústica Profesional",
        description="API de cálculo acústico arquitectónico: modos de resonancia, RT60, Bonello, diseño de salas",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database_engine = database_engine
    app.state.session_factory = session_factory

    def app_database_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def app_rate_limiter() -> FixedWindowRateLimiter:
        return app.state.rate_limiter

    def app_storage() -> StorageBackend:
        return app.state.storage

    # Keep settings and infrastructure app-scoped so test/dev environment changes
    # are not lost to module import order.
    app.dependency_overrides[get_db] = app_database_session
    app.dependency_overrides[get_rate_limiter] = app_rate_limiter
    app.dependency_overrides[get_storage] = app_storage

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api/v1")

    @app.exception_handler(ValueError)
    async def invalid_domain_input(_request: Request, exc: ValueError) -> JSONResponse:
        if isinstance(exc, ValidationError):
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal response contract validation failed"},
            )
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    return app


app = create_app()
