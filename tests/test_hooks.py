"""Run the hook code in tools/emu51.py against a model of the DVR (real AVI header from a sample recording)."""
import os, sys, random, subprocess
ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from emu51 import CPU, Halt
import poke

HDR = open(os.path.join(ROOT, 'samples/hook1/d1.avi'), 'rb').read(0x8000)
SPECF = os.path.join(ROOT, 'pokes/peek_irq.txt')
SPEC = open(SPECF).read().splitlines() + ['rec write 571A 00002000', 'rec hdr 0084 11223344', 'frame write 7284 AB', 'frame or 7290 0F']
FILE = poke.build(SPEC)
fails = 0

def check(cond, msg):
    global fails
    print(('ok   ' if cond else 'FAIL ') + msg)
    fails += not cond

def dvr(ihx):
    c = CPU(); c.load_ihx(os.path.join(ROOT, 'hook', ihx))
    rnd = random.Random(1)
    for i in range(0x8000):
        c.x[i] = rnd.randrange(256)           # XDATA garbage after power-on
    c.big[0x7D0000:0x7D8000] = HDR            # AVI header as built by bank11:8000 at record start
    c.x[0x7008:0x700C] = b'\x34\x01\x56\x02'  # other read/write window pages in use by the firmware
    c.sfr[0xA8] = 0x85                        # IE with EA on
    return c

# ---- boot hook (bank10) ----
c = dvr('poke_b10.ihx')
loaded = []
c.stubs[0x0CEE] = lambda c: c.rset(7, 1)
def bA7A(c):   # copy name from CODE (R2:R1) to XDATA R4:R0 -- our name lives in hook code
    src = c.r(2) << 8 | c.r(1); dst = c.r(4) << 8 | c.r(0)
    for i in range(11): c.x[dst + i] = c.code[src + i]
c.stubs[0xBA7A] = bA7A
def l0E3E(c):
    name = bytes(c.x[0x6BF0:0x6BFB]); loaded.append((c.r(3), c.r(2), c.r(1), name))
    c.big[0x7FFE00:0x7FFE00 + len(FILE)] = FILE; c.rset(7, 1)
c.stubs[0x0E3E] = l0E3E
c.stubs[0xA517] = lambda c: None
c.x[0x571A:0x571E] = b'\x11\x11\x11\x11'
c.run(0xDA00)
check(loaded == [(1, 0x6B, 0xF0, b'UPOKE   BIN')], 'boot: loads UPOKE.BIN via 01:6BF0 %r' % loaded)
check(bytes(c.x[0x6A00:0x6A00 + len(FILE)]) == FILE, 'boot: file copied to 0x6A00')
check(bytes(c.x[0x6BE0:0x6BF0]) == bytes(16) and c.x[0x6BFB:0x6BFD] == bytes(2), 'boot: logger state, counters, switches 6BE0-6BEF + 6BFB cleared')
check((bytes(c.x[0x7008:0x700C]), c.sfr[0xA8]) == (b'\x34\x01\x56\x02', 0x85), 'boot: window page and IE restored')
check(bytes(c.x[0x571A:0x571E]) == b'\x11\x11\x11\x11', 'boot: rec-only entries not applied at boot')
X = bytes(c.x)

