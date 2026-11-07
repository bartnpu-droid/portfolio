"""Builds the clinic website: site/pages/*.html + a design theme -> webapp/*.html

Each page starts with a JSON header in an HTML comment, for example:
    <!--{"title": "...", "description": "...", "path": "/implants", "sequence": true}-->

A theme (site/themes/<name>/) has its own layout.html, partials/ and, optionally, pages/ that replace
the shared ones (usually the home page). The chosen theme is remembered in site/THEME.

Run:  python site/build.py                 rebuild with the current theme
      python site/build.py --theme hive    switch the design (atelier = the dark original)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "site"
OUT = ROOT / "webapp"
THEMES = SRC / "themes"
THEME_FILE = SRC / "THEME"
DEFAULT_THEME = "atelier"

NAV = [("/treatments", "Treatments"), ("/implants", "Implants"), ("/team", "Team"),
       ("/patients", "For patients"), ("/contact", "Contact")]

SEQUENCE_SCRIPT = '<script type="module" src="/static/js/sequence.js"></script>'
HEADER_RE = re.compile(r"^\s*<!--(\{.*?\})-->\s*", re.S)
STATIC_REF = re.compile(r'(?P<attr>(?:src|href)=")(?P<url>/static/[^"?#]+\.(?:css|js))"')


def versioned(html: str) -> str:
    """/static/css/hive.css -> /static/css/hive.css?v=<content hash>: long browser caching, fresh after a change."""
    def add(m: re.Match) -> str:
        path = OUT / m.group("url").removeprefix("/static/")
        if not path.is_file():
            return m.group(0)
        digest = hashlib.sha1(path.read_bytes()).hexdigest()[:10]
        return f'{m.group("attr")}{m.group("url")}?v={digest}"'
    return STATIC_REF.sub(add, html)


def nav_html(path: str) -> str:
    links = []
    for href, label in NAV:
        current = ' aria-current="page"' if href == path else ""
        links.append(f'<a href="{href}"{current}>{label}</a>')
    return "\n      ".join(links)


def build_page(src: Path, layout: str, partials: dict[str, str]) -> str:
    text = src.read_text(encoding="utf-8")
    m = HEADER_RE.match(text)
    if not m:
        raise SystemExit(f"{src.name}: missing JSON header")
    meta = json.loads(m.group(1))
    content = text[m.end():]
    widget = f' data-target="{meta["chat_target"]}"' if meta.get("chat_target") else ""
    values = {
        "title": meta["title"],
        "description": meta["description"],
        "og_title": meta.get("og_title", meta["title"]),
        "path": meta["path"],
        "slug": src.stem,
        "nav": nav_html(meta["path"]),
        "head": meta.get("head", ""),
        "scripts": SEQUENCE_SCRIPT if meta.get("sequence") else "",
        "widget": widget,
        "robots": '<meta name="robots" content="noindex">' if meta.get("noindex") else "",
        "content": content.strip(),
        **partials,
    }
    html = layout
    # partials first (they may contain {{placeholders}} themselves), then the page values
    for _ in range(2):
        html = re.sub(r"\{\{(\w+)\}\}", lambda mm: values.get(mm.group(1), mm.group(0)), html)
    left = re.findall(r"\{\{\w+\}\}", html)
    if left:
        raise SystemExit(f"{src.name}: unknown placeholders {left}")
    return versioned(html)


def themes() -> list[str]:
    return sorted(p.name for p in THEMES.iterdir() if (p / "layout.html").is_file())


def current_theme() -> str:
    name = THEME_FILE.read_text(encoding="utf-8").strip() if THEME_FILE.is_file() else ""
    return name or DEFAULT_THEME


def build(out_dir: Path = OUT, theme: str | None = None) -> list[Path]:
    theme = theme or current_theme()
    folder = THEMES / theme
    if not (folder / "layout.html").is_file():
        raise SystemExit(f"unknown theme {theme!r}, available: {', '.join(themes())}")
    layout = (folder / "layout.html").read_text(encoding="utf-8")
    partials, pages = {}, {}
    for base in (SRC, folder):                      # theme files replace the shared ones
        partials.update({p.stem: p.read_text(encoding="utf-8").strip() for p in (base / "partials").glob("*.html")})
        pages.update({p.name: p for p in (base / "pages").glob("*.html")})
    written = []
    for name in sorted(pages):
        out = out_dir / name
        out.write_text(build_page(pages[name], layout, partials) + "\n", encoding="utf-8")
        written.append(out)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the clinic website into webapp/.")
    parser.add_argument("--theme", choices=themes(), help="switch the design; the choice is remembered")
    args = parser.parse_args()
    if args.theme:
        THEME_FILE.write_text(args.theme + "\n", encoding="utf-8")
    theme = current_theme()
    for out in build(theme=theme):
        print(f"built {out.relative_to(ROOT)}")
    print(f"theme: {theme}")


if __name__ == "__main__":
    main()
