from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    maua_ai_base_url: str = ""
    maua_ai_api_key: str = "maua"
    maua_ai_model: str = "qwen/qwen3.8-27b"
    maua_ai_timeout_seconds: float = 120.0
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    database_url: str = ""
    jwt_secret: str = "development-only-change-me-before-deploy"
    jwt_expire_minutes: int = 480
    seed_test_users: bool = False

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


settings = Settings()
