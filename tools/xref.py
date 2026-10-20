#!/usr/bin/env python3
"""Find callers of a banked function: direct LCALL/LJMP within its bank, plus via common-code stubs (90 hi lo 02 sw)."""
import re, sys
sys.path.insert(0, __import__('os').path.dirname(__file__))
import d51

def xref(d, loc):
    o = d51.cpu2file(loc); cpu, sp = d51.file2cpu(o)
    hi, lo = cpu >> 8, cpu & 0xFF
    res = []
    def calls(target, banks):
        for b in banks:
            seg = (0x40, 0x8000) if b == 'CODE' else (int(b[4:]) * 0x8000, int(b[4:]) * 0x8000 + 0x8000)
            for op in (b'\x12', b'\x02'):
                for m in re.finditer(re.escape(op + bytes([target >> 8, target & 0xFF])), d[seg[0]:seg[1]]):
                    c, s = d51.file2cpu(seg[0] + m.start()); res.append(('%s %s:%04X' % ('LCALL' if op == b'\x12' else 'LJMP ', s, c), target))
    if sp == 'CODE':
        calls(cpu, ['CODE'] + ['bank%02d' % i for i in range(1, 17)])
    else:
        calls(cpu, [sp])
        for m in re.finditer(re.escape(bytes([0x90, hi, lo, 0x02])), d[0x40:0x8000]):
            stub = m.start()  # file offset in common
            sw = int.from_bytes(d[0x40 + stub + 4:0x40 + stub + 6], 'big')
            bank = (sw - 0x200) // 0x1d + 1 if sw >= 0x200 else None
            if bank != int(sp[4:]):
                continue
            scpu = stub
            res.append(('stub CODE:%04X' % scpu, None))
            calls(scpu, ['CODE'] + ['bank%02d' % i for i in range(1, 17)])
    return res

if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()[:0x88000]
    for loc in sys.argv[2:]:
        print('==', loc)
        for r, _ in xref(d, loc): print('  ', r)
