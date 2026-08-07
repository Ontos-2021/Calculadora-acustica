from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://localhost:3000",
    ]
    api_version: str = "v1"
    debug: bool = False

    model_config = {"env_prefix": "ACOUSTIC_"}
