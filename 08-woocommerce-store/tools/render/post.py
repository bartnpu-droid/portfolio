"""Finishing for the renders: soft bloom around bright flames, light vignette, fine grain, JPEG."""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def finish(src: Path, dst: Path, bloom: float = 0.0, vignette: float = 0.12, grain: float = 1.6, quality: int = 90):
    img = Image.open(src).convert("RGB")
    a = np.asarray(img).astype(np.float32) / 255.0
    h, w, _ = a.shape
    if bloom > 0:
        lum = a.max(axis=2, keepdims=True)
        bright = np.clip((lum - 0.82) / 0.18, 0, 1) * a
        b_img = Image.fromarray((bright * 255).astype(np.uint8))
        glow = sum(np.asarray(b_img.filter(ImageFilter.GaussianBlur(r * w / 1000))).astype(np.float32) / 255.0 for r in (6, 18, 46))
        glow *= np.array([1.0, 0.78, 0.5], np.float32)  # warm halo
        a = 1 - (1 - a) * (1 - np.clip(glow * bloom, 0, 1))
    if vignette > 0:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
        a *= (1 - vignette * np.clip(d, 0, 1) ** 2.2)[..., None]
    if grain > 0:
        rng = np.random.default_rng(3)
        a += rng.normal(0, grain / 255.0, (h, w, 1)).astype(np.float32)
    out = Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))
    out.save(dst, quality=quality, optimize=True, progressive=True)


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    bloom = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    finish(src, dst, bloom)
