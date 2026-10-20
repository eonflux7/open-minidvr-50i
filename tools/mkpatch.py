"""Apply a list of (offset, expected_hex, new_hex) byte patches to a flash image, verifying originals."""
import sys, hashlib

PATCHES = {
    "audio16k": [
        (0x5BBB5, "00001f40", "00003e80"),  # record init: [590E] = rate
        (0x5BBBF, "00001f40", "00003e80"),  # record init: [5927] = rate
        (0x5876C, "7f407e1f", "7f807e3e"),  # AVI strf nSamplesPerSec
        (0x58462, "7f807e3e", "7f007e7d"),  # AVI strf nAvgBytesPerSec 16000 -> 32000
        (0x59034, "7f407e1f", "7f807e3e"),  # AVI strh dwRate
    ],
}
PATCHES["audio16k_v2"] = PATCHES["audio16k"] + [
    (0x692E8, "743ef0a37480", "747df0a37400"),  # bank13 record start: [5914] ticks 62.5 -> 125.0
    (0x69312, "00001f40", "00003e80"),          # bank13 record start: [5927] = rate (applied by bank11:c026)
]

def audio_rate(rate, ticks):
    """Full record-path audio patch for `rate` Hz (16-bit mono); `ticks` = 2-byte [5914] value (rate/128, 8.8)."""
    r = rate.to_bytes(4, "big").hex()
    lo, hi = rate & 0xFF, rate >> 8
    avg = rate * 2
    return [
        (0x5BBB5, "00001f40", r),
        (0x5BBBF, "00001f40", r),
        (0x5876C, "7f407e1f", f"7f{lo:02x}7e{hi:02x}"),
        (0x58462, "7f807e3e7d00", f"7f{avg & 0xFF:02x}7e{(avg >> 8) & 0xFF:02x}7d{avg >> 16:02x}"),
        (0x59034, "7f407e1f", f"7f{lo:02x}7e{hi:02x}"),
        (0x692E8, "743ef0a37480", f"74{ticks[0]:02x}f0a374{ticks[1]:02x}"),
        (0x69312, "00001f40", r),
    ]

PATCHES["audio32k"] = audio_rate(32000, (0xFA, 0x00))
PATCHES["audio48k_trunc"] = audio_rate(48000, (0x77, 0x00))  # driver's own (truncated) mode-0 value

def video_q(q):
    """Rate-control target for record modes 0/2/3 (stock 13; setter clamps to 1..50)."""
    return [
        (0x294DA, "740d", "74%02x" % q),  # bank05:94da  MOV A,#q -> [1F49]
        (0x2A6E5, "740d", "74%02x" % q),  # bank05:a6e5  MOV A,#q -> [1F3B]
    ]

PATCHES["video_q20"] = video_q(20)
PATCHES["video_q26"] = video_q(26)

# Mode size table bank05:959C (mode [53A2]: 1=VGA 640x480, 2=320x240, 3=D1 720x480, 4=HD 1280x720) -> [5356]/[5358]
PATCHES["size_test1"] = [
    (0x295F0, "74e0", "7420"),  # bank05:95f0  D1 height lo byte: 480 (01E0) -> 288 (0120)
    (0x29618, "74d0", "7440"),  # bank05:9618  HD height lo byte: 720 (02D0) -> 576 (0240)
]

# Capture window (bank06:8000, TVP5150 types 0/1): PAL [2D2D] = 288 lines. 592 = field1 + ~25 blank + 279 of field2
# if the capture line counter is frame-based. D1 (mode 3) rerouted into the unused mode-2 slot to set 720x592.
PATCHES["stack_test"] = [
    (0x3007B, "7401f0a37420", "7402f0a37450"),  # bank06:807b  type 0 PAL capture height 0x0120 -> 0x0250
    (0x3022F, "7401f0a37420", "7402f0a37450"),  # bank06:822f  type 1 PAL capture height 0x0120 -> 0x0250
    (0x295B0, "6033", "6007"),                  # bank05:95b0  mode 3 (D1) -> 95b9 (was 95e5)
    (0x295B9, "90535612868474f01286f504f090536e123b1a000034",
              "905356" "7402f0a3" "74d0f0a3" "7402f0a3" "7450" "128736" "8026"),
                                                # [5356]=02D0 (720) [5358]=0250 (592), LCALL 8736, SJMP 95f5 (D1 tail)
]
# RESULT stack_test: D1 froze the DVR (window > one field never completes). Do not reuse.

