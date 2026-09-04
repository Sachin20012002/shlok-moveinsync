from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SHLOK Mobility Intelligence"
    database_url: str = "sqlite:///./mobility.db"
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    ota_sla: float = 90.0
    ota_grace_minutes: int = 5
    minimum_completed_trips: int = 10
    vendor_minimum_completed_trips: int = 3
    gps_availability_sla: float = 95.0
    incident_reopen_drop_points: float = 5.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()