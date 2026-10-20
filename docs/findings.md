# Findings

What this mini DVR is, how its firmware works, and what each experiment showed. Addresses are `CODE:xxxx` (common
code, flash 0x40–0x7FFF) or `bankNN:xxxx` (bank NN mapped at CPU 0x8000–0xFFFF, flash file offset NN × 0x8000 +
(addr − 0x8000)). Registers are XDATA addresses (memory-mapped peripherals at 0x7000–0x7FFF). The raw, chronological
notebook is [lab-notes.md](lab-notes.md).

## Hardware

| Part | Marking | Notes |
|---|---|---|
| SoC | LQFP-64 `D2EG19A1-2539` | Unbranded. 8051 core, Keil C51 firmware with "Copyright,Syntek,2007" strings and DSC-style debug strings. Embedded RAM (no external DRAM chip), JPEG encoder, SD host, audio ADC. 12.000 MHz crystal. |
| Video decoder | TI TVP5150AM1 | CVBS → BT.656, I2C address 0xBA, driven by the SoC's I2C master at 7842–7844. Video only. |
| SPI flash | Zbit ZB25VQ16C (`25VQ16CSJG`) | 2 MB. Firmware plus a menu-settings sector at 0x1DF000 (`KTNS`). |
| Audio front end | SGMicro SGM324 quad op-amp | Feeds the SoC's 12-bit ADC. Low-pass characteristic about 8–10 kHz. |
| USB-C | 6-pin | **Power only** (no D+/D−). There's no USB route into the firmware. |
| Jacks | 2 × 3.5 mm TRRS | AV in and AV out. CTIA AV pinout (video on the sleeve, ground on ring 2); OMTP-wired cables give no picture. Pictures: [pinouts](av-pinouts-light.png), [re-soldering to CTIA](av-rewire-light.png). |

There are no labelled debug pads. The firmware sets up a UART (bank11:B939; putchar CODE:57E2, 185 debug strings),
but its TX pin wasn't found by probing.

The firmware is the **Eachine ProDVR / HMDVR** firmware, version 2015.05.26.01.IR (built September 2016). Eachine's
`CRESFW.BIN` update file equals the flash minus the 64-byte header (it's in "RAM layout", see below) and stops at
1,700,506 bytes.

## Memory, boot and the RAM-boot trick

- The flash has a 64-byte header, then common code at 0x40–0x7FFF, then banks 1–16 at N × 0x8000. Bank calls go
  through stubs `MOV DPTR,#target; LJMP <switcher>` (for example CODE:0322 for bank 11). Keil's long-math helpers
  CODE:3B1A take a 4-byte inline constant after the LCALL.
- At boot the firmware (bank10:A1A1, called from 8A5A) looks for **`ADJUST.BIN`** in the card root. It loads the file
  to big memory at 0x300000, **deletes it**, stops the peripherals and jumps to CODE:0080. That code copies 64 × 32 KB
  pages down to the RAM the CPU executes from, then jumps to 0000. So a full firmware image runs from RAM until power
  off, and the SPI flash is never written. It's one-shot because of the delete. It's also what makes this project safe
  for non-experts.
- The image layout is page 0 = flash[0x40:0x8040], page N = flash[N × 0x8000 : (N+1) × 0x8000]: the same as
  `CRESFW.BIN`. `tools/mkram.py` makes it. The copy loop CODE:0080–00ED must stay unchanged, because it runs while page
  0 is being overwritten.
- There's no checksum on images. Patched flash images boot fine.
- **SD updater (permanent install):** when there's no ADJUST.BIN, bank10:A1A1 looks for **`CRESFW.BIN`**. It loads
  the file to 0x300000 with the same loader (and deletes it), then calls bank03:A0CC and bank16:CCA7. CCA7 copies the
  64 bytes at 0x2FFFC0 (the flash header, just below the file) to 3F52, then bank08:D5FD (stub 1A7A) erases, writes
  and verifies flash 0–0x1FF000 from 0x2FFFC0. On success A1A1 ends in an endless loop (switch off); on failure it
  shows an error and boots on. There's no checksum, magic or version check on the way, so a patched CRESFW.BIN of the
  vendor size goes through like the vendor's. Flash beyond the file comes from whatever is in big memory there; the
  vendor's own update has the same property. The whole path runs before the poke hook (8A5A → A1A1, hook later at
  8A7E), and no patch touches bank10:A1A1–A2E3, bank16:CCA7, bank08:D5FD or bank03:A0CC. The loader's delete hook
  (bank04:81E4 → DA00) keeps only UPOKE.BIN, so CRESFW.BIN is deleted as in stock. So the original CRESFW.BIN
  restores stock from the patched firmware. User reports (IntoFPV, 2016): the red LED blinks while writing; the file
  sometimes stays on the card and has to be deleted. Not yet run with a patched file.

## The poke hook (UPOKE.BIN)

