#!/bin/bash
# usage: run.sh ROM SCRIPT FRAMES OUTDIR [gfx]
# Runs mupen64plus headless (Xvfb) with the scripted input plugin and saves screenshots
# at the given frames plus a contact sheet. Build the plugin first:
#   gcc -shared -fPIC -O2 -I/usr/include/mupen64plus -o scriptinput.so scriptinput.c
E=$(cd "$(dirname "$0")" && pwd)   # scriptinput.so + cfg/ live here
PY=${PYTHON:-python3}             # needs Pillow for the contact sheet
L=/usr/lib/x86_64-linux-gnu/mupen64plus
ROM=$1; SCRIPT=$2; FRAMES=$3; OUT=$4; GFX=${5:-mupen64plus-video-rice}  # glide64mk2 renders black under software GL
mkdir -p "$OUT"
timeout 900 xvfb-run -a -s "-screen 0 640x480x24" env LIBGL_ALWAYS_SOFTWARE=1 M64_INPUT_SCRIPT="$SCRIPT" M64_INPUT_LOG="$OUT/frames.log" \
  /usr/games/mupen64plus --configdir $E/cfg --plugindir $L --nospeedlimit --audio dummy --input $E/scriptinput.so \
  --gfx $L/$GFX.so --rsp $L/mupen64plus-rsp-hle.so --emumode 2 --noosd --windowed --resolution 640x480 \
  --sshotdir "$OUT" --testshots "$FRAMES" "$ROM" > "$OUT/run.log" 2>&1
$PY - "$OUT" <<'PY'
import sys, glob
from PIL import Image
out = sys.argv[1]
fs = sorted(glob.glob(out + "/*.png"))
fs = [f for f in fs if not f.endswith("sheet.png")]
ims = [Image.open(f).convert("RGB").resize((320, 240)) for f in fs]
cols = min(4, len(ims)) or 1; rows = (len(ims) + cols - 1) // cols
c = Image.new("RGB", (320 * cols, 240 * rows))
for i, im in enumerate(ims): c.paste(im, (320 * (i % cols), 240 * (i // cols)))
c.save(out + "/sheet.png"); print(len(ims), "shots ->", out + "/sheet.png")
PY
