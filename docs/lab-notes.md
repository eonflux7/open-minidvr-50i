# Mini DVR reverse-engineering — lab notes

> Raw, chronological working notes, kept as written (terse, with dead ends). For the organised summary see
> [findings.md](findings.md). File names like `patches/*.bin`, `dumps/`, `samples/` refer to local files that are not
> in the repository (vendor firmware and recordings).

_Last updated: 2026-10-16_

## Goal

Custom firmware for a generic FPV mini DVR (MJPEG AVI recorder, microSD, 3.5 mm AV in) used to record a **Sony VX2100E (PAL)**:

- **Proper PAL handling**: native 720×576 at the correct 4:3 aspect (or correct anamorphic 16:9), 25i/50 fields, no stretching
- **Higher quality**: higher MJPEG bitrate / quality at native resolution, and higher frame rate if possible (50p from fields)
- **Better audio**: currently 8 kHz mono; ideally 48 kHz, stereo if the hardware allows
- **Generic TRRS AV pinout**: the DVR expects the CTIA-style AV pinout, but many generic AV cables use the OMTP-style one (ground and a signal swapped between ring 2 and sleeve). Goal: accept both. **This is mainly a hardware problem**, because firmware can't move an analog ground. Options, simplest first:
  1. A CTIA↔OMTP swap adapter or cable (no mod)
  2. A small switch or solder jumpers on the jack lines (board mod)
  3. Route the alternate pin to the TVP5150's **second composite input** (it has AIP1A/AIP1B) and select it over I2C in firmware or with a button. This only covers the video line; ground still has to be on the right contact, so it can't fix every cable on its own.
  4. Automatic detection (measure the impedance or DC on ring 2/sleeve at power-up). Ambitious; needs extra analog switches.

  **Decision (2026-10-16): rewire the cable to CTIA.** No DVR mod. Options 2–4 are off unless needs change.

Current workaround: the 1280×720@25 mode gives the best bitrate but stretches the 4:3 PAL image to 16:9.

**Rule:** read-only until there is a verified backup of the flash. Never write to the DVR before that.

## Confirmed findings

### USB
- The DVR **never enumerates** on Windows: no device, no failed-descriptor error, no Kernel-PnP events.
- The board has a **6-pin power-only USB-C** connector (no D+/D−), so the USB route is a **dead end**.
- WSL2 has no USB bus by default. The WSL kernel has USB/IP, mass-storage, UVC, ACM and CH341/CP210x/FTDI/PL2303 modules. `usbipd-win` is **not installed** yet.

### Recordings (SD card, `DCIM\100DSCIM\PICTnnnn.AVI`)
- Video is MJPEG, 1280×720, **40.044 ms/frame (≈24.97 fps)**. One clip (PICT0003) is **720×480 at ≈29.15 fps**, with tiny ~6 KB frames (no signal, or the D1/NTSC mode).
- File layout:
  - RIFF AVI; a `JUNK` chunk pads the `movi` list to start at 0x7FF4.
  - Every chunk is **512-byte aligned**, and the gaps contain leftover buffer data. The firmware writes straight from DMA buffers.
  - Audio comes in **32,760-byte `01wb` chunks** (one 32 KB buffer) roughly every 51 video frames.
