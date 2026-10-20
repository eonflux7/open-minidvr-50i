#!/usr/bin/env python3
"""Turn a 50-fields/s DVR recording (field gate = both fields, e.g. 704x288 @ 49.9 fps) into real PAL 576i video.

Every AVI frame is one field. Each frame is classified as top or bottom field by the PAL WSS signal (line 23, which
only the top field carries; it is row 0 of a top field). A top field and the following bottom field are woven into
one 720x576 frame (704 active pixels centred in 720, BT.601; or 704x576 with --w704). The WSS line (row 0 of the top
field) and the last row of each field (PAL half line / blanking: bright in top fields, black in bottom fields) are
replaced by the neighbouring row of the same field. Stray fields (a dropped or
repeated field breaks the alternation) are skipped and reported. Output is 25 fps interlaced, top field first.
Audio is taken from the AVI's own chunks at the rate in its header, minus the 4-byte length tag (F8 7F 00 00) the DVR
writes at the start of every 32760-byte audio chunk (a click per chunk otherwise).

  weave.py PICT0024.AVI out.mp4                 576i25 H.264 (interlaced), AAC audio
  weave.py PICT0024.AVI out.mp4 --bob           576p50 (bwdif deinterlace, one frame per field)
  weave.py PICT0024.AVI out.mov --prores        576i25 ProRes 422 HQ + PCM audio, for editing
  weave.py PICT0024.AVI out.mp4 --w704          no side padding: 704x576, pixel aspect 12:11 (still 4:3)
"""
import argparse, json, os, struct, subprocess, sys, tempfile, wave
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('dst')
ap.add_argument('--bob', action='store_true', help='output 576p50 (motion-adaptive deinterlace, one frame per field)')
ap.add_argument('--prores', action='store_true', help='ProRes 422 HQ instead of H.264')
ap.add_argument('--crf', default='14')
ap.add_argument('--w704', action='store_true', help='output 704 wide (no 8-px side padding), SAR 12:11')
ap.add_argument('--wss', type=float, default=20.0, help='row0/row1 difference above which a field counts as top')
args = ap.parse_args()

info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                           'stream=width,height,r_frame_rate', '-of', 'json', args.src]))['streams'][0]
w, h = info['width'], info['height']
num, den = map(int, info['r_frame_rate'].split('/'))
with open(args.src, 'rb') as f:                           # the DVR derives the header frame rate from the audio byte
    hdr = f.read(0x200)                                   # count at its built-in 16000 B/s; undo that for faster audio
s = hdr.find(b'strf', hdr.find(b'auds'))
avg = struct.unpack('<I', hdr[s + 16:s + 20])[0] if s > 0 else 16000
if avg != 16000:
    num *= avg; den *= 16000
fps = num / den
if fps < 40:
    sys.exit(f'{args.src}: {fps:.2f} frames/s - this is not a both-fields recording (expected ~50)')
fs = w * h * 2                                            # yuv422p field
W, H = (w if args.w704 else 720), 2 * h
sar = '12/11' if args.w704 else '16/15'
x0 = (W - w) // 2


def avi_audio(path, tmpdir):
    """PCM of all 01wb chunks (idx1 order) with the per-chunk length tag removed, as a WAV file; None if no audio."""
    d = open(path, 'rb').read()
    i = d.rfind(b'idx1')
    s = d.find(b'strf', d.find(b'auds'))
    if i < 0 or s < 0:
        return None
    ch, rate = struct.unpack('<HI', d[s + 10:s + 16])
    movi = d.find(b'movi') - 4
    n = struct.unpack('<I', d[i + 4:i + 8])[0]
    parts = []
    for k in range(i + 8, i + 8 + n, 16):
        cid, _, off, sz = struct.unpack('<4sIII', d[k:k + 16])
        if cid == b'01wb':
            a = np.frombuffer(d[movi + off + 8:movi + off + 8 + sz], '<i2').copy()
            if len(a) > 2 and a[0] == 0x7FF8 and a[1] == 0:
                a[:2] = a[2]
            parts.append(a)
    if not parts:
        return None
    out = os.path.join(tmpdir, 'audio.wav')
    with wave.open(out, 'wb') as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(rate); w.writeframes(np.concatenate(parts).tobytes())
    return out