Small 8051 routines in unused bank space (`hook/poke_b10.asm` boot, `poke_b13.asm` record start, `peek_b07.asm`
capture ISR / logger, `peek_b04.asm` delete skip):
- At boot they load `UPOKE.BIN` from the card root and keep it (the delete is skipped).
- They apply `write` / `or` / `and` entries at **boot**, at **record start** and on **every recorded frame**. They can
  also write bytes into the AVI header at record start.
- `field peek` entries **log** chosen XDATA bytes for every captured field into the AVI header's JUNK chunk.
  `tools/plog.py` decodes them.
- Switches in XDATA (cleared at boot):
  - 6BEC field gate (0 stock, 1 both fields, 2 other field)
  - 6BED log event mask
  - 6BEB / 6BEE / 6BEF delays used in experiments

This turned every experiment into "copy a 100-byte file to the card" instead of flashing.

## Video

### Pipeline
- The TVP5150 delivers BT.656. The capture front end (72xx registers, set up by bank06:AB63) DMAs one field into a
  capture buffer. Window: 7204/05 H start, 7206/07 V start, 7208/09 H end, 720A/0B V end. A strip-based JPEG encoder
  compresses from that buffer.
- Stock firmware **drops every second field**: the capture-done handler only accepts fields with 720D bit 0 = 1. Every
  mode is a single 288-line field scaled up: HD × 2.5 to 720 lines, D1/VGA × 5/3 to 480. There's no frame memory, so
  woven 576-line frames are impossible on this chip.
- Mode table bank05:959C on [53A2]: 1 VGA 640×480, 2 QVGA, 3 D1, 4 HD.

### Changes in the release (`clean704_q4`)
- **D1** captures **704×288 at 1:1**. The H start must be a multiple of 8 bytes. H start is 8 bytes (pixel 4) and the
  H end is 0x587, which centres the 704 active pixels.
- **HD** records 1280×576 (720 → 576 lines). VGA is unchanged.
- **Bitrate target:**
  - Rate control (bank13:8DFC, every 32 frames) compares the accumulated size with [571A]/[571E] and steps the level
    [56E6] from 1 (coarsest) to 9 (finest).
  - The target is w × h / q. q is 13 stock for modes 0/2/3; it's 4 here (bytes `74 0D` at 0x294DA / 0x2A6E5).
  - The result is about 35–45 KB per field at the finest quantiser.

### 50 fields per second
- Field gate = both fields (`boot write 6BEC 01`): each field becomes one AVI frame, 704×288 at about 49.9 frames/s.
  The DVR writes the measured rate into the header.
- `tools/weave.py` classifies each field by the **PAL WSS line** (row 0 of a top field: row 0 − row 1 difference about
  45 versus about 3 for bottom fields). It weaves top + next bottom into 720×576 (704 centred, BT.601), and replaces
  the WSS row and each field's last row (the PAL half line, bright in top fields and black in bottom fields) with the
  neighbouring row of the same field.
- **Dropped fields are hidden:** the DVR repeats the previous idx1 entry (same offset) for a field it couldn't encode.
  Count repeats, not frames per second.

### NTSC (experimental, untested on hardware)
- Capture setup bank06:8000 reads TVP5150 reg 8C: low nibble 3, 4 or 7 → [2D2D] = 288 lines, anything else → 240.
  The JPEG scaler ratio comes from capture height / output height (bank10:AF73 → 1EAC/1EAE → descriptor 1E7C/1E7E),
  so on the PAL build an NTSC field is stretched 240 → 288.
- `ntsc_d1`: the D1 case of the mode table (bank05:95E5) calls new code at bank05:DA00 (zero fill D9F5–FFFF, no
  references) that sets [5356]/[5358] = 704/240, then continues as before (8736, [536E] = 6800). Applied on top of the
  release; `tests/test_ntsc.py` checks in the emulator that only [5358]/[5359] differ from the release.
- `weave.py` finds NTSC field parity from the picture (half-line-shift comparison plus a Viterbi path). On PAL
  recordings with the WSS rows cropped it agreed with WSS on 903/903 fields; on the two long clips it slipped only
  inside the 65–73 s stutter.

### Tearing band (fixed)
- A band of stale picture at the bottom while panning, on our higher-bitrate builds only: stock recordings measure
  no band (`tools/bandcheck.py` on PICT0002/0034/0035 scaled to 288 lines: −2% to +2%).
  Each capture buffer gets field N, and the JPEG encoder reads it
  strip by strip. At coarse quality the encoder is faster than the capture DMA and overtakes it near the bottom.
- Stock rate control starts coarse (level 2 → 9 over about 4 s), so the band was worst at the start.
  `rec write 56E6 09` (finest from the start) removed it: the bottom strips are current in about 97% of frames
  during pans.
- Waiting for end of field and an "edge fix" were tried and dropped: they cost 10–12% repeated fields, and the bottom
  row is overwritten by the capture anyway.

### Live view
- TV-out (AV out) shows the live picture in VGA. In D1 with the changed window, the live view is not right (preview
  size per mode at [5360]/[5362], not fixed). Recording isn't affected.

## Audio

