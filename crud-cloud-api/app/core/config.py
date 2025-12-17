from functools import lru_cache
from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Takehome Challenge CRUD API"
    secret_key: str = "super-secret-demo-key"
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"
    sqlite_path: str = "app.db"
    global_rate_limit: str = "60/minute"
    login_rate_limit: str = "5/minute"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
