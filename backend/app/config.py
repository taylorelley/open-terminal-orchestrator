"""Centralized configuration via environment variables."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Database
    database_url: str = "postgresql+asyncpg://shellguard:shellguard@localhost:5432/shellguard"

    # External services
    openshell_gateway: str = "http://openshell-gateway:6443"
    open_webui_api_key: str = ""
    admin_api_key: str = ""

    # Proxy
    sandbox_port: int = 8000
    proxy_timeout: int = 30

    # Pool defaults (overridden by system_config rows at runtime)
    pool_warmup_size: int = 2
    pool_max_sandboxes: int = 20
    pool_max_active: int = 10
    default_image_tag: str = "shellguard-sandbox:slim"

    # Lifecycle timeouts (seconds)
    idle_timeout: int = 1800  # 30 minutes
    suspend_timeout: int = 86400  # 24 hours
    startup_timeout: int = 120  # 2 minutes
    resume_timeout: int = 30  # 30 seconds

    # Pool manager loop interval (seconds)
    cleanup_interval: int = 30

    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "info"

    # CORS
    cors_origins: list[str] = ["*"]

    # Frontend
    frontend_dist_path: str = "../dist"

    @field_validator("database_url")
    @classmethod
    def convert_database_url(cls, v: str) -> str:
        """Ensure the URL uses the asyncpg driver prefix."""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


settings = Settings()
