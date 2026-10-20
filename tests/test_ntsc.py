"""Check the NTSC variant (tools/mkpatch.py "ntsc_d1", on top of the release build) in tools/emu51.py: the D1 branch of
the mode table (bank05:95E5) must leave the same state as the release one, except [5358] = 240 rows."""
import os, sys
ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from emu51 import CPU
import mkpatch

release = bytearray(open(os.path.join(ROOT, 'patches/peek6_a31hdr.bin'), 'rb').read())
ntsc = bytearray(release)
for off, old, new in mkpatch.PATCHES['ntsc_d1']:
    assert ntsc[off:off + len(old) // 2] == bytes.fromhex(old) and len(old) == len(new), hex(off)
    ntsc[off:off + len(new) // 2] = bytes.fromhex(new)
fails = 0

def check(cond, msg):
    global fails
    print(('ok   ' if cond else 'FAIL ') + msg)
    fails += not cond


class Keil(CPU):
    def call(self, target, ret):
        if target == 0x3B1A:                             # Keil: store the 4-byte inline constant at DPTR, skip it
            for i in range(4):
                self.xw(self.dptr + i, self.code[ret + i])
            self.pc = ret + 4
        else:
            super().call(target, ret)


def d1_branch(img):
    """Run the D1 case of the mode table from bank05:95E5 up to the shared tail at 95FC; return the touched XDATA."""
    c = Keil()
    for a in range(0x8000):
        c.code[0x8000 + a] = img[5 * 0x8000 + a]
    c.x[0x5356:0x5380] = b'\xee' * 0x2A
    c.pc = 0x95E5
    for _ in range(200):
        c.step()
        if c.pc == 0x95FC:
            break
    check(c.pc == 0x95FC, 'reaches 95FC')
    check(c.sfr[0x81] == 0x5F, 'stack balanced')
    return c


r, n = d1_branch(release), d1_branch(ntsc)
check(r.x[0x5356:0x535A].hex() == '02c00120', 'release: [5356] = 704, [5358] = 288')
check(n.x[0x5356:0x535A].hex() == '02c000f0', 'ntsc: [5356] = 704, [5358] = 240')
check(n.x[0x536E:0x5372].hex() == '00006800', 'ntsc: [536E] = 6800')
check(sorted(set(a for k, a in r.writes)) == sorted(set(a for k, a in n.writes)), 'same addresses written')
same = [a for a in range(0x5356, 0x5380) if a not in (0x5358, 0x5359)]
check(all(r.x[a] == n.x[a] for a in same), 'all other values identical')
sys.exit(1 if fails else 0)
