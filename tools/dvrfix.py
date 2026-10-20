#!/usr/bin/env python3
"""Convert a patched-DVR field recording (e.g. 704x288 MJPEG AVI) into a clean 4:3 MP4.

- finds the recurring glitch row of the recording (one fixed row that intermittently matches neither neighbour,
  a capture-pipeline hiccup at 1:1 vertical size) and interpolates it in every frame; other isolated rows are
  repaired when detected
- crops the edges (WSS data row on top, black band on the right) and scales to 768x576 square pixels

Usage: dvrfix.py input.avi output.mp4 [--crop W:H:X:Y] [--size WxH] [--keep-size]
"""
import argparse, json, subprocess, sys
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('dst')
ap.add_argument('--crop', default='696:286:0:1', help='ffmpeg crop applied after repair (default drops WSS row + right band)')
ap.add_argument('--size', default='768x576', help='output size (default 4:3 square pixels at 576 lines)')
ap.add_argument('--threshold', type=float, default=4.0)
args = ap.parse_args()

info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                           'stream=width,height,r_frame_rate', '-of', 'json', args.src]))['streams'][0]
w, h, rate = info['width'], info['height'], info['r_frame_rate']
fs = w * h * 2  # yuv422p

def row_scores(yf):
    up = np.abs(yf[1:-1] - yf[:-2]).mean(1); dn = np.abs(yf[1:-1] - yf[2:]).mean(1); br = np.abs(yf[:-2] - yf[2:]).mean(1)
    return np.minimum(up, dn) - br

# pass 1: find the recurring glitch row(s)
scan = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', args.src, '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE)
counts = np.zeros(h, int)
while True:
    b = scan.stdout.read(w * h)
    if len(b) < w * h:
        break
    s_ = row_scores(np.frombuffer(b, np.uint8).reshape(h, w)[:, 10:w - 20].astype(np.int16))
    if s_.max() > args.threshold:
        counts[int(np.argmax(s_)) + 1] += 1
scan.wait()
always = [int(r) for r in np.where(counts >= max(3, counts.sum() // 4))[0] if 0 < r < h - 1]
print('recurring glitch rows:', always, '(hits per row:', {int(r): int(counts[r]) for r in np.nonzero(counts)[0]}, ')')
dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', args.src, '-f', 'rawvideo', '-pix_fmt', 'yuv422p', '-'],
                       stdout=subprocess.PIPE)
ow, oh = args.size.split('x')
enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'yuv422p', '-s', f'{w}x{h}',
                        '-r', rate, '-i', '-', '-i', args.src, '-map', '0:v', '-map', '1:a?',
                        '-vf', f'crop={args.crop},scale={ow}:{oh}:flags=lanczos,setsar=1',
                        '-c:v', 'libx264', '-crf', '16', '-preset', 'slow', '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', '-b:a', '128k', args.dst], stdin=subprocess.PIPE)
n = fixed = 0
while True:
    buf = dec.stdout.read(fs)
    if len(buf) < fs:
        break
    f = np.frombuffer(buf, np.uint8).copy()
    y = f[:w * h].reshape(h, w); u = f[w * h:w * h * 3 // 2].reshape(h, w // 2); v = f[w * h * 3 // 2:].reshape(h, w // 2)
    score = row_scores(y[:, 10:w - 20].astype(np.int16))
    for r in sorted(set(always) | set(int(x) + 1 for x in np.where(score > args.threshold)[0])):
        for p in (y, u, v):
            p[r] = ((p[r - 1].astype(np.uint16) + p[r + 1]) // 2).astype(np.uint8)
        fixed += 1
    enc.stdin.write(f.tobytes()); n += 1
enc.stdin.close(); enc.wait(); dec.wait()
print(f'{args.dst}: {n} frames, {fixed} glitch rows repaired')
