#!/bin/bash
# Applies the Banjo's Brain mod to a banjo-kazooie decomp checkout and builds the ROM.
#
# usage: apply_mod.sh /path/to/banjo-kazooie [out.z64]
#
# The checkout must already have been built once with plain `make` (that sets up the
# tools and extracts your own baserom.us.v10.z64). Safe to run more than once.
# Tested against n64decomp/banjo-kazooie commit e8d31fa53645616fcac6e051543222b973a2edb0.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
DECOMP=$(cd "${1:?usage: apply_mod.sh /path/to/banjo-kazooie [out.z64]}" && pwd)
OUT=${2:-$DECOMP/banjo-brain.z64}
cd "$DECOMP"

if git apply --check "$HERE/banjo-brain.patch" 2>/dev/null; then
    git apply "$HERE/banjo-brain.patch"
    echo "applied source patch"
elif git apply --reverse --check "$HERE/banjo-brain.patch" 2>/dev/null; then
    echo "source patch already applied"
else
    echo "source patch does not apply cleanly to this checkout"; exit 1
fi

# build with the anti-tamper/anti-piracy checks compiled out (they fight modified code)
grep -rl "ANTI_TAMPER\|ANTI_PIRACY" src | xargs touch
touch src/core2/bsmethods.c
PATH="$DECOMP/.venv/bin:$PATH" make -j"$(nproc)" ANTI_TAMPER=0 ANTI_PIRACY=0
cp build/us.v10/banjo.us.v10.z64 "$OUT"
echo "built $OUT"
