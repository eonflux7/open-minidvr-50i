#!/usr/bin/env python3
"""Decode the read-back log (hook/peek_b07.asm) stored in a recording's AVI header JUNK chunk.

Usage: plog.py PICT0001.AVI [spec.txt] [--csv out.csv]
The spec (the pokes/*.txt used to build UPOKE.BIN) is optional and only supplies column names.
"""
import sys

args = [a for a in sys.argv[1:] if not a.startswith('--')]
csv = sys.argv[sys.argv.index('--csv') + 1] if '--csv' in sys.argv else None
if csv in args:
    args.remove(csv)
d = open(args[0], 'rb').read(0x8000)
names = {}
if len(args) > 1:
    for raw in open(args[1]):
        f = raw.split('#')[0].split()
        if len(f) >= 4 and f[1] == 'peek':
            names[int(f[2], 16)] = f[4] if len(f) > 4 else None
if d[0x14A:0x14E] != b'JUNK' or d[0x160:0x163] != b'PLO' and d[0x160:0x164] != b'PLG2':
    sys.exit('no read-back log in this file (was UPOKE.BIN with peek lines on the card at power-on?)')
v2 = d[0x160:0x164] == b'PLG2'
reclen, n = d[0x164], d[0x165]
cols = [('ev', 0), ('seq', 1), ('T0', 2), ('T2', 2)]
o = 0x166
if v2:
    st = d[o:o + 16]; o += 16
    print('logger state left by the previous recording: armed=%02X ptr=%04X reclen=%d seq=%d calls ev1..6=%s (mod 256)'
          ' | delay B222=%d gate=%d mask=%02X delay jpeg start=%d delay rejected=%d' % (st[0], st[1] << 8 | st[2], st[3], st[4],
          ' '.join('%d' % x for x in st[5:11]), st[11], st[12], st[13], st[14], st[15]))
for i in range(n):
    flags, hi, lo, cnt = d[o:o + 4]; o += 4
    a = hi << 8 | lo
    cols.append((names.get(a) or '%04X' % a, cnt))
recs = []
while o + reclen <= 0x7FF4 and (not v2 and d[o] == 0xA5 or v2 and 0xA1 <= d[o] <= 0xA6):
    r = d[o + 1:o + reclen]
    vals, p = [str(d[o] & 0x0F) if v2 else '-'], 0
    o += reclen
    for _, cnt in cols[1:]:
        vals.append(r[p:p + cnt].hex().upper()); p += cnt
    recs.append(vals)
hdr = [c for c, _ in cols]
w = [max(len(h), max((len(v[i]) for v in recs), default=0)) for i, h in enumerate(hdr)]
print(f'{len(recs)} records of {reclen} bytes')
if v2:
    from collections import Counter
    print('records per event:', dict(sorted(Counter(v[0] for v in recs).items())))
print('  '.join(h.rjust(w[i]) for i, h in enumerate(hdr)))
for v in recs:
    print('  '.join(x.rjust(w[i]) for i, x in enumerate(v)))
if csv:
    with open(csv, 'w') as f:
        f.write(','.join(hdr) + '\n')
        for v in recs:
            f.write(','.join(v) + '\n')
