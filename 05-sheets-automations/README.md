# Google Sheets automations for small businesses

Two small automations built on Google's free tools (Google Sheets + Apps Script): no server and no monthly fees.

## Live demo

- Website form: https://bartnpu-droid.github.io/portfolio/lead-form/
- Lead sheet (view only): https://docs.google.com/spreadsheets/d/1rsNpv_CeFH-Hbou-14sEqK-IBmug4VMMfRHzgb09o84/edit
- Price sheet (view only): https://docs.google.com/spreadsheets/d/1q7NUyXsYmyisAkQrBKAvWpM6npL0EwBZ-blJBqbhWVk/edit
- Telegram alerts of both demos: https://t.me/s/upworkdemoalerts (opens in the browser)

## 1. Website form → Google Sheet → Telegram alert

Demo company: "Brightway Cleaning" (fictional). Landing page: `../docs/lead-form/index.html`.

- The website form sends each request to an Apps Script web app.
- The request becomes a new row in Google Sheets: date, name, contact, service, preferred date, message, source, status.
- Status column with a dropdown and colours (New / Contacted / Booked / Lost).
- The owner gets an instant Telegram alert, plus a morning summary: new requests in the last 24 hours and how many still wait for a reply.
- Spam protection: hidden honeypot field, input checks, links removed from messages, a limit of 40 requests per hour.
- Demo mode (the demo sheet is public): contacts are masked, only the first name is shown, alerts contain no free text.

## 2. Daily price monitor → Google Sheet + Telegram alert

Demo store: [books.toscrape.com](https://books.toscrape.com), a public sandbox made for scraping practice.

- Products tab: one product page URL per row, an optional "alert below" price and an Active checkbox.
- Every morning the script opens each page and reads the title, price and stock.
- History tab keeps every check; Latest tab shows the current price, previous price, change in %, lowest price seen and a small trend chart per product.
- Telegram alert when a price changes, drops below your target (once, not every morning), a product goes out of stock or a page stops opening.
- Prices on the demo store never change. To show the alerts in the demo, two saved prices were edited by hand before one check (one up, one down) and an "alert below" price was set for one book.
- For sites that need a real browser (JavaScript, logins) I use Python with Playwright instead.

## Files

- `apps-script/Common.gs`: setup, daily triggers, Telegram sending, helpers
- `apps-script/Leads.gs`: the form endpoint (`doPost`), lead sheet, morning summary
- `apps-script/Prices.gs`: the price monitor
- `tests/run.js`: offline tests with in-memory fakes of the Google services (`node 05-sheets-automations/tests/run.js`)

## Setup

1. Create a new Apps Script project (script.google.com) and add the three `.gs` files.
2. Project Settings → Script properties: `TELEGRAM_BOT_TOKEN` (from @BotFather) and `TELEGRAM_CHAT_ID` (a channel like `@MyChannel` or a chat id).
3. Run `setup` once and allow access. It creates both spreadsheets and the daily triggers.
4. Deploy → New deployment → Web app (Execute as: Me, Who has access: Anyone). Put the web app URL into the website form.
