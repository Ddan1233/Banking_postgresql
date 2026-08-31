"""Configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """Runtime settings; secrets must be supplied through the environment."""

    app_name: str = "Banking Risk Multi-Agent API"
    app_version: str = "0.3.0"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    excel_workbook_path: Path = Path("Data.xlsx")
    database_url: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
