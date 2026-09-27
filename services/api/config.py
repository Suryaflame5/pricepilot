"""API configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./pricepilot.db"
    redis_url: str | None = None  # Disabled for desktop app
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]

    model_registry_dir: str = "ml/model_registry"
    calibration_store_dir: str = "ml/model_registry/calibration"
    conformal_store_dir: str = "ml/model_registry/conformal"
    shadow_log_dir: str = "ml/model_registry/shadow"
    monitoring_report_dir: str = "ml/model_registry/monitoring"

    alert_poll_seconds: int = 300

    seed_products: int = 5
    seed_history_days: int = 365
    seed_observations_per_day: int = 4


settings = Settings()
