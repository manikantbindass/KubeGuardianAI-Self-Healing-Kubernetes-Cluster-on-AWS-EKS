from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr
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
    prometheus_url: str = "http://127.0.0.1:9090"
    telemetry_token: SecretStr = SecretStr("")
    otel_exporter_otlp_endpoint: str = ""
    ops_auth_mode: str = "oidc"
    ops_dev_token: SecretStr = SecretStr("")
    ops_dev_viewer_token: SecretStr = SecretStr("")
    ops_oidc_issuer: str = ""
    ops_oidc_audience: str = "kubesentinel-api"
    ops_oidc_jwks_url: str = ""
    ops_oidc_roles_claim: str = "kubesentinel_roles"
    ops_bridge_token: SecretStr = SecretStr("")
    ops_namespaces: list[str] = ["kubesentinel", "sentinel-lab"]
    ops_demo_enabled: bool = False
    ops_approval_key_path: str = ""
    ops_approval_key_id: str = "local-operator"
    ops_detector_url: str = ""
    ops_loki_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
