"""Entry point: runs the Telegram bot (long polling), the Mini App web server
and the reminder scheduler in one process."""
from __future__ import annotations

import asyncio
import errno
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (BotCommand, BotCommandScopeChat, FSInputFile, InputProfilePhotoStatic,
                           MenuButtonWebApp, WebAppInfo)
from aiohttp import web

from . import scheduler
from .api import create_app
from .config import BASE_DIR, settings
from .db import db
from .handlers import admin, client
from .i18n import t
from .keyboards import webapp_url

log = logging.getLogger("barber")
ASSETS = BASE_DIR / "assets"

DESCRIPTIONS = {
    "en": (
        "💈 Book a haircut at {shop} in a few taps.\n\n"
        "• Pick a service, a barber and a free time\n"
        "• Get reminders before your visit\n"
        "• Cancel or reschedule anytime\n\n"
        "Press Start to book.",
        "Book a haircut at {shop} in a few taps. Reminders included.",
    ),
}


async def _safe(coro, what: str) -> None:
    try:
        await coro
    except Exception as e:
        log.info("%s skipped: %s", what, e)


async def setup_bot_ui(bot: Bot) -> None:
    """Commands, menu button, description and profile photo. Every step is optional."""
    for lang in settings.languages:
        code = None if lang == settings.default_lang else lang
        await _safe(bot.set_my_commands(
            [BotCommand(command="start", description="Main menu"),
             BotCommand(command="my", description="My bookings")],
            language_code=code), "commands")
        long_d, short_d = DESCRIPTIONS.get(lang, DESCRIPTIONS["en"])
        await _safe(bot.set_my_description(long_d.format(shop=settings.shop_name), language_code=code), "description")
        await _safe(bot.set_my_short_description(short_d.format(shop=settings.shop_name), language_code=code),
                    "short description")
    # Telegram keeps a language's commands and descriptions until they are cleared: remove the Russian
    # ones an earlier version set, so every user gets the English profile.
    if "ru" not in settings.languages:
        await _safe(bot.delete_my_commands(language_code="ru"), "old commands")
        await _safe(bot.set_my_description(description="", language_code="ru"), "old description")
        await _safe(bot.set_my_short_description(short_description="", language_code="ru"),
                    "old short description")
    for admin_id in settings.admin_ids:
        await _safe(bot.set_my_commands(
            [BotCommand(command="start", description="Main menu"),
             BotCommand(command="my", description="My bookings"),
             BotCommand(command="admin", description="Admin panel")],
            scope=BotCommandScopeChat(chat_id=admin_id)), "admin commands")

    url = webapp_url()
    if url:
        await _safe(bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
            text=t(settings.default_lang, "menu_button"), web_app=WebAppInfo(url=url))), "menu button")
    else:
        log.warning("WEBAPP_URL is not an https:// URL — the Mini App button is hidden. See README.")

    # Profile photo: upload once, then remember it so restarts don't re-upload.
    marker = BASE_DIR / "data" / ".avatar_set"
    avatar = ASSETS / "avatar.jpg"
    if avatar.exists() and not marker.exists():
        try:
            await bot.set_my_profile_photo(photo=InputProfilePhotoStatic(photo=FSInputFile(avatar)))
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("ok")
            log.info("Bot profile photo set")
        except Exception as e:
            log.info("profile photo skipped: %s", e)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    if not settings.bot_token:
        sys.exit("\n❌ BOT_TOKEN is missing. Open .env and paste the token from @BotFather.\n")

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        me = await bot.get_me()
    except TelegramUnauthorizedError:
        await bot.session.close()
        sys.exit("\n❌ Telegram rejected the bot token. Copy it again from @BotFather "
                 "(tap the token to copy) and paste it into .env.\n")

    await db.connect()
    runner = web.AppRunner(create_app(bot))
    await runner.setup()
    try:
        await web.TCPSite(runner, settings.web_host, settings.web_port).start()
    except OSError as e:
        await bot.session.close()
        if e.errno in (errno.EADDRINUSE, 48, 98):
            sys.exit(f"\n❌ Port {settings.web_port} is already used by another program. "
                     f"Set another WEB_PORT in .env (e.g. 8765) and start again.\n")
        raise

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin.router)   # staff handlers first
    dp.include_router(client.router)
    await setup_bot_ui(bot)
    reminder_task = asyncio.create_task(scheduler.run(bot))

    log.info("Mini App server on http://%s:%s", settings.web_host, settings.web_port)
    print(f"\n✅ @{me.username} is online: https://t.me/{me.username}\n", flush=True)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), handle_signals=True)
    finally:
        reminder_task.cancel()
        await runner.cleanup()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
