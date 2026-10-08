from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    baro_base_url: str = "https://ia.maua.br/api/v1"
    baro_api_key: str = ""
    baro_model: str = "google/gemma-3-27b"
    baro_supports_thinking: bool = False
    baro_timeout_seconds: float = 120.0
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    database_url: str = ""
    database_auto_create: bool = False
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=100)
    database_pool_timeout_seconds: float = Field(default=30.0, ge=1, le=300)
    database_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86_400)
    jwt_secret: str = Field(min_length=32)
    jwt_expire_minutes: int = 480
    seed_test_users: bool = False
    seed_test_password: str = ""
    semob_database_path: str = "data/database/semob.duckdb"
    semob_rag_path: str = "data/database/rag.sqlite"
    semob_memory_retention_days: int = 30
    app_environment: str = "production"

    @property
    def configured(self) -> bool:
        return bool(self.baro_api_key.strip() and self.baro_base_url.strip())

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url.strip())

    @property
    def sqlalchemy_database_url(self) -> str:
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url.removeprefix("postgres://")
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url.removeprefix("postgresql://")
        if url.startswith("postgresql+asyncpg://"):
            parts = urlsplit(url)
            query = []
            for key, value in parse_qsl(parts.query, keep_blank_values=True):
                if key == "channel_binding":
                    # libpq supports this option, but asyncpg does not expose it.
                    continue
                query.append(("ssl" if key == "sslmode" else key, value))
            url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        return url

    @property
    def base_url(self) -> str:
        return self.baro_base_url.rstrip("/")

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
    def development(self) -> bool:
        return self.app_environment.casefold() == "development"


settings = Settings()