def is_top(y):
    return np.abs(y[0, 16:w - 24].astype(np.int16) - y[1, 16:w - 24]).mean() > args.wss


dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', args.src, '-f', 'rawvideo', '-pix_fmt', 'yuv422p', '-'],
                       stdout=subprocess.PIPE)
rate = f'{num}/{2 * den}'                                 # woven frame rate = field rate / 2
if args.prores:
    venc = ['-c:v', 'prores_ks', '-profile:v', '3', '-pix_fmt', 'yuv422p10le']
    aenc = ['-c:a', 'pcm_s16le']
else:
    venc = ['-c:v', 'libx264', '-crf', args.crf, '-preset', 'slow', '-pix_fmt', 'yuv420p']
    aenc = ['-c:a', 'aac', '-b:a', '128k']
if args.bob:
    vf, flags = f'setfield=tff,bwdif=mode=send_field:parity=tff,setsar={sar}', []
else:
    vf = f'setfield=tff,setsar={sar}'
    flags = ['-field_order', 'tt'] + ([] if args.prores else ['-flags', '+ilme+ildct', '-x264opts', 'tff=1'])
tmp = tempfile.TemporaryDirectory()
audio = avi_audio(args.src, tmp.name) or args.src
enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'yuv422p', '-s', f'{W}x{H}',
                        '-r', rate, '-i', '-', '-i', audio, '-map', '0:v', '-map', '1:a?', '-vf', vf,
                        *venc, *flags, *aenc, '-shortest', args.dst], stdin=subprocess.PIPE)


def planes(buf):
    f = np.frombuffer(buf, np.uint8)
    return f[:w * h].reshape(h, w), f[w * h:w * h * 3 // 2].reshape(h, w // 2), f[w * h * 3 // 2:].reshape(h, w // 2)


out = np.empty(W * H * 2, np.uint8)
Y = out[:W * H].reshape(H, W); U = out[W * H:W * H * 3 // 2].reshape(H, W // 2); V = out[W * H * 3 // 2:].reshape(H, W // 2)
Y[:] = 16; U[:] = 128; V[:] = 128                         # black side borders (8 px each side)
n = woven = skipped = 0
pending = None                                            # a top field waiting for its bottom field
while True:
    buf = dec.stdout.read(fs)
    if len(buf) < fs:
        break
    y, u, v = planes(buf)
    n += 1
    if is_top(y):
        if pending is not None:
            skipped += 1                                  # two top fields in a row: drop the older one
        pending = (y.copy(), u.copy(), v.copy())
        continue
    if pending is None:
        skipped += 1                                      # bottom field without a top field before it
        continue
    ty, tu, tv = pending
    pending = None
    Y[0::2, x0:x0 + w], U[0::2, x0 // 2:(x0 + w) // 2], V[0::2, x0 // 2:(x0 + w) // 2] = ty, tu, tv
    Y[1::2, x0:x0 + w], U[1::2, x0 // 2:(x0 + w) // 2], V[1::2, x0 // 2:(x0 + w) // 2] = y, u, v
    for row in (0, H - 2, H - 1):                         # WSS line; last row of each field (half line / blanking):
        src = row + 2 if row == 0 else row - 2            # repeat the neighbouring row of the same field (black rows
        Y[row] = Y[src]; U[row] = U[src]; V[row] = V[src]  # make deinterlacers flicker at the edge)
    enc.stdin.write(out.tobytes())
    woven += 1
enc.stdin.close(); enc.wait(); dec.wait()
print(f'{args.dst}: {n} fields -> {woven} frames {W}x{H} ({"576p50 deinterlaced" if args.bob else "interlaced tff"}), '
      f'{skipped} stray fields skipped')
