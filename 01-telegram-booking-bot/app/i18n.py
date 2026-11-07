"""Tiny translation helper. Add a language by adding a dict to TEXTS
and listing it in the LANGUAGES env variable."""
from __future__ import annotations

from .config import settings

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "choose_lang": "Please choose your language:",
        "welcome": "👋 Welcome to <b>{shop}</b>!\n\nBook a haircut in a few taps: pick a service, a barber and a time that suits you.",
        "btn_book": "📅 Book appointment",
        "btn_my": "🗓 My bookings",
        "btn_prices": "💈 Services & prices",
        "btn_contacts": "📍 Contacts",
        "btn_lang": "🌐 Language",
        "btn_back": "⬅️ Back",
        "menu_button": "Book",
        "lang_set": "✅ Language updated.",
        "prices_title": "💈 <b>Services & prices</b>\n",
        "price_line": "• <b>{name}</b> — {price} · {dur} min",
        "contacts": "📍 <b>{shop}</b>\n{address}\n\n🕙 Every day {open}–{close}\n📞 {phone}",
        "my_empty": "You have no upcoming bookings yet.",
        "my_title": "🗓 <b>Your upcoming bookings</b>",
        "booking_line": "✂️ <b>{service}</b> with {master}\n🕒 {when} · {price}",
        "btn_cancel": "❌ Cancel",
        "btn_reschedule": "🔁 Reschedule",
        "cancel_confirm": "Cancel this booking?\n\n{line}",
        "btn_yes_cancel": "Yes, cancel",
        "btn_keep": "Keep it",
        "cancelled": "Your booking has been cancelled. Hope to see you another time! 👋",
        "kept": "Great, your booking stays as it is ✅",
        "confirmed": "✅ <b>You're booked!</b>\n\n✂️ {service}\n💈 Barber: {master}\n🕒 {when}\n💵 {price}\n📍 {address}\n\nWe'll remind you 24 hours and 2 hours before your visit.",
        "rescheduled": "🔁 <b>Booking moved</b>\n\n✂️ {service}\n💈 Barber: {master}\n🕒 {when}",
        "remind_24": "⏰ Reminder: <b>{service}</b> with {master}\n🕒 {when}\n📍 {address}\n\nCan't make it? Cancel or reschedule in «My bookings».",
        "remind_2": "⏰ See you soon! <b>{service}</b> with {master} at {time} — in about 2 hours.",
        "review_ask": "How was your visit with {master}? Please rate it:",
        "review_comment": "Thank you! ⭐ {stars}\nWould you like to add a short comment? Just send it as a message, or tap Skip.",
        "btn_skip": "Skip",
        "review_thanks": "Thanks for your feedback! 🙏",
        "error_slot_taken": "Sorry, this time was just taken. Please choose another slot.",
        "error_generic": "Something went wrong. Please try again.",
        # Admin
        "admin_only": "This section is for staff only.",
        "admin_title": "🛠 <b>Admin panel</b> — {shop}",
        "a_today": "📋 Today",
        "a_tomorrow": "📆 Tomorrow",
        "a_stats": "📊 Stats (7 days)",
        "a_services": "💈 Services",
        "a_masters": "✂️ Barbers",
        "a_broadcast": "📣 Broadcast",
        "a_export": "📤 Export",
        "a_day_title": "📋 <b>Bookings for {date}</b>",
        "a_day_empty": "No bookings for {date}.",
        "a_booking": "{icon} <b>{time}</b> {service} — {master}\n👤 {client}",
        "a_done": "✅ Done",
        "a_noshow": "🚫 No-show",
        "a_marked": "Status updated.",
        "a_stats_text": "📊 <b>Last 7 days</b>\n\nBookings: <b>{total}</b>\nCompleted: <b>{done}</b>\nCancelled: <b>{cancelled}</b>\nNo-shows: <b>{noshow}</b>\nRevenue: <b>{revenue}</b>\n{paid_online}\nNew clients: <b>{new_users}</b>\n\n🏆 Top service: {top_service}\n💈 Top barber: {top_master}\n⭐ Average rating: {rating}",
        "a_services_title": "💈 <b>Services</b>\nTap a service to edit it.",
        "a_service_card": "💈 <b>{name}</b>\n⏱ {dur} min · 💵 {price}\nStatus: {status}",
        "a_active": "active ✅",
        "a_hidden": "hidden 🙈",
        "a_toggle": "Show / hide",
        "a_edit_price": "Change price",
        "a_add_service": "➕ Add service",
        "a_ask_price": "Send the new price (number only):",
        "a_ask_service_name": "Send the service name:",
        "a_ask_service_duration": "Duration in minutes (e.g. 45):",
        "a_ask_service_price": "Price (number only):",
        "a_saved": "✅ Saved.",
        "a_bad_number": "Please send a number.",
        "a_masters_title": "✂️ <b>Barbers</b>\nTap a barber to manage.",
        "a_master_card": "✂️ <b>{name}</b> — {title}\nWorking days: {days}\nTelegram linked: {linked}\nStatus: {status}\nUpcoming days off: {offs}",
        "a_day_off": "🏖 Add day off",
        "a_link_tg": "🔗 Link Telegram ID",
        "a_ask_date": "Send the date as YYYY-MM-DD:",
        "a_bad_date": "Wrong date format. Example: 2026-12-24",
        "a_ask_tg": "Send the barber's numeric Telegram ID (they can get it from @userinfobot):",
        "a_broadcast_ask": "Send the text of the broadcast. It will go to all clients.",
        "a_broadcast_preview": "Preview:\n\n{text}\n\nSend it to <b>{n}</b> clients?",
        "a_send": "📣 Send",
        "a_cancel": "Cancel",
        "a_broadcast_done": "Sent to {ok} of {n} clients.",
        "a_cancelled": "Cancelled.",
        "a_export_done": "📤 Exported {n} bookings to Google Sheets.",
        "a_export_csv": "📤 Bookings export ({n} rows). Google Sheets is not configured, so here is a CSV file.",
        "a_new_booking": "🆕 <b>New booking</b>\n✂️ {service}\n💈 {master}\n🕒 {when}\n👤 {client}{paid}",
        "a_cancelled_booking": "❌ <b>Booking cancelled</b>\n✂️ {service}\n💈 {master}\n🕒 {when}\n👤 {client}",
        "a_rescheduled_booking": "🔁 <b>Booking moved</b>\n✂️ {service}\n💈 {master}\n🕒 {when}\n👤 {client}",
        "a_new_review": "⭐ <b>New review: {stars}</b>\n💈 {master}\n👤 {client}\n{comment}",
        "pay_line": "💳 Paid online: <b>{amount}</b>",
        "pay_rest": "💵 To pay at the shop: {amount}",
        "pay_expired": "The time to pay has run out. Please book again.",
        "invoice_title": "Booking · {service}",
        "invoice_desc": "{service} with {master}, {when}.",
        "invoice_deposit": "Prepayment {pct}%",
        "invoice_full": "Payment",
        "refund_yes": "💳 Your prepayment of {amount} will be refunded within a few days.",
        "refund_no": "💳 Prepayment of {amount} is non-refundable when cancelling less than {hours} hours before the visit.",
        "a_payments": "💳 Payments",
        "a_pay_title": "💳 <b>Online payments</b>\n\nProvider connected: {connected}\nMode: <b>{mode}</b>\nPrepayment: {pct}%\nSlot is held for {hold} min while the client pays.\nFree cancellation: {hours} h before the visit.",
        "a_pay_no_token": "To accept payments, connect a provider in @BotFather → Payments and put the token into PAYMENT_TOKEN in .env.",
        "a_mode_off": "No online payment",
        "a_mode_deposit": "Prepayment",
        "a_mode_full": "Full payment",
        "a_paid_tag": "💳 paid {amount}",
        "a_refund_due": "💸 <b>Refund needed: {amount}</b>\n✂️ {service} · {when}\n👤 {client}\n\nRefund it in your payment provider's dashboard, then tap the button.",
        "a_refunded": "✅ Refunded",
        "a_refund_marked": "Marked as refunded.",
        "a_paid_online": "Paid online: <b>{amount}</b>",
        "no": "—",
    },
}

LANG_NAMES = {"en": "🇬🇧 English"}

WEEKDAYS = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}
MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}


def norm_lang(lang: str | None) -> str:
    offered = [code for code in settings.languages if code in TEXTS] or ["en"]
    if lang in offered:
        return lang
    return settings.default_lang if settings.default_lang in offered else offered[0]


def t(lang: str | None, key: str, **kwargs) -> str:
    lang = norm_lang(lang)
    text = TEXTS.get(lang, TEXTS["en"]).get(key) or TEXTS["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text


def fmt_when(lang: str | None, dt) -> str:
    lang = norm_lang(lang)
    return f"{WEEKDAYS[lang][dt.weekday()]}, {dt.day} {MONTHS[lang][dt.month - 1]} · {dt:%H:%M}"


def fmt_date(lang: str | None, d) -> str:
    lang = norm_lang(lang)
    return f"{WEEKDAYS[lang][d.weekday()]}, {d.day} {MONTHS[lang][d.month - 1]}"