# ---- record start (bank13) ----
c = dvr('poke_b13.ihx'); c.x[:] = X
c.x[0x6BE0:0x6BF0] = bytes(range(0x50, 0x60))   # state left by a previous recording
c.x[0x6BC0:0x6BD0] = bytes(16)
c.writes.clear()
c.run(0xE800)
check(c.r(7) == 1, 'rec: returns R7=1 like the replaced code')
check(bytes(c.x[0x571A:0x571E]) == bytes.fromhex('00002000'), 'rec: rec entries applied')
check((bytes(c.x[0x7008:0x700C]), c.sfr[0xA8]) == (b'\x34\x01\x56\x02', 0x85), 'rec: window page and IE restored')
h = c.big[0x7D0000:0x7D8000]
check(h[0x160:0x164] == b'PLG2' and h[0x165] == 9, 'rec: log header written (%r n=%d len=%d)' % (bytes(h[0x160:0x164]), h[0x165], h[0x164]))
check(h[0x164] == 6 + 22, 'rec: record length 28')
check(bytes(h[0x166:0x176]) == bytes(range(0x50, 0x60)), 'rec: previous logger state in header')
check(bytes(h[0x176:0x176 + 36]) == FILE[4:4 + 36], 'rec: peek entries copied')
ptr = c.x[0x6BE1] << 8 | c.x[0x6BE2]
check(c.x[0x6BE0] == 0x5A and ptr == 0x8176 + 36, 'rec: armed, ptr %04X' % ptr)
check(bytes(c.x[0x6BE5:0x6BEE]) == bytes(range(0x55, 0x5E)), 'rec: counters and switches left alone')
bad = [w for w in c.writes if w[0] == 'big' and not (0x7D0160 <= w[1] < 0x7D8000 or 0x7D0084 <= w[1] < 0x7D0088)]
check(not bad, 'rec: big-memory writes only inside JUNK body + requested header bytes')
check(bytes(h[0x84:0x88]) == bytes.fromhex('11223344'), 'rec: header write applied')
check(h[:0x84] == HDR[:0x84] and h[0x88:0x160] == HDR[0x88:0x160] and h[0x1C0:] == HDR[0x1C0:], 'rec: rest of the header untouched')
check(bytes(c.x[0x6A00:0x6A00 + len(FILE)]) == FILE, 'rec: poke buffer untouched by the snapshot')
X, B = bytes(c.x), bytes(c.big[0x7D0000:0x7D8000])
c2 = dvr('poke_b13.ihx'); c2.x[:] = X; F2 = poke.build(['rec hdr 0020 AABB'])
c2.x[0x6A00:0x6A00 + len(F2)] = F2; c2.big[0x7D0000:0x7D8000] = HDR; c2.run(0xE800)
check(bytes(c2.big[0x7D0020:0x7D0022]) == b'\xAA\xBB' and c2.x[0x6BE0] == 0 and c2.big[0x7D0160:0x7D0164] == HDR[0x160:0x164],
      'rec: header writes without peek lines: applied, logger stays off')

# ---- interrupt logger (bank07, four wrappers) ----
c = dvr('peek_b07.ihx'); c.x[:] = X; c.big[0x7D0000:0x7D8000] = B
calls = []
ENTRY = {1: 0xDA00, 2: 0xDA03, 3: 0xDA06, 4: 0xDA09, 5: 0xDA0C}
for ev, h_ in ((1, 0xB26E), (2, 0xB222), (3, 0x9E43), (4, 0xB6E8), (5, 0xAB1E)):
    c.stubs[h_] = (lambda e: lambda c: calls.append((e, c.sfr[0xF0])))(ev)
c.sfr[0xD0] = 0x10                         # ISR register bank 2
c.sfr[0x81] = 0x90                         # stack in use by main code + dispatcher
cnt0 = bytes(c.x[0x6BE5:0x6BEB])
c.x[0x6BEB:0x6BF0] = bytes(5)
seq_ev = []
for i in range(2000):
    ev = (1, 2, 5, 3, 4)[i % 5]
    c.x[0x6BEB] = c.x[0x6BEE] = (0, 1, 3)[i % 3]
    seq_ev.append(ev)
    c.x[0x720D] = 0x81 if ev == 2 else (0x80 if i & 1 else 0x00)
    c.x[0x5229:0x522D] = i.to_bytes(4, 'big')
    c.sfr[0x8C], c.sfr[0x8A] = i >> 8, i & 0xFF
    c.writes.clear()
    c.run(ENTRY[ev])
    assert (bytes(c.x[0x7008:0x700C]), c.sfr[0xA8]) == (b'\x34\x01\x56\x02', 0x85), (i, bytes(c.x[0x7008:0x700C]).hex(), hex(c.sfr[0xA8]), hex(c.sfr[0x81]))
    bad = [w for w in c.writes if (w[0] == 'big' and not (0x7D0160 <= w[1] < 0x7D7FF0))
           or (w[0] == 'x' and w[1] not in (0x6BE1, 0x6BE2, 0x6BE4, 0x6BE5, 0x6BE6, 0x6BE7, 0x6BE8, 0x6BE9, 0x7008, 0x7009, 0x700A, 0x700B, 0x7284, 0x7290))]
    assert not bad, (i, bad[:5])
