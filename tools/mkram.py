#!/usr/bin/env python3
"""Make ADJUST.BIN (RAM-boot image) from a 2 MB flash image, to run a test firmware WITHOUT flashing.

At boot the firmware (bank10:A1A1) loads ADJUST.BIN from the card root to big memory 0x300000 (and deletes it), stops
the peripherals and jumps to CODE:0080, which copies 64 x 32 KB pages from 0x300000.. down to page 0.. - the RAM the
CPU executes from (the boot ROM normally fills it from the SPI flash) - and jumps to 0000. Layout (same as the
vendor's CRESFW.BIN): page 0 = flash[0x40:0x8040] (no 64-byte header), page N = flash[N*0x8000:(N+1)*0x8000].
The test firmware runs until power-off; the flash chip is not touched. One-shot: copy the file again for each boot.

Usage: mkram.py patches/<image>.bin F:/ADJUST.BIN
"""
import sys

img = open(sys.argv[1], 'rb').read()
assert len(img) == 0x200000, 'need a full 2 MB flash image'
orig = open('dumps/dump1.bin', 'rb').read()
loop = slice(0x40 + 0x80, 0x40 + 0xEE)          # CODE:0080-00ED copy loop runs while page 0 is overwritten
assert img[loop] == orig[loop], 'CODE:0080 copy loop differs from stock - unsafe for RAM boot'
ram = img[0x40:0x8040] + img[0x8000:]
assert len(ram) == 0x200000
open(sys.argv[2], 'wb').write(ram)
print(f'{sys.argv[2]}: {len(ram)} bytes (RAM image of {sys.argv[1]})')
