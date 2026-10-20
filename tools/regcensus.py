"""Census of 8051 MOVX writes/reads to peripheral XDATA (>=0x7000) using 'MOV DPTR,#imm' tracking."""
import sys, collections, re

def where(o):
    return "CODE:%04x" % (o - 0x40) if o < 0x8000 else "bank%02d:%04x" % (o // 0x8000, 0x8000 + o % 0x8000)

def main(path, code_end=0x88000):
    d = open(path, "rb").read()[:code_end]
    w = collections.defaultdict(set); r = collections.defaultdict(set)
    for m in re.finditer(rb"\x90([\x70-\x7f].)", d, re.S):
        o = m.start(); dptr = int.from_bytes(m.group(1), "big")
        # follow up to 6 bytes for MOVX @DPTR,A (F0) or MOVX A,@DPTR (E0), allowing MOV A,#imm / CLR A / INC A
        i = o + 3; k = 0
        while k < 3 and i < len(d):
            b = d[i]
            if b == 0xF0: w[dptr].add(where(o)); break
            if b == 0xE0: r[dptr].add(where(o)); break
            if b == 0x74: i += 2
            elif b in (0xE4, 0x04, 0x14, 0xEF, 0xEE, 0xED, 0xEC, 0xEB, 0xEA, 0xE9, 0xE8): i += 1
            else: break
            k += 1
    blocks = collections.defaultdict(lambda: [0, 0, set()])
    for a, s in w.items():
        blocks[a >> 8][0] += len(s); blocks[a >> 8][2] |= {x.split(":")[0] for x in s}
    for a, s in r.items():
        blocks[a >> 8][1] += len(s); blocks[a >> 8][2] |= {x.split(":")[0] for x in s}
    print("block  writes reads  banks")
    for b in sorted(blocks):
        wr, rd, banks = blocks[b]
        print("%02Xxx  %6d %5d  %s" % (b, wr, rd, " ".join(sorted(banks))))
    with open(sys.argv[2], "w") as out:
        for a in sorted(set(w) | set(r)):
            out.write("%04X W:%s R:%s\n" % (a, " ".join(sorted(w.get(a, ()))), " ".join(sorted(r.get(a, ())))))

if __name__ == "__main__":
    main(sys.argv[1])
