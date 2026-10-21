# NTSC (experimental)

**Untested on hardware.** Nobody has recorded with the NTSC build yet. What's known comes from the disassembly, the
emulator and simulated recordings.

- **Why there's a separate build:** the firmware itself detects NTSC (TVP5150 register 0x8C) and captures a 240-line
  field window. The PAL build fixes the D1 picture at 288 lines, so the JPEG scaler would stretch every NTSC field to
  288. The NTSC build is the PAL build plus one change: D1 is 704×240 (`tools/mkpatch.py` `ntsc_d1`, 31 bytes, checked
  in `tests/test_ntsc.py`).
- **Use it only with an NTSC camera.** A PAL camera on the NTSC build gets its 288-line fields squeezed to 240.
  The converter refuses NTSC recordings made with the PAL build and tells you to switch.
- **Field parity:** NTSC has no WSS line, so `weave.py` works it out from the picture. It compares each field with
  the previous one, shifted half a line up, half a line down and not at all, and picks the most likely top/bottom
  sequence for the whole clip. Checked against WSS on PAL recordings with the WSS rows cut off, it matched every field
  on clean clips (903 of 903). It can misjudge long stretches of repeated fields (like the stutter under [Limitations](limitations.md))
  and very flat scenes. `--parity picture` runs the same method on a PAL recording, for comparison.
- **Unknowns:** whether the encoder keeps up at about 60 fields/s (the line rate is the same as PAL's, so it should),
  what the top and bottom rows contain (VBI, closed captions, half lines: the converter leaves them as recorded), and
  the HD mode (still 1280×576, stretched from 240 lines). The UPOKE.BIN settings don't depend on the standard.

If you try it, please open an issue with a short raw `.AVI` and what you saw on the DVR.
