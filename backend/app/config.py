from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env"),
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://top25:top25@localhost:5432/top25"
    secret_pepper: str = "dev-pepper-change-me"
    docs_public: bool = False
    frontend_url: str = "http://localhost:5173"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "Top 25 <noreply@localhost>"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:5173/api/auth/google/callback"
    storage_dir: str = "uploads"
    cookie_secure: bool = False
    email_outbox: bool = False
    session_days: int = 30
    superadmin_email: str = ""
    superadmin_password: str = ""

    def storage_path(self) -> Path:
        path = Path(self.storage_dir)
        if not path.is_absolute():
            path = BACKEND_ROOT / path
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
