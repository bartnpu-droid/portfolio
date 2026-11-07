"""Validation of Telegram Mini App initData.
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

MAX_AGE_SEC = 24 * 3600


def validate_init_data(init_data: str, bot_token: str, max_age: int = MAX_AGE_SEC) -> dict | None:
    """Return the Telegram user dict if initData is authentic and fresh, else None."""
    if not init_data or not bot_token:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        return None
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None
    try:
        if time.time() - int(pairs.get("auth_date", "0")) > max_age:
            return None
        return json.loads(pairs.get("user", "{}")) or None
    except (ValueError, json.JSONDecodeError):
        return None