- Each JPEG frame has a COM segment containing `"NUL"`. The quantization tables follow the IJG pattern and **change per frame** (rate control).
- Audio is PCM s16le, 8 kHz, mono, but **the low 4 bits are always 0**, so it comes from a **12-bit ADC** (probably the SoC's built-in ADC, not a real audio codec).
- Some clips are heavily clipped (54% of samples at full scale), so the input level is too hot.
- There's no RTC: file timestamps are 2001-01-01 03:00 or 2020-01-01 00:0x.

### Board (PCB "V1.3")
| Part | Marking | Identification |
|---|---|---|
| Main SoC | LQFP-64, `D2EG19A1-2539` | **Unbranded / unknown.** No logo, no web hits. No external DRAM, so the RAM is embedded. |
| Video decoder | TI `5150AM1` | **TI TVP5150AM1**: CVBS to 8-bit BT.656. **Video only, no audio.** |
| SPI flash | "Z" logo, `25VQ16CSJG` | Probably **Zbit ZB25VQ16C**, 16 Mbit (2 MB) SPI NOR, SOP-8 (looks like 208 mil) |
| Op-amp | `SGM324 YTS14` | SGMicro SGM324 quad op-amp (probably the audio front end) |
| Power | 1S LiPo on `P1 BAT+/−`, slide switch, SOT-23-6 charger IC | |
| I/O | Two 3.5 mm jacks (probably AV in and AV out), microSD, 3 buttons K1–K3 | |

- There are **no labelled UART/debug pads**.
- The Allwinner F1C100s/F1C200s is **ruled out** (88-pin QFN, built-in TV decoder). The FPVault project targets the F1C200s, so it can't run on this board. It's only a reference, or an alternative hardware route.

## Implications for the goals (hypotheses)

- **PAL video:** the TVP5150 outputs full 720×576i50 BT.656. The SoC either scales this to 720p or crops/scales it for the D1 mode, so the decoder isn't the bottleneck. Whether native 720×576 at higher quality is possible depends on the SoC's JPEG encoder and the firmware's mode tables.
- **50p:** recording each field as a frame (720×288 at 50 fps, or line-doubled) needs the encoder to handle 50 JPEGs/s. That's unknown until the SoC is identified.
- **Bitrate:** limited by the encoder's quality tables and rate control, plus SD write speed. The per-frame DQT changes show that rate-control settings exist and might be tunable.
- **Audio:** 12-bit ADC. A higher sample rate is plausible in firmware. Stereo needs a second ADC channel physically wired from the jack, which is unknown (see next steps).

## Hardware for flash access

| Item | Purpose |
|---|---|
| Raspberry Pi Pico RP2040 (Type-C) | **SPI programmer** (`pico-serprog`, native 3.3 V) |
| CH341A kit with SOIC-8 clip | **Only the SOIC-8 clip and adapter board.** The black CH341A Pro board drives **5 V logic**, so it must not touch the 3.3 V flash unless modified. |
| Dupont jumper wires (F-F, 10 cm) | Clip/adapter to Pico wiring |
| 2.54 mm pin headers | Headers for the Pico |

Still needed if not already owned: a USB-C data cable, a soldering iron and solder, and a multimeter.

## Next steps

### While waiting for the parts
1. **Software prep** (needs approval at the time):
   - `usbipd-win` on Windows (winget) and `flashrom` in WSL (apt)
   - Download the `pico-serprog` UF2
   - **Check its pin mapping against the README**
2. **Mono/stereo continuity test** (multimeter, **battery disconnected**). Check whether the input jack's L and R contacts reach separate SGM324 inputs.
3. **Map the input jack** with the multimeter (battery disconnected): which contact (tip, ring 1, ring 2, sleeve) goes to ground, the TVP5150 input, the op-amp, and the AV-out circuitry. Also check whether TVP5150 input AIP1B is unused or connected. This is the basis for the TRRS-pinout goal.
4. **Leave the battery disconnected** for the flash work.
5. **Fix the audio clipping now**: a resistor divider, a lower source level, or both.
6. **More recording analysis** (no hardware needed):
   - Record a test clip from the VX2100E in each DVR mode (D1/VGA/720p).
   - Check for interlacing combs, field order, whether 720p is an upscale of 576 lines, and per-mode bitrate and quality tables.
   - Fix the aspect ratio in post (e.g. `ffmpeg -i in.avi -vf scale=960:720,setsar=1 …`) as an interim fix.

### Flash dump (when the parts arrive)
Pico wiring for `pico-serprog` (verified 2026-10-20 against stacksmashing main.c: CS=GP1, SCK=GP2, MOSI=GP3, MISO=GP4; upstream has no prebuilt UF2):

| Pico pin | Flash chip pin |
|---|---|
| **GP1** (Pico pin 2) for upstream stacksmashing build; GP5 only for forks that use it (e.g. Riku_V/libreboot) — check the build | 1 (CS) |
| GP4 | 2 (DO/MISO) |
| 3V3 | 3 (WP) |
| GND | 4 |
| GP3 | 5 (DI/MOSI) |
| GP2 | 6 (CLK) |
| 3V3 | 7 (HOLD) |
| 3V3 | 8 (VCC) |

Pin 1 is the corner with the **dot** on the chip; line it up with the clip's red wire.

Procedure:
1. Flash `pico-serprog` onto the Pico, then attach **only the Pico** to WSL with usbipd.
2. Read three times and compare:
   ```bash
   flashrom -p serprog:dev=/dev/ttyACM0 --flash-name
   flashrom -p serprog:dev=/dev/ttyACM0 -r dump1.bin   # x3: dump2, dump3
   sha256sum dump*.bin
   ```
   **Never use `-w` or `-E`** until the backup is verified and stored off-device.
3. If the ID or the dumps are unstable, the main chip is probably fighting over the bus. Fixes: retry or try the other slide-switch position, hold the SoC in reset, or lift flash pin 8 / remove the chip.

### After the dump
1. Analyze the image: `binwalk`, entropy, strings, headers and SDK names, to **identify the SoC vendor and architecture**.
2. Load it in Ghidra with the right architecture and load address. Find:
   - the mode tables (resolution, fps)
   - the JPEG quality and rate-control settings
   - the AVI writer
   - the audio setup (8000 Hz, ADC configuration)
3. Look for checksums or signatures over the image before attempting any patch.
4. Try small, reversible patches first (e.g. the audio sample rate or a quality table), always with the verified backup ready to restore.

## Files
- Analysis scripts: `tools/avi.py` (RIFF/JPEG markers), `tools/idx.py` (idx1/interleave/alignment), `tools/dqt.py` (per-frame DQT + COM). Run with `python3 -I tools/<script> <file.AVI>`.
- Board photos: `D:\DCIM\163___10\IMG_2339.JPG` (top), `IMG_2342.JPG` (bottom).

## 2026-10-20 build
- Installed in WSL: flashrom 1.6.0, binwalk, arm toolchain. Pico SDK 1.5.1 in `fw/pico-sdk`.
- Built upstream pico-serprog: `fw/pico-serprog/build/pico_serprog.uf2` (copy in project root and `%USERPROFILE%\Desktop`). Pins: CS=GP1, SCK=GP2, MOSI=GP3, MISO=GP4.
- CMake 4.x needs `export CMAKE_POLICY_VERSION_MINIMUM=3.5` to build SDK 1.5.1.
- Still to do: user installs usbipd-win on Windows (admin PowerShell: `winget install --exact dorssel.usbipd-win`).
- 2026-10-20: Pico soldered (holes 1-6 + 35-37), firmware flashed, usbipd installed; Pico = busid 2-1 (2e8a:000a, COM5) → `usbipd attach --wsl --busid 2-1` after each replug. No-chip test OK: flashrom sees "pico-serprog" (use sudo or relogin for dialout). Needs a USB-A→C data cable (C-C didn't work).

## 2026-10-20 FLASH DUMPED ✅
- 3 reads identical, sha256 3a07d8df9a7aee80d131866d7ac9970712325fd5350dae1e9f992ff089596eee, 2 MiB (SFDP chip, 2048 kB). Files: `dumps/dump{1,2,3}.bin`; off-device copy `%USERPROFILE%\Documents\minidvr_flash_backup\`.
- Board read in-circuit with battery still soldered, switch OFF (measured 0 V on flash VCC), WP/HOLD left unconnected. ~20 s per read at spispeed=1M.
- Content: entropy 6.57, data up to 0x1ff000. Strings: "BISStall", "SPI update OK", "2015.05.26.01.IR", "ulVceBusyMarker", "Dsc Firmware [%s]", JPEG HW messages → DSC-class SoC firmware (vendor TBD: Sunplus/iCatch/Generalplus suspects).
- Next: binwalk/strings, identify CPU arch + load address, find audio sample-rate config.

## 2026-10-20 Firmware analysis (Ghidra 12.1.4 headless, project ghidra/proj/minidvr)
- CPU: **8051**, Keil C51, chip vendor **Syntek** ("Copyright,Syntek,2007"). Firmware ver 2015.05.26.01.IR, built Sep 20 2016.
- Layout: file 0x00-0x3F header (44c07003 0000ffff ff8c0502 f7102350, no simple checksum match yet); CODE 0x0000-0x7FBF = file 0x40-0x7FFF (common); banks 1..16 = file N*0x8000, each mapped at CPU 0x8000-0xFFFF. Bank calls go through common stubs `MOV DPTR,#target; LJMP <bank switcher>` (e.g. CODE:1546 → bank11:93f5 via 0x0322). Unused bank space contains stale copies of common code (ignore).
- Keil helper CODE:3b1a takes 4-byte inline constant after LCALL (handled by scripts/FixInlineConst.java). Must disable "Non-Returning Functions - Discovered" analyzer.
- Scripts in ghidra/scripts: SetupBanks, SeedFuncs, FixInlineConst, Decomp, ListRange, Callers, NoRetList. Rebuild: see import cmd in session (BinaryLoader, 8051:BE:16:default, -preScript SetupBanks.java banks, post SeedFuncs+FixInlineConst, then a 2nd -process pass with FixInlineConst).
- **Audio driver bank11:93f5** supports 8000/16000/24000/32000/44100/48000 Hz; divider = 8,000,000/rate → XDATA 1F4C; mode (R7, 0..3) scales bytes/tick (5914/5915 = rate/128,/64,/32,/16 in 8.8 fixed). Rate read from XDATA long 0x5AB9.
- **Record init bank11:bbaf** (stub CODE:0b8c): hard-codes 8000 → [590E],[5927] (inline consts at bank11:bbb5 and bbbf, file 0x5BBB5/0x5BBBF), copies to [5AB9], sets reg 0x7766|=0x80.
- AVI writer bank11:8000: nSamplesPerSec from bank11:876c (`7F 40 7E 1F` = 8000, file 0x5876C); nAvgBytesPerSec constant 16000 at bank11:8462 (file 0x58462); bank11:9034 also loads 8000 (strh). bank13:930c sets [5927]=8000 (other path).
- SD updater exists in common code (strings at CODE ~0x190-0x230): looks for UPDATE.TXT, ADJUST.BIN, CRESFW.BIN. TODO: reverse it to learn image checksum/format before any patch.

## 2026-10-20 Updater + AVI audio fields
- Bank switchers CODE:0200 + 0x1d*(N-1) write N to XDATA 0x7000 → bank N = file block N (confirmed).
- SD updater: bank10:a1a1 checks ADJUST.BIN (loads into RAM and jumps to reset?) then CRESFW.BIN. CRESFW handler bank16:cca7: reads 64 B at file offset 0x2FFFC0 (or 0x3FFFC0) into shared buffer 0x3F52, then flash routine bank08:d5fd (stub CODE:1a7a) erases/writes/verifies 0..0x1FF000 (last 4 KB, blank in dump, is preserved). No checksum/magic check found in the write loop; trailer purpose unclear. Not reversed further: clip+flashrom is the write path, so the boot ROM's behaviour is what matters.
- AVI strf build (bank11 ~0x8442): 1FFE tag, 2000 nChannels=1 (const at bank11:844a `7F 01 7E 00`), 2002 nSamplesPerSec (bank11:876c 8000), 2006 nAvgBytesPerSec (bank11:8462 `7F 80 7E 3E` = 16000), 200A nBlockAlign=2 (bank11:8473). strh dwRate [1FF9] = 8000 at bank11:9034.
- Candidate 16 kHz test patch (file offsets): 0x5BBB5 & 0x5BBBF `00001F40`→`00003E80`; 0x5876C `7F407E1F`→`7F807E3E`; 0x58462 `7F807E3E`→`7F007E7D`; 0x59034 `7F407E1F`→`7F807E3E`. Unknown: bank13:930c also sets [5927]=8000.
- 2026-10-20: FLASHED patches/audio16k.bin (sha 3c854e0f…a32a) via clip; flashrom VERIFIED + independent read-back match. Awaiting boot/record test. Restore: flashrom -p serprog:dev=/dev/ttyACM0:115200,spispeed=1M -w dumps/dump1.bin
- audio16k result: header OK but capture stayed 8 kHz (bank13:92d5 is real record start, hard-codes [5914]=3E80 and [5927]=8000). Built patches/audio16k_v2.bin adding 0x692E9/0x692ED and 0x69312.
- Built patches/audio32k.bin (recommended next) and audio48k_trunc.bin ([5914] is 1 byte; driver truncates 44.1/48k values: 375->0x77). Header nAvgBytes patch now 6 bytes incl R5 (>65535).
- 2026-10-20: FLASHED patches/audio32k.bin (sha ef7defbf…4236), VERIFIED + read-back match. Awaiting record test.

## 2026-10-20 Audio dead end (for now) + video quality
- audio32k flashed: header says 32k but data still 16000 B/s (8 kHz capture). All firmware rate vars ([5927],[5AB9],[5914] ticks) patched in bank11+bank13; capture clock unaffected → real ADC clock is set elsewhere (unknown 0x79xx/0x77xx reg) or fixed in HW. a893 switch on rate only sets 77C0/77C1/77B2/77B3 = 0x1F (48k family) or 0x22 (44.1k family).
- DVR = Eachine ProDVR/HMDVR: ext/prodvr_gdrive/x/CRESFW.BIN (Sep 2016) is identical to our dump except: no 64-byte header (block 0 shifted -0x40) and one string block @0x50ec. No sibling firmware with other audio rate found.
- Video: JPEG q-table = Annex-K base × n/8, n∈{2,3,4,5,6,7,8,12}; rate control bank13:8dfc every 32 frames compares accumulated size to [571A] (lower) / [571E] (upper, ×1.25), steps level [56E6] (1..9), applies via CODE:13fc. Target set by bank13:d971 (stub CODE:08a4): lower = ([56E2]/[56E4]) × q, q clamped 1..50. Callers bank05:94b2/a692 set q=13 for modes 0/2/3, q=4 for mode 1 (bytes `74 0D` at file 0x294DA, 0x2A6E5).
- NOTE: "q" at 0x294DA/0x2A6E5 is a DIVISOR: rate-control target bytes/frame = w*h/q. Lower q = higher bitrate.
- Built patches/video_q20.bin, video_q26.bin (from ORIGINAL dump → audio back to correct 8 kHz).
- NOTE: rb'' + re.escape bug bit me once; use plain b'' with re.escape.

## 2026-10-20 New goal: native PAL 576i50 + audio-block RE
- User goal: 720x576, 50i, no scaling (VX2100E PAL source); bitrate secondary. Combine audio+video experiments per flash session.
- Measured: 720p (PICT0035) and D1 (PICT0002 720x480@25fps) both = ONE field (~288 lines) upscaled; no field weave/combing. Woven 720x576 unlikely (no DRAM; strip encoder). Proposed target: 720x288 @ 50 fps (every field as its own frame, 1:1), re-weave in post. Throughput lower than current 720p.
- 0x88000+ is a resource directory (offset/len table at 0x88400), not presets. Menu labels are bitmaps. bank08 "288" constants = FAT driver, not video. AVI biWidth/biHeight written as 0 initially (filled at finalize).
- tools/regcensus.py → analysis/regs.txt: peripheral blocks 70xx(bank sel) 71xx(SPI) 72xx 73xx(424 writes, banks 2/6/7/8/9) 74xx 75xx 76xx 77xx(system) 78xx 79xx(audio engine, banks 7/11/13) 7Cxx 7Exx(523 writes).
- Pending no-clip tests for user: (1) play PICT0035 (32k header) on the DVR itself → does DAC speed follow header? (2) record VX2100E motion clip in each menu resolution.

## 2026-10-20 mode test clips (samples/modes/t2..t4, recorded on audio32k fw)
- VGA=640x480, D1=720x480, HD=1280x720, all ~24.9 fps, audio header 32000 (still 8k capture).
- Row-sharpness periodicity (JPEG 1/8 harmonics masked): all three modes show period-5-row pattern
  (peak 0.40 c/row) => single 288-line field upscaled: HD x2.5, D1/VGA x5/3. No combing (no field weave).
- Horizontal: HD shows 0.469 c/col (720->1280, 16/9). D1/VGA inconclusive (D1 weak 1/18 peak).
- Target remains: D1 path with vertical scale 1:1 (288 rows) and 50 fps (both fields).

## 2026-10-20 mode/size RE
- Keil init table at file 0x2A8C: XDATA 6146/6148 = 640/480 defaults; 596-byte JPEG header -> XDATA 4640 (SOF h/w at 46CD/46CF).
- SOF writer bank16:D901 (stub CODE:04B4) <- bank13:C1B0 with w=[56E2], h=[56E4]. bank05:AEB5 copies [5356]/[5358] -> [56E2]/[56E4].
- Mode switch bank05:959C on [53A2]: 1/default=640x480 ([536E]=5C00), 2=320x240 (3400), 3=D1 720x480 (6800), 4=HD 1280x720 (7800).
  [54CF]=5 (modes 1-3) / 6 (4, default). Size handed to bank10:A30C (stub 04F6), A656 (07DE), C330 (07EA).
- bank05:9761 sets secondary size [5360]/[5362] per mode (preview?): HD 640x360, etc.
- Tools: tools/d51.py (8051 disassembler, bank aware), tools/xref.py (callers incl. bank stubs).
- Built patches/size_test1.bin (sha 19c63a9a...365f) from ORIGINAL dump: D1 height 480->288 (0x295F1 E0->20),
  HD height 720->576 (0x29619 D0->40). Audio stock 8k. Not yet flashed.
- FLASHED size_test1 (2026-10-20) with chip's own settings sector 0x1DF000 preserved (VERIFIED). Pre-flash chip read saved: dumps/pre_size_test1_chip.bin.
- SETTINGS BLOCK is at 0x1DF000 (magic "KTNS"), NOT 0x1FF000. DVR rewrites it on menu changes; preserve it when flashing.
  Diffs after user menu changes: +0x12..13, +0x1A, +0x24, +0x28, +0x53.

## 2026-10-20 size_test1 RESULT (samples/size1: hd.avi d1.avi vga.avi)
- D1 -> 720x288 file + SOF + AVI header all 720x288; NO vertical scaling pattern (0.40 peak gone) => 1:1 field lines. SUCCESS.
- HD -> 1280x576: 0.40 peak gone, odd/even row asymmetry 0.052 (x2 line doubling). Scaler follows [5356]/[5358].
- VGA unchanged (0.40 peak, x5/3). All ~24.9 fps, audio 8 kHz.
- AV OUT live preview: patched modes show picture in top 60% (D1) / 80% (HD) + garbage/green below => preview reads
  encoder buffer assuming old height (cosmetic). Preview showed FULL scene => scaled, not cropped.
- D1 horizontal: weak 1/18 c/col peak persists (possible slight horizontal resample); unresolved.
- Next: 50 fps (capture both fields); fix preview height; ([5360]/[5362] per-mode preview size at bank05:9761?).

## 2026-10-20 capture front end (72xx) + field hunt
- Interrupt INT0 CODE:4D12: status 7710-13 & enable 7724-27; bit0 = system tick (+USB check, counter [5229]); bits 1,2,4,14 -> bank07 B222/B6E8/B26E/9E43.
- TVP5150 driver: I2C helper [61F7]=0xBA addr,[61F8]=reg,[61F9]=val; write bank05:B828 (stub 065E), read 0664. Init table XDATA 5C42
  from Keil init record at file 0x1FBF (58 5C42): 7F=00 03=0F 04=00 15=10 0D=47 16=8C 11=02 12=00 13=02 14=00 17=00 18=3F.
  Reg 0F not written (default: pin24=VSYNC per field, pin23=GLCO). Output = BT.656 embedded sync. Datasheet: ext/tvp5150/t.txt.
- Capture window setup bank06:8000 (stub 0EEC; R7 type -> [20F0]); reads TVP reg 8C (std). Types 0 (8039) / 1 (81EF): H start
  [2D23]=0x20, H size [2D2B]=0x558 (1368 B = 684 px -> scaled to 720!), V start [2D25]=0, V size [2D2D]=0x120 PAL / 0xF0 NTSC.
  Type 2 (83A3): fixed 240 lines, [2D21]=flag. Registers written bank06:AB63: 7204/05 Hstart, 7206/07 Vstart, 7208/09 Hend,
  720A/0B Vend, 720C bits, 7220 bits0-1=[2D21] (mode?), 7200/01=[2D1F/20], 728A=[2D22], 728C/D, 72B0-2. [2D21]=1 -> 7270=0032.
- Built patches/stack_test.bin (sha e7812def...b314) from ORIGINAL: PAL capture height 288->592 (both paths), D1 -> 720x592 via
  mode-2 slot (95B0 JZ->95B9). Hypothesis: frame-based line counter => field1 / gap / field2 stacked. Not flashed.
- FLASHED stack_test (settings preserved, VERIFIED). Pre-flash chip: dumps/pre_stack_test_chip.bin
- stack_test RESULT: VGA looked normal (window probably applied on mode change); selecting D1 froze DVR instantly (black AV OUT,
  no buttons), hangs every boot (saved mode D1). => capture line counter restarts per field / window > field never completes.
- Frame gate ISR bank07:9E43 (INT0 bit14, stub 1ADA): skip unless 720D.7=1 (+[5639] skip-once, [552A] countdown, [5529] bits);
  at end if 720D.7==0 -> invalidate slot [246C], set [5639]=1. Interpreted as 720D.7 = field ID => keeps odd fields only.
- Built patches/fields50_test.bin (sha bdc00b73...1aad) = size_test1 + NOP JNB at 0x39E49 + SJMP at 0x39F4E. Not flashed.
- FLASHED fields50_test (settings preserved, VERIFIED). Pre-flash chip: dumps/pre_fields50_chip.bin
- fields50_test RESULT (samples/f50/d1.avi): still 25 fps (338 fr / 13.5 s), consecutive still frames 0 vertical shift (same field).
  Gate ISR is NOT the decimator; hardware delivers one field per frame. Harmless (1 repeat at frame 3 also in test1).
- Settings block 0x1DF000: +0x23 = Size menu (0 VGA, 2 D1, 3 HD); +0x12/13 look like file counter.
- Capture setup also: 7230=[2D2F]*8+7, 7232=[2D30]*2+1, 7231=7, 7233=1 (CF19); [2D2F]/[2D30]=0. 728C/D=[2D35]/[2D34]=0x47.
  720C: bits 3,5,6 cleared, bits0-2=[2D31]&7, bit4 set. 7220 bits0-1=[2D21]; [2D21]=1 -> 7270/71 = 32 00 else 00 02.
  720D.2 busy-waited (bank06:D429). Candidates for field select: 720C bits 3/5/6, 7220/[2D21], 7270, 7232.
- Built patches/capmode1_test.bin = fields50_test + 7220 low bits=1 + 7270/71=32 00 (bank06:ABCB, ABDA). Not flashed.
- 2026-10-20: user reversed clip once (heat); DVR + Pico + chip verified OK afterwards. FLASHED capmode1_test (VERIFIED).
- capmode1_test RESULT (samples/cap1): green vertical stripes = YCbCr read as raw sensor data; still 25 fps. [2D21]/7220=1 is raw
  input format, 7270=32 00 no fps effect. DVR currently on this broken-picture image.
- Built patches/c720_test.bin = fields50_test + 720C bits 3,5,6 set (bank06:ABB0, B4B0 ANL #97 -> ORL #68). Not flashed.
- FLASHED c720_test (VERIFIED).
- c720_test RESULT (samples/c720): every frame solid Y=U=V=255 (no input data), still 25 fps (360 fr / 14.45 s).
  => 720C bits 3/5/6 (some combination) blank the data; frame cadence is sync-driven and stays 1 field/frame even with
  blank data, so none of these bits enables every-field capture. DVR currently on this blank image -> needs reflash.
- Remaining blind suspects: 7200 bit4 (differs type0 0x12 vs type1 0x02), 7201=0x2C, 7230-7233, 728A, 728C/D, 72B0-2.
- FLASHED width720 = size_test1 + full 720 px capture width (VERIFIED).
- width720 RESULT (samples/w720): works. Horizontal 1/18 resample peak gone => 720 px 1:1. Picture spans ~cols 5..711:
  col 0 bright artifact, cols 1-4 black, last ~16 cols black (analog blanking edge; stock cropped+stretched it). 25 fps, 0 errors.
  CURRENT DVR STATE: width720 (D1 = 720x288 1:1 both axes, HD 1280x576, VGA stock, audio 8k).
- User: edges glitchy (top green = PAL WSS line 23 data, right black band, left bright col). Bitrate: D1 16 KB/fr vs HD 50 KB/fr
  (target ~ pixel count x q). Capture HW has no own firmware (fixed logic); only TVP5150 is programmable.
- Built patches/clean704_q40.bin = size_test1 + capture H start 12 B / size 1408 B (704 px), D1 704x288, q 13->40 (D1+HD). Not flashed.
- FLASHED clean704_q40 (VERIFIED).
- clean704_q40 RESULT: colours Y/C swapped (H start 12 B bad); 13.6 KB/frame, quant DC mostly 32 (coarser). q is a divisor:
  target = w*h/q bytes/frame. Luma DC quant observed: HD 8-16, D1(q13) 16-32. Levels n/8 x AnnexK, n in {2..8,12,16}.
- Built patches/clean704_q4.bin = size_test1 + H start 16 B (px 8) + H size 704 px + D1 704x288 + q=4. Not flashed.
- FLASHED clean704_q4 (VERIFIED).
- clean704_q4 RESULT (samples/q4): colours correct, 704x288, 24.95 fps, 0 errors, 33.7 KB/frame (840 KB/s), luma DC quant 4
  on 646/825 frames (= finest level n=2, saturated; target 50 KB not reachable without finer tables). Left edge clean; right ~8
  cols black (picture in 720 capture actually spans cols 5..703, not 711). H start 8 B (px 4) would leave 1 dim left + 4 black right.
  CURRENT DVR STATE: clean704_q4.

## 2026-10-20 fast flash + SD poke hook
- tools/flash.sh: fast flash (--flash-contents dumps/chip_current.bin, layout tools/dvr.layout excludes settings sector
  0x1DF000, --noverify-all, SPEED default 12M). chip_current.bin = last verified image (clean704_q4).
- File API: CODE:0E3E (bank04:8000) = look up + LOAD whole file into big memory by first letter of name:
  C*/A* -> 0x300000, U* -> 0x7FFE00 (UPDATE.TXT = date/time setter, handler bank13:A03B). CODE:0CEE = card ready.
  Big memory: 8 MB, 32 KB pages via 7008 (lo) / 7009 (hi), visible at XDATA 0x8000-0xFFFF (page = addr>>15).
  CODE:0562 (bank13:C7AF) file transfer: [2448]=offset, [244C]=buf gptr, [244F]=len. Math: 30B4 = divide (op 0F), 30C0 = multiply (0A).
- Firmware has UART printf (putchar CODE:57E2, SBUF) + 185 debug strings; TX pin not located.
- Hook (hook/poke_b10.asm, poke_b13.asm; sdas8051): boot hook bank10:DA00 (from 8A7D, was LCALL A517) loads UPOKE.BIN
  (<=512 B) via 0E3E -> window page 0xFF -> copies to XDATA 0x6A00 (RAM self-test 0x6BFF), applies "boot" entries;
  record hook bank13:E800 (from C203, was MOV R7,#1/RET) applies "rec" entries. Format PK01 + [flags][hi][lo][val].
  tools/poke.py builds files from text specs in pokes/. Built patches/clean704_q4_hook.bin (sha 98985a63...eeb2). Not flashed.
- Test file on card: UPOKE.BIN = pokes/test_bitrate.txt (rate target 8 KB/frame at record start).
- FLASHED clean704_q4_hook via tools/flash.sh (6 s, VERIFIED; independent 12M read-back matches).
- NOTE: the U*-file loader DELETES the file after loading (UPDATE.TXT behaviour) -> UPOKE.BIN is one-shot per power-on
  session (RAM buffer persists until power off). Copy it again for every test session.

## 2026-10-20 hook v2: read-back log + persistent UPOKE.BIN
- AVI header is built at record start (bank13:C1DB -> bank11:8000) in big memory 0x7D0000 (window page 0xFA) via
  CODE:0562 = copy to big memory (R4-R7 = big addr, R1-R3 = src gptr, [244F] = len); flushed to the card at stop
  (bank02:D38C, [217F]=0x7D0000). JUNK chunk at file 0x14A, body 0x152..0x7FF3, all zeros -> log space.
- Field ISR bank07:9E43 ends at 9F65 (LCALL 83D8 = re-arm capture: 720C bits5/6 -> bit5, then RET); all paths go there.
  Ring: A89E -> [54DB] write idx, [5535] slot, slot table 54ED, next capture address [246D-F] -> 72DD/72DE/72DF.
- File loader bank04:8000 deletes EVERY loaded file at 81E3 (LCALL 1066), not only U*.
- hook/peek_b07.asm (bank07:DA00, from 9F65): per-field logger. hook/peek_b04.asm (bank04:DA00, from 81E3): skip delete
  for name ptr 01:6BF0 (UPOKE.BIN only). poke_b13.asm: + loginit (writes "PLOG" header at file 0x160, arms 6BE0=5A).
  poke_b10.asm: clears 6BE0 at boot. State XDATA 6BE0-6BE4. Spec lines: `field peek <addr> <count> [name]`.
- tools/emu51.py (mini 8051 emulator) + tests/test_hooks.py: all checks pass (bounds, window/IE restore, disarmed cases).
- tools/plog.py decodes the log. pokes/peek_capture.txt = ring/capture state (36-byte records, ~18 s of fields).
- Built patches/clean704_q4_peek.bin (sha 87fb1bf6...bc4b) = clean704_q4 + HOOK2. Not flashed.
- Card F: has UPOKE.BIN = pokes/peek_capture.bin.
- FLASHED clean704_q4_peek via tools/flash.sh (6 s, VERIFIED; independent read-back matches). CURRENT DVR STATE.
- peek1 RESULT (samples/peek1/PICT0015.AVI): recording fine, UPOKE.BIN NOT deleted (nodel works), but JUNK all zeros.
  Cause: big-memory window has separate pages: 7008/09 = READ page, 700A/0B = WRITE page (CODE:00A2 copy loop reads and
  writes the same DPTR with different pages; C7AF/524F writes via 700A). Logger read the JUNK check via 7008 but wrote
  through whatever 700A held (stray 36-byte records into an unknown page; no visible harm).
- Fixed: peek_b07/poke_b13 set + restore all four (7008-700B); emu51 models separate read/write pages; tests pass.
  Built patches/clean704_q4_peek2.bin. Not flashed.
- FLASHED clean704_q4_peek2 (VERIFIED, read-back matches). CURRENT DVR STATE.
- peek2 RESULT (samples/peek2/PICT0016.AVI): PLOG header written correctly (loginit + 700A write page OK), 0 records:
  the bank07:9F65 (INT0 bit14 frame-gate, 9E43) hook never logged during recording (matches fields50: that gate has no
  effect). INT0 is the only interrupt (vector 0003 -> 4D12). Sub-handlers via stubs (all bank07, switcher 02AE):
  1ACE bit4 -> B26E, 1AD4 bit1 (+720D.0) -> B222 (bumps [1EE1], ring/gate, LJMP 9ACD), 1ADA bit14 -> 9E43, 1AE0 bit2 ->
  B6E8; bit0 inline = system tick [5229] (32-bit). Firmware SP = 0x5F (CODE:416D).
- Hook v3: wrappers ev1-ev4 at bank07:DA00/DA09/DA12/DA1B log (marker A0+ev) then LJMP to handler; stubs retargeted
  (2 bytes each in common code); 9F65 back to stock. Counters 6BE5-6BE8 always count; loginit snapshots 6BE0-6BEF to
  6BC0 and writes it into the "PLG2" header (record twice: 2nd file shows what happened in the 1st). Entry area now
  0x6A04..0x6BBF (111 entries). pokes/peek_irq.txt (28-byte records). Tests pass. Built patches/clean704_q4_peek3.bin.
  Card: UPOKE.BIN = peek_irq.bin. Not flashed.
- FLASHED clean704_q4_peek3 (VERIFIED, read-back matches). CURRENT DVR STATE.
- peek3 RESULT (samples/peek3/PICT0017/18): LOGGER WORKS (1155 records = ~11.5 s each). Per frame: ev1 (bit4, B26E)
  twice = every field (VSYNC), 720D bit0 = field id; ev2 (bit1, B222) once = only when 720D.0=1 (dispatcher 4DB3 gate =
  the 25 fps field decimation!); ev4 (bit2, B6E8) once (likely JPEG done); ev3 (bit14) never. D1 capture dest 72DD-DF =
  00 14 5C constant, ring/slot unused => single capture buffer. 7284-87 toggles 40391D00 / 40E51600 per frame (double-
  buffered encoder output?). T0/T2 not running (0). Tick [5229] ~1 per frame.
  First file's snapshot showed 0x99 in 6BE0-6BE5/6BE7 (boot clear overwritten or not run?) - harmless so far, watch it.
- Tearing band vs bitrate: hook1/d1.avi (PICT0014, 14 KB/frame, lots of motion) has NO band; 30 KB/frame files have band
  rows ~271-285. => encoder reading the single capture buffer while the next field overwrites it; big frames encode slower.
- Card: UPOKE.BIN = pokes/bitrate24k_log.bin (24 KB/frame target + log) to find the threshold.
- br24 RESULT (samples/br24/PICT0019, TV out OFF per user, camera off at start): 24K target did not lower size (31.5 KB
  mean; RC overshoots) -> no threshold info. Band still present with TV out off. ev1 pattern drifts vs ev2 with TV out
  off => ev1 (bit4, B26E) = TV-out vsync, not capture. ev4 (B6E8 -> 8BB1) = JPEG done: reads 7414-17 (end ptr) ->
  [5676-79]; JPEG output addr 7314-17 / 7324-27 from [5676]. JPEG source setup bank07:A943 (from A033/AB6F/AC6F) copies
  descriptor gptr [2473] into 7320-23, 7328/29, 7330-37, 732A/B. Capture dest 72DC-DF (bank06:CD09).
- Card: UPOKE.BIN = pokes/peek_jpeg.bin (buffer addresses log, no flash).
- peek_jpeg v3a (direct reads of 72DC-DF, 7314-17, 7320-37, 7304) -> DVR showed "card full", would not record (card has
  29 GB free, files intact). Reading write-only/engine registers has side effects. Replaced by RAM-shadow-only v3b:
  capture dest shadow [20E0-20E3] (bank06:CCFF), JPEG descriptor ptr [2473], [5676], [1E71], [1E91].
- jpeg1 RESULT (samples/jpeg1/PICT0021, v3b RAM-only log): records fine. capture shadow [20E0]=14000432 constant;
  JPEG descriptor ptr = 01:1E75 (+1/+2 = 0x02C0 width ...). [5676] alternates 0x238D40 / 0x2CED40 per frame (also
  0x16E540 at start) = capture buffers (7284 earlier: 0x16E540 / 0x1D3940, spacing = one 704/720x288x2 field).
- Tear visual (PICT0018 frame 377): rows below ~278 show NEWER picture (further along the pan) = next field written into
  the buffer still being compressed. No stale rows. Bitrate-dependent (slow encode).
- Capture-done path: B222 -> (1EBF.1) A513: if [1603] (pool empty?) skip; else take next free buffer from queue
  15FF..1603, [5674] idx -> table 16FC -> [5676] -> 7284-87 (A59B); finished buffer queued 1609..160C for encoder.
  JPEG done 8BB1 (ev4) reads 7414-17, [1EDE] = buffer being encoded.
- Card: UPOKE.BIN = pokes/peek_pool.bin.
- pool1 RESULT (samples/pool1/PICT0022, peek_pool): pool never starves (flag 1603 = 0 at 183/184 ev2); capture
  alternates 2 buffers idx 0/1 = 0x16E540 / 0x1D3940; JPEG done often during the discarded field (720D=80 at 91/183).
- Tear direction (PICT0018 f377, fast pan): band shift ratio -0.53 => torn rows are OLDER (the discarded field written
  20 ms BEFORE the kept one into the same buffer) -> the encoder reads the bottom rows before the kept field's data has
  landed. JPEG start = bank07:9F69 (called from scheduler 9674 / 96D8; source buffer = table 16FC[1EDD]).
- Hook v4: ev5 wrapper bank07:DA24 at JPEG start (log + optional delay [6BEA] x256 DJNZ, boot-cleared, settable by
  `boot write 6BEA nn`). plog handles ev5 + 5 counters. Tests pass. Built patches/clean704_q4_peek4.bin (bf2bdaea...).
  Card: UPOKE.BIN = pokes/peek_jstart.bin (delay 0). Not flashed.
- Hook v5 (user asked to bundle audio/50i tooling to avoid flashing): jump table bank07:DA00 (ev1 DA00, ev2 DA03,
  ev3 DA06, ev4 DA09, ev5 DA0C); CODE:4DB7 JNB 720D.0 NOPed, ev2 applies field gate [6BEC] (0 stock, 1 both, 2 field0),
  rejected = ev6; JPEG start delay [6BEB]; event mask [6BED] (0 = all); "frame" pokes (flags bit3) applied per accepted
  frame before B222; "rec hdr" op 4 writes AVI header bytes at record start (even without peeks). Counters 6BE5-6BEA.
  Boot clears 6BE0-6BED. Tests pass (incl. gate modes, mask, frame pokes, header writes). Audio: no extra hook (chunk
  writer bank11:A6ED runs only every 32 KB); audio state can be peeked on the 50/25 Hz events, ADC regs poked at rec.
  Built patches/clean704_q4_peek5.bin (58cef334...). Card: UPOKE.BIN = pokes/peek_jstart.bin (v5 layout). Not flashed.
- FLASHED clean704_q4_peek5 (VERIFIED, read-back matches). CURRENT DVR STATE.
- jstart1 RESULT (samples/jstart1/PICT0023, stock gate): DVR works on peek5. ev6 every frame => INT0 bit1 capture-done
  fires for BOTH fields (720D=84 field0 rejected, 85 field1 kept) -> 50i feasible. ev5 (9F69) never fires in D1 record
  (JPEG started elsewhere). Order per frame: ev6 (f0 done) -> ev2 (f1 done, buffer swap) -> ev4 (JPEG done, before next
  f0 done). => each buffer gets f0 then f1 written over it; tear = f0 residue at the bottom not yet overwritten by f1.
- Card: UPOKE.BIN = pokes/fields50.bin (gate = both fields).
- 50i RESULT (samples/f50b/PICT0024, gate=1 both fields): WORKS. 903 frames / 18.09 s = 49.9 fps (DVR writes the
  measured rate into the header itself), 2 stray/dup fields, audio intact, 37.6 KB/field (1.83 MB/s), NO band.
  Field parity: top field carries PAL WSS (line 23) in row 0 (row0-row1 diff ~45 vs ~3); order is not perfectly regular
  near start -> classify per frame. tools/weave.py: per-field WSS classification, pair top+next bottom, pad 704->720,
  blank WSS row, output 720x576 tff 25i H.264 (or --bob bwdif 576p50, --prores). Outputs in
  %USERPROFILE%\Videos\minidvr_50i\PICT0024_576i25.mp4 / _576p50.mp4.
- Also: stock-gate recording on peek5 (PICT0023, ev6 logging at field-0 end) had NO band -> extra ISR time at the
  discarded field's capture-done appears to stop the encoder overtaking the incoming kept field (unconfirmed A/B).
- USER: 50i videos smooth, but the bottom tear is still present and very visible (my row detector missed it).
  Analysis (tools/bandcheck.py, new): in 50i stale rows = 276-279 and 286-287 (lower lines of the last two 8-line JPEG
  strips), content = 2 fields earlier (= previous use of the same buffer). PICT0024 stale share 50-57% vs 22% baseline;
  PICT0023 (25p, v5) milder (rows 278-279 19%), not clean. => JPEG runs strip-locked with the capture and reads the last
  strips a few lines before they reach memory.
- 7230/7232 = horizontal/vertical decimation ([2D2F]: 2D32 = (Hsize+k)/(k+1)), NOT a sync margin. Capture window
  cannot exceed ~288 lines (row 0 = line 23 WSS). JPEG descriptor 1E75: 00 | 02C0 w | 0120 h | 02D0 pitch | 1000 1000
  (scale 1.0, 4.12) -> JPEG engine scales (stock D1 288->480).
- B222 tail 9ACD -> 9AD7 LCALL 82B5 (72F0 = A, 72F1 = 04 "go"), also 9B37 (A=90), after the buffer swap (A513).
- Hook v6: ev5 = 82B5 "go" (9AD7/9B37 -> DA0C) with delay [6BEE]; delay [6BEB] before B222; [6BEF] on rejected field.
  ev5 at 9F69 removed. Boot clears 6BE0-6BEF. Tests pass. Built patches/clean704_q4_peek6.bin (bbff7473...).
  Card: UPOKE.BIN = pokes/f50_go16.bin (50i, go delay 16). Not flashed.
- FLASHED clean704_q4_peek6 (VERIFIED, read-back matches). CURRENT DVR STATE.
- go16 RESULT (samples/go16/PICT0025, peek6): 49.9 fps fine; band score +3% (vs +12% PICT0024) but ev5 never ran
  ([5665]=0 -> 9ACD LJMP 9B80 = RET) so no delay was applied; scene darker/blurrier -> not conclusive.
  Log: JPEG done (ev4) for a field comes BEFORE that field's capture-done (ev2) => JPEG races the capture.
- Real D1 JPEG start = bank07:AB1E (7324 <- [5676], A943 descriptor 1E75, 82DA sets 7300.2 start), only entered via
  LJMP at 96A9 (scheduler ~95xx-96xx). Hook v7: 96A9 -> ev5 (log + delay 6BEE) -> AB1E; 9AD7/9B37 back to stock.
  Built patches/clean704_q4_peek7.bin (34c0318c...), 8 bytes vs peek6. Card unchanged (f50_go16). Not flashed.
- RAM BOOT (no flashing!): bank10:A1A1 (boot, from 8A5A before our hook) loads ADJUST.BIN to 0x300000 (deleted after
  load), stops peripherals, LJMP CODE:0080 = copy 64 x 32 KB pages 0x300000.. -> page 0.. (the RAM the CPU executes
  from; boot ROM fills it from flash) then LJMP 0000. Layout = vendor CRESFW.BIN: page0 = flash[0x40:0x8040], page N =
  flash[N*0x8000:]. tools/mkram.py builds ADJUST.BIN (checks the CODE:0080 loop is stock). One-shot per boot, can't brick.
- ram1 RESULT (samples/ram1/PICT0026, peek7 via ADJUST.BIN, 50i, 6BEE=16): ADJUST.BIN consumed, ev5 present => RAM boot
  WORKS. Band score -3% (vs +12%), but 46.9 fps (6% fields dropped). At ev5 720D bit2 = 0 (mid-field), at ev2 bit2 = 1.
- peek8 (RAM only): ev5 [6BEE]=FF waits for 720D.2 (end of field, timeout 64K polls); rec XOR op 5. Tests pass.
  Card: ADJUST.BIN = peek8, UPOKE.BIN = pokes/ab_eof_d8.bin (rec1 FF, rec2 8, alternating).
- ab1 RESULT (samples/ab1, peek8 RAM boot, 50i): PICT0027 6BEE=FF (wait end of field): 49.8 fps, band score +1%;
  PICT0028 6BEE=8: 49.8 fps, band -1%. Both clean visually at the bottom (detailed moving fields), 2-3 stray fields
  (same as before). ev5 (AB1E) runs for every 2nd field only (380/762) - other half started elsewhere, still clean.
  => TEARING FIXED: 50i + JPEG start waits for end of field. Recommended default: 6BEC=01, 6BEE=FF.
  Outputs in %USERPROFILE%\Videos\minidvr_50i\PICT0027_*/PICT0028_*.
- USER on ab1: wait8 had ghosting on a red wire; wait-end-of-field (6BEE=FF) good, no ghosting => use FF.
  Subtle bottom lines = last row of each field (row 287: bright in top fields, black in bottom fields; PAL half
  line/blanking), not tearing. weave.py now blanks row 0 (WSS) and row 287 of each field; --w704 option (SAR 12:11).
  Side black: left 8 px = weave padding; right ~7 px real blanking + 8 pad (capture window starts at px 8, picture at
  ~px 5 of the line). H end shadow = start + size - 1 (bank06:8098). Field vertical alignment: inconclusive (needs
  still footage).
- Card: ADJUST.BIN = peek8, UPOKE.BIN = pokes/f50_center.bin (50i, FF, H start 8 B / end 0x587).
- center1 RESULT (samples/center1/PICT0029, peek8 RAM, 50i + FF + H start 8 B): log confirms 2D23=0008, 2D27=0587.
  Picture now starts at col 1 (col 0 dim), right black only 4 cols (was 8) -> full analog width captured.
  Field alignment from 122 still pairs: bottom field exactly +0.5 field line below top => weave/tff correct.
  Bottom clean visually (bandcheck +6% is blur/half-line). User's "5-6 bottom lines" screenshot = start of PICT0027:
  row 287 black in BOTH fields for the first ~1 s (later top field row 287 bright), smeared by bwdif; now blanked.
  Outputs: %USERPROFILE%\Videos\minidvr_50i\PICT0029_final_*.
  FINAL SETTINGS candidate: 50i (6BEC=01), JPEG start waits end of field (6BEE=FF), capture H start 8 B.
- USER: subtle horizontal lines at the bottom in the first ~5 s (576p50 AND 576i). Cause: rate control ramps from
  level 5 (luma DC q16, 19 KB/field) to level 1 (q4, 45 KB) over ~4 s; the last 8-line JPEG strip contains the
  row-287 edge (bright 110 in top fields, black 14 in bottom fields) -> DCT ringing through rows 280-286, different
  per field -> line pattern; small at q4. Rate control bank13:8DFC every 32 frames: size > upper -> [56E6]++ (coarser),
  < lower -> -- (1 = finest), applies via CODE:13FC when [1F38]. Start level [56E6] = [5372] (bank05:AEDB).
- Card: ADJUST.BIN = peek8, UPOKE.BIN = pokes/f50_q1.bin (+ boot 5372=1, rec 56E6=1).
- Next idea for residual ringing: copy row 286 -> row 287 in the captured buffer before the JPEG start (ev5 window).
- USER: same faint lines at the TOP. Confirmed: top-field rows 0-7 temporal noise 3.4-3.8 vs bottom field 2.0-2.3,
  stops at row 8 = WSS line (row 0 of top field) ringing in the first JPEG strip. Bottom: bottom-field rows 280-287.
- Hook v9 (RAM only so far): edge fix [6BFB] bit0 top / bit1 bottom: before the JPEG start bit (82DA) on both D1 start
  paths (AB72 -> DA0F, AC8F -> DA12; AC40 path logged as ev3), copy row 1 -> row 0 and row 286 -> row 287 (1408 B,
  pitch 0x5A0) in the buffer at [5677..5679] via both windows, page crossing handled; scratch 6BF0-6BF8; boot clears
  6BFB. emu51: + RLC/RRC. Tests pass (incl. page-crossing src/dst). Built patches/clean704_q4_peek9.bin.
  Card: ADJUST.BIN = peek9, UPOKE.BIN = pokes/ab_edge.bin (rec1 edge fix ON, rec2 OFF; q start finest).
- edge1 RESULT (samples/edge1/PICT0030 fix ON (short, user started moving; may also be our stray writes), PICT0031 OFF):
  edge fix had NO effect (row0 vs row1 44.7 vs 43.3): in the AB1E path [5676] = table 1738[slot] -> 7324/7410/7414 =
  JPEG bitstream OUTPUT, not the picture -> my rows were written into the output area (!). In D1 the JPEG engine reads
  the capture buffer directly. Also [5372] is a JPEG mode value (mode setup writes 2; bank05:9550 -> 1F5E -> 04F6);
  setting it to 1 made quality worse (level 9, DC q24) -> do not touch. Rate-control start: only rec 56E6=1.
- Fix: edge fix now patches BOTH capture buffers from table 16FC (entries 0/1, 20-byte stride, address +1..+3), guard
  0x100000..0x79FFFF. Tests pass. Card: ADJUST.BIN = peek9 (fixed), UPOKE.BIN = pokes/ab_edge.txt (rec1 ON, rec2 OFF).
- edge2 RESULT (samples/edge2: PICT0032 edge fix ON 48.3 fps, PICT0033 OFF 49.9 fps): buffers 16FC/1710 = 0x16E540 /
  0x1D3940 (confirmed). Top fixed (row0-row1 12.3 vs 4.8 baseline-ish, still-noise spike gone). Bottom only partly
  (row287-286 31.5 vs 57): the AC40 start path (ev3, alternates with AB1E: 2-5-2-3) starts mid-field (720D.2 = 0) with
  no wait. RATE LEVEL: [56E6] 9 = FINEST, 1 = coarsest (log 1->9 while luma DC 24->4); my rec 56E6=1 forced coarse.
- peek9 rev: weof subroutine; AC40 path optional end-of-field wait [6BFC]=FF (boot clears 6BFB/6BFC). Tests pass.
  Card: ADJUST.BIN = peek9, UPOKE.BIN = pokes/ab_ac40wait.bin (edge fix on, rec1 AC40 wait ON, rec2 OFF, 56E6=9).
- ac40wait RESULT (2026-10-20). PICT0034/35 = accidental runs of FLASH peek6 (user restarted DVR; ADJUST.BIN one-shot) with
  same UPOKE (50i, centring, 56E6=09): NO tear band (bandcheck +0%), row 287 clean (|287-286| ~2-5), WSS only in row 0,
  repeats 0.3%, 49.9 fps. PICT0036 (AC40 wait ON) / 0037 (OFF) = peek9 RAM, edge fix 03: top fixed, bottom NOT fixed in
  either (row 287 still 109/15), 10-12% REPEATED fields (DVR repeats idx entries for dropped fields; check with offsets,
  not fps). Edge fix + weof are counterproductive. Hypothesis: finest start quality (56E6=09) makes JPEG slow enough to
  never overtake capture (PICT0024's band was with coarse start). Edge top fix also breaks weave.py WSS parity detection.
  Rendered PICT0035_chipfw_576p50/576i25 for user review. Next: if user confirms, permanent build = peek6 behaviour +
  defaults (50i D1 only, centring, finest start), no weof, no edge fix.
- coarse_start RESULT (PICT0038, chip fw peek6, no 56E6 poke): quality ramp 2->9 over ~4 s. Band in first 4 s +10%
  (rows 280-287 stale 13-26%), after reaching level 9 +1% => tearing = compressor overtaking capture at coarse levels;
  finest start avoids it. NEW: from ~6 s long stretches of ".rr" (1 of 3 fields written), 311/832 repeats (37%), not
  correlated with field size (24-35 KB vs 44 KB in clean PICT0035). ev4 668 vs 521 unique written. Cause unknown
  (signal/cable while panning? SD? encoder?). Card now: UPOKE = pokes/final_drops.txt (final config + log ev2/ev4 with
  pool queue 15FF and encoder queue 1609). Card has no ADJUST.BIN (uartfind consumed; UART hunt abandoned by user).
- final_drops RESULT (PICT0039, chip fw peek6 + pokes/final_drops.txt): 31 s, 49.94 fps, 3 repeats (start only),
  pan 10-20 s no drops (user kept cable still) => PICT0038 drops most likely cable/signal while panning. Pan: bottom
  strip matches current field in 97% of frames (band score +6% mostly the junk row 287, which weave.py replaces).
  Row 287 junk again (|287-286| 33). Rendered PICT0039_final_576p50/576i25. => FINAL CONFIG = this. Next: permanent
  build with defaults baked in (50i D1 only, centring, 56E6=09 at rec start), RAM test, then flash on user OK.

## 2026-10-20 Audio engine RE (static + register peeks)
- Audio regs readable via field peeks. 7928-792B = hardware DMA write pointer (LE), stock +320 B/field = 16000 B/s.
  Ring: start 7920 = 0x1E6B KB = 0x79AC00, size 0x2FFD0 = 6 x 32760 (bank13:CD4E consts). No audio IRQ (INT0 bits 0/1/2/4/14
  only); bank13:bfed/cb08 poll 7928 and write a 32760 (0x7FF8) chunk when available.
- CRACKLE: every 01wb chunk starts with 4 bytes F8 7F 00 00 (chunk length in the data) -> click once per chunk (stock too).
  Fix in post: drop/interpolate the first 2 samples of each chunk.
- 7903/7904-7905 (and 7944-7946) = channels(?)/byte rate, LATCHED at engine start: rec/frame pokes read back but no effect
  (PICT0041). Record path hard-codes them: bank13:CD72 [58FA]=01, CD7E [58FB/FC]=3E80 (-> bank11:9fcc -> 7903-7905) and
  bank13:92E8 [5914]=3E80 (-> bank11:a893 -> 7904/7944). audio32k missed CD81, hence its failure.
- a893 switch on [5927]: 77C0/77C1/77B2/77B3 = 0x1F for 8/16/24/32/48k, 0x22 for 22.5/44.1k (audio MCLK divider, family).
- Poking 77C0..B3 = 0F (PICT0042): audio really 2x (~32-34.5 kB/s, 12-bit kept) but 226/759 video repeats spread evenly ->
  don't use. 
- Built patches/peek6_a16k.bin (a7a2149d...) = flashed peek6 + PATCHES["a16k"] (16 bytes: rate vars, AVI header, 92E8, CD81).
  Card: ADJUST.BIN = peek6_a16k RAM image, UPOKE.BIN = pokes/audio_a16k.txt. Awaiting recording.
- PICT0043 (RAM peek6_a16k): 7903-7905 = 01 007D latched from start, header 16000, but pointer still +320/field = 16000 B/s.
  => byte-rate regs do NOT set the ADC rate. Only the 77C0/77C1/77B2/77B3 dividers do (PICT0042). The firmware always writes
  all four together (a2c5/a893), so static code can't tell which pair is the ADC clock -> bisect test 77C0/C1 only.
- PICT0044 (77C0/C1 = 0F only): audio 16000 B/s, 4 repeats -> 77C0/C1 not the ADC clock. 77B2/B3 is. Next: 77B2 alone.
- PICT0045 (77B2 = 0F only): 431.4 B/field = 10785 Hz, 2 repeats. => ADC rate = 496000 / (77B2 + 77B3) (stock 31+31 -> 8000;
  both 0F -> 16533, PICT0042). 16000 exact = 0F + 10. Hypothesis: PICT0042 drops = A/V sync logic (rate vars said 8000).
  Card: ADJUST.BIN = peek6_a16k + UPOKE = pokes/audio_16k_clk.txt (77B2/B3 = 0F10). WAV: Music\minidvr_audio\PICT0045_10k8.wav
- PICT0046 (RAM a16k + 77B2/B3 = 0F10): audio exactly 16003 Hz, header 16000, but 58% repeats (worse). Not SD bandwidth
  (PICT0040 wrote 2.35 MB/s video fine; 0046 only 0.92). Drops start after 2nd chunk; ok at 21.6 kB/s, bad at 32 kB/s.
  Chunk write path: bank13:d431 -> cb08 (avail = 7928 - [5905]?) -> stubs 1420 (bank11:BDFB), 1426 (bank11:A695), 140E
  (bank11:C100 returns [3719] status). Diagnostic card: pokes/audio_diag.txt (chip fw, no ADJUST).
- PICT0047 (chip fw peek6, ONLY 77B2/B3 = 0F10, stock rate vars): 16 kHz audio, 4 repeats -> CLEAN. Drops in 0042/0046 came
  from the extra changes (77C0/C1; a16k rate vars/latched 7904 byte rate), not from the audio rate itself.
- Built patches/peek6_a16hdr.bin = peek6 + PATCHES["a16k_hdr"] (AVI header only). Card: ADJUST = that, UPOKE = audio_16k_final.
- 32k request: 496000/n -> 31000 (08+08) or 33067 (07+08). Card: ADJUST = peek6_a31hdr, UPOKE = audio_31k (replaces the 16k final test).
- PICT0048 (RAM peek6_a31hdr + 77B2/B3 = 0808): 31007 Hz measured, strf 31000/62000, 3 repeats -> CLEAN, plays right off card.
  Spectrum: real content to ~10 kHz (8-10k 72.8 dB), flat floor ~60 dB above 10 kHz (loud = quiet frames) -> analog
  front end / source limits ~10 kHz. 0% clipping, 12-bit kept. WAV: Music\minidvr_audio\PICT0048_31k.wav (tag removed).
  AUDIO FINAL CANDIDATE: 31 kHz (77B2/B3 = 08/08 + audio_hdr(31000)). To bake in: a2c5/a893 write the same A to all four
  dividers (77C0,C1,B2,B3) -> needs a small code change so B2/B3 get 08 while C0/C1 stay 1F.
- 48k request: testing 49600 (05+05). Card: ADJUST = peek6_a49hdr, UPOKE = audio_49k.
- PICT0049 (49600 Hz, 05+05): rate exact, header ok, first ~12 s clean, then audio chunks bunch up (A.....A) and video breaks
  down (283/1039 repeats). Spectrum: 10-14k loud 68.5 vs quiet 63.6 dB -> a little real content above 10k (vs none at 31k,
  different music though). Gradual backlog -> audio write path lags at ~100 kB/s. Next: LONG (2-3 min) 31k test for stability.
  Card: ADJUST = peek6_a31hdr, UPOKE = audio_31k.
- PICT0050 (31k, 152 s): 446 repeats in two bursts (60-90 s: 70/181/84 per 10 s; 140-152 s: 58/50), clean elsewhere.
  Not correlated with video field size (44.9 KB windows clean). Before a burst, A spacing in idx drops 26 -> ~20 (video
  entries missing first), audio dur 153.1 vs video 152.3 s. Control next: same long test at stock 8 kHz (final_drops.bin, no
  ADJUST) to see whether bursts are audio-related or SD/long-recording related.
- PICT0051 (control, stock 8 kHz, final video, 160 s): 418 repeats, SAME burst at 60-90 s (32/165/217), clean elsewhere.
  => bursts are NOT audio-related (31k: 446). 31 kHz CLEARED as audio setting. Open: what happens at 60-90 s (user action?
  SD card? file size ~110-170 MB?). 
- 10 kHz ceiling analysis: spectra rel. to 2-4 kHz for 31k (0048) and 49.6k (0049) are nearly identical in Hz (-14 dB @8k,
  -21..-25 @10k, floor ~-32 from ~12-14k), i.e. roll-off does NOT scale with sample rate -> fixed analog filter (op-amp
  front end, SGM324) + white noise floor of the 12-bit ADC/analog chain. Not firmware. Only a hardware mod (filter cap) could
  move it. Input already near full scale (0049 clip 0.03%), so more gain won't lower the floor.
- Stereo static: record path has no channel concept beyond 7902 = [58F9]|4 (58F9 = 08) and the 79xx single ring; [58FA] is
  01 or D9 (from [5AB8]) -> not a channel count. Driver bank11:93f5 mode R7 (from [3BD7], bank14 callers C80A/CE4E, probably
  the playback/DAC path) scales byte rate x2/x4/x8. No evidence of a 2nd ADC channel. Hardware question: AV plug poles.
- Card: ADJUST = peek6_a31hdr, UPOKE = audio_31k for the long STILL test.
