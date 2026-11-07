"""Runs the AI receptionist: website chat server + Telegram bot in one process."""
from __future__ import annotations

import asyncio
import errno
import logging
import sys

from aiohttp import web

from .assistant import Assistant
from .config import settings
from .kb import KnowledgeBase
from .store import store
from .web import create_app

log = logging.getLogger("assistant")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    await store.connect()
    kb = KnowledgeBase(settings.knowledge_dir)
    log.info("Knowledge base: %d sections", len(kb.chunks))

    bot = dp = None
    if settings.bot_token:
        from aiogram import Bot, Dispatcher
        from aiogram.exceptions import TelegramUnauthorizedError
        from aiogram.types import BotCommand

        from . import bot as tg

        bot = Bot(settings.bot_token)
        try:
            me = await bot.get_me()
        except TelegramUnauthorizedError:
            sys.exit("\n❌ Telegram rejected BOT_TOKEN. Copy it again from @BotFather.\n")
        dp = Dispatcher()
        dp.include_router(tg.admin)
        dp.include_router(tg.router)

    async def on_lead(lead_id, kind, data):
        if bot:
            from .bot import notify_lead
            await notify_lead(bot, lead_id, kind, data)

    async def on_alert(text):
        for admin_id in settings.admin_ids if bot else ():
            try:
                await bot.send_message(admin_id, text)
            except Exception as e:
                log.info("alert to %s failed: %s", admin_id, e)

    assistant = Assistant(kb, on_lead=on_lead, on_alert=on_alert)
    log.info("AI provider: %s (%s)", type(assistant.provider).__name__, settings.model)

    runner = web.AppRunner(create_app(assistant))
    await runner.setup()
    try:
        await web.TCPSite(runner, settings.web_host, settings.web_port).start()
    except OSError as e:
        if e.errno in (errno.EADDRINUSE, 48, 98):
            sys.exit(f"\n❌ Port {settings.web_port} is busy. Set another WEB_PORT in .env.\n")
        raise
    print(f"\n✅ Website: http://localhost:{settings.web_port}"
          + (f"  ·  public: {settings.public_url}" if settings.public_url else ""), flush=True)

    try:
        if bot:
            from . import bot as tg
            tg.setup(assistant)
            await bot.set_my_commands([BotCommand(command="start", description="Start"),
                                       BotCommand(command="reset", description="New conversation")])
            await bot.set_my_description(
                f"🦷 Virtual receptionist of {settings.clinic_name}, London. Ask about treatments and prices, "
                "opening hours, or request an appointment — 24/7.")
            print(f"✅ Telegram: https://t.me/{me.username}\n", flush=True)
            await dp.start_polling(bot)
        else:
            print("ℹ️  No BOT_TOKEN — running the website chat only.\n", flush=True)
            await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await store.close()
        if bot:
            await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
