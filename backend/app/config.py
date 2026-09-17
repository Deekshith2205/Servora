"""Central settings for the Servora backend.

Reads from environment variables (populated via a local .env file — see
.env.example). Nothing here should ever hold a real secret value.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "anthropic"  # "anthropic" | "gemini"
    anthropic_api_key: str = ""
    google_api_key: str = ""
    llm_model: str = "claude-opus-5"

    database_url: str = "sqlite:///./servora.db"
    frontend_origin: str = "http://localhost:5173"

    # Real "Sign in with Google" — see app/api/auth.py::google_sign_in().
    # Empty (the honest default) means the feature is off; only the
    # Client ID is ever read here, never a client secret.
    google_client_id: str = ""

    # Every /api/chat or /api/booking call triggers a real LLM call chain
    # (classifier + planner + specialist(s) + critic, sometimes several in
    # parallel — see [SWARM] #88) — real cost and, on a free-tier provider
    # key, a real rate-limit risk (hit live while testing this). Disabled
    # in tests (see tests/conftest.py) so a fast, LLM-mocked test run
    # sending many requests in a few seconds never trips it.
    rate_limit_enabled: bool = True
    # Generous enough that a real demo session — several DEMO_SCRIPT.md
    # scenarios plus a judge poking at edge cases — never trips it (both
    # endpoints share one budget per client, deliberately: they're the
    # same real cost/abuse surface), while still stopping a genuine
    # burst/abuse pattern within the window.
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60


settings = Settings()
