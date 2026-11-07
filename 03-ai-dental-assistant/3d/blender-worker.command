#!/bin/bash
# Blender render worker: renders the jobs Claude puts into the jobs/ folder, using the Mac's GPU.
# Start:  bash ~/Downloads/Portfolio/_3d/blender-worker.command   (leave the window open; Control+C to stop)
cd "$(dirname "$0")"
B="/Applications/Blender.app/Contents/MacOS/Blender"
if [ ! -x "$B" ]; then
  APP=$(mdfind "kMDItemCFBundleIdentifier == 'org.blenderfoundation.blender'" 2>/dev/null | head -1)
  [ -n "$APP" ] && B="$APP/Contents/MacOS/Blender"
fi
mkdir -p jobs done logs out
if [ ! -x "$B" ]; then
  echo "no-blender" > status.txt
  echo "Blender not found. Install it from https://www.blender.org/download/ and run this again."
  exit 1
fi
"$B" --version 2>/dev/null | head -1 > status.txt
echo "ready $(date +%H:%M:%S)" >> status.txt
echo "✅ Render worker is running ($(head -1 status.txt)). Leave this window open."
while true; do
  for job in jobs/*.job; do
    [ -e "$job" ] || continue
    name=$(basename "$job" .job)
    args=$(cat "$job")
    mv "$job" "done/$name.job"
    echo "$(date +%H:%M:%S) ▶ rendering $name"
    echo "busy $name $(date +%H:%M:%S)" > busy.txt
    "$B" -b --factory-startup -P implant_scene.py -- $args > "logs/$name.log" 2>&1
    echo $? > "logs/$name.exit"
    rm -f busy.txt
    echo "$(date +%H:%M:%S) ✔ finished $name"
  done
  sleep 2
done
