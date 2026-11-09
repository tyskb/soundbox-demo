#!/bin/bash
# Hero shot for every size x colour -> v2/img/pod<size>-<colour>.jpg (1200px JPEG).
# Run from the repo root after building each size (POD_SIZE=n Blender -b -P blender/build_pod.py).
B=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
for n in ${SIZES:-4 1 2 6 8}; do
  for c in ${COLOURS:-white:#ecebe6 grey:#7b8089 orange:#e5742c green:#3d5c49 black:#2b2c30}; do
    id=${c%%:*}; hex=${c#*:}
    [ -n "$NEWER_THAN" ] && [ "v2/img/pod$n-$id.jpg" -nt "$NEWER_THAN" ] && continue   # already rendered from this build
    POD_COLOUR=$hex TAG=-$n-$id SHOT=hero_3q RES=${RES:-1400} SAMPLES=${SAMPLES:-128} "$B" -b "blender/soundbox$n.blend" -P blender/render.py 2>&1 | grep -E "Error|Traceback"
    sips -s format jpeg -s formatOptions 82 -Z 1200 "blender/renders/hero_3q-$n-$id.png" --out "v2/img/pod$n-$id.jpg" >/dev/null
    mv "blender/renders/hero_3q-$n-$id.png" blender/renders/sizes/
    echo "done $n $id"
  done
done
