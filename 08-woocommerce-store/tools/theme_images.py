"""Theme images (hero, story, category tiles, scent cards) cut from the Blender renders.

python3 tools/theme_images.py <renders folder> <theme>/assets/images
"""
import sys
from pathlib import Path

from PIL import Image

src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)


def save(img, name: str, size: tuple[int, int], quality: int = 82):
    if img is None:
        print("skip", name, "(render missing)")
        return
    img = img.convert("RGB")
    w, h = img.size
    tw, th = size
    scale = max(tw / w, th / h)
    img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    w, h = img.size
    left, top = (w - tw) // 2, (h - th) // 2
    img.crop((left, top, left + tw, top + th)).save(out / name, quality=quality, optimize=True, progressive=True)
    print(name, (out / name).stat().st_size // 1024, "KB")


def crop_frac(img, aspect: float, cx: float = 0.5):
    """Crop to an aspect ratio (w/h) around a horizontal centre given as a fraction."""
    if img is None:
        return None
    w, h = img.size
    if w / h > aspect:
        nw = round(h * aspect)
        left = min(max(0, round(cx * w - nw / 2)), w - nw)
        return img.crop((left, 0, left + nw, h))
    nh = round(w / aspect)
    return img.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))


def load(name):
    path = src / name
    return Image.open(path) if path.exists() else None


save(load("hero-wide.jpg"), "hero.jpg", (1920, 1080), 84)
save(load("story.jpg"), "story.jpg", (960, 1200))
tiles = {
    "cat-candles.jpg": ("jar-fig-200.jpg", 0.47),
    "cat-diffusers.jpg": ("diffuser-fig.jpg", 0.5),
    "cat-accessories.jpg": ("matches.jpg", 0.49),
    "cat-gifts.jpg": ("giftset.jpg", 0.5),
}
for name, (file, cx) in tiles.items():
    save(crop_frac(load(file), 4 / 5, cx), name, (720, 900))
def zoom(img, frac, cy=0.5):
    """Square crop of a fraction of the image, centred horizontally, at height cy."""
    if img is None:
        return None
    w, h = img.size
    s = round(min(w, h) * frac)
    top = min(max(0, round(cy * h - s / 2)), h - s)
    return img.crop(((w - s) // 2, top, (w - s) // 2 + s, top + s))


for key in ("fig", "salt", "amber"):
    save(zoom(load(f"jar-{key}-200-lit.jpg"), 0.7, 0.5), f"scent-{key}.jpg", (800, 800))
