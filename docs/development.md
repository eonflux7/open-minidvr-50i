# Development

## Repository layout

| Path | What |
|---|---|
| `docs/index.html` | browser patcher (the patch and UPOKE.BIN are embedded) |
| `docs/patch.json`, `docs/UPOKE.BIN` | release patch (byte runs with their original bytes, plus the extra `ntsc` runs) and the settings preset |
| `tools/weave.py` | converter: weaves the recorded fields into interlaced video (PAL and NTSC) |
| `tools/convert.bat`, `tools/convert.command`, `tools/convert.sh` | converter launchers for Windows, macOS and Linux (they offer to install what's missing) |
| `.github/workflows/windows-converter.yml`, `tools/windows-readme.txt` | builds the standalone Windows converter (PyInstaller + ffmpeg essentials) for each `v*` release |
| `tools/pinouts.py`, `docs/av-*.png` | AV cable pictures: TRRS pinouts (CTIA, OMTP, camcorder AV) and re-soldering to CTIA |
| `tools/banner.py`, `docs/banner-*.png` | README banner (dark and light versions) |
| `tools/mkpatch.py` | all byte patches (named sets), verified against the original bytes |
| `tools/mkrelease.py` | builds `docs/patch.json` from a stock dump and the release build; also applies it from the shell |
| `tools/mkram.py` | flash image to ADJUST.BIN (RAM-boot image) |
| `tools/poke.py`, `tools/plog.py` | UPOKE.BIN compiler, and decoder for register logs stored in recordings |
| `hook/*.asm` | poke/logger hook sources (sdas8051); `.ihx` are the assembled outputs used by mkpatch |
| `pokes/*.txt` | every UPOKE experiment; `release_50i.txt` is the shipped preset |
| `tools/d51.py`, `tools/xref.py`, `tools/regcensus.py`, `ghidra/scripts/` | 8051 disassembler, cross-references, register census, Ghidra scripts for the banked image |
| `tools/emu51.py`, `tests/` | small 8051 emulator and tests for the hook and patches |
| `tools/flash.sh`, `tools/dvr.layout` | flashrom + pico-serprog flashing that keeps the menu-settings sector |

No vendor firmware, flash dumps or recordings are in this repository. `patch.json` holds only the bytes that are
changed, plus the original bytes at those places so the patch can be verified.

## Command-line use

To make ADJUST.BIN without the browser:

```
python3 tools/mkrelease.py apply CRESFW.BIN /path/to/sdcard/ADJUST.BIN   # or a 2 MB flash dump instead of CRESFW.BIN
python3 tools/mkrelease.py apply CRESFW.BIN /path/to/sdcard/ADJUST.BIN --ntsc   # NTSC build (experimental, untested)
python3 tools/mkrelease.py apply CRESFW.BIN /path/to/sdcard/CRESFW.BIN   # permanent install via the SD updater
python3 tools/poke.py pokes/release_50i.txt /path/to/sdcard/UPOKE.BIN
```

`tools/mkpatch.py` holds every patch set used during development. Each one is a list of (offset, original bytes, new
bytes) applied to a 2 MB flash dump and checked against the original bytes. `tools/mkram.py` turns a patched dump
into an ADJUST.BIN. The tests need local files that aren't in the repository: `tests/test_release.py` needs the peek6 build in
`patches/`, and `tests/test_hooks.py` needs a sample AVI header in `samples/`.

**Note on reproducibility:** the release is hook revision 6 (`clean704_q4_peek6` + `release_31k`). The sources in
`hook/` have moved on since then: more logger events, plus experimental edge-fix and wait modes that are off by
default. So rebuilding peek6 from today's sources won't match the tested binary byte for byte. `docs/patch.json`
*is* the exact tested build, regenerated with `tools/mkrelease.py json STOCK_DUMP RELEASE_BUILD CRESFW.BIN`.
