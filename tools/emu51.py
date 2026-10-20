"""Minimal 8051 emulator for testing hook code against a model of the DVR's memory.

XDATA 0x8000-0xFFFF is the big-memory window, 32 KB pages of an 8 MB array: reads use page [7008] | [7009] << 8,
writes use page [700A] | [700B] << 8 (the firmware's boot copy loop CODE:00A2 relies on this).
Calls/jumps to addresses outside the loaded code go to `stubs[addr](cpu)` (Python) and return.
"""


class Halt(Exception):
    pass


class CPU:
    def __init__(self):
        self.code = {}            # addr -> byte (only our hook code)
        self.iram = bytearray(256)
        self.sfr = bytearray(256)
        self.x = bytearray(0x8000)
        self.big = bytearray(0x800000)
        self.pc = 0
        self.stubs = {}
        self.writes = []          # (kind, addr) log of XDATA writes
        self.sfr[0x81] = 0x5F     # SP as set by the firmware's startup (CODE:416D)
        self.cycles = 0

    # ---- memory ----
    def load_ihx(self, path):
        for line in open(path):
            line = line.strip()
            if line.startswith(':') and int(line[7:9], 16) == 0:
                n, a = int(line[1:3], 16), int(line[3:7], 16)
                for i in range(n):
                    self.code[a + i] = int(line[9 + 2 * i:11 + 2 * i], 16)

    def page(self):
        return self.x[0x7008] | self.x[0x7009] << 8

    def wpage(self):
        return self.x[0x700A] | self.x[0x700B] << 8

    def xr(self, a):
        if a < 0x8000:
            return self.x[a]
        return self.big[(self.page() * 0x8000 + a - 0x8000) & 0x7FFFFF]

    def xw(self, a, v):
        if a < 0x8000:
            self.x[a] = v
            self.writes.append(('x', a))
        else:
            b = (self.wpage() * 0x8000 + a - 0x8000) & 0x7FFFFF
            self.big[b] = v
            self.writes.append(('big', b))

    def dr(self, a):              # direct
        return self.iram[a] if a < 0x80 else self.sfr_r(a)

    def dw(self, a, v):
        if a < 0x80:
            self.iram[a] = v & 0xFF
        else:
            self.sfr[a] = v & 0xFF

    def sfr_r(self, a):
        if a == 0xD0:             # PSW with parity
            p = bin(self.sfr[0xE0]).count('1') & 1
            return (self.sfr[0xD0] & 0xFE) | p
        return self.sfr[a]

    @property
    def a(self):
        return self.sfr[0xE0]

    @a.setter
    def a(self, v):
        self.sfr[0xE0] = v & 0xFF

    @property
    def c(self):
        return self.sfr[0xD0] >> 7

    @c.setter
    def c(self, v):
        self.sfr[0xD0] = (self.sfr[0xD0] & 0x7F) | (0x80 if v else 0)

    def rb(self):
        return self.sfr[0xD0] & 0x18

    def r(self, n):
        return self.iram[self.rb() + n]

    def rset(self, n, v):
        self.iram[self.rb() + n] = v & 0xFF

    @property
    def dptr(self):
        return self.sfr[0x83] << 8 | self.sfr[0x82]

    @dptr.setter
    def dptr(self, v):
        self.sfr[0x83] = (v >> 8) & 0xFF
        self.sfr[0x82] = v & 0xFF

    def bit_r(self, b):
        a = b if b >= 0x80 else 0x20 + (b >> 3)
        if b >= 0x80:
            a = b & 0xF8
        return (self.dr(a) >> (b & 7)) & 1

    def bit_w(self, b, v):
        a = b & 0xF8 if b >= 0x80 else 0x20 + (b >> 3)
        m = 1 << (b & 7)
        self.dw(a, (self.dr(a) | m) if v else (self.dr(a) & ~m))

    def push(self, v):
        sp = (self.sfr[0x81] + 1) & 0xFF
        self.sfr[0x81] = sp
        self.iram[sp] = v & 0xFF

    def pop(self):
        sp = self.sfr[0x81]
        v = self.iram[sp]
        self.sfr[0x81] = (sp - 1) & 0xFF
        return v

    def fetch(self):
        if self.pc not in self.code:
            raise Halt('fetch outside code at %04X' % self.pc)
        v = self.code[self.pc]
        self.pc = (self.pc + 1) & 0xFFFF
        return v

    def rel(self):
        o = self.fetch()
        return (self.pc + (o - 256 if o > 127 else o)) & 0xFFFF

    # ---- control ----
    def call(self, target, ret):
        if target in self.code:
            self.push(ret & 0xFF)
            self.push(ret >> 8)
            self.pc = target
        else:
            if target not in self.stubs:
                raise Halt('call to unknown %04X' % target)
            self.stubs[target](self)
            self.pc = ret

    def jump(self, target):
        if target in self.code:
            self.pc = target
        else:
            if target not in self.stubs:
                raise Halt('jump to unknown %04X' % target)
            self.stubs[target](self)
            self.ret()

    def ret(self):
        hi = self.pop()
        lo = self.pop()
        self.pc = hi << 8 | lo

    def run(self, entry, max_steps=200000):
        """Call `entry` as a subroutine with a sentinel return address; run until it returns."""
        SENT = 0xFFFE
        self.push(SENT & 0xFF)
        self.push(SENT >> 8)
        self.pc = entry
        steps = 0
        while self.pc != SENT:
            self.step()
            steps += 1
            if steps > max_steps:
                raise Halt('too many steps at %04X' % self.pc)
        return steps

    def addc(self, v, cin):
        a = self.a
        r = a + v + cin
        self.c = r > 0xFF
        self.a = r

    def subb(self, v):
        a = self.a
        r = a - v - self.c
        self.c = r < 0
        self.a = r

    def step(self):
        op = self.fetch()
        lo = op & 0x0F
        # register / indirect operand helpers
        def opnd_r():
            if lo >= 8:
                return self.r(lo - 8)
            return self.iram[self.r(lo & 1)]

        def opnd_w(v):
            if lo >= 8:
                self.rset(lo - 8, v)
            else:
                self.iram[self.r(lo & 1)] = v & 0xFF

        if op == 0x00:
            pass
        elif op == 0x02:
            hi = self.fetch(); l = self.fetch(); self.jump(hi << 8 | l)
        elif op == 0x12:
            hi = self.fetch(); l = self.fetch(); self.call(hi << 8 | l, self.pc)
        elif op == 0x22 or op == 0x32:
            self.ret()
        elif op == 0x80:
            self.pc = self.rel()
        elif op == 0x60:
            t = self.rel(); self.pc = t if self.a == 0 else self.pc
        elif op == 0x70:
            t = self.rel(); self.pc = t if self.a != 0 else self.pc
        elif op == 0x40:
            t = self.rel(); self.pc = t if self.c else self.pc
        elif op == 0x50:
            t = self.rel(); self.pc = t if not self.c else self.pc
        elif op in (0x20, 0x30):
            b = self.fetch(); t = self.rel()
            if self.bit_r(b) == (op == 0x20):
                self.pc = t
        elif op == 0xB4 or op == 0xB5 or 0xB8 <= op <= 0xBF:
            if op == 0xB4:
                x = self.a; v = self.fetch()
            elif op == 0xB5:
                x = self.a; v = self.dr(self.fetch())
            else:
                x = self.r(op - 0xB8); v = self.fetch()
            t = self.rel()
            self.c = x < v
            if x != v:
                self.pc = t
        elif 0xD8 <= op <= 0xDF:
            t = self.rel(); n = op - 0xD8; v = (self.r(n) - 1) & 0xFF; self.rset(n, v)
            if v:
                self.pc = t
        elif op == 0xD5:
            d = self.fetch(); t = self.rel(); v = (self.dr(d) - 1) & 0xFF; self.dw(d, v)
            if v:
                self.pc = t
        elif op == 0x90:
            hi = self.fetch(); l = self.fetch(); self.dptr = hi << 8 | l
        elif op == 0xA3:
            self.dptr = (self.dptr + 1) & 0xFFFF
        elif op == 0xE0:
            self.a = self.xr(self.dptr)
        elif op == 0xF0:
            self.xw(self.dptr, self.a)
        elif op == 0x74:
            self.a = self.fetch()
        elif op == 0xE4:
            self.a = 0
        elif op == 0xE5:
            self.a = self.dr(self.fetch())
        elif op == 0xF5:
            self.dw(self.fetch(), self.a)
        elif op == 0x75:
            d = self.fetch(); self.dw(d, self.fetch())
        elif op == 0x85:
            s = self.fetch(); d = self.fetch(); self.dw(d, self.dr(s))
        elif 0x78 <= op <= 0x7F:
            self.rset(op - 0x78, self.fetch())
        elif 0xA8 <= op <= 0xAF:
            self.rset(op - 0xA8, self.dr(self.fetch()))
        elif 0x88 <= op <= 0x8F:
            self.dw(self.fetch(), self.r(op - 0x88))
        elif 0xE6 <= op <= 0xEF:
            self.a = opnd_r()
        elif 0xF6 <= op <= 0xFF:
            opnd_w(self.a)
        elif 0xC6 <= op <= 0xCF:
            v = opnd_r(); opnd_w(self.a); self.a = v
        elif op == 0xC5:
            d = self.fetch(); v = self.dr(d); self.dw(d, self.a); self.a = v
        elif op == 0x04:
            self.a = self.a + 1
        elif op == 0x14:
            self.a = self.a - 1
        elif 0x06 <= op <= 0x0F:
            opnd_w(opnd_r() + 1)
        elif 0x16 <= op <= 0x1F:
            opnd_w(opnd_r() - 1)
        elif op == 0x24:
            self.addc(self.fetch(), 0)
        elif op == 0x34:
            self.addc(self.fetch(), self.c)
        elif op == 0x25:
            self.addc(self.dr(self.fetch()), 0)
        elif op == 0x35:
            self.addc(self.dr(self.fetch()), self.c)
        elif op == 0x45:
            self.a = self.a | self.dr(self.fetch())
        elif 0x26 <= op <= 0x2F:
            self.addc(opnd_r(), 0)
        elif 0x36 <= op <= 0x3F:
            self.addc(opnd_r(), self.c)
        elif op == 0x94:
            self.subb(self.fetch())
        elif 0x96 <= op <= 0x9F:
            self.subb(opnd_r())
        elif op == 0x44:
            self.a = self.a | self.fetch()
        elif op == 0x54:
            self.a = self.a & self.fetch()
        elif op == 0x64:
            self.a = self.a ^ self.fetch()
        elif 0x46 <= op <= 0x4F:
            self.a = self.a | opnd_r()
        elif 0x56 <= op <= 0x5F:
            self.a = self.a & opnd_r()
        elif 0x66 <= op <= 0x6F:
            self.a = self.a ^ opnd_r()
        elif op == 0x33:                                  # RLC A
            v = (self.a << 1) | self.c; self.c = v >> 8; self.a = v
        elif op == 0x13:                                  # RRC A
            v = self.a | (self.c << 8); self.c = v & 1; self.a = v >> 1
        elif op == 0x03:
            self.a = ((self.a >> 1) | (self.a << 7)) & 0xFF
        elif op == 0x23:
            self.a = ((self.a << 1) | (self.a >> 7)) & 0xFF
        elif op == 0xC4:
            self.a = ((self.a << 4) | (self.a >> 4)) & 0xFF
        elif op == 0xF4:
            self.a = ~self.a
        elif op == 0xC3:
            self.c = 0
        elif op == 0xD3:
            self.c = 1
        elif op == 0xC2:
            self.bit_w(self.fetch(), 0)
        elif op == 0xD2:
            self.bit_w(self.fetch(), 1)
        elif op == 0xC0:
            self.push(self.dr(self.fetch()))
        elif op == 0xD0:
            d = self.fetch(); self.dw(d, self.pop())
        else:
            raise Halt('unimplemented opcode %02X at %04X' % (op, (self.pc - 1) & 0xFFFF))