check([e for e, _ in calls] == seq_ev, 'irq: original handler jumped to after every record')
check(all(b == e for e, b in calls), 'irq: B holds the event number')
cnt = [(c.x[0x6BE5 + k] - cnt0[k]) & 0xFF for k in range(4)]
check(cnt == [400 & 0xFF] * 4, 'irq: event counters %r' % cnt)
check(True, 'irq: 2000 calls, window/IE restored and all writes in bounds')
avi = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'emu_test.avi')
open(avi, 'wb').write(bytes(c.big[0x7D0000:0x7D8000]) + b'\0' * 16)
out = subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'tools/plog.py'), avi, SPECF],
                     capture_output=True, text=True).stdout.splitlines()
print('\n'.join(out[:7]))
n = int(out[1].split()[0])
check(n == (0x7FF0 - 0x19A) // 28, 'plog: %d records decoded until full' % n)
rows = [l.split() for l in out[4:]]
check([r[0] for r in rows[:5]] == ['1', '2', '5', '3', '4'], 'plog: event column')
check(rows[0][1] == '01' and rows[9][1] == '0A', 'plog: seq counts 1..')
check(rows[9][4] == '00000009' and rows[1][6] == '81', 'plog: peeks (tick, 720D) decoded')
check(c.x[0x7284] == 0xAB and c.x[0x7290] & 0x0F == 0x0F, 'frame: per-frame pokes applied')

# edge fix: rows 1 -> 0 and 286 -> 287 in both capture buffers (table 16FC, entries 0/1), across 32 KB pages
def efrun(bases, mask):
    c = dvr('peek_b07.ihx'); hit = []; c.stubs[0x82DA] = lambda c: hit.append(1)
    bufs = {}
    for k, base in enumerate(bases):
        buf = bytearray(0x5A0 * 288)
        for r in range(288):
            buf[r * 0x5A0:(r + 1) * 0x5A0] = bytes(((r * 7 + x + k * 3) & 0xFF) for x in range(0x5A0))
        if 0x100000 <= base < 0x7A0000: c.big[base:base + len(buf)] = buf
        bufs[base] = buf
        c.x[0x16FC + 20 * k:0x16FC + 20 * k + 4] = base.to_bytes(4, 'big')
    c.x[0x6BFB] = mask; c.x[0x6BE0] = 0
    c.run(0xDA0F)
    ok = hit == [1] and (bytes(c.x[0x7008:0x700C]), c.sfr[0xA8]) == (b'\x34\x01\x56\x02', 0x85)
    inside = []
    for base, buf in bufs.items():
        if not (0x100000 <= base < 0x7A0000):
            continue
        exp = bytearray(buf)
        if mask & 1: exp[0:1408] = buf[0x5A0:0x5A0 + 1408]
        if mask & 2: exp[287 * 0x5A0:287 * 0x5A0 + 1408] = buf[286 * 0x5A0:286 * 0x5A0 + 1408]
        ok = ok and c.big[base:base + len(buf)] == exp
        inside.append((base, base + len(buf)))
    bad = [w for w in c.writes if w[0] == 'big' and not any(a <= w[1] < b for a, b in inside)]
    return ok and not bad
for bases in ((0x1D3940, 0x16E540), (0x238D40, 0x2CED40), (0x1FF660, 0x30FC00), (0x79AAC0 - 0x100, 0x400000)):
    check(all(efrun(bases, m) for m in (0, 1, 2, 3)), 'edge fix: buffers %06X/%06X, masks 0-3, rows 0/287 fixed, rest intact' % bases)
check(efrun((0x000000, 0x238D40), 3) and efrun((0x7A0000, 0x050000), 3), 'edge fix: buffers outside 0x100000-0x79FFFF are skipped')
c = dvr('peek_b07.ihx'); hit = []; c.stubs[0x82DA] = lambda c: hit.append(1); c.x[0x6BFB] = 0; c.x[0x6BE0] = 0
n0 = c.x[0x6BE7]; c.run(0xDA12)
check(hit == [1] and c.x[0x6BE7] == (n0 + 1) & 0xFF, 'edge fix B path: counted as event 3, start bit called')
c = dvr('peek_b07.ihx'); hit = []; c.stubs[0x82DA] = lambda c: hit.append(1); c.x[0x6BFB] = 0; c.x[0x6BE0] = 0; c.x[0x6BFC] = 0xFF
polls = [0]; oxr = c.xr
def xr2(a, o=oxr):
    if a == 0x720D:
        polls[0] += 1; return 0x85 if polls[0] > 200 else 0x81
    return o(a)
c.xr = xr2; c.run(0xDA12)
check(hit == [1] and 200 < polls[0] < 210, 'edge fix B path: waits for end of field when 6BFC = FF (%d polls)' % polls[0])

# rec XOR toggles a byte on every recording; other ops unaffected
c = dvr('poke_b13.ihx'); c.x[:] = X; F3 = poke.build(['boot write 6BEE 08', 'rec xor 6BEE F7', 'rec or 6BED 01', 'rec and 6BEC FE'])
c.x[0x6A00:0x6A00 + len(F3)] = F3; c.x[0x6BEE] = 0x08; c.x[0x6BED] = 0x30; c.x[0x6BEC] = 0x03; vals = []
for k in range(3):
    c.big[0x7D0000:0x7D8000] = HDR; c.run(0xE800); vals.append(c.x[0x6BEE])
check(vals == [0xFF, 0x08, 0xFF] and c.x[0x6BED] == 0x31 and c.x[0x6BEC] == 0x02, 'rec: xor toggles %r, or/and ok' % vals)

# ev5 FF mode: waits for 720D bit2, then AB1E with A preserved; times out if bit2 never comes
c = dvr('peek_b07.ihx'); hit = []; c.stubs[0xAB1E] = lambda c: hit.append(c.a)
polls = [0]
orig_xr = c.xr
def xr(a, orig=orig_xr):
    if a == 0x720D:
        polls[0] += 1
        return 0x85 if polls[0] > 300 else 0x81
    return orig(a)
c.xr = xr; c.x[0x6BE0] = 0; c.x[0x6BED] = 0; c.x[0x6BEE] = 0xFF; c.a = 0x37; c.run(0xDA0C)
check(hit == [0x37] and 300 < polls[0] < 310, 'ev5 FF: waits for end of field (%d polls), A kept' % polls[0])
c.xr = lambda a, orig=orig_xr: 0x81 if a == 0x720D else orig(a); hit.clear(); st = c.run(0xDA0C, max_steps=2000000)
check(hit == [0x37] and st > 65536 * 3, 'ev5 FF: timeout after 64K polls (%d steps)' % st)

# delays: ev5 (6BEE, A preserved for 82B5), accepted capture-done (6BEB), rejected field (6BEF)
for name, entry, reg, stub, setup in (('ev5 go', 0xDA0C, 0x6BEE, 0xAB1E, None), ('ev2 accepted', 0xDA03, 0x6BEB, 0xB222, 0x85),
                                      ('ev6 rejected', 0xDA03, 0x6BEF, None, 0x84)):
    c = dvr('peek_b07.ihx'); hit = []; st = []
    if stub: c.stubs[stub] = lambda c: hit.append(c.a)
    for dly in (0, 1, 10):
        c.x[0x6BE0] = 0; c.x[0x6BEB:0x6BF0] = bytes(5); c.x[reg] = dly
        if setup is not None: c.x[0x720D] = setup
        c.a = 0x90; st.append(c.run(entry))
    ok = st[1] - st[0] >= 256 and st[2] - st[0] >= 2560 and (not stub or len(hit) == 3)
    if name == 'ev5 go': ok = ok and hit == [0x90] * 3
    check(ok, 'delay: %s scales with %04X (steps %r)' % (name, reg, st))

# field gate: which 720D.0 values reach B222 per mode; rejected ones count as ev6 and log only if armed
for mode, want in ((0, [False, True]), (1, [True, True]), (2, [True, False])):
    got = []
    for fld in (0, 1):
        c = dvr('peek_b07.ihx'); c.x[:] = X; c.big[0x7D0000:0x7D8000] = B; c.x[0x6BEB:0x6BEE] = bytes([0, mode, 0])
        hit = []; c.stubs[0xB222] = lambda c: hit.append(1); c.x[0x720D] = 0x84 | fld; n6 = c.x[0x6BEA]
        c.run(0xDA03); got.append(bool(hit))
        if not hit:
            assert c.x[0x6BEA] == (n6 + 1) & 0xFF and c.big[0x7D0000 + (c.x[0x6BE1] << 8 | c.x[0x6BE2]) - 0x8000 - 28] == 0xA6
    check(got == want, 'gate: mode %d passes fields %r' % (mode, [f for f in (0, 1) if got[f]]))

# event mask: only selected events are logged, counters always run
c = dvr('peek_b07.ihx'); c.x[:] = X; c.big[0x7D0000:0x7D8000] = B
for h_ in (0xB26E, 0xB222, 0xB6E8): c.stubs[h_] = lambda c: None
c.x[0x6BEB:0x6BEE] = bytes([0, 0, 1 << 4]); c.x[0x720D] = 0x85; p0 = c.x[0x6BE1] << 8 | c.x[0x6BE2]
c.run(0xDA00); c.run(0xDA03); p1 = c.x[0x6BE1] << 8 | c.x[0x6BE2]; c.run(0xDA09); p2 = c.x[0x6BE1] << 8 | c.x[0x6BE2]
check(p1 == p0 and p2 == p0 + 28, 'mask: event mask 0x10 logs only ev4')

# disarmed / corrupt state: no writes at all
for st in (0x00, 0x5B):
    c = dvr('peek_b07.ihx'); c.stubs[0xB26E] = lambda c: None; c.x[0x6BE0] = st; c.writes.clear(); c.run(0xDA00)
    check([w for w in c.writes if w != ('x', 0x6BE5)] == [], 'irq: only the counter written when state byte = %02X' % st)
c = dvr('peek_b07.ihx'); c.stubs[0xB26E] = lambda c: None
c.x[0x6BE0] = 0x5A; c.x[0x6BE1], c.x[0x6BE2] = 0x40, 0x00; c.writes.clear(); c.run(0xDA00)
check([w for w in c.writes if w != ('x', 0x6BE5)] == [], 'irq: only the counter written when ptr is outside the header page')
c = dvr('peek_b07.ihx'); c.stubs[0xB26E] = lambda c: None; c.x[:] = X; c.big[0x7D014A] = 0; c.writes.clear(); c.run(0xDA00)
check(not [w for w in c.writes if w[0] == 'big'], 'irq: no big-memory writes when the JUNK chunk is gone')

# ---- delete skip (bank04) ----
for regs, want in (((1, 0x6B, 0xF0), False), ((1, 0x6B, 0xE0), True), ((0, 0x6B, 0xF0), True)):
    c = dvr('peek_b04.ihx'); dels = []
    c.stubs[0x1066] = lambda c: dels.append(1)
    c.rset(3, regs[0]); c.rset(2, regs[1]); c.rset(1, regs[2]); c.run(0xDA00)
    check(bool(dels) == want, 'nodel: name ptr %02X:%02X%02X -> delete %s' % (*regs, want))
print('FAILURES:', fails)
sys.exit(fails != 0)
