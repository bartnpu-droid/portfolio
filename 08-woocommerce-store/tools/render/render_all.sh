#!/bin/bash
# Renders every product photo and scene, then finishes them as JPEGs in final/.
# Needs the Blender Python module (pip install bpy) and the Fraunces and Instrument Sans
# variable TTFs from Google Fonts in ./fonts (or OMBRA_FONTS=/path).
cd "$(dirname "$0")"
PY=${PY:-python3}
mkdir -p raw final
render() { # shot resolution samples bloom
  $PY studio.py "$1" --res "$2" --samples "$3" --out raw && $PY post.py "raw/$1.png" "final/$1.jpg" "$4"
}
for s in jar-{fig,salt,amber}-{200,400} vessel tin-{fig,salt,amber} diffuser-{fig,salt,amber} spray-{fig,salt,amber} matches giftset; do
  render "$s" 1000 64 0
done
for s in jar-{fig,salt,amber}-200-lit vessel-lit; do render "$s" 1000 72 0.9; done
render hero-wide 1920 96 0.9
render story 1350 96 0.9
