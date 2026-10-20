import struct, sys, collections
d = open(sys.argv[1],'rb').read()
i = d.rfind(b'idx1'); n = struct.unpack('<I', d[i+4:i+8])[0]//16
movi = d.find(b'movi') - 4  # offsets relative to 'movi' fourcc start-4? test both
ents = [struct.unpack('<4sIII', d[i+8+16*k:i+24+16*k]) for k in range(n)]
base = d.find(b'movi')
# figure base: offset points at chunk header
for b in (base, base-4, 0):
    if d[b+ents[0][2]:b+ents[0][2]+4]==ents[0][0]: break
print('idx entries', n, 'base', hex(b))
print('first 24 ids:', ' '.join(e[0].decode() for e in ents[:24]))
c = collections.Counter(e[0] for e in ents); print(c)
for k in c:
    s=[e[3] for e in ents if e[0]==k]; print(k, 'sizes min/max', min(s), max(s), 'common', collections.Counter(s).most_common(3))
au=[e for e in ents if e[0]==b'01wb']; print('audio total bytes', sum(e[3] for e in au), '-> s', sum(e[3] for e in au)/16000)
# gaps between consecutive chunks
gaps=collections.Counter(); fills=collections.Counter(); offs=[]
for a,bb in zip(ents, ents[1:]):
    end = b+a[2]+8+a[3]; nxt=b+bb[2]; gaps[nxt-end]+=1
    if nxt-end>=8: fills[d[end:end+4]]+=1
    offs.append(b+bb[2])
print('gap sizes (top):', gaps.most_common(6))
print('gap filler fourcc:', fills.most_common(5))
print('chunk start alignment mod 512:', collections.Counter(o%512 for o in offs).most_common(4), ' mod 32768:', collections.Counter(o%32768 for o in offs).most_common(3))
# where audio chunks sit relative to video frame count
vi=0; pattern=[]
for e in ents[:200]:
    if e[0]==b'00dc': vi+=1
    else: pattern.append(vi)
print('video frames before each audio chunk (first 10):', pattern[:10])
# sample filler content
for a,bb in zip(ents[:5], ents[1:6]):
    end=b+a[2]+8+a[3]; nxt=b+bb[2]
    if nxt>end: print('gap @',hex(end),'len',nxt-end, d[end:end+16].hex())
