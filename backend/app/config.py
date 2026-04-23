from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
ROOT_ENV_FILE = REPO_ROOT / ".env"
BACKEND_ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://root:@localhost:3306/novel_ai"
    zhipu_api_key: str = ""
    ark_api_key: str = ""
    ai_timeout_seconds: int = 600
    storage_path: str = "./storage/projects"
    secret_key: str = "change_this_in_production"
    cors_origins: str = "http://localhost:5173"

    # Later files override earlier ones, so backend/.env is canonical
    # while the repo root .env remains a compatibility fallback.
    model_config = SettingsConfigDict(
        env_file=(str(ROOT_ENV_FILE), str(BACKEND_ENV_FILE)),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
