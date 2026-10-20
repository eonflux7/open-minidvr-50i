import struct, sys, collections, hashlib
p = sys.argv[1]
d = open(p,'rb').read()
def walk(off, end, depth=0, out=None):
    while off + 8 <= end:
        cid = d[off:off+4]; sz = struct.unpack('<I', d[off+4:off+8])[0]
        if cid in (b'RIFF', b'LIST'):
            typ = d[off+8:off+12]
            out.append((depth, off, cid.decode('latin1')+':'+typ.decode('latin1'), sz))
            if typ != b'movi': walk(off+12, off+8+sz, depth+1, out)
            else: out.append((depth+1, off, '[movi]', sz)); movi.append((off+12, off+8+sz))
        else:
            out.append((depth, off, cid.decode('latin1'), sz))
        off += 8 + sz + (sz & 1)
    return out
movi=[]
for depth, off, n, sz in walk(0, len(d), 0, []):
    print('  '*depth + f'{n:12s} @0x{off:08x} size={sz}')
# movi chunks
ms, me = movi[0]; off = ms; seq=[]; sizes=collections.defaultdict(list)
while off + 8 <= me:
    cid = d[off:off+4]; sz = struct.unpack('<I', d[off+4:off+8])[0]
    seq.append((cid, off+8, sz)); sizes[cid].append(sz); off += 8 + sz + (sz&1)
print('movi chunk ids:', {k.decode('latin1'):len(v) for k,v in sizes.items()})
print('first 30 chunk ids:', ' '.join(c.decode('latin1') for c,_,_ in seq[:30]))
for k,v in sizes.items():
    print(k, 'min',min(v),'max',max(v),'most common', collections.Counter(v).most_common(3))
# audio duration check
wb = sum(sizes.get(b'01wb',[])); print('audio bytes', wb, '=> sec @8k16m', wb/16000)
# first video frame JPEG markers
vid = [x for x in seq if x[0] in (b'00dc', b'00db')]
c, o, sz = vid[0]; j = d[o:o+sz]
print('frame0 head:', j[:4].hex(), 'tail:', j[-4:].hex(), 'trailing pad after EOI:', sz - (j.rfind(b'\xff\xd9')+2))
i=2
while i < len(j)-4:
    if j[i]!=0xFF: print('  non-marker at',i); break
    m=j[i+1]; L=struct.unpack('>H', j[i+2:i+4])[0]; seg=j[i+4:i+2+L]
    info=''
    if m==0xDB:
        q=seg; k=0
        while k < len(q):
            pq_tq=q[k]; tab=q[k+1:k+65]; info+=f' T{pq_tq&15}:{list(tab[:8])}... md5={hashlib.md5(tab).hexdigest()[:8]}'; k+=65
    elif m==0xC0: info=' SOF0 '+seg.hex()
    elif 0xE0<=m<=0xEF or m==0xFE: info=' '+repr(seg[:64])
    elif m==0xDD: info=' restart interval '+str(struct.unpack('>H',seg[:2])[0])
    print(f'  FF{m:02X} len={L}{info}')
    if m==0xDA: break
    i+=2+L
# check idx1 tail for anything after
