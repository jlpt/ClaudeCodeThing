#!/bin/bash
# Applies the Malevolent Shrine mod to a banjo-kazooie decomp checkout and builds the ROM.
#
# usage: apply_mod.sh /path/to/banjo-kazooie [out.z64]
#
# The checkout must already have been built once with plain `make` (that extracts the
# assets from your own baserom.us.v10.z64). Re-run this script after `make clean`, because
# extraction regenerates assets/assets.yaml. It is safe to run more than once.
# Tested against n64decomp/banjo-kazooie commit e8d31fa53645616fcac6e051543222b973a2edb0.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
DECOMP=$(cd "${1:?usage: apply_mod.sh /path/to/banjo-kazooie [out.z64]}" && pwd)
OUT=${2:-$DECOMP/banjo-malevolent-shrine.z64}
cd "$DECOMP"

[ -f assets/assets.yaml ] || { echo "assets/ not extracted yet: run 'make' in $DECOMP first"; exit 1; }

# 1. source changes
if git apply --check "$HERE/malevolent-shrine.patch" 2>/dev/null; then
    git apply "$HERE/malevolent-shrine.patch"
    echo "applied source patch"
elif git apply --reverse --check "$HERE/malevolent-shrine.patch" 2>/dev/null; then
    echo "source patch already applied"
else
    echo "source patch does not apply cleanly to this checkout"; exit 1
fi

# 2. new assets in empty slots of the asset table:
#    0x0004 = the hand-sign animation, 0x02D8 = the shrine model
cp "$HERE/assets/anim/0004.anim.bin" assets/anim/0004.anim.bin
cp "$HERE/assets/model/02D8.model.bin" assets/model/02D8.model.bin
python3 - <<'PY'
p = "assets/assets.yaml"
s = open(p).read()
entries = [
    ('  - {uid: 0x0003, type: Animation, compressed: true , flags: 0x0003, relative_path: "anim/0003.anim.bin"}\n',
     '  - {uid: 0x0004, type: Animation, compressed: true , flags: 0x0003, relative_path: "anim/0004.anim.bin"}\n'),
    ('  - {uid: 0x02D7, type: Model , compressed: true , flags: 0x0000, relative_path: "model/02D7.model.bin"}\n',
     '  - {uid: 0x02D8, type: Model , compressed: true , flags: 0x0000, relative_path: "model/02D8.model.bin"}\n'),
]
for before, line in entries:
    if line not in s:
        assert before in s, "unexpected assets.yaml layout"
        s = s.replace(before, before + line)
        print("registered", line.split(",")[0].strip())
open(p, "w").write(s)
PY

# 3. turn Banjo's player models (0x34E high poly, 0x34D low poly) into Sukuna.
#    The originals are kept as *.orig so re-running always starts from the real models.
PY="$DECOMP/.venv/bin/python3"
"$PY" -c "import numpy" 2>/dev/null || "$PY" -m pip install -q numpy
for id in 034E 034D; do
    f="assets/model/$id.model.bin"
    [ -f "$f.orig" ] || cp "$f" "$f.orig"
    "$PY" "$HERE/../tools/sukuna.py" "$f.orig" "$f"
done

# 4. build with the anti-tamper/anti-piracy checks compiled out (they fight modified code)
grep -rl "ANTI_TAMPER\|ANTI_PIRACY" src | xargs touch
touch src/core2/bs/jig.c
PATH="$DECOMP/.venv/bin:$PATH" make -j"$(nproc)" ANTI_TAMPER=0 ANTI_PIRACY=0
cp build/us.v10/banjo.us.v10.z64 "$OUT"
echo "built $OUT"
