#!/usr/bin/env bash
# Fast flash of a patched image to the DVR's SPI flash via pico-serprog.
#
#   tools/flash.sh patches/<image>.bin            fast path (uses dumps/chip_current.bin as known chip contents)
#   tools/flash.sh --read                         full read into dumps/chip_current.bin (resync / first use)
#
# Fast path: the settings sector (0x1DF000, "KTNS") is excluded via tools/dvr.layout (regions code + tail only), so
# flashrom never touches it and the DVR keeps the user's menu settings. Only changed erase blocks are written
# and verified (--flash-contents + --noverify-all). chip_current.bin is updated after a verified write.
set -euo pipefail
cd "$(dirname "$0")/.."
DEV=${DEV:-/dev/ttyACM0}
SPEED=${SPEED:-12M}
PROG="serprog:dev=$DEV:115200,spispeed=$SPEED"
CUR=dumps/chip_current.bin
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

if [[ "${1:-}" == "--read" ]]; then
    sudo flashrom -p "$PROG" -r "$TMP/r1.bin" 2>&1 | grep -E "rror|FAIL|differ" || true
    sudo flashrom -p "$PROG" -r "$TMP/r2.bin" 2>&1 | grep -E "rror|FAIL|differ" || true
    cmp -s "$TMP/r1.bin" "$TMP/r2.bin" || { echo "two reads differ - check clip/wiring"; exit 1; }
    cp "$TMP/r1.bin" "$CUR"; sudo chown "$USER" "$CUR" 2>/dev/null || true
    echo "read OK -> $CUR  $(sha256sum "$CUR" | cut -c1-16)"
    exit 0
fi

IMG=${1:?image}
[[ -f "$CUR" ]] || { echo "no $CUR - run: tools/flash.sh --read"; exit 1; }
python3 -I - "$IMG" "$CUR" "$TMP/new.bin" <<'EOF'
import sys
img = bytearray(open(sys.argv[1], 'rb').read()); cur = open(sys.argv[2], 'rb').read()
assert len(img) == len(cur) == 0x200000, 'size'
img[0x1DF000:0x1E0000] = cur[0x1DF000:0x1E0000]
open(sys.argv[3], 'wb').write(img)
print('bytes changing:', sum(1 for a, b in zip(img, cur) if a != b))
EOF
start=$(date +%s)
sudo flashrom -p "$PROG" --layout tools/dvr.layout -i code -i tail --flash-contents "$CUR" --noverify-all \
    -w "$TMP/new.bin" > "$TMP/log" 2>&1 || true
grep -E 'Found|done|VERIFIED|FAIL|rror' "$TMP/log" || true
echo "took $(( $(date +%s) - start )) s"
grep -qE 'VERIFIED|identical' "$TMP/log" || { echo "NOT VERIFIED - chip_current.bin left unchanged; run tools/flash.sh --read"; exit 1; }
cp "$TMP/new.bin" "$CUR"
echo "chip_current.bin updated  $(sha256sum "$CUR" | cut -c1-16)"
