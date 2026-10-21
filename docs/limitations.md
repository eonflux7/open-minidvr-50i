# Limitations (measured, not guessed)

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
- **Only D1 mode was tested** with these settings, and only with a PAL camera. VGA is stock, and HD records 1280×576.
- **The picture is JPEG at about 35–45 KB per field (about 2 MB/s).** It's a strip encoder with no frame memory, so
  true full frames (576 or 480 lines) are impossible on this chip. That's why the project records fields.
- **ADJUST.BIN is one-shot.** The vendor bootloader deletes it after loading. To make the patch permanent, use the
  DVR's own SD updater ([Making it permanent](../README.md#making-it-permanent-sd-card-no-programmer)). Or, if you have a clip programmer, use `tools/flash.sh`.
- **One firmware only:** Eachine ProDVR firmware 2015.05.26.01.IR (CRESFW.BIN of September 2016). Other versions are
  refused.
