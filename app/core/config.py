from functools import lru_cache
from typing import List

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    app_name: str = "Internal Developer Platform (IDP)"
    environment: str = Field("local", description="Runtime environment")
    database_url: str = Field(
        "postgresql+asyncpg://idp:idp@db:5432/idp", description="DB DSN"
    )
    redis_url: str = Field("redis://redis:6379/0", description="Redis URL")
    jwt_secret: str = Field("changeme", description="JWT secret key")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 6
    log_level: str = "INFO"
    mandatory_tags: List[str] = ["owner", "data_sensitivity"]
    allowed_data_sensitivity: List[str] = ["public", "internal", "confidential"]

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
