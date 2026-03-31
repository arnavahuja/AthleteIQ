import os
from pydantic_settings import BaseSettings

# Resolve paths relative to project root (one level above backend/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    db_path: str = os.path.join(PROJECT_ROOT, "data", "athleteiq.db")
    data_dir: str = os.path.join(PROJECT_ROOT, "data")

    class Config:
        env_file = os.path.join(PROJECT_ROOT, ".env")
        env_file_encoding = "utf-8"


settings = Settings()