# Frame gate ISR bank07:9E43 (INT0 bit 14): keeps a frame only while 720D.7 = 1 (field ID?), drops it if 720D.7 = 0 at the end.
PATCHES["fields50_test"] = PATCHES["size_test1"] + [
    (0x39E49, "30e706", "000000"),  # bank07:9e49  JNB 720D.7 -> NOPs (accept both fields)
    (0x39F4E, "20e714", "801500"),  # bank07:9f4e  JB 720D.7,9F65 -> SJMP 9F65 (never invalidate at end)
]
# RESULT fields50_test: still 25 fps, same field every frame (gate is not the decimator). Harmless.

# Capture front end as if [2D21] = 1 (bank06:AB63): 7220 bits0-1 = 1, and D0B6(1) -> 7270/7271 = 32 00 (stock 00 02).
PATCHES["capmode1_test"] = PATCHES["fields50_test"] + [
    (0x32BCB, "e05403", "740100"),  # bank06:abcb  R7 = 1 for 7220 bits 0-1 (was [2D21] & 3)
    (0x32BDA, "e014", "e400"),      # bank06:abda  take the [2D21]==1 branch -> D0B6(R7=1)
]
# RESULT capmode1_test: picture = YCbCr stream read as raw sensor data (green/stripes), still 25 fps. Mode 1 = raw input.

# 720C option bits 3/5/6 are cleared by the firmware (ANL #97); set them instead (both setup paths).
PATCHES["c720_test"] = PATCHES["fields50_test"] + [
    (0x32BB0, "5497", "4468"),  # bank06:abb0  720C: ANL A,#97 -> ORL A,#68 (bits 3,5,6 on)
    (0x334B0, "5497", "4468"),  # bank06:b4b0  same in the second setup path
]
# RESULT c720_test: all frames solid 0xFF (data blanked), still 25 fps => no every-field bit among 720C bits 3/5/6.

# Full-width capture: H start [2D23] 0x0020 -> 0x0000, H size [2D2B] 0x0558 (684 px) -> 0x05A0 (720 px), both TVP paths.
PATCHES["width720"] = PATCHES["size_test1"] + [
    (0x30052, "7420", "7400"),  # bank06:8052  type 0 [2D24] H start lo 0x20 -> 0x00
    (0x30061, "7458", "74a0"),  # bank06:8061  type 0 [2D2C] H size lo -> 0x05A0
    (0x30206, "7420", "7400"),  # bank06:8206  type 1 [2D24] H start lo 0x20 -> 0x00
    (0x30215, "7458", "74a0"),  # bank06:8215  type 1 [2D2C] H size lo -> 0x05A0
]
# RESULT width720: works, 1:1 horizontally; edges: col 0 bright, cols 1-4 dark, right ~8-16 cols black; top row = PAL WSS data.

# Clean BT.601 active width: capture 704 px starting at pixel 6 (12 bytes), D1 = 704x288; D1/HD quality target 13 -> 40.
PATCHES["clean704_q40"] = PATCHES["size_test1"] + [
    (0x30052, "7420", "740c"),  # bank06:8052  type 0 [2D24] H start lo -> 0x0C (pixel 6)
    (0x30061, "7458", "7480"),  # bank06:8061  type 0 [2D2C] H size lo -> 0x0580 (704 px)
    (0x30206, "7420", "740c"),  # bank06:8206  type 1
    (0x30215, "7458", "7480"),  # bank06:8215  type 1
    (0x295EB, "74d0", "74c0"),  # bank05:95eb  D1 width 720 (02D0) -> 704 (02C0)
] + video_q(40)
# RESULT clean704_q40: Y/C swapped (H start 12 B not accepted; working starts 0/32 are multiples of 8). q is a DIVISOR:
# target bytes/frame = w*h/q (HD 1280x576/13 = 55 KB ~ measured 50; D1 720x288/13 = 16 KB) -> q=40 made it coarser.

