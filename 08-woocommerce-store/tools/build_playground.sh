#!/bin/bash
# Builds the three zips the Playground blueprint downloads: theme, plugin, product photos.
# Usage: tools/build_playground.sh <folder with the product renders>
set -euo pipefail
cd "$(dirname "$0")/.."
RENDERS="$1"
OUT=playground
TMP=$(mktemp -d)

(cd theme && zip -qr -X "$TMP/ombra-theme.zip" ombra -x '*.DS_Store')
(cd plugin && zip -qr -X "$TMP/ombra-store-tools.zip" ombra-store-tools -x '*.DS_Store')

mkdir -p "$TMP/images"
for f in jar-{fig,salt,amber}-{200,400}.jpg jar-{fig,salt,amber}-200-lit.jpg vessel.jpg vessel-lit.jpg \
         tin-{fig,salt,amber}.jpg diffuser-{fig,salt,amber}.jpg spray-{fig,salt,amber}.jpg matches.jpg giftset.jpg; do
  if [ -f "$RENDERS/$f" ]; then cp "$RENDERS/$f" "$TMP/images/$f"; else echo "missing render: $f" >&2; fi
done
(cd "$TMP" && zip -qr -X ombra-images.zip images)

cp "$TMP/ombra-theme.zip" "$TMP/ombra-store-tools.zip" "$TMP/ombra-images.zip" "$OUT/"
rm -rf "$TMP"
ls -la "$OUT"/*.zip
