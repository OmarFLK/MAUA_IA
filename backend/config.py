from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    maua_ai_base_url: str = ""
    maua_ai_api_key: str = ""
    maua_ai_model: str = "google/gemma-3-27b"
    maua_ai_supports_thinking: bool = False
    maua_ai_timeout_seconds: float = 120.0
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    database_url: str = ""
    jwt_secret: str = Field(min_length=32)
    jwt_expire_minutes: int = 480
    seed_test_users: bool = False
    seed_test_password: str = ""
    semob_database_path: str = "data/database/semob.duckdb"
    semob_rag_path: str = "data/database/rag.sqlite"
    semob_memory_path: str = "data/database/memory.sqlite"
    semob_memory_retention_days: int = 30
    semob_session_path: str = "data/database/session.sqlite"
    app_environment: str = "production"

    @property
    def configured(self) -> bool:
        url = self.maua_ai_base_url.strip().lower()
        return bool(url and ".exemplo" not in url and "entre em contato" not in url)

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url.strip())

    @property
    def base_url(self) -> str:
        return self.maua_ai_base_url.rstrip("/")

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def semob_database_file(self) -> Path:
        return Path(self.semob_database_path).resolve()

    @property
    def semob_rag_file(self) -> Path:
        return Path(self.semob_rag_path).resolve()

    @property
    def semob_memory_file(self) -> Path:
        return Path(self.semob_memory_path).resolve()

    @property
    def semob_session_file(self) -> Path:
        return Path(self.semob_session_path).resolve()

    @property
    def development(self) -> bool:
        return self.app_environment.casefold() == "development"


settings = Settings()