PATCHES["clean704_q4"] = PATCHES["size_test1"] + [
    (0x30052, "7420", "7410"),  # bank06:8052  type 0 [2D24] H start lo -> 0x10 (pixel 8)
    (0x30061, "7458", "7480"),  # bank06:8061  type 0 [2D2C] H size lo -> 0x0580 (704 px)
    (0x30206, "7420", "7410"),  # bank06:8206  type 1
    (0x30215, "7458", "7480"),  # bank06:8215  type 1
    (0x295EB, "74d0", "74c0"),  # bank05:95eb  D1 width 720 (02D0) -> 704 (02C0)
] + video_q(4)                  # D1 target 704*288/4 = 50 KB/frame

def ihx_patches(path, bank):
    """Patches placing an assembled Intel HEX (CPU addresses 0x8000-0xFFFF of `bank`) into zero padding."""
    out = []
    for line in open(path):
        line = line.strip()
        if not line.startswith(':') or int(line[7:9], 16) != 0:
            continue
        n, addr = int(line[1:3], 16), int(line[3:7], 16)
        data = line[9:9 + 2 * n]
        out.append((bank * 0x8000 + addr - 0x8000, "00" * n, data))
    return out

# SD-card poke hook (hook/poke_b10.asm, hook/poke_b13.asm): UPOKE.BIN loaded at boot, applied at boot / record start
HOOK = (ihx_patches("hook/poke_b10.ihx", 10) + ihx_patches("hook/poke_b13.ihx", 13) + [
    (0x50A7D, "12a517", "12da00"),  # bank10:8a7d  LCALL A517 -> LCALL DA00 (boot hook, tail-calls A517)
    (0x6C203, "7f0122", "02e800"),  # bank13:c203  MOV R7,#1 / RET -> LJMP E800 (record hook, same epilogue)
])
PATCHES["clean704_q4_hook"] = PATCHES["clean704_q4"] + HOOK

# Hook v2: + read-back logger (hook/peek_b07.asm; armed at record start by poke_b13.asm, log in the AVI header JUNK
# chunk, decoded by tools/plog.py) + UPOKE.BIN no longer deleted after loading (hook/peek_b04.asm).
HOOK2 = HOOK + ihx_patches("hook/peek_b07.ihx", 7) + ihx_patches("hook/peek_b04.ihx", 4) + [
    (0x39F65, "1283d8", "02da00"),  # bank07:9f65  LCALL 83D8 (re-arm capture, then RET) -> LJMP DA00 (logger)
    (0x201E3, "121066", "12da00"),  # bank04:81e3  LCALL 1066 (delete loaded file) -> LCALL DA00 (skip for UPOKE.BIN)
]
PATCHES["clean704_q4_peek"] = PATCHES["clean704_q4"] + HOOK2

# Hook v3: logger at the entry of all four INT0 sub-handlers (hook/peek_b07.asm ev1-ev4) via their common-code stubs
# (90 hi lo 02 02AE -> wrapper in bank07), instead of the bank07:9F65 exit hook (bit14 handler never ran while recording).
HOOK3 = HOOK + ihx_patches("hook/peek_b07.ihx", 7) + ihx_patches("hook/peek_b04.ihx", 4) + [
    (0x201E3, "121066", "12da00"),  # bank04:81e3  LCALL 1066 (delete loaded file) -> LCALL DA00 (skip for UPOKE.BIN)
    (0x1B0E + 1, "b26e", "da00"),   # CODE:1ACE stub bit4  B26E -> ev1
    (0x1B14 + 1, "b222", "da09"),   # CODE:1AD4 stub bit1  B222 -> ev2
    (0x1B1A + 1, "9e43", "da12"),   # CODE:1ADA stub bit14 9E43 -> ev3
    (0x1B20 + 1, "b6e8", "da1b"),   # CODE:1AE0 stub bit2  B6E8 -> ev4
]
PATCHES["clean704_q4_peek3"] = PATCHES["clean704_q4"] + HOOK3

# Hook v4: + ev5 at JPEG start (bank07:9F69) with optional delay [6BEA] (hook/peek_b07.asm)
HOOK4 = HOOK3 + [
    (0x39674, "129f69", "12da24"),  # bank07:9674  LCALL 9F69 (start JPEG) -> LCALL DA24 (ev5)
    (0x396D8, "029f69", "02da24"),  # bank07:96d8  LJMP 9F69 -> LJMP DA24 (ev5)
]
PATCHES["clean704_q4_peek4"] = PATCHES["clean704_q4"] + HOOK4

