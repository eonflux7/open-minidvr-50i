#!/usr/bin/env python3
"""Measure the bottom tearing band in a DVR recording.

For each moving frame and each pair of rows near the bottom, find which frame's picture (this one, or 1-3 frames
earlier; compared against the rows just above, where the picture is known good) the rows continue. Stale rows
continue an OLDER frame. Prints the stale share per row pair and a score (mean stale share of rows 270-287 minus the
baseline of rows 250-269). 50i files: frame = field, so "2 earlier" = the previous use of the same buffer.

Usage: bandcheck.py PICT0024.AVI [more.avi ...]
"""
import sys, json, subprocess
import numpy as np


def analyse(src):
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                               'stream=width,height', '-of', 'json', src]))['streams'][0]
    w, h = info['width'], info['height']
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', src, '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE)
    F = []
    while True:
        b = p.stdout.read(w * h)
        if len(b) < w * h:
            break
        F.append(np.frombuffer(b, np.uint8).reshape(h, w).astype(np.float32)[:, 30:w - 34])
    F = np.array(F)
    rows = list(range(250, h, 2))
    stale = {r: [0, 0] for r in rows}
    for i in range(4, len(F)):
        if np.abs(F[i] - F[i - 2]).mean() < 10:
            continue
        for r in rows:
            band = F[i][r:r + 2]
            e = [np.abs(band - F[i - d][r - 3:r - 1]).mean() for d in (0, 1, 2, 3)]
            stale[r][0] += int(np.argmin(e) != 0); stale[r][1] += 1
    share = {r: (s / t if t else 0) for r, (s, t) in stale.items()}
    base = np.mean([share[r] for r in rows if r < 270]); band = np.mean([share[r] for r in rows if r >= 270])
    worst = sorted(rows, key=lambda r: -share[r])[:4]
    print(f'{src}: {len(F)} frames, moving {stale[rows[0]][1]}; stale share rows 250-269 {base:.0%}, 270-{h-1} '
          f'{band:.0%} -> band score {band - base:+.0%}; worst rows ' +
          ', '.join(f'{r}-{r+1} {share[r]:.0%}' for r in sorted(worst)))


for f in sys.argv[1:]:
    analyse(f)
