# Product photos in Blender

Every product photo, the hero and the "lit" shots of the Ombra store are rendered from code: no photo stock, no hand-modelled files.

- `studio.py` builds each scene with Blender's Python API: the packaging is turned from profiles (glass jars, a brushed tin, a terracotta bowl, a reed diffuser, a spray bottle, a match jar, a gift box), with materials for glass, wax with subsurface scattering, brushed metal, terracotta, ash wood and paper. The studio is a plaster sweep lit by a low sun through a window frame, so every packshot gets the same soft window shadow. Night scenes are lit only by the candle flames and a faint dusk light.
- `labels.py` prints the labels with the brand fonts (Fraunces and Instrument Sans) as textures for the 3D labels.
- `post.py` adds the finishing: a warm glow around flames, a light vignette and fine grain, then saves a JPEG.

Run: `pip install bpy pillow numpy`, put the Fraunces and Instrument Sans variable TTFs from Google Fonts in `fonts/`, then `./render_all.sh` (Cycles on the CPU, about 3 minutes per 1000 px photo on two cores).
