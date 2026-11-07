"""Application settings, loaded from environment variables / .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _ids(value: str) -> set[int]:
    return {int(x) for x in value.replace(" ", "").split(",") if x}


@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_ids: set[int] = field(default_factory=lambda: _ids(os.getenv("ADMIN_IDS", "")))
    webapp_url: str = os.getenv("WEBAPP_URL", "").rstrip("/")
    web_host: str = os.getenv("WEB_HOST", "0.0.0.0")
    web_port: int = int(os.getenv("WEB_PORT", "8080"))
    db_path: str = os.getenv("DB_PATH", str(BASE_DIR / "data" / "barber.db"))
    timezone: ZoneInfo = ZoneInfo(os.getenv("TIMEZONE", "Europe/London"))
    languages: tuple[str, ...] = tuple(os.getenv("LANGUAGES", "en").split(","))
    default_lang: str = os.getenv("DEFAULT_LANG", "en")
    currency: str = os.getenv("CURRENCY", "$")

    shop_name: str = os.getenv("SHOP_NAME", "Northside Barber Co.")
    shop_address: str = os.getenv("SHOP_ADDRESS", "24 Baker Street, London")
    shop_phone: str = os.getenv("SHOP_PHONE", "+44 20 0000 0000")
    shop_lat: float = float(os.getenv("SHOP_LAT", "51.5203"))
    shop_lon: float = float(os.getenv("SHOP_LON", "-0.1571"))
    open_time: str = os.getenv("OPEN_TIME", "10:00")
    close_time: str = os.getenv("CLOSE_TIME", "20:00")
    slot_step_min: int = int(os.getenv("SLOT_STEP_MIN", "15"))
    min_lead_min: int = int(os.getenv("MIN_LEAD_MIN", "30"))
    booking_days_ahead: int = int(os.getenv("BOOKING_DAYS_AHEAD", "14"))

    payment_token: str = os.getenv("PAYMENT_TOKEN", "")
    payment_currency: str = os.getenv("PAYMENT_CURRENCY", "USD")
    payment_hold_min: int = int(os.getenv("PAYMENT_HOLD_MIN", "15"))
    refund_free_hours: int = int(os.getenv("REFUND_FREE_HOURS", "24"))

    google_sheet_id: str = os.getenv("GOOGLE_SHEET_ID", "")
    google_credentials: str = os.getenv("GOOGLE_CREDENTIALS", "")

    # Lets you open the Mini App in a normal browser (no Telegram) for previews.
    # Never enable in production.
    dev_mode: bool = os.getenv("DEV_MODE", "0") == "1"


settings = Settings()
