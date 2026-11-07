"""Local business lead generator.

1. Pulls businesses of one niche in one area from OpenStreetMap (Overpass API).
2. Cleans and de-duplicates them, separates chains from independents.
3. Visits each business website to find a contact e-mail, social links
   and the online booking system they use.
4. Checks that e-mail domains can receive mail (MX record).
5. Writes a formatted Excel report, a CSV and a masked sample for sharing.

Data: © OpenStreetMap contributors, available under the Open Database License (ODbL).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import ssl
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import aiohttp

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
USER_AGENT = "LeadResearchBot/1.0 (business contact research; respects robots.txt)"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}")
JUNK_EMAIL = re.compile(
    r"(example\.|sentry|wixpress|godaddy|domain\.com|email\.com|yourdomain|\.png|\.jpg|\.jpeg|\.gif|\.webp|\.svg"
    r"|@2x|noreply|no-reply|donotreply|privacy@|abuse@|webmaster@|yoursite|yourwebsite|yourcompany|website\.com"
    r"|mysite|sample|test@|user@|name@|john@|jane@|filler@)", re.I)
BOOKING_SYSTEMS = {
    "Fresha": ["fresha.com"],
    "Booksy": ["booksy.com"],
    "Treatwell": ["treatwell.co.uk", "treatwell.com"],
    "Setmore": ["setmore.com"],
    "Square Appointments": ["squareup.com/appointments", "square.site", "book.squareup.com"],
    "Phorest": ["phorest.com"],
    "Timely": ["gettimely.com"],
    "Shedul / Other": ["shedul.com"],
    "SimplyBook": ["simplybook.me", "simplybook.it"],
    "Calendly": ["calendly.com"],
    "Vagaro": ["vagaro.com"],
    "Squire": ["getsquire.com"],
}
CONTACT_HINTS = ("contact", "about", "book", "find-us", "visit", "location")


@dataclass
class Lead:
    name: str
    address: str = ""
    postcode: str = ""
    phone: str = ""
    website: str = ""
    email: str = ""
    email_source: str = ""      # osm | website
    email_status: str = ""      # mx_ok | no_mx | unchecked
    instagram: str = ""
    facebook: str = ""
    booking_system: str = ""
    opening_hours: str = ""
    osm_url: str = ""
    lat: float | None = None
    lon: float | None = None
    website_status: str = ""    # ok | unreachable | none
    notes: str = ""
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------- OSM
def build_query(cfg: dict) -> str:
    area = cfg["area_name"]
    filters = "\n".join(f"  nwr(area.a){f};" for f in cfg["osm_filters"])
    return (
        f'[out:json][timeout:{cfg.get("overpass_timeout", 180)}];\n'
        f'area["name"="{area}"]["boundary"="administrative"]->.a;\n'
        f"(\n{filters}\n);\nout center tags;"
    )


async def fetch_osm(session: aiohttp.ClientSession, query: str) -> list[dict]:
    errors = []
    for url in OVERPASS_URLS:
        try:
            async with session.post(url, data={"data": query}, timeout=aiohttp.ClientTimeout(total=240)) as r:
                if r.status == 200:
                    return (await r.json(content_type=None)).get("elements", [])
                errors.append(f"{url} -> HTTP {r.status}")
        except Exception as e:  # try the mirror
            errors.append(f"{url} -> {e}")
    raise RuntimeError("OpenStreetMap request failed:\n  " + "\n  ".join(errors))


def norm_phone(raw: str, country_code: str = "44") -> str:
    if not raw:
        return ""
    raw = raw.split(";")[0]
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    elif digits.startswith("0"):
        digits = f"+{country_code}" + digits[1:]
    elif not digits.startswith("+"):
        digits = "+" + digits
    d = digits[1:]
    if d.startswith("44") and len(d) == 12:  # +44 20 7946 0123 / +44 7911 123456
        rest = d[2:]
        if rest.startswith("20"):
            return f"+44 20 {rest[2:6]} {rest[6:]}"
        return f"+44 {rest[:4]} {rest[4:]}"
    return digits


def norm_url(raw: str) -> str:
    if not raw:
        return ""
    raw = raw.strip().split(";")[0].split(" ")[0]
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    p = urlparse(raw)
    if not p.netloc or "." not in p.netloc:
        return ""
    return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")


def social(tags: dict, key: str, base: str) -> str:
    v = tags.get(f"contact:{key}") or tags.get(key) or ""
    if not v:
        return ""
    if v.startswith("http"):
        return v
    return base + v.lstrip("@")


def element_to_lead(el: dict, country_code: str) -> Lead | None:
    tags = el.get("tags", {})
    name = (tags.get("name") or "").strip()
    if not name:
        return None
    street = " ".join(x for x in [tags.get("addr:housenumber", ""), tags.get("addr:street", "")] if x)
    city = tags.get("addr:city", "")
    postcode = tags.get("addr:postcode", "")
    address = ", ".join(x for x in [street, city, postcode] if x)
    lat = el.get("lat") or (el.get("center") or {}).get("lat")
    lon = el.get("lon") or (el.get("center") or {}).get("lon")
    email = (tags.get("email") or tags.get("contact:email") or "").split(";")[0].strip()
    return Lead(
        name=name,
        address=address,
        postcode=postcode.upper(),
        phone=norm_phone(tags.get("phone") or tags.get("contact:phone") or "", country_code),
        website=norm_url(tags.get("website") or tags.get("contact:website") or tags.get("url") or ""),
        email=email.lower(),
        email_source="osm" if email else "",
        instagram=social(tags, "instagram", "https://instagram.com/"),
        facebook=social(tags, "facebook", "https://facebook.com/"),
        opening_hours=tags.get("opening_hours", ""),
        osm_url=f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
        lat=lat,
        lon=lon,
    )


# ---------------------------------------------------------------- cleaning
def norm_name(s: str) -> str:
    s = s.lower().replace("&", "and")
    s = re.sub(r"\b(the|ltd|limited|barbers?|barbershop|london)\b", " ", s)
    return re.sub(r"[^a-z0-9]", "", s)


def domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def dedupe(leads: list[Lead]) -> tuple[list[Lead], int]:
    """Same website domain, same phone, or same name+postcode = same business.
    Keeps the record with the most filled fields."""
    def score(l: Lead) -> int:
        return sum(bool(getattr(l, f)) for f in ("address", "phone", "website", "email", "opening_hours"))

    groups: list[list[Lead]] = []
    index: dict[str, int] = {}
    for lead in leads:
        keys = [k for k in (
            f"d:{domain(lead.website)}" if lead.website and not is_platform(lead.website) else "",
            f"p:{lead.phone}" if lead.phone else "",
            f"n:{norm_name(lead.name)}:{lead.postcode.replace(' ', '')}" if lead.postcode else "",
        ) if k]
        hit = next((index[k] for k in keys if k in index), None)
        if hit is None:
            groups.append([lead])
            hit = len(groups) - 1
        else:
            groups[hit].append(lead)
        for k in keys:
            index.setdefault(k, hit)
    kept = [max(g, key=score) for g in groups]
    for g, best in zip(groups, kept):  # fill gaps from duplicates
        for other in g:
            for f in ("phone", "website", "email", "instagram", "facebook", "opening_hours", "address", "postcode"):
                if not getattr(best, f) and getattr(other, f):
                    setattr(best, f, getattr(other, f))
    return kept, len(leads) - len(kept)


def is_platform(url: str) -> bool:
    d = domain(url)
    return any(d.endswith(x) for x in ("facebook.com", "instagram.com", "linktr.ee", "google.com", "goo.gl")) or \
        any(p in url for ps in BOOKING_SYSTEMS.values() for p in ps)


def split_chains(leads: list[Lead], chains: list[str]) -> tuple[list[Lead], list[Lead]]:
    pats = [c.lower() for c in chains]
    independent, excluded = [], []
    for l in leads:
        hit = next((c for c in pats if c in l.name.lower()), None)
        if hit:
            l.notes = f"chain: {hit}"
            excluded.append(l)
        else:
            independent.append(l)
    return independent, excluded


# ---------------------------------------------------------------- website enrichment
def extract_emails(html: str, site_domain: str = "") -> list[str]:
    found = set(m.group(0).lower().strip(".") for m in EMAIL_RE.finditer(html))
    found |= {unquote(m).lower().strip() for m in re.findall(r"mailto:([^\"'?>\s]+)", html, re.I)}
    clean = [e for e in found
             if EMAIL_RE.fullmatch(e) and not JUNK_EMAIL.search(e) and len(e) < 80]
    # same-domain addresses first, then generic inboxes
    def rank(e: str):
        d = e.split("@")[1]
        return (0 if site_domain and d.endswith(site_domain) else 1,
                0 if e.split("@")[0] in ("info", "hello", "contact", "bookings", "booking", "enquiries") else 1, e)
    return sorted(set(clean), key=rank)


def _best_handle(handles: list[str], name: str) -> str:
    """Pick the social handle that looks most like the business (themes often link their own pages)."""
    if not handles:
        return ""
    words = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if len(w) > 2 and w not in ("the", "and", "barber", "barbers")]
    def score(h: str) -> int:
        hl = h.lower()
        return sum(w in hl for w in words)
    best = max(handles, key=lambda h: (score(h), -handles.index(h)))
    return best


def extract_socials(html: str, name: str = "") -> tuple[str, str]:
    bad = {"sharer", "share", "p", "reel", "reels", "explore", "tr", "plugins", "dialog", "2008", "profile.php",
           "profile", "watch", "events", "groups", "pages", "people", "hashtag", "accounts", "stories"}
    igs = [h for h in dict.fromkeys(re.findall(r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?", html))
           if h.lower() not in bad]
    fbs = [h for h in dict.fromkeys(re.findall(r"https?://(?:www\.)?facebook\.com/([A-Za-z0-9_.\-]+)/?", html))
           if h.lower() not in bad and not h.isdigit()]
    ig, fb = _best_handle(igs, name), _best_handle(fbs, name)
    return (f"https://instagram.com/{ig}" if ig else ""), (f"https://facebook.com/{fb}" if fb else "")


def detect_booking(html: str, url: str = "") -> str:
    text = (html + " " + url).lower()
    return ", ".join(name for name, pats in BOOKING_SYSTEMS.items() if any(p in text for p in pats))


def contact_links(html: str, base: str) -> list[str]:
    links = re.findall(r'href=["\']([^"\'#]+)["\']', html, re.I)
    out = []
    for href in links:
        full = urljoin(base + "/", href)
        if domain(full) == domain(base) and any(h in full.lower() for h in CONTACT_HINTS):
            if full not in out:
                out.append(full)
    return out[:3]


async def get_text(session: aiohttp.ClientSession, url: str, timeout: int) -> tuple[str, str]:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=True,
                           ssl=False) as r:
        if r.status >= 400:
            raise aiohttp.ClientResponseError(r.request_info, (), status=r.status)
        ctype = r.headers.get("content-type", "")
        if "html" not in ctype and "text" not in ctype:
            return "", str(r.url)
        return (await r.text(errors="ignore"))[:600_000], str(r.url)


async def enrich(session: aiohttp.ClientSession, lead: Lead, timeout: int) -> None:
    if not lead.website:
        lead.website_status = "none"
        return
    if is_platform(lead.website):
        lead.booking_system = lead.booking_system or detect_booking("", lead.website)
        if "instagram.com" in lead.website and not lead.instagram:
            lead.instagram = lead.website
        if "facebook.com" in lead.website and not lead.facebook:
            lead.facebook = lead.website
        lead.website_status = "social/booking page"
        return
    try:
        html, final = await get_text(session, lead.website, timeout)
    except Exception:
        lead.website_status = "unreachable"
        return
    lead.website_status = "ok"
    pages = [html]
    for link in contact_links(html, final):
        try:
            pages.append((await get_text(session, link, timeout))[0])
        except Exception:
            pass
    allhtml = "\n".join(pages)
    if not lead.email:
        emails = extract_emails(allhtml, domain(final))
        if emails:
            lead.email, lead.email_source = emails[0], "website"
            if len(emails) > 1:
                lead.extra["other_emails"] = ", ".join(emails[1:4])
    ig, fb = extract_socials(allhtml, lead.name)
    lead.instagram = lead.instagram or ig
    lead.facebook = lead.facebook or fb
    lead.booking_system = detect_booking(allhtml, final)


def check_mx(domains: set[str]) -> dict[str, bool]:
    try:
        import dns.resolver
    except ImportError:
        return {}
    result = {}
    res = dns.resolver.Resolver()
    res.lifetime = 5
    for d in domains:
        try:
            result[d] = bool(res.resolve(d, "MX"))
        except Exception:
            try:  # some domains accept mail on the A record
                result[d] = bool(res.resolve(d, "A"))
            except Exception:
                result[d] = False
    return result


# ---------------------------------------------------------------- output
COLUMNS = [
    ("Business name", "name", 30), ("Address", "address", 38), ("Postcode", "postcode", 10),
    ("Phone", "phone", 17), ("Website", "website", 30), ("Email", "email", 30),
    ("Email check", "email_status", 11), ("Instagram", "instagram", 28), ("Facebook", "facebook", 28),
    ("Online booking", "booking_system", 18), ("Opening hours", "opening_hours", 28),
    ("Website status", "website_status", 14), ("Map link", "osm_url", 22), ("Lat", "lat", 9), ("Lon", "lon", 9),
]


def mask_phone(p: str) -> str:
    digits = [i for i, c in enumerate(p) if c.isdigit()]
    keep = set(digits[:4] + digits[-2:])
    return "".join(c if (not c.isdigit() or i in keep) else "•" for i, c in enumerate(p))


def mask_email(e: str) -> str:
    if "@" not in e:
        return e
    local, dom = e.split("@", 1)
    parts = dom.split(".")
    return f"{local[0]}•••@{parts[0][0]}•••." + ".".join(parts[1:])


def write_excel(path: Path, leads: list[Lead], excluded: list[Lead], stats: dict, masked: bool = False) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    head_fill = PatternFill("solid", fgColor="1F4D3A")
    head_font = Font(bold=True, color="FFFFFF")

    def sheet(ws, rows: list[Lead], extra_col: str | None = None):
        cols = COLUMNS + ([("Reason", "notes", 20)] if extra_col else [])
        ws.append([c[0] for c in cols])
        for cell in ws[1]:
            cell.fill, cell.font = head_fill, head_font
            cell.alignment = Alignment(vertical="center")
        ws.row_dimensions[1].height = 22
        for l in rows:
            vals = []
            for _, attr, _w in cols:
                v = getattr(l, attr)
                if masked and attr == "phone":
                    v = mask_phone(v)
                if masked and attr == "email":
                    v = mask_email(v)
                vals.append(v if v is not None else "")
            ws.append(vals)
            r = ws.max_row
            for ci, (_, attr, _w) in enumerate(cols, 1):
                v = getattr(l, attr)
                if attr in ("website", "instagram", "facebook", "osm_url") and v and not masked:
                    ws.cell(r, ci).hyperlink = v
                    ws.cell(r, ci).font = Font(color="1F4D8C", underline="single")
        for i, (_, _a, w) in enumerate(cols, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = ws.dimensions

    ws = wb.active
    ws.title = "Leads"
    sheet(ws, leads)
    contacts = [l for l in leads if l.phone or l.website or l.email]
    if contacts and not masked:
        sheet(wb.create_sheet("With contacts"), contacts)

    s = wb.create_sheet("Summary")
    s.column_dimensions["A"].width = 38
    s.column_dimensions["B"].width = 16
    s.append(["Report", stats["title"]])
    s["A1"].font = Font(bold=True, size=14)
    s["B1"].font = Font(bold=True, size=14)
    s.append([])
    for k, v in stats["rows"]:
        s.append([k, v])
    s.append([])
    s.append(["Online booking systems in use", ""])
    s.cell(s.max_row, 1).font = Font(bold=True)
    for name, n in stats["booking"]:
        s.append([name, n])
    s.append([])
    s.append(["Source", "© OpenStreetMap contributors (ODbL) + business websites"])
    s.append(["Generated", time.strftime("%Y-%m-%d %H:%M")])
    if masked:
        s.append(["Note", "Sample with masked contacts. Full contacts in the client version."])

    if excluded:
        sheet(wb.create_sheet("Excluded (chains)"), excluded, extra_col="notes")
    wb.save(path)


def write_csv(path: Path, leads: list[Lead]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([c[0] for c in COLUMNS])
        for l in leads:
            w.writerow([getattr(l, c[1]) if getattr(l, c[1]) is not None else "" for c in COLUMNS])


# ---------------------------------------------------------------- main
async def run(cfg: dict, osm_file: str | None = None) -> dict:
    t0 = time.time()
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-GB,en;q=0.8"}
    out_dir = Path(cfg.get("output_dir", "output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    try:  # use certifi's CA bundle so a fresh macOS Python install works out of the box
        import certifi
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ssl_ctx = ssl.create_default_context()
    connector = aiohttp.TCPConnector(ssl=ssl_ctx, limit=cfg.get("concurrency", 10) * 2)
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        if osm_file:
            elements = json.load(open(osm_file)).get("elements", [])
        else:
            print(f"→ Querying OpenStreetMap for {cfg['area_name']}…", flush=True)
            elements = await fetch_osm(session, build_query(cfg))
        raw = [l for l in (element_to_lead(e, cfg.get("country_code", "44")) for e in elements) if l]
        print(f"  found {len(raw)} named places", flush=True)

        leads, dupes = dedupe(raw)
        leads, excluded = split_chains(leads, cfg.get("exclude_chains", []))
        leads = leads[: cfg.get("max_places", 10_000)]
        print(f"  {dupes} duplicates removed, {len(excluded)} chain locations set aside, {len(leads)} independents",
              flush=True)

        if cfg.get("crawl_websites", True):
            todo = [l for l in leads if l.website]
            print(f"→ Visiting {len(todo)} websites for e-mails, socials and booking systems…", flush=True)
            sem = asyncio.Semaphore(cfg.get("concurrency", 10))
            done = 0

            async def one(lead: Lead):
                nonlocal done
                async with sem:
                    try:  # one odd website must never stop the whole run
                        await enrich(session, lead, cfg.get("timeout_sec", 12))
                    except Exception as e:
                        lead.website_status = lead.website_status or "error"
                        lead.notes = f"enrich error: {type(e).__name__}"
                done += 1
                if done % 10 == 0 or done == len(todo):
                    print(f"  {done}/{len(todo)}", flush=True)

            await asyncio.gather(*(one(l) for l in todo))
            for l in leads:
                if not l.website:
                    l.website_status = "none"

    domains = {l.email.split("@")[1] for l in leads if "@" in l.email}
    print(f"→ Checking {len(domains)} e-mail domains…", flush=True)
    mx = await asyncio.to_thread(check_mx, domains)
    for l in leads:
        if l.email:
            l.email_status = "unchecked" if not mx else ("mx_ok" if mx.get(l.email.split("@")[1]) else "no_mx")

    leads.sort(key=lambda l: (not l.email, not l.website, l.name.lower()))
    counts = {}
    for l in leads:
        for b in filter(None, (x.strip() for x in l.booking_system.split(","))):
            counts[b] = counts.get(b, 0) + 1
    stats = {
        "title": cfg.get("title", cfg["area_name"]),
        "rows": [
            ("Places found in OpenStreetMap", len(raw)),
            ("Duplicates removed", dupes),
            ("Chain locations excluded", len(excluded)),
            ("Independent businesses", len(leads)),
            ("With any contact (phone, website or e-mail)",
             sum(bool(l.phone or l.website or l.email) for l in leads)),
            ("With phone", sum(bool(l.phone) for l in leads)),
            ("With website", sum(bool(l.website) for l in leads)),
            ("With e-mail", sum(bool(l.email) for l in leads)),
            ("E-mail domain accepts mail", sum(l.email_status == "mx_ok" for l in leads)),
            ("With Instagram", sum(bool(l.instagram) for l in leads)),
            ("Using an online booking system", sum(bool(l.booking_system) for l in leads)),
            ("No online booking found (website checked)",
             sum(l.website_status == "ok" and not l.booking_system for l in leads)),
        ],
        "booking": sorted(counts.items(), key=lambda x: -x[1]),
    }
    base = out_dir / cfg.get("file_name", "leads")
    write_excel(base.with_suffix(".xlsx"), leads, excluded, stats)
    write_excel(Path(f"{base}_sample_masked.xlsx"), leads[:25], [], stats, masked=True)
    write_csv(base.with_suffix(".csv"), leads)
    print(f"\n✅ Done in {time.time() - t0:.0f}s → {base}.xlsx", flush=True)
    for k, v in stats["rows"]:
        print(f"   {k}: {v}")
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Local business lead generator (OpenStreetMap + websites)")
    ap.add_argument("config", nargs="?", default="config.json")
    ap.add_argument("--osm-file", help="use a saved Overpass JSON instead of querying (for testing)")
    ap.add_argument("--no-crawl", action="store_true", help="skip visiting websites")
    args = ap.parse_args()
    cfg = json.load(open(args.config))
    if args.no_crawl:
        cfg["crawl_websites"] = False
    try:
        asyncio.run(run(cfg, args.osm_file))
    except RuntimeError as e:
        sys.exit(f"\n❌ {e}\nCheck your internet connection and try again in a minute.")


if __name__ == "__main__":
    main()
