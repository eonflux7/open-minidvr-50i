#!/usr/bin/env python3
"""Minimal 8051 linear disassembler for the minidvr dump (bank-aware addressing).

Usage: d51.py <dump> <loc> [count]
  loc = CODE:xxxx | bankNN:xxxx | 0xFILEOFF
Knows Keil quirks: LCALL 3b1a is followed by a 4-byte inline constant.
"""
import sys

# (mnemonic, length); operand formats: a=addr8, i=#imm8, r=rel8, A=addr11, L=addr16, I=#imm16, b=bit
T = {}
def op(code, mn, ln):
    head, _, args = mn.partition(' ')
    toks = []
    for t in args.split(',') if args else []:
        if t in ('a', 'i', 'r', 'b', 'L', 'I'): t = '{%s}' % t
        elif t == '/b': t = '/{b}'
        elif t == 'A' and head in ('AJMP', 'ACALL'): t = '{A}'
        toks.append(t)
    T[code] = (head + (' ' + ','.join(toks) if toks else ''), ln)

op(0x00,'NOP',1); op(0x02,'LJMP L',3); op(0x03,'RR A',1); op(0x04,'INC A',1); op(0x05,'INC a',2)
op(0x06,'INC @R0',1); op(0x07,'INC @R1',1)
op(0x10,'JBC b,r',3); op(0x12,'LCALL L',3); op(0x13,'RRC A',1); op(0x14,'DEC A',1); op(0x15,'DEC a',2)
op(0x16,'DEC @R0',1); op(0x17,'DEC @R1',1)
op(0x20,'JB b,r',3); op(0x22,'RET',1); op(0x23,'RL A',1); op(0x24,'ADD A,i',2); op(0x25,'ADD A,a',2)
op(0x26,'ADD A,@R0',1); op(0x27,'ADD A,@R1',1)
op(0x30,'JNB b,r',3); op(0x32,'RETI',1); op(0x33,'RLC A',1); op(0x34,'ADDC A,i',2); op(0x35,'ADDC A,a',2)
op(0x36,'ADDC A,@R0',1); op(0x37,'ADDC A,@R1',1)
op(0x40,'JC r',2); op(0x42,'ORL a,A',2); op(0x43,'ORL a,i',3); op(0x44,'ORL A,i',2); op(0x45,'ORL A,a',2)
op(0x46,'ORL A,@R0',1); op(0x47,'ORL A,@R1',1)
op(0x50,'JNC r',2); op(0x52,'ANL a,A',2); op(0x53,'ANL a,i',3); op(0x54,'ANL A,i',2); op(0x55,'ANL A,a',2)
op(0x56,'ANL A,@R0',1); op(0x57,'ANL A,@R1',1)
op(0x60,'JZ r',2); op(0x62,'XRL a,A',2); op(0x63,'XRL a,i',3); op(0x64,'XRL A,i',2); op(0x65,'XRL A,a',2)
op(0x66,'XRL A,@R0',1); op(0x67,'XRL A,@R1',1)
op(0x70,'JNZ r',2); op(0x72,'ORL C,b',2); op(0x73,'JMP @A+DPTR',1); op(0x74,'MOV A,i',2); op(0x75,'MOV a,i',3)
op(0x76,'MOV @R0,i',2); op(0x77,'MOV @R1,i',2)
op(0x80,'SJMP r',2); op(0x82,'ANL C,b',2); op(0x83,'MOVC A,@A+PC',1); op(0x84,'DIV AB',1); op(0x85,'MOV a,a',3)
op(0x86,'MOV a,@R0',2); op(0x87,'MOV a,@R1',2)
op(0x90,'MOV DPTR,I',3); op(0x92,'MOV b,C',2); op(0x93,'MOVC A,@A+DPTR',1); op(0x94,'SUBB A,i',2); op(0x95,'SUBB A,a',2)
op(0x96,'SUBB A,@R0',1); op(0x97,'SUBB A,@R1',1)
op(0xA0,'ORL C,/b',2); op(0xA2,'MOV C,b',2); op(0xA3,'INC DPTR',1); op(0xA4,'MUL AB',1); op(0xA5,'DB A5',1)
op(0xA6,'MOV @R0,a',2); op(0xA7,'MOV @R1,a',2)
op(0xB0,'ANL C,/b',2); op(0xB2,'CPL b',2); op(0xB3,'CPL C',1); op(0xB4,'CJNE A,i,r',3); op(0xB5,'CJNE A,a,r',3)
op(0xB6,'CJNE @R0,i,r',3); op(0xB7,'CJNE @R1,i,r',3)
op(0xC0,'PUSH a',2); op(0xC2,'CLR b',2); op(0xC3,'CLR C',1); op(0xC4,'SWAP A',1); op(0xC5,'XCH A,a',2)
op(0xC6,'XCH A,@R0',1); op(0xC7,'XCH A,@R1',1)
op(0xD0,'POP a',2); op(0xD2,'SETB b',2); op(0xD3,'SETB C',1); op(0xD4,'DA A',1); op(0xD5,'DJNZ a,r',3)
op(0xD6,'XCHD A,@R0',1); op(0xD7,'XCHD A,@R1',1)
op(0xE0,'MOVX A,@DPTR',1); op(0xE2,'MOVX A,@R0',1); op(0xE3,'MOVX A,@R1',1); op(0xE4,'CLR A',1); op(0xE5,'MOV A,a',2)
op(0xE6,'MOV A,@R0',1); op(0xE7,'MOV A,@R1',1)
op(0xF0,'MOVX @DPTR,A',1); op(0xF2,'MOVX @R0,A',1); op(0xF3,'MOVX @R1,A',1); op(0xF4,'CPL A',1); op(0xF5,'MOV a,A',2)
op(0xF6,'MOV @R0,A',1); op(0xF7,'MOV @R1,A',1)
for n in range(8):
    op(0x08+n,f'INC R{n}',1); op(0x18+n,f'DEC R{n}',1); op(0x28+n,f'ADD A,R{n}',1); op(0x38+n,f'ADDC A,R{n}',1)
    op(0x48+n,f'ORL A,R{n}',1); op(0x58+n,f'ANL A,R{n}',1); op(0x68+n,f'XRL A,R{n}',1); op(0x78+n,f'MOV R{n},i',2)
    op(0x88+n,f'MOV a,R{n}',2); op(0x98+n,f'SUBB A,R{n}',1); op(0xA8+n,f'MOV R{n},a',2); op(0xB8+n,f'CJNE R{n},i,r',3)
    op(0xC8+n,f'XCH A,R{n}',1); op(0xD8+n,f'DJNZ R{n},r',2); op(0xE8+n,f'MOV A,R{n}',1); op(0xF8+n,f'MOV R{n},A',1)
