# TACET One: product landing page

A launch page for **TACET One**, over-ear noise-cancelling headphones, in the style of the big consumer-tech product
pages: white and light-grey chapters, one black chapter for sound, huge centred headlines and the product as the only
picture. Every picture of the headphones is a photoreal render from a procedural Blender model made for this page.

> Concept project. TACET is a fictional brand: the product, prices and specifications are illustrative.

## What's on the page

- **Hero:** the three colours, Moss, Obsidian and Bone, with a slow drift as the page starts to scroll
- **Highlights rail:** big cards you swipe or step through: a live noise-cancelling animation, a battery ring that
  fills, a close-up of the ear cushion, two devices at once, and the ear cup taken apart
- **Take a closer look:** a 360° view you turn by hand (mouse, finger or arrow keys): 144 rendered angles per colour,
  2.5° apart, always one sharp frame on screen. It moves only when you turn it. Switching colour dissolves on the
  same angle
- **Sound:** the ear cup comes apart into cap, shell, driver, baffle and cushion as the picture moves up the screen,
  with numbered tags that follow the parts. The page never stops scrolling
- **Quiet, on demand:** Off, Aware and Silence modes with a live noise meter
- **Battery counter, "little things" grid, tech specs, pre-order card with a waitlist form**
- Phone layout, keyboard focus, reduced-motion support; animations only run while they are on screen

## How it is built

- Plain HTML, CSS and JavaScript: no framework, no build step, no third-party scripts. Inter Tight and
  JetBrains Mono are served from the site itself
- Made to stay smooth on phones: native scrolling, canvases only as big as the picture they show, nothing redraws
  unless it changed, and every animation pauses when it leaves the screen
- **The headphones** are modelled in code for Blender (`3d/tacet_scene.py`): superellipse ear cups with a rounded
  shell and a machined aluminium cap, pillowy protein-leather cushions with pleats at the opening, a headband shaped to
  a head with a padded underside, aluminium yokes on pivots, steel sliders, and inside the cup a 40 mm driver,
  a perforated baffle and four microphones for the exploded view
- **Rendering:** Cycles on the Mac's GPU (Metal), studio lighting with large soft boxes and rim lights, a shadow
  catcher for real contact shadows, AgX colour. Shots: the three-colour hero, a 360° turntable per colour
  (72 angles plus the 72 halfway angles), a 60-frame exploded sequence with the screen position of every part saved for the tags, and two close-ups
- **Images for the web** (`3d/build_assets.py`): the renders are placed on the colour of their section and saved as
  WebP in two sizes. The page picks the size for the screen, loads the frames coarse-to-fine and decodes the ones
  around the current angle (or scroll position) ahead of time, so turning and scrolling never wait on a picture

```
site/index.html          the page
site/css/style.css       design: colours, type, layout
site/js/main.js          360° view, exploded view, noise demo, counters, form
site/img/                renders: hero, look/<size>/<colour>-NN[h].webp, explode/<size>/NN.webp, close-ups
3d/tacet_scene.py        the Blender model, materials, lights and shots
3d/build_assets.py       renders -> web images
versions/v1-dark/        the first draft: a dark page with a real-time three.js model
versions/v3-colour-picker/ an alternative: three still views per colour instead of the 360° view
```

Screens: `screenshots/` (desktop and phone). A 40-second walkthrough: `tacet-one-demo.mp4`.

## Run

Double-click `start.command` (Mac), or from a terminal:

```bash
cd site && python3 -m http.server 8093
```

then open http://localhost:8093. Any static hosting works (Netlify, Vercel, GitHub Pages): upload the `site` folder.

To render again (Blender 4.2 or newer):

```bash
blender -b --factory-startup -P 3d/tacet_scene.py -- --shot look --colour bone --gpu --out out/look/bone
python3 3d/build_assets.py out site/img
```
