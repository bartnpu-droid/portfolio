# Portfolio

Live demos:
- 01 Telegram booking bot: https://t.me/NorthsideBarberDemoBot
- 03 Dental clinic website with the AI receptionist: https://dental-clinic-production-b8f4.up.railway.app
- 04 TACET One product landing page: https://tacet-one-production.up.railway.app

## 01 — Telegram booking bot with Mini App and online payments
Folder: `01-telegram-booking-bot`
Demo barbershop "Northside Barber Co." (fictional).
- Telegram Mini App: services → barber → free time → confirmation ticket
- Online prepayment / full payment (Telegram Payments), slot hold, refund rules
- Reminders 24 h and 2 h before, review request after the visit
- Admin panel: schedule, 7-day stats, services, barbers, days off, broadcast, Google Sheets export
- Python, aiogram 3, aiohttp, SQLite, Docker, automated tests
Run: `bash start.command` inside the folder.
Screens: `01-telegram-booking-bot/screenshots/`, demo video: `01-telegram-booking-bot/barbershop-bot-demo.mp4`

## 02 — Lead generation: independent barbershops in London
Folder: `02-london-barbershop-leads`
- 1,153 places from OpenStreetMap → 10 duplicates removed → 8 chain locations excluded → 1,135 independents
- Websites visited for e-mails, Instagram/Facebook and the online booking system used
- E-mail domains checked (MX)
- Excel report: Leads, With contacts, Summary, Excluded chains + CSV
- Share only `output/*_sample_masked.xlsx` (contacts masked)
Run: `bash run.command` inside the folder.
Screens: `02-london-barbershop-leads/screenshots/`
Data © OpenStreetMap contributors (ODbL) + business websites.

## 03 — Dental clinic website with 3D + AI receptionist
Folder: `03-ai-dental-assistant`
- 7-page clinic website with a photoreal 3D dental implant rendered in Blender (Cycles): it turns with the
  cursor on the home page and comes apart as you scroll; cream-and-green design built around a honeycomb motif
- AI receptionist built into the site: "Ask" next to every treatment, the chat follows the visitor across pages; also in Telegram
- Answers only from the clinic's knowledge base (prices, hours, insurance, aftercare, emergencies); a test checks the site's prices against it
- Appointment / callback requests (from the AI or the booking form) → Telegram notification for staff, admin stats, CSV export
- Safety rules for medical topics, spam and budget limits, SEO, accessibility, mobile layout
Run: `bash start.command` inside the folder (add the API key to `.env` first), then open the address it prints
Screens: `03-ai-dental-assistant/screenshots/`, demo video: `03-ai-dental-assistant/ai-dental-receptionist-demo.mp4`

## 04 — 3D product landing page
Folder: `04-3d-product-landing`
Concept launch page for "TACET One" noise-cancelling headphones (fictional brand), in the style of the big tech launch pages.
- Photoreal renders of a headphone model built in Blender for this page (Cycles, Mac GPU), three colours
- 360° view you turn by hand: 144 rendered angles per colour, always sharp; colours swap on the same angle
- Ear cup that comes apart into five layers while the page keeps scrolling, with tags that follow the parts
- Highlights rail, live noise-cancelling demo with a noise meter, battery counter, specs, pre-order form
- Static site, no build step; Lighthouse 99–100 for performance, accessibility and best practices
Run: double-click `start.command` inside the folder
Screens: `04-3d-product-landing/screenshots/`, demo video: `04-3d-product-landing/tacet-one-demo.mp4`

## 05 — Google Sheets automations (form → sheet → Telegram, daily price monitor)
Folder: `05-sheets-automations`
- Website form → Google Sheet → instant Telegram alert + morning summary (demo company "Brightway Cleaning", fictional)
- Daily price monitor: product pages → Google Sheet with history, % change, lowest price, trend charts → Telegram alerts
- Google Apps Script, no server and no monthly fees; offline tests: `node 05-sheets-automations/tests/run.js`
Landing page with the form: `docs/lead-form/index.html`
Live demo: https://bartnpu-droid.github.io/portfolio/lead-form/ (alerts: https://t.me/s/upworkdemoalerts)
Screens: `05-sheets-automations/screenshots/`

## 06 — PDF invoices → Excel, checked automatically
Folder: `06-pdf-invoices-to-excel`
- Reads normal and scanned invoice PDFs (OCR with Tesseract): supplier, number, dates, currency, line items, subtotal, tax, total
- UK, EU and US formats, multi-page invoices; quantity × price, line sums and totals are checked, problems are flagged
- Output: Excel with Invoices / Line items / Summary tabs, plus CSV; 14 tests: `cd 06-pdf-invoices-to-excel && python -m pytest`
Screens: `06-pdf-invoices-to-excel/screenshots/`

## 07 — Shopify sections: hero from a design, free shipping bar, FAQ
Folder: `07-shopify-sections`
Custom Online Store 2.0 sections for "Solenne", a fictional summer clothing brand, built on Dawn and tested in a Shopify development store with a full catalog (8 products with sizes, collections, menus, product pages, cart). No apps.
- Hero with separate desktop and mobile images, two buttons, overlay, 9 text positions, typography settings to match a Figma file; first hero loads with high priority, no layout jump
- Free shipping progress bar in the cart drawer and on the cart page, updates instantly after every cart change
- FAQ accordion on native `<details>`, one-open-at-a-time without JavaScript, optional FAQPage structured data
- Every text, image, colour and position is a setting in the theme editor; Shopify Theme Check: 0 issues
Screens: `07-shopify-sections/screenshots/`, demo video: `07-shopify-sections/solenne-shopify-demo.mp4`
