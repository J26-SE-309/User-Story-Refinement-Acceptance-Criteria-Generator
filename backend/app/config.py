"""Service settings, read from environment variables or backend/.env (see .env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "story-refinement"
    # This component's own database and account. No other component connects to it.
    database_url: str = "postgresql+psycopg://story_user:story-local@localhost:5442/story_db"
    cors_origins: list[str] = ["http://localhost:3000"]
    story_generation_mode: str = "baseline"
    story_model_device: str = "auto"
    story_data_dir: str = "../../Datasets/story-refinement"
    story_model_path: str = "models/story-refinement-model"


@lru_cache
def get_settings() -> Settings:
    return Settings()