for k in range(8):
    op(0x01+k*0x20,'AJMP A',2); op(0x11+k*0x20,'ACALL A',2)
SFR = {0x81:'SP',0x82:'DPL',0x83:'DPH',0xD0:'PSW',0xE0:'ACC',0xF0:'B',0xA8:'IE',0x80:'P0',0x90:'P1',0xA0:'P2',0xB0:'P3'}

def file2cpu(o):
    if o < 0x8000: return o - 0x40, 'CODE'
    return 0x8000 + o % 0x8000, 'bank%02d' % (o // 0x8000)

def cpu2file(s):
    if s.startswith('0x'): return int(s, 16)
    sp, a = s.split(':'); a = int(a, 16)
    if sp == 'CODE': return a + 0x40
    return int(sp[4:]) * 0x8000 + (a - 0x8000)

def dis(d, o):
    """Return (text, length, target_cpu_or_None)."""
    b = d[o]; mn, ln = T.get(b, ('DB %02X' % b, 1))
    cpu, sp = file2cpu(o)
    ops = list(d[o + 1:o + ln]); tgt = None
    out = ''; i = 0
    while i < len(mn):
        if mn[i] != '{':
            out += mn[i]; i += 1; continue
        c = mn[i + 1]; i += 3
        if c == 'a':
            v = ops.pop(0); out += SFR.get(v, '%02Xh' % v)
        elif c == 'i':
            out += '#%02Xh' % ops.pop(0)
        elif c == 'b':
            out += 'bit%02Xh' % ops.pop(0)
        elif c == 'r':
            v = ops.pop(0); rel = v - 256 if v > 127 else v
            tgt = (cpu + ln + rel) & 0xFFFF; out += '%04X' % tgt
        elif c == 'L':
            tgt = (ops.pop(0) << 8) | ops.pop(0); out += '%04X' % tgt
        elif c == 'I':
            out += '#%04Xh' % ((ops.pop(0) << 8) | ops.pop(0))
        elif c == 'A':
            tgt = ((cpu + 2) & 0xF800) | ((b >> 5) << 8) | ops.pop(0); out += '%04X' % tgt
    return out, ln, tgt

def listing(d, o, n):
    lines = []
    for _ in range(n):
        txt, ln, tgt = dis(d, o)
        cpu, sp = file2cpu(o)
        lines.append('%s:%04X  %-10s %s' % (sp, cpu, d[o:o + ln].hex(), txt))
        o += ln
        if d[o - ln] == 0x12 and tgt == 0x3B1A:
            lines.append('%s:%04X  %-10s   .const %s' % (sp, cpu + ln, d[o:o + 4].hex(), d[o:o + 4].hex()))
            o += 4
    return lines

if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    o = cpu2file(sys.argv[2]); n = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    print('\n'.join(listing(d, o, n)))
