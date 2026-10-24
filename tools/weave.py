#!/usr/bin/env python3
"""Turn a both-fields DVR recording (704x288 @ 49.9 fps, or 704x240 @ ~59.9 fps from the NTSC build) into real PAL 576i
or NTSC 480i video.

Every AVI frame is one field. Each frame is classified as top or bottom field by the PAL WSS signal (line 23, which
only the top field carries; it is row 0 of a top field). A top field and the following bottom field are woven into
one 720x576 frame (704 active pixels centred in 720, BT.601; or 704x576 with --w704). The WSS line (row 0 of the top
field) and the last row of each field (PAL half line / blanking: bright in top fields, black in bottom fields) are
replaced by the neighbouring row of the same field. Stray fields (a dropped or
repeated field breaks the alternation) are skipped and reported. Output is 25 fps interlaced, top field first.
NTSC (704x240 fields, experimental): there is no WSS line, so the field parity is worked out from the picture: each field
is compared with the previous one shifted half a line down, half a line up and not at all, and a best path through the
whole recording (fields alternate, a repeated parity costs extra) picks top/bottom. Checked against WSS on PAL
recordings: exact on clean ones, but it can slip in long stretches of repeated fields. Edge rows are left as recorded.
Output is 720x480 (or 704x480), ~29.97 fps interlaced, top field first.
Audio is taken from the AVI's own chunks at the rate in its header, minus the 4-byte length tag (F8 7F 00 00) the DVR
writes at the start of every 32760-byte audio chunk (a click per chunk otherwise).

  weave.py                                      no arguments: pick the AVIs in a file dialog (makes both versions)
  weave.py PICT0024.AVI PICT0025.AVI            each one to NAME_576i.mp4 next to it (NAME_480i.mp4 for NTSC)
  weave.py PICT0024.AVI --both                  NAME_576i.mp4 and NAME_576p50.mp4 (what convert.bat does)
  weave.py PICT0024.AVI out.mp4                 576i25 H.264 (interlaced), AAC audio
  weave.py PICT0024.AVI out.mp4 --bob           576p50 (bwdif deinterlace, one frame per field)
  weave.py PICT0024.AVI out.mov --prores        576i25 ProRes 422 HQ + PCM audio, for editing
  weave.py PICT0024.AVI out.mp4 --w704          no side padding: 704x576, pixel aspect 12:11 (still 4:3)
  weave.py PICT0024.AVI out.mp4 --widescreen    camera set to 16:9 (squeezed into the 4:3 signal): marked 16:9
  weave.py PICT0024.AVI out.mp4 --parity picture  PAL with the NTSC parity method (for testing it against WSS)
  weave.py PICT0024.AVI PICT0024_{fmt}.mp4      {fmt} becomes 576i, 576p50, 480i or 480p60
"""
import argparse, os, shutil, struct, subprocess, sys, tempfile, time, wave
from fractions import Fraction

OUT_EXT = ('.mp4', '.mov', '.mkv')
FROZEN = getattr(sys, 'frozen', False)                  # the Windows .exe (PyInstaller), ffmpeg.exe next to it
if FROZEN:
    os.environ['PATH'] = os.path.dirname(sys.executable) + os.pathsep + os.environ.get('PATH', '')


def pause(msg='Press Enter to close.'):
    try:
        input('\n' + msg)
    except EOFError:                                      # no keyboard (input redirected): nothing to wait for
        pass


class Failed(Exception):
    """A problem with one file, explained in plain words; the other files still get converted."""


def need_tools(need_x264=True):
    """Plain-language help instead of a traceback when numpy or ffmpeg is missing."""
    missing = []
    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append(('numpy (a Python package)',
                        'brew install numpy' if sys.platform == 'darwin' else
                        f'"{sys.executable}" -m pip install numpy' if os.name == 'nt' else
                        'sudo apt install python3-numpy   (or dnf / pacman; or: pip install numpy)'))
    if not shutil.which('ffmpeg'):
        missing.append(('ffmpeg (the video tool)',
                        'winget install -e --id Gyan.FFmpeg.Essentials' if os.name == 'nt' else
                        'brew install ffmpeg' if sys.platform == 'darwin' else
                        'sudo apt install ffmpeg   (or dnf / pacman, depending on your Linux)'))
    elif need_x264 and 'libx264' not in subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], text=True,
                                                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout:
        missing.append(('an ffmpeg with the H.264 encoder (libx264); yours has none',
                        'Fedora: ffmpeg from RPM Fusion (https://rpmfusion.org); openSUSE: from Packman. '
                        'Or convert with --prores'))
    if missing and FROZEN:
        print('ffmpeg.exe is missing. Unzip the whole MiniDVR-Convert folder and keep ffmpeg.exe next to the .exe.')
        pause()
        sys.exit(1)
    if missing:
        print('The converter needs some programs that are not installed (or not on the PATH):\n')
        for what, how in missing:
            print(f'  - {what}\n      install with:  {how}')
        print('\nInstall them, open a NEW terminal window (so it finds them), and try again.')
        if os.name == 'nt':
            print('Easier: drag the .AVI onto tools/convert.bat, which offers to install them for you.')
        sys.exit(1)


