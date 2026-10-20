#!/usr/bin/env python3
"""Carve contiguous RIFF/AVI files from a FAT32 SD card image.

Usage: carve_avi.py <image> <outdir>
Headers are found at any byte offset (old FS layout may differ). This DVR writes the
stream data first and the first cluster (RIFF header) last, so a file of N clusters is
stored as: clusters 1..N-1 contiguously, immediately followed by cluster 0.
"""
import os, re, struct, sys

img, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
f = open(img, 'rb')
mbr = f.read(512)
lba = struct.unpack('<I', mbr[454:458])[0]
f.seek(lba * 512)
bs = f.read(512)
bps, spc, rsv, nf = struct.unpack('<HBHB', bs[11:17])
fatsz = struct.unpack('<I', bs[36:40])[0]
data = (lba + rsv + nf * fatsz) * bps
clus = bps * spc
size = os.path.getsize(img)

n = 0
CH = 64 <<20
hits = []
pos = 0
while pos < size:
    f.seek(pos)
    buf = f.read(CH + 12)
    for m in re.finditer(b'RIFF....AVI ', buf, re.S):
        if m.start() < CH:
            hits.append(pos + m.start())
    pos += CH
for hp in hits:
    f.seek(hp + 4)
    ln = struct.unpack('<I', f.read(4))[0] + 8
    n += 1
    name = os.path.join(out, 'rec_%03d_off%011d.avi' % (n, hp))
    nclus = -(-ln // clus)
    start = hp - (nclus - 1) * clus
    with open(name, 'wb') as o:
        f.seek(hp)
        o.write(f.read(min(clus, ln)))
        f.seek(start)
        left = ln - clus
        while left > 0:
            b = f.read(min(left, 8 << 20))
            if not b:
                break
            o.write(b)
            left -= len(b)
    print(name, ln, flush=True)
print('carved', n)
