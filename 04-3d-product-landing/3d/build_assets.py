"""Turn the Blender renders (RGBA PNG) into the images the page loads (WebP on the colour of their section).

python3 build_assets.py <renders: .../out/tacet> <site/img>
"""
import json
import os
import shutil
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image

SRC, DST = sys.argv[1], sys.argv[2]
WHITE, BLACK = (255, 255, 255, 255), (0, 0, 0, 255)


def clean_alpha(im, floor=0.1, edge=0.06):
    """The shadow catcher leaves a faint tint over the whole floor: drop it, and fade what is left of the
    shadows towards the borders so the picture has no visible edge on the page. The product itself is untouched."""
    a = np.asarray(im, dtype=np.float32)
    al = a[..., 3] / 255.0
    al1 = np.clip((al - floor) / (1 - floor), 0, 1)
    h, w = al.shape
    sm = lambda t: np.clip(t, 0, 1) ** 2 * (3 - 2 * np.clip(t, 0, 1))  # noqa: E731
    x = np.linspace(0, 1, w)[None, :]
    y = np.linspace(0, 1, h)[:, None]
    m = sm(np.minimum(x, 1 - x) / edge) * sm(np.minimum(y, 1 - y) / edge)
    al2 = np.where(al1 > 0.97, al1, al1 * m)
    a[..., 3] = al2 * 255.0
    return Image.fromarray(a.round().astype(np.uint8), "RGBA")


def flat(path, bg, clean=True):
    im = Image.open(path).convert("RGBA")
    if clean and bg == WHITE:
        im = clean_alpha(im)
    base = Image.new("RGBA", im.size, bg)
    base.alpha_composite(im)
    return base.convert("RGB")


def save(im, path, size=None, q=80):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if size:
        im = im.resize(size, Image.LANCZOS)
    im.save(path, "WEBP", quality=q, method=6)


def look(job):
    """One turntable frame: 72 angles 5° apart (NN) and the 72 angles halfway between them (NNh)."""
    colour, i, half = job
    h = "h" if half else ""
    src = os.path.join(SRC, "look", colour, f"look_{colour}_{i:03d}{h}.png")
    if not os.path.exists(src):
        return f"missing {src}"
    im = flat(src, WHITE)
    save(im, os.path.join(DST, "look", "1200", f"{colour}-{i:02d}{h}.webp"), (1200, 1200), 78)
    save(im, os.path.join(DST, "look", "640", f"{colour}-{i:02d}{h}.webp"), (640, 640), 76)
    return None


VIEWS = {"front": 6, "three-quarter": 18, "side": 24}   # turntable frames (5° apart) used for the colour picker


def colors(job):
    """The colour picker: three rendered views of each colour, on white, in two sizes."""
    colour, view = job
    src = os.path.join(SRC, "look", colour, f"look_{colour}_{VIEWS[view]:03d}.png")
    if not os.path.exists(src):
        return f"missing {src}"
    im = flat(src, WHITE)
    save(im, os.path.join(DST, "colors", "1200", f"{colour}-{view}.webp"), (1200, 1200), 82)
    save(im, os.path.join(DST, "colors", "640", f"{colour}-{view}.webp"), (640, 640), 80)
    return None


def explode(i):
    src = os.path.join(SRC, "explode", f"explode_{i:03d}.png")
    if not os.path.exists(src):
        return f"missing {src}"
    im = flat(src, BLACK)
    save(im, os.path.join(DST, "explode", "1600", f"{i:02d}.webp"), (1600, 1000), 78)
    save(im, os.path.join(DST, "explode", "960", f"{i:02d}.webp"), (960, 600), 76)
    return None


def stills():
    hero = os.path.join(SRC, "hero", "hero2.png")
    if not os.path.exists(hero):
        hero = os.path.join(SRC, "hero", "hero.png")
    im = flat(hero, WHITE)
    im = im.crop((0, round(im.height * 0.105), im.width, round(im.height * 0.105) + round(im.width / 2.4)))
    save(im, os.path.join(DST, "hero-2400.webp"), (2400, 1000), 82)
    save(im, os.path.join(DST, "hero-1600.webp"), (1600, 667), 80)
    save(im, os.path.join(DST, "hero-1200.webp"), (1200, 500), 80)
    w = round(im.height * 1.91)
    og = im.crop(((im.width - w) // 2, 0, (im.width - w) // 2 + w, im.height)).resize((1200, 628), Image.LANCZOS)
    og.save(os.path.join(DST, "og.jpg"), quality=86, optimize=True, progressive=True)
    for name, out, bg in (("cushion2.png", "cushion.webp", WHITE), ("layers2.png", "layers.webp", BLACK)):
        src = os.path.join(SRC, "stills", name)
        if not os.path.exists(src):
            src = os.path.join(SRC, "stills", name.replace("2.png", ".png"))
        im = flat(src, bg)
        save(im, os.path.join(DST, out), None, 82)
        save(im, os.path.join(DST, out.replace(".webp", "-450.webp")), (450, round(450 * im.height / im.width)), 80)
    shutil.copy(os.path.join(SRC, "explode", "anchors.json"), os.path.join(DST, "explode", "anchors.json"))


if __name__ == "__main__":
    what = sys.argv[3] if len(sys.argv) > 3 else "all"   # all | look[:bone] | halves[:bone] | explode | stills | colors
    colours = what.split(":")[1].split(",") if ":" in what else ["bone", "obsidian", "moss"]
    what = what.split(":")[0]
    os.makedirs(os.path.join(DST, "explode"), exist_ok=True)
    with Pool(4) as pool:
        if what == "colors":                               # three still views per colour (alternative picker)
            print("colors", [m for m in pool.map(colors, [(c, v) for c in colours for v in VIEWS]) if m][:5])
        if what in ("all", "look", "halves"):              # the 360° frames: NN every 5°, NNh halfway between
            halves = (True,) if what == "halves" else (False, True)
            jobs = [(c, i, h) for c in colours for i in range(72) for h in halves]
            print("look", [m for m in pool.map(look, jobs) if m][:5])
        if what in ("all", "explode"):
            print("explode", [m for m in pool.map(explode, range(60)) if m][:5])
    if what in ("all", "stills"):
        stills()
        print("stills ok")
    print(json.dumps({"files": sum(len(f) for _, _, f in os.walk(DST))}))
