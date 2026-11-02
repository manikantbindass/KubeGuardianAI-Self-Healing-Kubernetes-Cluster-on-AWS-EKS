from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+psycopg://sentinel:sentinel_local@127.0.0.1:5432/sentinel")
    )
    redis_url: RedisDsn = Field(default=RedisDsn("redis://127.0.0.1:6379/0"))
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
