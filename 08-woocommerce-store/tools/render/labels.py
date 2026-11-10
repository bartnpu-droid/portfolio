"""Label artwork for the Ombra product renders (PIL), printed onto the 3D packaging in Blender."""
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONTS = Path(os.environ.get("OMBRA_FONTS", Path(__file__).resolve().parent / "fonts"))
PX_PER_M = 20000  # label texture resolution: 2 px per 0.1 mm

PAPER = (243, 237, 227)
INK = (38, 33, 29)
EMBER = (164, 83, 46)
KRAFT = (196, 160, 118)

SCENTS = {
    "fig": {"name": "Fig & Cedar", "no": "01"},
    "salt": {"name": "Sea Salt & Sage", "no": "02"},
    "amber": {"name": "Amber & Smoke", "no": "03"},
}


def font(family: str, size: int, wght: int = 400, opsz: float | None = None, italic: bool = False):
    files = {
        "serif": "Fraunces-Italic[SOFT,WONK,opsz,wght].ttf" if italic else "Fraunces[SOFT,WONK,opsz,wght].ttf",
        "sans": "InstrumentSans-Italic[wdth,wght].ttf" if italic else "InstrumentSans[wdth,wght].ttf",
    }
    f = ImageFont.truetype(str(FONTS / files[family]), size)
    values = []
    for axis in f.get_variation_axes():
        tag = axis["name"].lower() if isinstance(axis["name"], str) else axis["name"].decode().lower()
        if "optical" in tag:
            values.append(opsz if opsz is not None else min(144, max(9, size / 4)))
        elif "weight" in tag:
            values.append(wght)
        elif "soft" in tag:
            values.append(30)
        elif "wonk" in tag:
            values.append(0)
        elif "width" in tag:
            values.append(100)
        else:
            values.append(axis["default"])
    f.set_variation_by_axes(values)
    return f


def tracked(draw: ImageDraw.ImageDraw, cx: float, y: float, text: str, f, fill, tracking: float = 0.0):
    """Draw text centred on cx with extra letter spacing (tracking as a fraction of the font size)."""
    size = f.size
    widths = [draw.textlength(ch, font=f) for ch in text]
    gap = tracking * size
    total = sum(widths) + gap * (len(text) - 1)
    x = cx - total / 2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=f, fill=fill)
        x += w + gap
    return total


def centered(draw, cx, y, text, f, fill):
    w = draw.textlength(text, font=f)
    draw.text((cx - w / 2, y), text, font=f, fill=fill)
    return w


def paper(w: int, h: int, color=PAPER, grain: float = 5.0, seed: int = 1) -> Image.Image:
    rng = np.random.default_rng(seed)
    base = np.ones((h, w, 3), np.float32) * np.array(color, np.float32)
    noise = rng.normal(0, grain, (h, w, 1)).astype(np.float32)
    fibres = rng.normal(0, grain * 0.25, (h, 1, 1)).astype(np.float32)  # faint horizontal fibres
    img = np.clip(base + noise + fibres, 0, 255).astype(np.uint8)
    return Image.fromarray(img, "RGB")


def jar_label(scent: str, weight: str, w_m: float, h_m: float, path: Path):
    """Wrapped band label for the glass jar candles."""
    W, H = int(w_m * PX_PER_M), int(h_m * PX_PER_M)
    img = paper(W, H)
    d = ImageDraw.Draw(img)
    cx = W / 2
    s = SCENTS[scent]
    u = H / 100  # 1 % of the label height
    tracked(d, cx, 11 * u, "OMBRA", font("serif", int(13 * u), 500, opsz=72), INK, 0.42)
    d.line([(cx - 9 * u, 31 * u), (cx + 9 * u, 31 * u)], fill=INK, width=max(2, int(0.45 * u)))
    centered(d, cx, 36 * u, s["name"], font("serif", int(15 * u), 460, opsz=48, italic=True), INK)
    tracked(d, cx, 60 * u, "HAND-POURED CANDLE", font("sans", int(5.6 * u), 620), INK, 0.22)
    d.ellipse([cx - 1.1 * u, 73 * u - 1.1 * u, cx + 1.1 * u, 73 * u + 1.1 * u], fill=EMBER)
    tracked(d, cx, 79 * u, f"NO. {s['no']}  ·  {weight}", font("sans", int(5.2 * u), 560), INK, 0.16)
    img.save(path)


def band_label(lines: list[tuple], w_m: float, h_m: float, path: Path, color=PAPER, ink=INK, striker: bool = False):
    """Generic front label: lines are (kind, text, y %, size %, extra)."""
    W, H = int(w_m * PX_PER_M), int(h_m * PX_PER_M)
    img = paper(W, H, color)
    d = ImageDraw.Draw(img)
    cx = W / 2
    u = H / 100
    for kind, text, y, size, extra in lines:
        if kind == "mark":
            tracked(d, cx, y * u, text, font("serif", int(size * u), 500, opsz=72), ink, 0.42)
        elif kind == "italic":
            centered(d, cx, y * u, text, font("serif", int(size * u), 460, opsz=48, italic=True), ink)
        elif kind == "caps":
            tracked(d, cx, y * u, text, font("sans", int(size * u), 620), ink, extra or 0.2)
        elif kind == "rule":
            d.line([(cx - size * u, y * u), (cx + size * u, y * u)], fill=ink, width=max(2, int(0.45 * u)))
        elif kind == "dot":
            d.ellipse([cx - size * u, y * u - size * u, cx + size * u, y * u + size * u], fill=EMBER)
    if striker:
        rng = np.random.default_rng(7)
        top = int(H * 0.8)
        grit = rng.normal(0, 14, (H - top, W, 1))
        strip = np.clip(np.array([62, 52, 47], np.float32) + grit, 0, 255).astype(np.uint8)
        img.paste(Image.fromarray(strip, "RGB"), (0, top))
    img.save(path)


def round_label(lines: list[tuple], d_m: float, path: Path, color=PAPER, ink=INK):
    """Round label for the tin lids: the square image is mapped onto a disc."""
    S = int(d_m * PX_PER_M)
    img = paper(S, S, color)
    d = ImageDraw.Draw(img)
    u = S / 100
    d.ellipse([3 * u, 3 * u, 97 * u, 97 * u], outline=ink, width=max(2, int(0.35 * u)))
    cx = S / 2
    for kind, text, y, size, extra in lines:
        if kind == "mark":
            tracked(d, cx, y * u, text, font("serif", int(size * u), 500, opsz=72), ink, 0.42)
        elif kind == "italic":
            centered(d, cx, y * u, text, font("serif", int(size * u), 460, opsz=48, italic=True), ink)
        elif kind == "caps":
            tracked(d, cx, y * u, text, font("sans", int(size * u), 620), ink, extra or 0.2)
        elif kind == "dot":
            d.ellipse([cx - size * u, y * u - size * u, cx + size * u, y * u + size * u], fill=EMBER)
    img.save(path)


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "labels"
    out.mkdir(exist_ok=True)
    jar_label("fig", "200 G / 7 OZ", 0.072, 0.050, out / "jar-fig.png")
    print("ok")
