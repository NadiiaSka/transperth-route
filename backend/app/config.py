from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str = "postgresql://transperth:transperth@localhost:5432/transperth"
    osrm_url: str = "http://localhost:5001"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"


settings = Settings()
