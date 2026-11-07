"""Website: clinic pages, the chat API used by the widget, and the booking form API."""
from __future__ import annotations

import logging
import re
import secrets
import time
from collections import defaultdict, deque
from urllib.parse import quote

from aiohttp import web

from .config import BASE_DIR, settings
from .store import store

log = logging.getLogger(__name__)
WEBAPP = BASE_DIR / "webapp"
PAGES = {  # clean URL -> built page in webapp/ (source: site/pages, build: python site/build.py)
    "/": "index.html", "/treatments": "treatments.html", "/implants": "implants.html", "/team": "team.html",
    "/patients": "patients.html", "/contact": "contact.html",
    "/demo": "demo.html", "/bubble": "bubble.html",   # bare widget demos
}
SITEMAP = ["/", "/treatments", "/implants", "/team", "/patients", "/contact"]
SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
HOST_RE = re.compile(r"^[A-Za-z0-9.-]+(:\d+)?$")
PHONE_RE = re.compile(r"^\+?[\d\s().-]{7,24}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_MESSAGE = 2000
RATE = defaultdict(deque)  # ip -> timestamps
RATE_LIMIT, RATE_WINDOW = 20, 60  # burst limit: messages per minute per IP
DAILY: dict[str, list] = {}       # ip -> [day, count]: daily limit survives clearing the browser session
FORM_RATE = defaultdict(deque)    # ip -> booking form posts in the last hour
YES = ("yes", "on", "true", "1")


def _cors(resp: web.StreamResponse) -> web.StreamResponse:
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return resp


def _ip(request: web.Request) -> str:
    """The visitor's address behind a proxy: X-Real-IP (set by the hosting edge, e.g. Railway, which replaces
    any copy sent by the visitor), CF-Connecting-IP (the Cloudflare tunnel of start.command), else the socket."""
    return (request.headers.get("X-Real-IP") or request.headers.get("CF-Connecting-IP")
            or request.remote or "?")


def _limited(ip: str) -> str | None:
    """Returns an error message if this IP should be throttled, else None."""
    q, now = RATE[ip], time.monotonic()
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return "Too many messages, please wait a minute."
    day = time.strftime("%Y-%m-%d")
    entry = DAILY.get(ip)
    if not entry or entry[0] != day:
        if len(DAILY) > 50_000:  # keep memory bounded
            DAILY.clear()
        entry = DAILY[ip] = [day, 0]
    if entry[1] >= settings.ip_daily_limit:
        return "You've reached today's message limit for the chat. Please call the clinic."
    entry[1] += 1
    q.append(now)
    return None


def _form_limited(ip: str) -> bool:
    q, now = FORM_RATE[ip], time.monotonic()
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= settings.form_hourly_limit:
        return True
    if len(FORM_RATE) > 50_000:
        FORM_RATE.clear()
    q.append(now)
    return False


def _origin(request: web.Request) -> str:
    """Absolute site URL for canonical links, Open Graph tags and the sitemap."""
    if settings.public_url:
        return settings.public_url
    host = request.headers.get("X-Forwarded-Host") or request.host
    proto = request.headers.get("X-Forwarded-Proto") or request.scheme
    if not HOST_RE.match(host or "") or proto not in ("http", "https"):
        host, proto = f"localhost:{settings.web_port}", "http"
    return f"{proto}://{host}"


_cache: dict[str, tuple[float, str]] = {}


def _read(name: str) -> str:
    path = WEBAPP / name
    mtime = path.stat().st_mtime
    hit = _cache.get(name)
    if not hit or hit[0] != mtime:
        hit = _cache[name] = (mtime, path.read_text(encoding="utf-8"))
    return hit[1]


def _html(request: web.Request, name: str, status: int = 200) -> web.Response:
    resp = web.Response(text=_read(name).replace("__ORIGIN__", _origin(request)), status=status,
                        content_type="text/html", headers={"Cache-Control": "no-cache"})
    if settings.site_noindex:
        resp.headers["X-Robots-Tag"] = "noindex"
    return resp


@web.middleware
async def pages_middleware(request: web.Request, handler):
    path = request.path
    clean = "/" if path in ("/index.html", "/index") else path.rstrip("/").removesuffix(".html")
    if clean != path and clean in PAGES and request.method in ("GET", "HEAD"):
        raise web.HTTPPermanentRedirect(clean + (f"?{request.query_string}" if request.query_string else ""))
    try:
        return await handler(request)
    except web.HTTPNotFound:
        if request.method in ("GET", "HEAD") and not path.startswith(("/api/", "/static/")):
            return _html(request, "404.html", status=404)
        raise


TEXT_TYPES = {"text/html", "text/css", "text/plain", "text/javascript", "application/javascript",
              "application/json", "image/svg+xml", "application/xml"}


ICON_RE = re.compile(r'<link rel="icon" href="([^"?]+)')
COMPRESSIBLE = (".css", ".js", ".svg", ".json", ".txt", ".xml", ".html")


@web.middleware
async def compression_middleware(request: web.Request, handler):
    """Gzip pages, CSS, JS, SVG and API answers; images and fonts are already compressed."""
    resp = await handler(request)
    if ("gzip" in request.headers.get("Accept-Encoding", "") and isinstance(resp, web.StreamResponse)
            and not resp.prepared and "Content-Encoding" not in resp.headers):
        if isinstance(resp, web.FileResponse):
            if request.path.endswith(COMPRESSIBLE):
                resp.enable_compression()
        elif resp.status == 200 and resp.content_type in TEXT_TYPES:
            resp.enable_compression()
    return resp


async def _cache_headers(request: web.Request, response: web.StreamResponse) -> None:
    """Caching and compression for every response.

    CSS/JS links carry ?v=<content hash> (added by site/build.py), so browsers keep them for a year and still get
    a new file after every change. Frames, images, fonts and vendor files are cached for 30 days; anything else
    under /static/ is checked with the server each time.
    """
    path = request.path
    if path.startswith("/static/"):
        if "v" in request.query:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif path.startswith(("/static/seq/", "/static/img/", "/static/fonts/", "/static/vendor/")):
            response.headers["Cache-Control"] = "public, max-age=2592000"
        else:
            response.headers.setdefault("Cache-Control", "no-cache")


def create_app(assistant) -> web.Application:
    async def page(request: web.Request):
        return _html(request, PAGES[request.path])

    async def chat(request: web.Request):
        if request.method == "OPTIONS":
            return _cors(web.Response())
        error = _limited(_ip(request))
        if error:
            return _cors(web.json_response({"error": error}, status=429))
        try:
            data = await request.json()
        except Exception:
            return _cors(web.json_response({"error": "bad request"}, status=400))
        session, message = str(data.get("session", "")), str(data.get("message", ""))
        if not SESSION_RE.match(session) or not message.strip():
            return _cors(web.json_response({"error": "bad request"}, status=400))
        if len(message) > MAX_MESSAGE:
            return _cors(web.json_response({"error": "Please keep messages under 2,000 characters."}, status=400))
        reply = await assistant.reply(f"web:{session}", message)
        return _cors(web.json_response({"reply": reply}))

    async def contact(request: web.Request):
        """Booking form: validates, saves an appointment request and notifies the clinic like the AI does."""
        if request.method == "OPTIONS":
            return _cors(web.Response())
        is_json = request.content_type == "application/json"

        def answer(ok: bool, message: str, field: str | None = None, status: int = 200):
            if not is_json:  # plain HTML form post (JavaScript off): back to the page with a notice
                query = "sent=1" if ok else "error=" + quote(message)
                return web.Response(status=303, headers={"Location": f"/contact?{query}#book"})
            body = {"ok": True, "message": message} if ok else {"ok": False, "error": message, "field": field}
            return _cors(web.json_response(body, status=status))

        if _form_limited(_ip(request)):
            return answer(False, f"Too many requests from your network. Please call us on {settings.clinic_phone}.",
                          status=429)
        try:
            raw = await request.json() if is_json else await request.post()
            data = {k: str(v).strip() for k, v in raw.items() if isinstance(v, (str, int, float, bool))}
        except Exception:
            return answer(False, "The request couldn't be read. Please try again.", status=400)

        # bots: the hidden "company" field is only filled in by scripts, and people don't submit in under 2.5 s
        elapsed = data.get("elapsed", "")
        if data.get("company") or (elapsed.isdigit() and int(elapsed) < 2500):
            log.info("booking form: ignored a bot submission")
            return answer(True, "Request sent.")

        name, phone, email = data.get("name", ""), data.get("phone", ""), data.get("email", "")
        treatment = data.get("treatment", "")
        if not 2 <= len(name) <= 80:
            return answer(False, "Enter your name.", "name", 400)
        if not PHONE_RE.match(phone) or not 7 <= len(re.sub(r"\D", "", phone)) <= 15:
            return answer(False, "Enter a phone number we can call, for example 07911 123456.", "phone", 400)
        if email and (len(email) > 120 or not EMAIL_RE.match(email)):
            return answer(False, "Enter a valid email address, or leave it empty.", "email", 400)
        if not treatment or len(treatment) > 80:
            return answer(False, "Choose what the visit is for.", "treatment", 400)
        if data.get("consent", "").lower() not in YES:
            return answer(False, "Tick the box so we can contact you about this request.", "consent", 400)

        notes = data.get("notes", "")[:1000]
        if data.get("new_patient", "").lower() in YES:
            notes = f"New patient. {notes}".strip()
        lead = {"name": name, "phone": phone, "email": email or None, "treatment": treatment,
                "preferred_time": data.get("preferred_time", "")[:120] or None, "notes": notes or None}
        lead_id = await store.add_lead(f"form:{secrets.token_hex(4)}", "appointment", lead)
        if assistant.on_lead:
            try:
                await assistant.on_lead(lead_id, "appointment", lead)
            except Exception as e:  # the request is saved even if Telegram is down
                log.warning("lead notification failed: %s", e)
        first = name.split()[0]
        return answer(True, f"Request sent. Thanks, {first}: reception will call you on {phone} to confirm, "
                            "usually within 2 working hours.")

    async def robots(request: web.Request):
        if settings.site_noindex:
            body = "User-agent: *\nDisallow: /\n"
        else:
            body = f"User-agent: *\nDisallow: /api/\nSitemap: {_origin(request)}/sitemap.xml\n"
        return web.Response(text=body, content_type="text/plain")

    async def sitemap(request: web.Request):
        origin = _origin(request)
        urls = "".join(f"<url><loc>{origin}{p}</loc></url>" for p in SITEMAP)
        return web.Response(content_type="application/xml",
                            text='<?xml version="1.0" encoding="UTF-8"?>\n'
                                 f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')

    async def health(request):
        return web.json_response({"ok": True})

    async def favicon(request):
        # the icon of the current design, as linked from the home page (a temporary redirect: designs can change)
        m = ICON_RE.search(_read("index.html"))
        raise web.HTTPFound(m.group(1) if m else "/static/img/favicon.svg")

    app = web.Application(client_max_size=64 * 1024, middlewares=[compression_middleware, pages_middleware])
    for path in PAGES:
        app.router.add_get(path, page)
    app.router.add_get("/health", health)
    app.router.add_get("/robots.txt", robots)
    app.router.add_get("/sitemap.xml", sitemap)
    app.router.add_get("/favicon.ico", favicon)
    app.router.add_route("*", "/api/chat", chat)
    app.router.add_route("*", "/api/contact", contact)
    app.router.add_static("/static", WEBAPP)
    app.on_response_prepare.append(_cache_headers)
    return app