### What the firmware does
- **Record path** (bank13:CD4E…, at record start):
  - sets a ring buffer in big memory at 0x79AC00, size 0x2FFD0 (6 × 32760)
  - hard-codes [58FA] = 01 and [58FB/58FC] = 0x3E80 (16000 bytes/s)
  - calls bank11:9FCC through stub CODE:142C, which programs the audio engine (79xx): 7903–7905 from [58FA..FC],
    ring start/size in 1 KB units at 7920–7927, and so on, then starts it via 7900
  - a second path (bank13:92E8 → [5914], bank11:A893 → 7904/7944) writes the same byte rate
- **No audio interrupt.** INT0 (CODE:4D12) only handles bits 0/1/2/4/14 (tick, capture, TV-out, JPEG).
  bank13:BFED / CB08 poll the hardware write pointer **7928–792B** (little endian, readable) and write a 32760-byte
  `01wb` chunk once that much has built up.
- **Click per chunk:** every chunk starts with the 4 bytes `F8 7F 00 00` (0x7FF8, the chunk length) inside the sample
  data. That's a click every 2 s at stock rate. weave.py removes it.
- **Header frame rate:** at finalize the firmware computes µs per frame from the audio byte count at a fixed
  16000 bytes/s. With faster audio the header frame rate is too low by exactly (real audio bytes/s ÷ 16000). weave.py
  corrects it using the header's nAvgBytesPerSec.

### The real sample clock
- The bytes-per-second registers 7903–7905 / 7944–7946 are **not** the sample rate:
  - written mid-recording, they read back but change nothing
  - patched before the engine starts (latched from the start), they still change nothing
- The audio driver's rate switch (bank11:A893 on [5927]) writes one divider value to **77C0, 77C1, 77B2, 77B3**
  (bank11:A2C5/A2CA): 0x1F for 8/16/24/32/48 kHz, 0x22 for 22.5/44.1 kHz.
- Bisecting with pokes (pointer increments logged per field):

| 77C0/C1 | 77B2 | 77B3 | measured | video |
|---|---|---|---|---|
| 1F/1F | 1F | 1F | 8000 Hz (stock) | clean |
| 0F/0F | 0F | 0F | ≈16.5 kHz | 29% repeated fields |
| 0F/0F | 1F | 1F | 8000 Hz | clean |
| 1F/1F | 0F | 1F | 10785 Hz | clean |
| 1F/1F | 0F | 10 | 16003 Hz | clean |
| 1F/1F | 08 | 08 | 31007 Hz | clean |
| 1F/1F | 05 | 05 | 49611 Hz | clean for 12 s, then the audio writer falls behind and video breaks down |

- **Sample rate = 496000 / (77B2 + 77B3).** The record init rewrites the dividers, so the release re-applies them
  every frame from UPOKE.BIN. `audio_clk()` in mkpatch.py bakes them into bank11 (tested in the emulator, not on the
  device).
- What **not** to change, because both cause heavy field drops: 77C0/77C1, and the firmware's internal rate
  variables ([5927], [590E], [5914], [58FB]).
- The sample format stays 12-bit (low 4 bits zero) at every rate.

### Limits
- **Bandwidth:** relative to the 2–4 kHz level, the 31 kHz and 49.6 kHz recordings have the same curve in hertz:
  - about −14 dB at 8 kHz
  - −21 to −25 dB at 10 kHz
  - a flat noise floor (about −32 dB) from 12–14 kHz up

  The roll-off doesn't scale with the sample rate, so it's an analog filter (op-amp front end) plus the ADC/analog
  noise floor, not firmware.
- **Stereo:** the record path knows one stream (7902 = [58F9] | 4, a single ring). The driver's mode argument (bank11:93F5,
  from [3BD7], called from bank14) scales the byte rate for the playback side. The TRRS jack likely carries L and R,
  but the board seems to feed one ADC input. Stereo would need hardware changes plus an unknown second ADC channel.
- **Throughput:** about 62 kB/s of audio next to about 2 MB/s of video is fine. 99 kB/s (49.6 kHz) builds a backlog
  in the chunk writer.

## Open issues

- Long recordings showed about 30 s of repeated fields around the 1:00–1:30 mark. That happened in a 31 kHz recording
  and in a stock 8 kHz control, and not elsewhere in the same recordings, even with heavier video. The camera was
  moving and the cable may have been touched, which caused similar drops before. Not settled.
- Live view in D1 with the changed window.
- A permanent install with all settings built in, so UPOKE.BIN isn't needed either. The firmware itself can now go in
  through the SD updater (patcher step 5) or `tools/flash.sh`, but a build with the UPOKE settings baked in hasn't been
  made and tested. The SD-updater route itself hasn't been run with a patched file yet.

## Tools used

- flashrom + pico-serprog on a Raspberry Pi Pico, SOIC-8 clip: three identical reads before any write, and the
  settings sector is always preserved.
- Ghidra 12 headless with scripts in `ghidra/scripts` for the banked layout and Keil inline constants.
- `tools/d51.py` (bank-aware disassembler), `tools/xref.py`, `tools/regcensus.py` (register access map), and
  `tools/emu51.py` (enough 8051 to unit-test the hooks against a model of the DVR).
