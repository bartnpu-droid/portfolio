"""PNG frames rendered in Blender -> WebP sequences for the site (1200 px and 600 px wide, with alpha)."""
import sys
from pathlib import Path

from PIL import Image

src, name, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
frames = sorted(src.glob(f"{name}_*.png"))
for size in (1200, 600):
    (out / str(size)).mkdir(parents=True, exist_ok=True)
total = 0
for f in frames:
    im = Image.open(f).convert("RGBA")
    for size in (1200, 600):
        frame = im if im.width == size else im.resize((size, round(im.height * size / im.width)), Image.LANCZOS)
        dst = out / str(size) / (f.stem + ".webp")
        frame.save(dst, "WEBP", quality=78 if size == 1200 else 76, alpha_quality=80, method=6)
        total += dst.stat().st_size
print(f"{len(frames)} frames -> {total / 1e6:.1f} MB")
