from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://root:@localhost:3306/novel_ai"
    zhipu_api_key: str = ""
    ark_api_key: str = ""
    storage_path: str = "./storage/projects"
    secret_key: str = "change_this_in_production"
    cors_origins: str = "http://localhost:5173"

    class Config:
        env_file = ".env"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
