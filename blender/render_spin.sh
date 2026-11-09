#!/bin/bash
# 360 turntable for the v2 hero: 36 frames + shell/logo masks per size -> v2/spin/<size>/
# Run from the repo root after building each size (POD_SIZE=n Blender -b -P blender/build_pod.py).
B=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
for n in ${SIZES:-4 1 2 6 8}; do
  SHOT=spin FRAMES=36 SAMPLES=${SAMPLES:-48} "$B" -b "blender/soundbox$n.blend" -P blender/render.py 2>&1 | grep -E "Error|Traceback|rendered spin"
  mkdir -p "v2/spin/$n"
  for f in blender/renders/spin/$n/[0-9][0-9].png; do
    sips -s format jpeg -s formatOptions 78 "$f" --out "v2/spin/$n/$(basename "$f" .png).jpg" >/dev/null
  done
  for f in blender/renders/spin/$n/m[0-9][0-9].png; do   # masks at half size; the page filters them up
    sips -Z 500 "$f" --out "v2/spin/$n/$(basename "$f")" >/dev/null
  done
  echo "done $n"
done
