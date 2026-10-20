import sys, collections, hashlib
d=open(sys.argv[1],'rb').read(); c=collections.Counter(); com=collections.Counter(); n=0; i=0
while True:
    i=d.find(b'\xff\xd8\xff\xdb',i)
    if i<0: break
    q=d[i+6:i+6+130]; c[hashlib.md5(q).hexdigest()[:8]]+=1
    j=d.find(b'\xff\xfe',i,i+1000); com[d[j+4:j+7] if j>0 else None]+=1; n+=1; i+=4
print('frames',n,'distinct DQT',len(c),c.most_common(4),'COM',com)
