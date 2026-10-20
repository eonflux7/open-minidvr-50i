"""Check the release patch (tools/mkpatch.py "release_31k_clk") in tools/emu51.py: audio clock dividers written by bank11."""
import os, sys
ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from emu51 import CPU
import mkpatch

img = bytearray(open(os.path.join(ROOT, 'patches/clean704_q4_peek6.bin'), 'rb').read())
for off, old, new in mkpatch.PATCHES['release_31k_clk']:
    assert img[off:off + len(old) // 2] == bytes.fromhex(old), hex(off)
    img[off:off + len(new) // 2] = bytes.fromhex(new)
fails = 0

def check(cond, msg):
    global fails
    print(('ok   ' if cond else 'FAIL ') + msg)
    fails += not cond

def bank11():
    c = CPU()
    for a in range(0x8000):
        c.code[0x8000 + a] = img[11 * 0x8000 + a]
    return c

c = bank11(); c.run(0xA2C5)                              # 9fcc path: 48 kHz family
check(list(c.x[0x77C0:0x77C2]) == [0x1F, 0x1F], 'a2c5: 77C0/77C1 = 1F (stock)')
check(list(c.x[0x77B2:0x77B4]) == [0x08, 0x08], 'a2c5: 77B2/77B3 = 08 (31 kHz)')
c = bank11(); c.dptr = 0x77C0; c.a = 0x22; c.run(0xA2CA)  # a893 path: 44.1 kHz family entry
check(list(c.x[0x77C0:0x77C2]) == [0x22, 0x22], 'a2ca: 77C0/77C1 = caller value')
check(list(c.x[0x77B2:0x77B4]) == [0x08, 0x08], 'a2ca: 77B2/77B3 = 08')
sys.exit(1 if fails else 0)
