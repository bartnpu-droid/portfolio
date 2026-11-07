# Barbershop Booking Bot — Telegram bot + Mini App

A complete online booking system for a barbershop that lives inside Telegram.
Clients book in a few taps through a Telegram **Mini App**; the owner runs the
shop from an **admin panel** right in the chat.

> Demo project. The shop "Northside Barber Co.", its barbers and prices are fictional.

Demo video: [`barbershop-bot-demo.mp4`](barbershop-bot-demo.mp4) (22 s, a booking made in the Mini App).
Try it live: https://t.me/NorthsideBarberDemoBot

## Features

**For clients**
- Telegram Mini App: service price list → barber → date & time → confirmation ticket
- "Any barber" option that books the least busy barber who is free at that time
- Real availability: service length, opening hours, working days and days off are all respected
- Booking confirmation in chat, reminders **24 h** and **2 h** before the visit
- "My bookings" with one-tap cancel and reschedule
- Rating and comment request one hour after the visit

**For the owner and barbers**
- `/admin` panel: today's and tomorrow's schedule, mark visits as done / no-show
- 7-day stats: bookings, revenue, cancellations, no-shows, new clients, top service, top barber, rating
- Manage services (add, change price, hide) and barbers (hide, days off, link Telegram account)
- Instant notifications to the shop and to the barber about new, moved and cancelled bookings, and new reviews
- Broadcast a message to all clients
- Export all bookings to Google Sheets (or CSV if Sheets is not configured)
- Online payments: no payment, prepayment (20/30/50%) or full payment, switchable in the admin panel

**Online payments (Telegram Payments)**
- Pay inside Telegram right after choosing a time (cards, Apple Pay, Google Pay — depending on the provider)
- The slot is held for 15 minutes while the client pays, then released automatically
- Booking is confirmed only after a successful payment; paid amounts show in stats and export
- Refund rule: free cancellation up to 24 h before the visit (configurable); the admin gets a "refund needed" alert
- Rescheduling keeps the payment

**Under the hood**
- Python 3.11+, aiogram 3, aiohttp, SQLite
- Mini App requests are authenticated by validating Telegram `initData` (HMAC-SHA256)
- Booking writes are serialised, so two clients can never take the same slot
- One process runs the bot, the web server and the reminder scheduler
- Docker image, health check, automated tests

## Project structure

```
app/
  main.py         entry point: bot + web server + scheduler
  config.py       settings from .env
  db.py           SQLite schema, demo data, queries
  slots.py        free-slot calculation (pure functions)
  booking.py      booking rules: create, cancel, reschedule
  api.py          HTTP API for the Mini App
  webapp_auth.py  Telegram initData validation
  scheduler.py    reminders and review requests
  notify.py       messages to clients and staff
  export.py       Google Sheets / CSV export
  i18n.py         translations
  handlers/       client.py, admin.py
webapp/           Mini App (HTML, CSS, vanilla JS)
tests/            pytest suite
```

## Quick start

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. Copy the settings file and fill it in:
   ```bash
   cp .env.example .env
   ```
   Set `BOT_TOKEN`, `ADMIN_IDS` (your Telegram ID from @userinfobot) and `WEBAPP_URL`.
3. Run it, either with Docker:
   ```bash
   docker compose up -d --build
   ```
   or with Python:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python -m app.main
   ```
4. Open your bot in Telegram and press **Start**. Staff use `/admin`.

### Mini App URL

Telegram opens Mini Apps only over **HTTPS**. The server listens on port `8080`:

- **Production:** put it behind a domain with HTTPS (Nginx/Caddy, or a platform like Railway/Render/Fly.io)
  and set `WEBAPP_URL=https://your-domain`.
- **Local testing:** expose the port with a tunnel, for example
  `cloudflared tunnel --url http://localhost:8080`, and set `WEBAPP_URL` to the `https://…trycloudflare.com`
  address it prints, then restart the bot.

### Online payments (optional)

1. In @BotFather open your bot → **Payments** and connect a provider (start with its TEST mode).
2. Put the token into `PAYMENT_TOKEN` in `.env` and set `PAYMENT_CURRENCY` (e.g. `USD`, `EUR`, `GBP`).
3. Restart the bot and choose the mode in `/admin` → **Payments**.

Refunds for provider payments are made in the provider's dashboard; the bot tells the admin when one is due
and lets them mark it as done.

### Google Sheets export (optional)

1. Create a Google Cloud service account and download its JSON key.
2. Share your spreadsheet with the service account e-mail (Editor).
3. Set `GOOGLE_SHEET_ID` (from the sheet URL) and `GOOGLE_CREDENTIALS` (path to the JSON key).

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite covers slot calculation, double-booking protection (including concurrent requests),
"any barber" assignment, rescheduling, days off, reminders, review requests and the Mini App API
with signed `initData`.

## Customising

- Shop name, address, hours, currency and time zone — `.env`
- Services and barbers — admin panel, or the demo data in `app/db.py`
- Texts and languages — `app/i18n.py` and `webapp/app.js`
- Colours and fonts — CSS variables at the top of `webapp/style.css`
