"""Settings from environment variables / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _ids(v: str) -> set[int]:
    return {int(x) for x in v.replace(" ", "").split(",") if x}


@dataclass(frozen=True)
class Settings:
    # LLM: "anthropic", "openai" or "mock" (offline demo, no key needed)
    llm_provider: str = os.getenv("LLM_PROVIDER", "anthropic").lower()
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "")
    max_output_tokens: int = int(os.getenv("MAX_OUTPUT_TOKENS", "1024"))
    # Extended thinking makes replies slower and can use up the token limit; a receptionist doesn't need it
    anthropic_thinking: bool = os.getenv("ANTHROPIC_THINKING", "off").lower() in ("on", "1", "true")
    # USD per 1M tokens (defaults: Claude Haiku 5.5 list price). Used for the budget cap and /admin estimate.
    price_in_per_m: float = float(os.getenv("PRICE_INPUT_PER_M", "0.10"))
    price_out_per_m: float = float(os.getenv("PRICE_OUTPUT_PER_M", "0.50"))
    price_cache_read_per_m: float = float(os.getenv("PRICE_CACHE_READ_PER_M", "0.01"))
    price_cache_write_per_m: float = float(os.getenv("PRICE_CACHE_WRITE_PER_M", "0.125"))
    # Hard daily spending cap: above it the assistant stops calling the AI and asks patients to phone
    daily_budget_usd: float = float(os.getenv("DAILY_BUDGET_USD", "3"))
    # Website: messages per IP address per day (a new browser session doesn't reset it)
    ip_daily_limit: int = int(os.getenv("IP_DAILY_LIMIT", "100"))

    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_ids: set[int] = field(default_factory=lambda: _ids(os.getenv("ADMIN_IDS", "")))

    web_host: str = os.getenv("WEB_HOST", "0.0.0.0")
    web_port: int = int(os.getenv("WEB_PORT", "8090"))
    public_url: str = os.getenv("PUBLIC_URL", "").rstrip("/")
    # Keep the demo site out of search engines (fictional clinic). Set SITE_NOINDEX=0 for a real clinic.
    site_noindex: bool = os.getenv("SITE_NOINDEX", "1").lower() in ("1", "true", "on", "yes")
    form_hourly_limit: int = int(os.getenv("FORM_HOURLY_LIMIT", "5"))  # booking form posts per IP per hour

    db_path: str = os.getenv("DB_PATH", str(BASE_DIR / "data" / "assistant.db"))
    knowledge_dir: str = os.getenv("KNOWLEDGE_DIR", str(BASE_DIR / "knowledge"))

    clinic_name: str = os.getenv("CLINIC_NAME", "BrightSmile Dental")
    clinic_phone: str = os.getenv("CLINIC_PHONE", "020 0000 0000")
    # Knowledge bases up to this size are sent whole; bigger ones are searched (BM25)
    full_context_chars: int = int(os.getenv("FULL_CONTEXT_CHARS", "30000"))
    history_messages: int = int(os.getenv("HISTORY_MESSAGES", "12"))
    daily_message_limit: int = int(os.getenv("DAILY_MESSAGE_LIMIT", "40"))  # per user, protects the budget
    timezone: str = os.getenv("TIMEZONE", "Europe/London")

    @property
    def model(self) -> str:
        if self.llm_model:
            return self.llm_model
        return {"anthropic": "claude-haiku-5-5", "openai": "gpt-4o-mini"}.get(self.llm_provider, "mock")


settings = Settings()