# Hook v5 (hook/peek_b07.asm jump table at bank07:DA00): logger ev1-ev6, JPEG start delay [6BEB], field gate [6BEC]
# (dispatcher's own 720D.0 test NOPed), event mask [6BED], per-frame pokes; header writes at record start (poke_b13).
HOOK5 = HOOK + ihx_patches("hook/peek_b07.ihx", 7) + ihx_patches("hook/peek_b04.ihx", 4) + [
    (0x201E3, "121066", "12da00"),  # bank04:81e3  LCALL 1066 (delete loaded file) -> LCALL DA00 (skip for UPOKE.BIN)
    (0x1B0E + 1, "b26e", "da00"),   # CODE:1ACE stub bit4  B26E -> ev1
    (0x1B14 + 1, "b222", "da03"),   # CODE:1AD4 stub bit1  B222 -> ev2 (field gate)
    (0x1B1A + 1, "9e43", "da06"),   # CODE:1ADA stub bit14 9E43 -> ev3
    (0x1B20 + 1, "b6e8", "da09"),   # CODE:1AE0 stub bit2  B6E8 -> ev4
    (0x39674, "129f69", "12da0c"),  # bank07:9674  LCALL 9F69 (start JPEG) -> ev5
    (0x396D8, "029f69", "02da0c"),  # bank07:96d8  LJMP 9F69 -> ev5
    (0x4DF7, "30e003", "000000"),   # CODE:4DB7  JNB 720D.0,skip -> NOPs (ev2 applies the field gate instead)
]
PATCHES["clean704_q4_peek5"] = PATCHES["clean704_q4"] + HOOK5

# Hook v6: ev5 moved from 9F69 (never runs in D1) to the 72F0/72F1 "go" at bank07:82B5 (after the buffer swap), with
# delay [6BEE]; delays [6BEB] before B222 and [6BEF] on rejected fields (tearing experiments).
HOOK6 = [p for p in HOOK5 if p[0] not in (0x39674, 0x396D8)] + [
    (0x39AD7, "1282b5", "12da0c"),  # bank07:9ad7  LCALL 82B5 -> ev5 (log + delay 6BEE)
    (0x39B37, "1282b5", "12da0c"),  # bank07:9b37  LCALL 82B5 -> ev5
]
PATCHES["clean704_q4_peek6"] = PATCHES["clean704_q4"] + HOOK6

# Hook v7: ev5 + delay [6BEE] moved to the real D1 JPEG start bank07:AB1E (82B5 is not on the D1 path: [5665] = 0).
HOOK7 = [p for p in HOOK6 if p[0] not in (0x39AD7, 0x39B37)] + [
    (0x396A9, "02ab1e", "02da0c"),  # bank07:96a9  LJMP AB1E (JPEG start) -> ev5 (log + delay 6BEE) -> AB1E
]
PATCHES["clean704_q4_peek7"] = PATCHES["clean704_q4"] + HOOK7
# peek8 = same patch list; hook sources add ev5 wait-for-end-of-field mode ([6BEE] = FF) and rec XOR (op 5)
PATCHES["clean704_q4_peek8"] = PATCHES["clean704_q4"] + HOOK7

# Hook v9: edge fix [6BFB] before the JPEG start bit on both D1 start paths (AB72 / AC8F -> bank07:DA0F / DA12)
HOOK9 = HOOK7 + [
    (0x3AB72, "1282da", "12da0f"),  # bank07:ab72  LCALL 82DA (start bit) -> edge fix A -> 82DA
    (0x3AC8F, "1282da", "12da12"),  # bank07:ac8f  LCALL 82DA -> log ev3 + edge fix -> 82DA
]
PATCHES["clean704_q4_peek9"] = PATCHES["clean704_q4"] + HOOK9

# UART pin finder (RAM test only, never flash): boot stops in hook/uart_b10.asm, sending 'U' forever
PATCHES["uartfind"] = PATCHES["clean704_q4"] + [p for p in HOOK if p[0] != 0x50A7D] + ihx_patches("hook/uart_b10.ihx", 10) + [
    (0x50A7D, "12a517", "12e000"),  # bank10:8a7d  LCALL A517 -> LCALL E000 (UART pin finder, never returns)
]

