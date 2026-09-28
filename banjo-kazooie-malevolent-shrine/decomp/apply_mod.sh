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

# 2. the new hand-sign animation as asset 0x0004 (an empty slot in the asset table)
cp "$HERE/assets/anim/0004.anim.bin" assets/anim/0004.anim.bin
python3 - <<'PY'
p = "assets/assets.yaml"
s = open(p).read()
line4 = '  - {uid: 0x0004, type: Animation, compressed: true , flags: 0x0003, relative_path: "anim/0004.anim.bin"}\n'
line3 = '  - {uid: 0x0003, type: Animation, compressed: true , flags: 0x0003, relative_path: "anim/0003.anim.bin"}\n'
if line4 not in s:
    assert line3 in s, "unexpected assets.yaml layout"
    s = s.replace(line3, line3 + line4)
    open(p, "w").write(s)
    print("registered anim 0x0004 in assets.yaml")
PY

# 3. build with the anti-tamper/anti-piracy checks compiled out (they fight modified code)
grep -rl "ANTI_TAMPER\|ANTI_PIRACY" src | xargs touch
touch src/core2/bs/jig.c
PATH="$DECOMP/.venv/bin:$PATH" make -j"$(nproc)" ANTI_TAMPER=0 ANTI_PIRACY=0
cp build/us.v10/banjo.us.v10.z64 "$OUT"
echo "built $OUT"
