"""Central settings for the Servora backend.

Reads from environment variables (populated via a local .env file — see
.env.example). Nothing here should ever hold a real secret value.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-5"

    database_url: str = "sqlite:///./servora.db"
    frontend_origin: str = "http://localhost:5173"


settings = Settings()