# Audio 16 kHz on the chip firmware: both record paths hard-code the hardware byte rate 0x3E80 (bank13:92E8 -> [5914]
# -> 7904/7944 via bank11:a893, bank13:CD81 -> [58FB] -> 7903-7905 via bank11:9fcc); the engine latches it at start
# apply to the flashed image: mkpatch.py patches/clean704_q4_peek6.bin out.bin a16k (hook/*.ihx have moved on since peek6)
PATCHES["a16k"] = audio_rate(16000, (0x7D, 0x00)) + [
    (0x6CD81, "743ef0a37480", "747df0a37400"),  # bank13:cd81  [58FB] = 3E80 -> 7D00 (32000 B/s = 16 kHz mono)
]

# 16 kHz final approach: ADC clock only (77B2/77B3 = 0F/10 -> 496000/31 = 16000 Hz, PICT0047 clean) + AVI header constants;
# the firmware's internal rate vars stay 8000 (changing them, PICT0046, or 77C0/C1, PICT0042, caused heavy field drops)
PATCHES["a16k_hdr"] = [
    (0x5876C, "7f407e1f", "7f807e3e"),          # AVI strf nSamplesPerSec 8000 -> 16000
    (0x58462, "7f807e3e7d00", "7f007e7d7d00"),  # AVI strf nAvgBytesPerSec 16000 -> 32000
    (0x59034, "7f407e1f", "7f807e3e"),          # AVI strh dwRate 8000 -> 16000
]

def audio_hdr(rate):
    """AVI header constants only (16-bit mono at `rate` Hz); the ADC clock itself is set by 77B2 + 77B3 = 496000 / rate."""
    lo, hi, avg = rate & 0xFF, rate >> 8, rate * 2
    return [
        (0x5876C, "7f407e1f", f"7f{lo:02x}7e{hi:02x}"),
        (0x58462, "7f807e3e7d00", f"7f{avg & 0xFF:02x}7e{(avg >> 8) & 0xFF:02x}7d{avg >> 16:02x}"),
        (0x59034, "7f407e1f", f"7f{lo:02x}7e{hi:02x}"),
    ]

PATCHES["a31k_hdr"] = audio_hdr(31000)  # 77B2/77B3 = 08/08
PATCHES["a49k_hdr"] = audio_hdr(49600)  # 77B2/77B3 = 05/05

# ADC clock baked in: bank11:a2c5/a2ca write the same value to all four dividers 77C0/77C1/77B2/77B3; send the 77B2/77B3
# half to bank11:E000 (zero fill D9F5-FFFF) which writes 08/08 instead (77C0/C1 keep 1F/22, changing them drops fields)
def audio_clk(div):
    return [
        (0x5A2CD, "9077b2f0a3f022", "02e000" + "00" * 4),  # bank11:a2cd  -> LJMP E000 (rest dead)
        (0x5E000, "00" * 9, f"9077b274{div:02x}f0a3f022"),  # bank11:e000  77B2 = 77B3 = div; RET
    ]

# Public release: exactly the device-tested build (PICT0048): chip firmware peek6 + 31 kHz AVI header; the 31 kHz clock
# itself comes from UPOKE.BIN (frame write 77B2 0808). audio_clk() bakes it in but is emulator-tested only (not released).
PATCHES["release_31k"] = audio_hdr(31000)
PATCHES["release_31k_clk"] = audio_hdr(31000) + audio_clk(0x08)  # untested on hardware

def main(src, dst, name):
    img = bytearray(open(src, "rb").read())
    for off, old, new in PATCHES[name]:
        old_b, new_b = bytes.fromhex(old), bytes.fromhex(new)
        if img[off:off + len(old_b)] != old_b:
            sys.exit(f"mismatch at {off:#x}: {img[off:off+len(old_b)].hex()} != {old}")
        img[off:off + len(new_b)] = new_b
    open(dst, "wb").write(img)
    print(dst, hashlib.sha256(img).hexdigest())

if __name__ == "__main__":
    main(*sys.argv[1:4])

