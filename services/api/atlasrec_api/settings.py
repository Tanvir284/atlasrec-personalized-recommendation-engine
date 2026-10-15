from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    profile: str = Field("demo", validation_alias="ATLASREC_PROFILE")
    environment: str = Field("development", validation_alias="ATLASREC_ENV")
    database_url: str = "postgresql+psycopg://atlasrec:local-demo-password@localhost:5432/atlasrec"
    redis_url: str = "redis://localhost:6379/0"
    artifact_dir: Path = Path("artifacts")
    data_dir: Path = Path("data")
    research_dataset_id: str | None = None
    allowed_origins: str = "http://localhost:3000"
    cookie_secure: bool = False
    demo_admin_email: str = "admin@atlasrec.local"
    demo_admin_password: str = "AtlasDemo!2026"
    train_threads: int = 2
    train_time_budget: int = 300
    worker_concurrency: int = 1
    drift_window: int = Field(500, ge=20, le=5000)
    drift_category_threshold: float = Field(0.2, ge=0, le=1)
    drift_numeric_threshold: float = Field(0.5, ge=0)
    drift_numeric_min_samples: int = Field(30, ge=2)

    @model_validator(mode="after")
    def validate_environment(self):
        if self.profile not in ("demo", "research"):
            raise ValueError("Unknown operating profile")
        if self.database_url.startswith("sqlite") and self.environment != "test":
            raise ValueError("SQLite is allowed only in isolated tests; app requires PostgreSQL")
        if self.environment == "production":
            if self.profile == "demo" or not self.cookie_secure or "local-demo-password" in self.database_url:
                raise ValueError("Production rejects demo profile, local credentials and insecure cookies")
            if self.demo_admin_email == "admin@atlasrec.local" or self.demo_admin_password == "AtlasDemo!2026":
                raise ValueError("Production rejects documented local demo admin credentials")
            if not all(s.startswith("https://") for s in self.allowed_origins.split(",")):
                raise ValueError("Production allowed origins must be HTTPS")
        return self


settings = Settings()
