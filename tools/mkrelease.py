#!/usr/bin/env python3
"""Build the public release patch (docs/patch.json) and, optionally, an ADJUST.BIN from a user's firmware file.

The release never ships vendor firmware. patch.json lists the changed byte runs (RAM-image offsets, with the original
bytes they replace) between the stock firmware and the tested release build. docs/index.html applies it in the browser
to the vendor's own CRESFW.BIN (or a 2 MB flash dump) and saves ADJUST.BIN; this script does the same from the shell.

  mkrelease.py json  STOCK_DUMP.bin RELEASE.bin            -> docs/patch.json (maintainers)
  mkrelease.py apply CRESFW.BIN|DUMP.bin F:/ADJUST.BIN     -> ADJUST.BIN (users with Python)
"""
import hashlib, json, os, sys

RAM = 0x200000                 # ADJUST.BIN = 64 x 32 KB pages copied to the CPU's RAM (tools/mkram.py)
CRESFW_SIZE = 1700506          # Eachine ProDVR CRESFW.BIN (Sep 2016), = RAM image truncated
HERE = os.path.dirname(os.path.abspath(__file__))
JSON = os.path.join(HERE, '..', 'docs', 'patch.json')   # served with docs/index.html (GitHub Pages)


def to_ram(img):
    """2 MB flash image (64-byte header + pages) -> RAM image layout; CRESFW.BIN is already in RAM layout."""
    if len(img) == 0x200000 and img[:4] == bytes.fromhex('44c07003'):
        return bytearray(img[0x40:0x8040] + img[0x8000:])
    return bytearray(img)


def runs(a, b):
    out, i = [], 0
    while i < len(a):
        if a[i] != b[i]:
            j = i
            while j < len(a) and (a[j] != b[j] or (j + 1 < len(a) and a[j + 1] != b[j + 1] and j - i < 4096)):
                j += 1
            out.append([i, a[i:j].hex(), b[i:j].hex()])
            i = j
        else:
            i += 1
    return out


def make_json(stock, release, cresfw=None):
    a, b = to_ram(open(stock, 'rb').read()), to_ram(open(release, 'rb').read())
    p = runs(a, b)
    assert max(o + len(n) // 2 for o, _, n in p) <= CRESFW_SIZE, 'patch reaches past the end of CRESFW.BIN'
    meta = {'name': 'minidvr release 1 (poke hook v6, 704x288 D1, 31 kHz audio header)', 'ram_size': RAM,
            'cresfw_size': CRESFW_SIZE, 'patches': p}
    if cresfw:
        meta['cresfw_sha256'] = hashlib.sha256(open(cresfw, 'rb').read()).hexdigest()
    json.dump(meta, open(JSON, 'w'), indent=0)
    print(f'{JSON}: {len(p)} runs, {sum(len(n) // 2 for _, _, n in p)} bytes')
    embed(meta)


def embed(meta):
    """Put the patch and the UPOKE.BIN preset into docs/index.html so the page also works offline (file://)."""
    import base64, re
    page = os.path.join(HERE, '..', 'docs', 'index.html')
    html = open(page).read()
    upoke = base64.b64encode(open(os.path.join(HERE, '..', 'docs', 'UPOKE.BIN'), 'rb').read()).decode()
    html = re.sub(r'(<script id="patch" type="application/json">).*?(</script>)',
                  lambda m: m.group(1) + json.dumps(meta, separators=(',', ':')) + m.group(2), html, flags=re.S)
    html = re.sub(r'(<script id="upoke-data" type="text/plain">).*?(</script>)',
                  lambda m: m.group(1) + upoke + m.group(2), html, flags=re.S)
    open(page, 'w').write(html)
    print(f'{page}: patch + UPOKE.BIN embedded')


def apply(src, dst):
    meta = json.load(open(JSON))
    ram = to_ram(open(src, 'rb').read())
    if len(ram) == meta['cresfw_size']:
        ram += b'\xff' * (meta['ram_size'] - len(ram))          # CRESFW.BIN stops early; the rest is unused fill
    if len(ram) != meta['ram_size']:
        sys.exit(f'{src}: unexpected size {len(ram)} - not a ProDVR CRESFW.BIN or 2 MB flash dump')
    for off, old, new in meta['patches']:
        if ram[off:off + len(old) // 2].hex() != old:
            sys.exit(f'{src}: firmware differs at 0x{off:x} - different firmware version, NOT patching')
        ram[off:off + len(new) // 2] = bytes.fromhex(new)
    open(dst, 'wb').write(ram)
    print(f'{dst}: {len(ram)} bytes, sha256 {hashlib.sha256(ram).hexdigest()[:16]}...')


if __name__ == '__main__':
    if sys.argv[1] == 'json':
        make_json(*sys.argv[2:5])
    elif sys.argv[1] == 'apply':
        apply(*sys.argv[2:4])
    else:
        sys.exit(__doc__)
