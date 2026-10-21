<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/banner-dark.png">
    <img alt="open-minidvr-50i" src="docs/banner-light.png" width="100%">
  </picture>
</p>

**Better video and audio for a cheap FPV mini DVR.**

Custom firmware patches for the small FPV mini DVR/Eachine ProDVR (and clones built on the same
board). It was reverse-engineered to record a Sony VX2100E (PAL) as well as this hardware allows.

| | Stock firmware | With this project |
|---|---|---|
| Video | only every second field, upscaled to 720×480 or 1280×720 | **every field**, recorded at 704 pixels wide and woven into real **interlaced video** on the PC (720×576 PAL, 720×480 NTSC), no scaling |
| Picture | 684 px window, cropped more on the left than the right, stretched to 720 wide | all 704 active pixels at 1:1, centred, finest JPEG quality from the start |
| Audio | 8 kHz mono, a click once per 32 KB block | **31 kHz** mono (real sound up to about 10 kHz), clicks removed by the converter |

> [!WARNING]
> **NTSC support is experimental and untested.** The patcher also offers an NTSC build for NTSC camcorders
> (704×240 fields at about 60 per second, converted to 720×480 29.97i). It has only been checked in an emulator and
> on simulated recordings, never on a real DVR with an NTSC camera. It may not work at all. It can't damage anything
> (same RAM boot as the PAL build), and reports are welcome. Details: [NTSC (experimental)](docs/ntsc.md).

**It doesn't touch your DVR's chip.** The patched firmware is loaded from the SD card into RAM at power-on. If you
switch off and start without the file, you're back to the stock firmware. Nothing to brick.

## Quick start (no programming needed)

