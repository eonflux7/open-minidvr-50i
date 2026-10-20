#!/usr/bin/env python3
"""Build UPOKE.BIN for the SD-card poke hook (hook/poke_b10.asm, hook/poke_b13.asm).

Spec: one entry per line, '#' comments:   <when> <op> <addr hex> <value hex>
  when = boot | rec | both     (boot: once after power-on; rec: at every record start)
  op   = write | or | and | xor (xor: rec only - e.g. toggle a switch between two values on every recording)
Multi-byte values (e.g. 0000C600) are written big-endian to consecutive addresses (Keil long layout).

  when = frame                 (every accepted capture-done, i.e. every recorded frame; ops write/or/and)
Header write:    rec hdr <offset hex> <bytes hex>
  writes the bytes (in file order) into the recording's AVI header at record start (offset < 0x8000)
Switches (XDATA, cleared at boot, set with "boot write"): 6BEC field gate (0 stock = field 720D.0=1, 1 both
  fields, 2 field 720D.0=0), 6BED log event mask (bit n = event n, 0 = all); delays in x256 loops: 6BEB before the
  capture-done handler B222, 6BEE before the JPEG start (AB1E, event 5), 6BEF on a rejected field

Read-back log:   field peek <addr hex> <count> [name]
  logs <count> bytes from XDATA <addr> (< 0x8000) on every captured field while recording; the log is stored in the
  recording's AVI header and decoded with tools/plog.py. The optional name labels the column.

Usage: poke.py spec.txt OUT.BIN        (OUT.BIN is normally F:/UPOKE.BIN in the card's root directory)
       poke.py --show UPOKE.BIN
"""
import sys

WHEN = {'boot': 1, 'rec': 2, 'both': 3, 'field': 4, 'frame': 8}
OP = {'write': 0, 'or': 1, 'and': 2, 'peek': 3, 'hdr': 4, 'xor': 5}
MAX_ENTRIES = (0x6BC0 - 0x6A04) // 4  # 111


def build(lines):
    out = bytearray(b'PK01')
    for n, raw in enumerate(lines, 1):
        line = raw.split('#')[0].strip()
        if not line:
            continue
        when, op, addr, val = line.split()[:4]
        a = int(addr, 16)
        if op == 'peek':
            n_ = int(val, 0)
            assert when == 'field' and 1 <= n_ <= 64 and a + n_ <= 0x8000, raw
            out += bytes([WHEN[when] | OP[op] << 4, a >> 8, a & 0xFF, n_])
            continue
        assert when != 'field', raw
        assert op != 'xor' or when == 'rec', 'xor only for rec entries: ' + raw
        if op == 'hdr':
            assert when == 'rec' and a + len(val) // 2 <= 0x8000, raw
            for i, b in enumerate(bytes.fromhex(val)):
                out += bytes([WHEN[when] | OP[op] << 4, (a + i) >> 8, (a + i) & 0xFF, b])
            continue
        vb = bytes.fromhex(val if len(val) % 2 == 0 else '0' + val)
        for i, b in enumerate(vb):
            out += bytes([WHEN[when] | OP[op] << 4, (a + i) >> 8, (a + i) & 0xFF, b])
    entries = (len(out) - 4) // 4
    if entries > MAX_ENTRIES:
        sys.exit(f'too many entries ({entries} > {MAX_ENTRIES})')
    return bytes(out + b'\0' * 4)


def show(data):
    assert data[:4] == b'PK01', 'bad magic'
    rw = {v: k for k, v in WHEN.items()}; ro = {v: k for k, v in OP.items()}
    for i in range(4, len(data) - 3, 4):
        f, hi, lo, v = data[i:i + 4]
        if f == 0:
            break
        print(f'{rw.get(f & 15, f & 15):5} {ro.get(f >> 4, f >> 4):5} {hi << 8 | lo:04X} {v:02X}')


if __name__ == '__main__':
    if sys.argv[1] == '--show':
        show(open(sys.argv[2], 'rb').read())
    else:
        data = build(open(sys.argv[1]).read().splitlines())
        open(sys.argv[2], 'wb').write(data)
        print(f'{sys.argv[2]}: {(len(data) - 8) // 4} entries, {len(data)} bytes')
        show(data)
