# minidvr: better video and audio for a cheap FPV mini DVR

Custom firmware patches for the small FPV "mini DVR" sold as the **Eachine ProDVR** (and clones built on the same
board). It was reverse-engineered to record a Sony VX2100E (PAL) as well as this hardware allows.

| | Stock firmware | With this project |
|---|---|---|
| Video | one field per frame (288 lines) upscaled to 720×480 or 1280×720, 25 fps | **every field** (704×288 at 50 fields/s), woven into real **720×576 50i** on the PC, no scaling |
| Picture | off-centre, tearing band at the bottom when moving | centred capture window, finest JPEG quality from the start (no tearing band) |
| Audio | 8 kHz mono, a click once per 32 KB block | **31 kHz** mono (real sound up to about 10 kHz), clicks removed by the converter |

**It doesn't touch your DVR's chip.** The patched firmware is loaded from the SD card into RAM at power-on. If you
switch off and start without the file, you're back to the stock firmware. Nothing to brick.

## Quick start (no programming needed)

1. **Make the files:** open the patcher page (<https://eonflux7.github.io/open-minidvr-50i/>, or `docs/index.html` offline) and follow the steps:
   - download Eachine's official ProDVR firmware (`CRESFW.BIN`)
   - drop it on the page
   - save **ADJUST.BIN** and **UPOKE.BIN**

   The page runs entirely in your browser. It checks every byte it changes and refuses any other firmware version.
2. **Copy both files to the root of the microSD card** (not into a folder).
3. **Switch the DVR on and record in D1 mode.** Startup takes a little longer while it loads the file.
4. **Copy ADJUST.BIN again before every power-on.** The DVR deletes it when it loads it. UPOKE.BIN stays on the card.
5. **Convert the recordings on a PC** (next section). The raw files hold one field per frame and look squashed until
   they're converted.

### Converting recordings

You need [Python 3](https://www.python.org/downloads/) (tick "Add to PATH" when installing),
[ffmpeg](https://ffmpeg.org/download.html) on your PATH, and numpy:

```
pip install numpy
```

On Windows you can then drag an `.AVI` onto `tools/convert.bat`. Or run it yourself:

```
python tools/weave.py PICT0001.AVI PICT0001.mp4           # 720x576 interlaced (25i), for TVs and editing
python tools/weave.py PICT0001.AVI PICT0001.mp4 --bob     # 720x576 at 50p, smooth on computers and phones
python tools/weave.py PICT0001.AVI PICT0001.mov --prores  # ProRes 422 HQ + PCM audio, for editing
```

The converter:
- pairs each top field with the next bottom field into a full frame (it tells them apart by the PAL widescreen
  signal line)
- skips stray fields
- hides the half-line and WSS rows at the edges
- removes the per-block audio click
- corrects the frame rate that the firmware writes into the file header (details below)

## Limitations (measured, not guessed)

- **Mono only.** The AV jack is TRRS, but the board feeds a single audio stream to the chip, and the firmware has no
  second input channel. Stereo would need board surgery plus an undocumented second ADC input. For stereo, record the
  camera's audio separately and sync it in post; the DVR's own track makes a good sync reference.
- **About 10 kHz audio bandwidth.** The roll-off sits at the same frequency whether the chip samples at 31 kHz or
  49.6 kHz, so it's an analog filter on the board (op-amp front end) plus the noise floor of the 12-bit ADC. Higher
  sample rates don't add real highs.
- **Audio rate tops out at about 31 kHz.** The chip can sample at 49.6 kHz, but then the firmware's SD writer falls
  behind after about 12 s and starts dropping video fields.
- **Rates come in steps.** The sample rate is 496000 / (77B2 + 77B3), so the options are 31000 Hz, 33067 Hz, 49600 Hz
  and so on. There's no exact 32 or 48 kHz. Players and editors handle 31 kHz fine.
- **Long recordings can stutter for a while.** Two long test recordings, one at stock 8 kHz audio, both had about 30 s
  of repeated fields around the 1:00–1:30 mark. The camera was moving and the cable may have been touched. The cause
  isn't settled. It's not the audio rate and not the picture content.
- **The raw AVI isn't directly watchable:** it holds 704×288 fields, and its header frame rate is wrong, because the
  firmware computes the frame rate from the amount of audio at a fixed 8 kHz. Always run the converter.
- **Only D1 mode was tested** with the 50i settings. VGA is stock, and HD records 1280×576.
- **The picture is JPEG at about 35–45 KB per field (about 2 MB/s).** It's a strip encoder with no frame memory, so
  true 576-line frames are impossible on this chip. That's why the project records fields.
- **ADJUST.BIN is one-shot.** The vendor bootloader deletes it after loading. Making the patch permanent means
  flashing the SPI chip with a clip programmer (see `tools/flash.sh`). Only do that if you know what you're doing.
- **One firmware only:** Eachine ProDVR firmware 2015.05.26.01.IR (CRESFW.BIN of September 2016). Other versions are
  refused.

## How it works (short version)

- **CPU:** Syntek-class 8051 SoC (unbranded "D2EG19A1"), Keil C51 firmware, 16 banks of 32 KB, plus a TI TVP5150
  video decoder.
- **RAM boot:** the vendor bootloader loads `ADJUST.BIN` into RAM and runs it. Our image is the stock firmware plus:
  - a capture window of 704×288 at 1:1 in D1, with a higher bitrate target
  - a small **poke hook** that reads `UPOKE.BIN` and applies register writes at boot, at record start and every frame
    (it can also log registers into the AVI header for research, see `tools/poke.py` and `tools/plog.py`)
  - a 31 kHz audio header
- **50i:** the capture front end normally drops every second field. The hook's field gate keeps both, and the
  encoder gets each 288-line field as its own frame.
- **Tearing fix:** the band came from the JPEG encoder overtaking the capture DMA while rate control started coarse.
  Starting at the finest level (`56E6 = 9`) removes it.
- **Audio:**
  - The record path hard-codes 8 kHz, and its byte-rate registers turned out to be bookkeeping only.
  - The real sample clock is the divider pair **77B2/77B3**: rate = 496000 / (77B2 + 77B3). Stock is 0x1F + 0x1F,
    which gives 8 kHz.
  - The pair is set from UPOKE.BIN.
  - Changing the neighbouring pair 77C0/77C1, or the firmware's internal rate variables, causes heavy field drops.

The full story, with register maps, addresses and every experiment, is in [docs/findings.md](docs/findings.md) and
the raw lab notebook [docs/lab-notes.md](docs/lab-notes.md).

## Repository layout

| Path | What |
|---|---|
| `docs/index.html` | browser patcher (the patch and UPOKE.BIN are embedded) |
| `docs/patch.json`, `docs/UPOKE.BIN` | release patch (byte runs with their original bytes) and the settings preset |
| `tools/weave.py`, `tools/convert.bat` | field-to-576i converter |
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

## Command-line use and development

To make ADJUST.BIN without the browser:

```
python3 tools/mkrelease.py apply CRESFW.BIN /path/to/sdcard/ADJUST.BIN   # or a 2 MB flash dump instead of CRESFW.BIN
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

## License

MIT (see [LICENSE](LICENSE)) for the code and documentation in this repository. The DVR firmware itself belongs to
its vendor and isn't included. Use at your own risk: the RAM-boot route doesn't write to the DVR's flash, but the
flashing tools do.