1. **Make the files:** open the patcher page (<https://eonflux7.github.io/open-minidvr-50i/>, or `docs/index.html` offline) and follow the steps:
   - download Eachine's official ProDVR firmware (`CRESFW.BIN`)
   - pick your camera's standard: PAL, or NTSC (experimental, see above)
   - drop it on the page
   - save **ADJUST.BIN** and **UPOKE.BIN**

   The page runs entirely in your browser. It checks every byte it changes and refuses any other firmware version.
2. **Copy both files to the root of the microSD card** (not into a folder).
3. **Switch the DVR on and record in D1 mode.** Startup takes a little longer while it loads the file. No picture?
   Check the cable's pinout: [Connecting the camera](docs/av-cable.md).
4. **Copy ADJUST.BIN again before every power-on.** The DVR deletes it when it loads it. UPOKE.BIN stays on the card.
5. **Convert the recordings on a computer** ([below](#converting-recordings)). The raw files hold one field per frame
   and look squashed until they're converted.
6. **Optional: make it permanent** with the SD card alone, so you no longer need ADJUST.BIN
   ([below](#making-it-permanent-sd-card-no-programmer)).

### Converting recordings

**Windows:** download `MiniDVR-Convert-windows.zip` from the
[latest release](https://github.com/eonflux7/open-minidvr-50i/releases/latest) and unzip it. Drag one or more `.AVI`
files onto `MiniDVR-Convert.exe`, or double-click it and choose the files. Nothing to install: Python and ffmpeg are
included. The first time, Windows may say "Windows protected your PC" because the program isn't signed with a paid
certificate: click **More info**, then **Run anyway**.

**macOS and Linux:** download this project (the green **Code** button at the top of the GitHub page, then
**Download ZIP**) and unzip it.
- **macOS:** double-click `tools/convert.command` and choose the files. The first time, macOS may refuse to open it
  because it was downloaded: right-click it, choose **Open**, then **Open** again. If Python, numpy or ffmpeg is
  missing, it offers to install them with [Homebrew](https://brew.sh) (and Homebrew too, if needed).
- **Linux:** run `sh tools/convert.sh` in a terminal and choose the files, or give their names:
  `sh tools/convert.sh PICT0001.AVI PICT0002.AVI` (you can drag files into the terminal window instead of typing).
  If something is missing, it offers to install it with your package manager (apt, dnf, pacman or zypper). On
  Fedora and openSUSE, get ffmpeg from RPM Fusion or Packman: the distribution's own ffmpeg can't write H.264.

There's also `tools/convert.bat` for Windows users who'd rather run the Python version: it offers to install Python,
numpy and ffmpeg with winget.

Each recording becomes two files next to it:

| PAL | NTSC | What it's for |
|---|---|---|
| `PICT0001_576i.mp4` | `PICT0001_480i.mp4` | interlaced, like the camera: TVs, DVD/Blu-ray authoring, video editors |
| `PICT0001_576p50.mp4` | `PICT0001_480p60.mp4` | progressive, one frame per field: smooth on computers and phones, and for uploading |

It recognises PAL and NTSC recordings by itself.

If something is wrong (a recording made without ADJUST.BIN, an unfinished copy, a missing program), it says so in plain
words and carries on with the other files.

With a terminal you can also choose the output yourself:

```
python tools/weave.py PICT0001.AVI PICT0001.mp4           # interlaced only
python tools/weave.py PICT0001.AVI PICT0001.mp4 --bob     # progressive only
python tools/weave.py PICT0001.AVI PICT0001.mov --prores  # ProRes 422 HQ + PCM audio, for editing
```

It pairs the fields into full frames, hides the edge rows, removes the audio clicks and fixes the header frame rate
([details](docs/how-it-works.md#the-converter)).

### Making it permanent (SD card, no programmer)

The DVR has its own firmware updater: at power-on it looks for `CRESFW.BIN` in the card root and writes it into its
flash chip. That's how Eachine ships updates. Step 5 of the patcher page makes a patched `CRESFW.BIN`: exactly the
firmware you've been running as ADJUST.BIN, in the vendor's update format and at the same size. After the update the
DVR starts with it every time, and you no longer need ADJUST.BIN. Keep UPOKE.BIN on the card, because the settings
(both fields, centring, quality, 31 kHz) still come from it.

> [!CAUTION]
> **This writes to the chip.** Try ADJUST.BIN first, with the same PAL/NTSC choice. If the power fails during the
> write, the DVR won't start and needs a clip programmer to recover. The updater is the vendor's, but it hasn't yet
> been run with this project's file. The NTSC build is untested even as ADJUST.BIN, so don't flash it until someone
> has recorded with it.

1. Charge the battery fully, or power the DVR over USB.
2. Copy `CRESFW.BIN` to the card root. **Remove ADJUST.BIN**, because if it's there the DVR loads that instead.
3. Switch on and leave the DVR alone while the red LED blinks. When it stops, wait about 30 s, then switch off.
4. Delete `CRESFW.BIN` from the card if it's still there. Otherwise the DVR writes it again at every start.
5. Record a short D1 clip with no ADJUST.BIN on the card. A raw file 704 pixels wide means it worked. Menu settings
   may return to their defaults.

**To undo:** do the same with Eachine's original, unmodified `CRESFW.BIN` (SHA-256 `a6134cc0…10df64`). Keep a copy of
it before you flash. The updater runs before any of this project's code, so it works the same from the patched firmware.

From the shell: `python3 tools/mkrelease.py apply CRESFW.BIN /path/to/sdcard/CRESFW.BIN`. An output named CRESFW.BIN
gets the update format.

## More documentation

- [Connecting the camera (AV cable)](docs/av-cable.md): pinouts, which cable works, re-soldering to CTIA
- [Limitations](docs/limitations.md): what this hardware can't do, measured
- [NTSC (experimental)](docs/ntsc.md): the untested NTSC build
- [How it works](docs/how-it-works.md): the firmware patches, the converter and the updater
- [Development](docs/development.md): repository layout, command-line use, rebuilding the patch
- [Findings](docs/findings.md) and the [lab notebook](docs/lab-notes.md): register maps, addresses, every experiment

## License

MIT (see [LICENSE](LICENSE)) for the code and documentation in this repository. The DVR firmware itself belongs to
its vendor and isn't included. Use at your own risk: the RAM-boot route doesn't write to the DVR's flash, but the
flashing tools do.
