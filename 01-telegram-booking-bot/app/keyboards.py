from __future__ import annotations

from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup, WebAppInfo

from .config import settings
from .i18n import LANG_NAMES, t


def webapp_url(**query) -> str | None:
    if not settings.webapp_url.startswith("https://"):
        return None  # Telegram only opens Mini Apps over HTTPS
    q = "&".join(f"{k}={v}" for k, v in query.items())
    return f"{settings.webapp_url}/" + (f"?{q}" if q else "")


def main_menu(lang: str) -> InlineKeyboardMarkup:
    rows = []
    url = webapp_url()
    if url:
        rows.append([Btn(text=t(lang, "btn_book"), web_app=WebAppInfo(url=url))])
    rows.append([Btn(text=t(lang, "btn_my"), callback_data="my")])
    rows.append([Btn(text=t(lang, "btn_prices"), callback_data="prices"),
                 Btn(text=t(lang, "btn_contacts"), callback_data="contacts")])
    if len(settings.languages) > 1:
        rows.append([Btn(text=t(lang, "btn_lang"), callback_data="lang")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_menu(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[Btn(text=t(lang, "btn_back"), callback_data="menu")]])


def lang_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [Btn(text=LANG_NAMES.get(code, code), callback_data=f"setlang:{code}")] for code in settings.languages
    ])


def booking_actions(lang: str, bid: int) -> InlineKeyboardMarkup:
    row = []
    url = webapp_url(reschedule=bid)
    if url:
        row.append(Btn(text=t(lang, "btn_reschedule"), web_app=WebAppInfo(url=url)))
    row.append(Btn(text=t(lang, "btn_cancel"), callback_data=f"cancel:{bid}"))
    return InlineKeyboardMarkup(inline_keyboard=[row])


def cancel_confirm(lang: str, bid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        Btn(text=t(lang, "btn_yes_cancel"), callback_data=f"cancelyes:{bid}"),
        Btn(text=t(lang, "btn_keep"), callback_data="keep"),
    ]])


def rating_kb(bid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        Btn(text="⭐" * n if n <= 3 else f"{n}⭐", callback_data=f"rate:{bid}:{n}") for n in range(1, 6)
    ]])


def skip_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[Btn(text=t(lang, "btn_skip"), callback_data="rskip")]])
