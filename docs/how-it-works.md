# How it works (short version)

## The firmware

- **CPU:** Syntek-class 8051 SoC (unbranded "D2EG19A1"), Keil C51 firmware, 16 banks of 32 KB, plus a TI TVP5150
  video decoder.
- **RAM boot:** the vendor bootloader loads `ADJUST.BIN` into RAM and runs it. Our image is the stock firmware plus:
  - a capture window of 704×288 at 1:1 in D1, with a higher bitrate target
  - a small **poke hook** that reads `UPOKE.BIN` and applies register writes at boot, at record start and every frame
    (it can also log registers into the AVI header for research, see `tools/poke.py` and `tools/plog.py`)
  - a 31 kHz audio header
- **Both fields:** the capture front end normally drops every second field. The hook's field gate keeps both, and the
  encoder gets each field (288 lines PAL, 240 NTSC) as its own frame.
- **Tearing fix:** the higher bitrate made a band of stale picture appear at the bottom (stock doesn't show it). The
  JPEG encoder overtook the capture DMA while rate control started coarse. Starting at the finest level (`56E6 = 9`)
  removes it.
- **Audio:**
  - The record path hard-codes 8 kHz, and its byte-rate registers turned out to be bookkeeping only.
  - The real sample clock is the divider pair **77B2/77B3**: rate = 496000 / (77B2 + 77B3). Stock is 0x1F + 0x1F,
    which gives 8 kHz.
  - The pair is set from UPOKE.BIN.
  - Changing the neighbouring pair 77C0/77C1, or the firmware's internal rate variables, causes heavy field drops.

## The converter

`tools/weave.py`:
- pairs each top field with the next bottom field into a full frame (PAL: it tells them apart by the widescreen
  signal line; NTSC: from the picture itself, see [NTSC](ntsc.md))
- skips stray fields
- hides the half-line and WSS rows at the edges
- removes the per-block audio click
- corrects the frame rate that the firmware writes into the file header (see [Limitations](limitations.md))

## The SD updater

The permanent install uses the DVR's own updater. It runs before any of this project's code (it's called at
bank10:8A5A, before the hook) and none of the patches touch it, so flashing Eachine's original `CRESFW.BIN` from the
patched firmware works the same as from stock.

The full story, with register maps, addresses and every experiment, is in [findings.md](findings.md) and
the raw lab notebook [lab-notes.md](lab-notes.md).