def pick_files():
    """File dialog for people who double-click instead of using a terminal: the system's own dialog where there is
    one (macOS, GNOME, KDE), else tkinter (Windows, and Linux without zenity/kdialog)."""
    title = 'Choose the DVR recordings to convert'
    dialogs = []
    if sys.platform == 'darwin':
        dialogs.append(['osascript', '-e', f'set fs to choose file with prompt "{title}" of type {{"public.avi", "avi"}} '
                        'with multiple selections allowed', '-e', 'set out to ""', '-e', 'repeat with f in fs',
                        '-e', 'set out to out & POSIX path of f & linefeed', '-e', 'end repeat', '-e', 'return out'])
    elif os.name != 'nt' and (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        if shutil.which('zenity'):
            dialogs.append(['zenity', '--file-selection', '--multiple', '--separator=\n', f'--title={title}',
                            '--file-filter=DVR recordings | *.avi *.AVI', '--file-filter=All files | *'])
        if shutil.which('kdialog'):
            dialogs.append(['kdialog', '--title', title, '--getopenfilename', os.getcwd(),
                            '*.avi *.AVI|DVR recordings', '--multiple', '--separate-output'])
    for cmd in dialogs[:1]:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        return [f for f in r.stdout.splitlines() if f] if r.returncode == 0 else []   # non-zero: cancelled
    try:
        import tkinter, tkinter.filedialog
        root = tkinter.Tk(); root.withdraw()
        files = tkinter.filedialog.askopenfilenames(title=title,
                                                    filetypes=[('DVR recordings', '*.avi *.AVI'), ('All files', '*')])
        root.destroy()
        return list(files)
    except Exception:                                     # no display / tkinter not installed
        print(__doc__.split('\n\n')[-1])
        print('Give the .AVI files on the command line (no file dialog available here).')
        return []


def convert(src, dst, args):
    import numpy as np
    if not os.path.isfile(src):
        raise Failed(f'file not found: {src}')
    with open(src, 'rb') as f:
        hdr = f.read(0x2000)
    v = hdr.find(b'strh')                                 # video stream header: rate/scale and length in frames,
    while v >= 0 and hdr[v + 8:v + 12] != b'vids':
        v = hdr.find(b'strh', v + 4)
    vf = hdr.find(b'strf', v)                             # then its BITMAPINFOHEADER: width and height
    if not hdr.startswith(b'RIFF') or hdr[8:12] != b'AVI ' or v < 0 or vf < 0:
        raise Failed('not a DVR .AVI recording (or it wasn\'t copied completely)')
    scale, rate, _, total = struct.unpack('<IIII', hdr[v + 28:v + 44])
    w, h = struct.unpack('<ii', hdr[vf + 12:vf + 20]); h = abs(h)
    fr = Fraction(rate, scale or 1)
    num, den = fr.numerator, fr.denominator
    s = hdr.find(b'strf', hdr.find(b'auds'))              # the DVR derives the header frame rate from the audio byte
    avg = struct.unpack('<I', hdr[s + 16:s + 20])[0] if s > 0 else 16000   # count at its built-in 16000 B/s;
    if avg != 16000:                                                         # undo that for faster audio
        num *= avg; den *= 16000
    fps = num / den
    if h not in (288, 240) or w > 720:                    # VGA 640x480 / HD 1280x576: each field stretched, can't weave
        raise Failed(f'{w}x{h} frames - this was recorded in VGA or HD size. Only D1 records the fields as they are '
                     f'(704x288, 704x240 for NTSC); set the DVR\'s size menu to D1 and record again.')
    if fps < 40:
        raise Failed(f'{fps:.2f} frames/s - this is not a both-fields recording (expected ~50, or ~60 for NTSC). '
                     f'Was ADJUST.BIN on the card, and was the DVR in D1 mode?')
    ntsc = h == 240
    if not ntsc and fps > 55:
        raise Failed(f'{fps:.2f} fields/s at {h} lines - an NTSC camera recorded with the PAL build (fields stretched '
                     f'to {h} lines). Use the NTSC build of ADJUST.BIN.')
    use_wss = args.parity == 'wss' or (args.parity == 'auto' and not ntsc)
    dst = dst.replace('{fmt}', f'{2 * h}p{round(fps)}' if args.bob else f'{2 * h}i')
    fs = w * h * 2                                        # yuv422p field
    W, H = (w if args.w704 else 720), 2 * h
    # BT.601: the 704 active pixels are the 4:3 (or 16:9) picture, so the 8-px padding keeps the same pixel aspect
    sar = ('40/33' if ntsc else '16/11') if args.widescreen else ('10/11' if ntsc else '12/11')
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
        with wave.open(out, 'wb') as w_:
            w_.setnchannels(ch); w_.setsampwidth(2); w_.setframerate(rate); w_.writeframes(np.concatenate(parts).tobytes())
        return out

    def is_top(y):
        return np.abs(y[0, 16:w - 24].astype(np.int16) - y[1, 16:w - 24]).mean() > args.wss

    def picture_parity(path):
        """Top (True) / bottom per field from the picture alone (no WSS); see the module docstring."""
        dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                               stdout=subprocess.PIPE)
        cost, back, prev = np.zeros(2), [], None           # Viterbi over states 0 = top, 1 = bottom
        while True:
            buf = dec.stdout.read(w * h)
            if len(buf) < w * h:
                break
            b = np.frombuffer(buf, np.uint8).reshape(h, w)[2:h - 3, 16:w - 24].astype(np.float32)  # skip VBI/edge rows
            if prev is not None:
                a, bm = prev, b[1:-1]
                e = np.array([np.abs(bm - (a[1:-1] + a[2:]) / 2).mean(),    # half a line below the previous field
                              np.abs(bm - (a[:-2] + a[1:-1]) / 2).mean(),   # half a line above
                              np.abs(bm - a[1:-1]).mean()])                 # same parity (repeated or dropped field)
                lo, hi, eq = e / (e.mean() + 1e-6)
                tot = cost[:, None] + np.array([[eq + 0.5, lo], [hi, eq + 0.5]])  # [previous][this]
                back.append(tot.argmin(0)); cost = tot.min(0)
            prev = b
        dec.wait()
        st = [int(cost.argmin())]
        for bk in reversed(back):
            st.append(int(bk[st[-1]]))
        return [s == 0 for s in reversed(st)]

    rate = f'{num}/{2 * den}'                             # woven frame rate = field rate / 2
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
    print(f'{os.path.basename(src)} -> {dst}')
    if not use_wss:
        print('  finding the field order from the picture...', flush=True)
    parity = None if use_wss else picture_parity(src)
    tmp = tempfile.TemporaryDirectory()
    audio = avi_audio(src, tmp.name) or src
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', src, '-f', 'rawvideo', '-pix_fmt', 'yuv422p', '-'],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'yuv422p', '-s', f'{W}x{H}',
                            '-r', rate, '-i', '-', '-i', audio, '-map', '0:v', '-map', '1:a?', '-vf', vf,
                            *venc, *flags, *aenc, '-shortest', dst], stdin=subprocess.PIPE)

    def planes(buf):
        f = np.frombuffer(buf, np.uint8)
        return f[:w * h].reshape(h, w), f[w * h:w * h * 3 // 2].reshape(h, w // 2), f[w * h * 3 // 2:].reshape(h, w // 2)

    out = np.empty(W * H * 2, np.uint8)
    Y = out[:W * H].reshape(H, W); U = out[W * H:W * H * 3 // 2].reshape(H, W // 2); V = out[W * H * 3 // 2:].reshape(H, W // 2)
    Y[:] = 16; U[:] = 128; V[:] = 128                     # black side borders (8 px each side)
    n = woven = skipped = 0
    pending = None                                        # a top field waiting for its bottom field
    shown = time.monotonic()
    try:
        while True:
            buf = dec.stdout.read(fs)
            if len(buf) < fs:
                break
            y, u, v = planes(buf)
            n += 1
            if time.monotonic() - shown > 0.5:            # progress line, rewritten in place
                shown = time.monotonic()
                print(f'\r  {100 * n // total}%' if total else f'\r  {n} fields', end='', flush=True)
            if (is_top(y) if parity is None else parity[n - 1]):
                if pending is not None:
                    skipped += 1                          # two top fields in a row: drop the older one
                pending = (y.copy(), u.copy(), v.copy())
                continue
            if pending is None:
                skipped += 1                              # bottom field without a top field before it
                continue
            ty, tu, tv = pending
            pending = None
            Y[0::2, x0:x0 + w], U[0::2, x0 // 2:(x0 + w) // 2], V[0::2, x0 // 2:(x0 + w) // 2] = ty, tu, tv
            Y[1::2, x0:x0 + w], U[1::2, x0 // 2:(x0 + w) // 2], V[1::2, x0 // 2:(x0 + w) // 2] = y, u, v
            for row in () if ntsc else (0, H - 2, H - 1):  # WSS line; last row of each field (half line / blanking):
                src_row = row + 2 if row == 0 else row - 2  # repeat the neighbouring row of the same field (black rows
                Y[row] = Y[src_row]; U[row] = U[src_row]; V[row] = V[src_row]  # make deinterlacers flicker at the edge)
            enc.stdin.write(out.tobytes())
            woven += 1
        enc.stdin.close()
    except BrokenPipeError:
        pass
    enc.wait(); dec.wait()
    print('\r', end='')
    if enc.returncode:
        raise Failed(f'ffmpeg could not write {dst} (see its message above; is the file open in a player, or the disk full?)')
    print(f'  done: {n} fields -> {woven} frames {W}x{H} '
          f'({f"{H}p{round(fps)} deinterlaced" if args.bob else "interlaced tff"}), {skipped} stray fields skipped')


def main():
    ap = argparse.ArgumentParser(description='Convert Mini DVR both-fields recordings (.AVI) into normal video files.',
                                 epilog='Without any file names a file dialog opens. Output goes next to each .AVI '
                                        'unless an output name (.mp4/.mov/.mkv) follows a single input.')
    ap.add_argument('files', nargs='*', help='the .AVI recordings, optionally followed by one output name')
    ap.add_argument('--both', action='store_true', help='make the interlaced and the smooth (--bob) version of each')
    ap.add_argument('--bob', action='store_true', help='output 576p50 / 480p60 (motion-adaptive deinterlace, one frame per field)')
    ap.add_argument('--prores', action='store_true', help='ProRes 422 HQ instead of H.264')
    ap.add_argument('--crf', default='14')
    ap.add_argument('--w704', action='store_true', help='output 704 wide (no 8-px side padding)')
    ap.add_argument('--widescreen', action='store_true',
                    help='mark the video 16:9 (only for a camera set to 16:9; a 4:3 camera would look stretched)')
    ap.add_argument('--wss', type=float, default=20.0, help='row0/row1 difference above which a field counts as top')
    ap.add_argument('--parity', choices=['auto', 'wss', 'picture'], default='auto',
                    help='field parity from the PAL WSS line or from the picture (auto: WSS for 288-line fields, picture for 240)')
    ap.add_argument('--pause', action='store_true', help='wait for Enter at the end (keeps a double-clicked window open)')
    args = ap.parse_args()
    need_tools(need_x264=not args.prores)

    files, dst = args.files, None
    if not files:
        files = pick_files()
        args.both = args.pause = True
        if not files:
            print('No files chosen.')
    elif len(files) == 2 and files[1].lower().endswith(OUT_EXT):
        files, dst = files[:1], files[1]
        if args.both and '{fmt}' not in dst:
            dst = os.path.splitext(dst)[0] + '_{fmt}' + os.path.splitext(dst)[1]
    elif any(f.lower().endswith(OUT_EXT) for f in files):
        ap.error('an output name only works with a single input file')
    if FROZEN:                                            # files dropped on the .exe: like convert.bat
        args.pause = True
        args.both = args.both or not (dst or args.bob or args.prores)
    ext = '.mov' if args.prores else '.mp4'
    failed = 0
    for src in files:
        for bob in ((False, True) if args.both else (args.bob,)):
            args.bob = bob
            out = dst or os.path.splitext(src)[0] + '_{fmt}' + ext
            try:
                convert(src, out, args)
            except Failed as e:
                print(f'\n{os.path.basename(src)}: {e}')
                failed += 1
                break
    if len(files) > 1 or failed:
        print(f'\n{len(files) - failed} of {len(files)} files converted.')
    if args.pause:
        pause()
    sys.exit(1 if failed or not files else 0)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        if not FROZEN:
            raise
        import traceback                                  # keep the .exe's window open long enough to read it
        traceback.print_exc()
        pause('Something went wrong (details above). Press Enter to close.')
        sys.exit(1)
