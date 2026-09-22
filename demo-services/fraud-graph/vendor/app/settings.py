from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "dev"
    APP_VERSION: str = "0.2.0"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8090
    MODEL_PATH: str = "artifacts/models/edge_model.pt"
    ALERT_MIN_SCORE: float = 0.80
    MODEL_BLEND_WEIGHT: float = Field(default=0.15, ge=0.0, le=1.0)
    MODEL_UPLIFT_ONLY: bool = True
    AMOUNT_Z_WARMUP_EVENTS: int = Field(default=6, ge=1, le=120)

    # Comma-separated allowlist. Use "*" for public demos (default).
    CORS_ALLOW_ORIGINS: str = "*"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
