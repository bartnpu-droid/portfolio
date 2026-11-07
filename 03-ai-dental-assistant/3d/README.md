# 3D implant: built and rendered in Blender with Python

Everything in the site's implant images comes from `implant_scene.py`: no downloaded models.

- **Crown**: a lower first molar with five cusps, fissures, marginal ridges and an emergence profile;
  porcelain shader with subsurface scattering, glaze coat and a technician's fissure stain
- **Abutment**: gold-coloured titanium nitride, hex connection, anti-rotation flat, screw channel
- **Implant**: titanium with a real thread profile (0.8 mm pitch), cutting flutes, polished collar, internal hex
- **Lighting**: studio softboxes + strip rim lights; Cycles, AgX colour, transparent background

Sequences used on the site:

| Sequence | Frames | Used for |
|---|---|---|
| `hero` | 61 (−30° … +30°) | home page: turns with the cursor or a finger |
| `explode` | 72 | home and implants page: comes apart as you scroll |

## Render

```bash
# any machine with the `bpy` module (CPU):
pip install bpy
python implant_scene.py --out still.png --res 1200x1500 --samples 96
python implant_scene.py --seq hero --frames 61 --out out/hero --res 1200x1500 --samples 80 --elev 23

# a Mac with Blender (GPU, Metal), 20–30x faster:
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P implant_scene.py -- \
    --seq explode --frames 72 --out out/explode --res 1200x1500 --samples 72 --elev 23 --gpu

# frames -> WebP for the website (1200 px and 600 px, with alpha)
python frames_to_webp.py out/hero hero ../webapp/seq/hero
```

`blender-worker.command` keeps Blender running on a Mac and renders job files dropped into `jobs/`.
