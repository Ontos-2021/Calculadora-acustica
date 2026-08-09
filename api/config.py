from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEVELOPMENT_API_KEY_PEPPER = "development-only-api-key-pepper"


class Settings(BaseSettings):
    environment: Literal["development", "test", "production"] = "development"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://localhost:3000",
    ]
    api_version: str = "v1"
    debug: bool = False

    database_url: str = Field(
        default="sqlite:///./acoustic.db",
        validation_alias=AliasChoices("DATABASE_URL", "ACOUSTIC_DATABASE_URL"),
    )
    database_echo: bool = False
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("REDIS_URL", "ACOUSTIC_REDIS_URL"),
    )
    api_key_pepper: SecretStr = Field(
        default=DEVELOPMENT_API_KEY_PEPPER,
        validation_alias=AliasChoices("API_KEY_PEPPER", "ACOUSTIC_API_KEY_PEPPER"),
    )

    storage_backend: Literal["local", "s3"] = Field(
        default="local",
        validation_alias=AliasChoices("STORAGE_BACKEND", "ACOUSTIC_STORAGE_BACKEND"),
    )
    storage_local_path: Path = Field(
        default=Path("var/storage"),
        validation_alias=AliasChoices("STORAGE_LOCAL_PATH", "ACOUSTIC_STORAGE_LOCAL_PATH"),
    )
    storage_s3_bucket: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "STORAGE_S3_BUCKET", "S3_BUCKET", "ACOUSTIC_STORAGE_S3_BUCKET"
        ),
    )
    storage_s3_endpoint_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "STORAGE_S3_ENDPOINT_URL", "S3_ENDPOINT_URL", "ACOUSTIC_STORAGE_S3_ENDPOINT_URL"
        ),
    )
    storage_s3_region: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices(
            "STORAGE_S3_REGION", "AWS_DEFAULT_REGION", "ACOUSTIC_STORAGE_S3_REGION"
        ),
    )
    storage_s3_access_key_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "STORAGE_S3_ACCESS_KEY_ID",
            "AWS_ACCESS_KEY_ID",
            "ACOUSTIC_STORAGE_S3_ACCESS_KEY_ID",
        ),
    )
    storage_s3_secret_access_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "STORAGE_S3_SECRET_ACCESS_KEY",
            "AWS_SECRET_ACCESS_KEY",
            "ACOUSTIC_STORAGE_S3_SECRET_ACCESS_KEY",
        ),
    )
    storage_s3_prefix: str = Field(
        default="acoustic",
        validation_alias=AliasChoices("STORAGE_S3_PREFIX", "ACOUSTIC_STORAGE_S3_PREFIX"),
    )

    rate_limit_key_prefix: str = "acoustic:rate-limit"
    job_queue_name: str = "acoustic:jobs"
    worker_poll_timeout_seconds: int = Field(default=5, ge=1, le=60)

    model_config = SettingsConfigDict(
        env_prefix="ACOUSTIC_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator(
        "storage_s3_bucket",
        "storage_s3_endpoint_url",
        "storage_s3_access_key_id",
        "storage_s3_secret_access_key",
        mode="before",
    )
    @classmethod
    def empty_optional_storage_value_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_environment(self) -> "Settings":
        if self.storage_backend == "s3":
            if not self.storage_s3_bucket:
                raise ValueError("STORAGE_S3_BUCKET is required for S3 storage")
            if bool(self.storage_s3_access_key_id) != bool(self.storage_s3_secret_access_key):
                raise ValueError("both S3 access key fields must be set together")
        if self.environment != "production":
            return self

        pepper = self.api_key_pepper.get_secret_value()
        if pepper == DEVELOPMENT_API_KEY_PEPPER or len(pepper) < 32:
            raise ValueError(
                "API_KEY_PEPPER must be a unique secret of at least 32 characters in production"
            )
        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("DATABASE_URL must use PostgreSQL in production")
        if not self.redis_url.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must use Redis in production")
        if self.storage_backend == "local":
            raise ValueError("STORAGE_BACKEND must be 's3' in production")
        return self

    @property
    def api_key_pepper_value(self) -> str:
        return self.api_key_pepper.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()
