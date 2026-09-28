#!/bin/bash
# usage: DECOMP=/path/to/banjo-kazooie [SHRINE_TEST=1] build_test_rom.sh OUT.z64 [TEST_BOOT_MAP]
# Builds the mod ROM. With TEST_BOOT_MAP (e.g. MAP_2_MM_MUMBOS_MOUNTAIN), the game boots straight
# into that map (testing only); code_0.c is restored afterwards. SHRINE_TEST=1 also spawns a ring of
# Grublins around Banjo and shows an ALIVE counter (see malevolent_shrine.inc).
set -e
cd "${DECOMP:?set DECOMP to the banjo-kazooie decomp checkout}"
export PATH="$PWD/.venv/bin:$PATH"
OUT=$1; MAP=$2
cp src/core1/code_0.c /tmp/code_0.c.keep
cp src/core2/bs/jig.c /tmp/jig.c.keep
if [ -n "$MAP" ]; then
  python3 - "$MAP" <<'PY'
import sys
p="src/core1/code_0.c"; s=open(p).read()
old="enum map_e getDefaultBootMap(void) {\n    return MAP_1F_CS_START_RAREWARE;\n}"
assert s.count(old)==1
open(p,"w").write(s.replace(old,"enum map_e getDefaultBootMap(void) {\n    return %s; // TEST ONLY\n}" % sys.argv[1]))
PY
fi
if [ -n "$SHRINE_TEST" ]; then sed -i '1i #define SHRINE_TEST 1' src/core2/bs/jig.c; fi
touch src/core1/code_0.c src/core2/bs/jig.c
make -j$(nproc) ANTI_TAMPER=0 ANTI_PIRACY=0 > /tmp/bk_build_last.log 2>&1 || { cp /tmp/code_0.c.keep src/core1/code_0.c; cp /tmp/jig.c.keep src/core2/bs/jig.c; grep -i -A5 error /tmp/bk_build_last.log | head -40; exit 1; }
cp /tmp/code_0.c.keep src/core1/code_0.c
cp /tmp/jig.c.keep src/core2/bs/jig.c
touch src/core1/code_0.c src/core2/bs/jig.c
cp build/us.v10/banjo.us.v10.z64 "$OUT"
echo "built $OUT"
