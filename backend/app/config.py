"""Central settings. Secrets live here and are never serialised to the frontend."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "sqlite:///./tradeai.db"
    redis_url: Optional[str] = None

    ai_provider: str = "auto"
    openai_api_key: Optional[SecretStr] = None
    gemini_api_key: Optional[SecretStr] = None
    anthropic_api_key: Optional[SecretStr] = None
    anthropic_model: str = "claude-sonnet-5-5"
    openai_model: str = "gpt-4o-mini"
    gemini_model: str = "gemini-3.8-flash"

    frontend_url: str = "http://localhost:5173"

    # what-if risk defaults, adjustable per request
    account_size: float = 100_000.0
    max_risk_per_trade_pct: float = 1.0
    max_position_pct: float = 25.0
    max_daily_loss_pct: float = 3.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
