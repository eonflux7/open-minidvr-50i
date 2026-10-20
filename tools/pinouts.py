#!/usr/bin/env python3
"""Draw the README's AV cable pictures: docs/av-pinouts-{dark,light}.png (CTIA, OMTP and camcorder AV TRRS pinouts)
and docs/av-rewire-{dark,light}.png (re-soldering an OMTP or camcorder AV cable to CTIA, the pinout the DVR takes).

The README picks the dark or light version with <picture>, like the banner.

Usage: pinouts.py [--font Regular.ttf] [--bold Bold.ttf]   (default: DejaVu Sans)
"""
import argparse, os
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument('--font', default='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
ap.add_argument('--bold', default='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
args = ap.parse_args()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs')
S = 2                                                     # drawn at 2x and scaled down for smooth edges

THEMES = {
    'light': dict(bg=(255, 255, 255), card=(208, 215, 222), text=(17, 24, 39), muted=(107, 114, 128),
                  guide=(229, 231, 235), pick=(240, 253, 244), pick_edge=(22, 163, 74), ok=(21, 128, 61),
                  bad=(185, 28, 28), insul=(31, 41, 55), body=(55, 65, 81), collar=(201, 162, 39),
                  sig={'left': (75, 85, 99), 'right': (200, 30, 30), 'gnd': (21, 128, 61), 'video': (161, 98, 7)}),
    'dark': dict(bg=(13, 17, 23), card=(48, 54, 61), text=(243, 244, 246), muted=(156, 163, 175),
                 guide=(48, 54, 61), pick=(15, 42, 26), pick_edge=(34, 197, 94), ok=(74, 222, 128),
                 bad=(248, 113, 113), insul=(0, 0, 0), body=(75, 85, 99), collar=(201, 162, 39),
                 sig={'left': (209, 213, 219), 'right': (248, 113, 113), 'gnd': (74, 222, 128), 'video': (250, 204, 21)}),
}
FILL = {'left': (229, 231, 235), 'right': (224, 49, 43), 'gnd': (34, 164, 71), 'video': (250, 204, 21)}
NAME = {'left': 'Left audio', 'right': 'Right audio', 'gnd': 'Ground', 'video': 'Video'}
RCA = {'left': 'white RCA', 'right': 'red RCA', 'gnd': 'all shields', 'video': 'yellow RCA'}
CONTACTS = ('Tip', 'Ring 1', 'Ring 2', 'Sleeve')
PINOUTS = {                                               # tip, ring 1, ring 2, sleeve
    'CTIA': ('left', 'right', 'gnd', 'video'),
    'OMTP': ('left', 'right', 'video', 'gnd'),
    'Camcorder AV': ('left', 'video', 'gnd', 'right'),
}


def font(size, bold=False):
    return ImageFont.truetype(args.bold if bold else args.font, size * S)


class Canvas:
    """ImageDraw in 1x coordinates (everything is multiplied by S)."""

    def __init__(self, w, h, t):
        self.t, self.w, self.h = t, w, h
        self.im = Image.new('RGB', (w * S, h * S), t['bg'])
        self.d = ImageDraw.Draw(self.im)
        self.d.rounded_rectangle((S, S, w * S - S, h * S - S), 10 * S, outline=t['card'], width=S)

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=1, r=0):
        self.d.rounded_rectangle((x0 * S, y0 * S, x1 * S, y1 * S), r * S, fill=fill, outline=outline, width=width * S)

    def line(self, pts, fill, width=1, dash=None):
        pts = [(x * S, y * S) for x, y in pts]
        if not dash:
            self.d.line(pts, fill=fill, width=width * S, joint='curve')
            for x, y in (pts[0], pts[-1]):
                self.d.ellipse((x - width * S / 2, y - width * S / 2, x + width * S / 2, y + width * S / 2), fill=fill)
            return
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):      # dashed: straight segments only
            n = max(1, int(((xb - xa) ** 2 + (yb - ya) ** 2) ** .5 / (dash * S)))
            for k in range(0, n, 2):
                self.d.line((xa + (xb - xa) * k / n, ya + (yb - ya) * k / n,
                             xa + (xb - xa) * min(k + 1, n) / n, ya + (yb - ya) * min(k + 1, n) / n),
                            fill=fill, width=width * S)

    def dot(self, x, y, r, fill, outline=None):
        self.d.ellipse(((x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S), fill=fill, outline=outline,
                       width=S if outline else 0)

    def text(self, x, y, s, size, fill, bold=False, anchor='ls'):
        self.d.text((x * S, y * S), s, font=font(size, bold), fill=fill, anchor=anchor)

    def save(self, name):
        path = os.path.join(OUT, name)
        self.im.resize((self.w, self.h), Image.LANCZOS).save(path, optimize=True)
        print(path, (self.w, self.h))


def plug(c, cx, top, sigs, seg=52, gap=8, hw=16):
    """Vertical TRRS plug, tip up. Returns the y centre of each contact."""
    t, ys = c.t, []
    y = top
    for i, s in enumerate(sigs):
        y0, y1 = y, y + seg
        if i == 0:                                        # rounded tip
            c.d.pieslice(((cx - hw) * S, (y0 - 4) * S, (cx + hw) * S, (y0 + 2 * hw - 4) * S), 180, 360, fill=FILL[s])
            c.rect(cx - hw, y0 + hw - 4, cx + hw, y1, fill=FILL[s])
        else:
            c.rect(cx - hw, y0, cx + hw, y1, fill=FILL[s])
        if s == 'left':                                   # light grey needs an edge on a white page
            c.line([(cx - hw, y0 + (hw - 4 if i == 0 else 0)), (cx - hw, y1)], t['muted'])
            c.line([(cx + hw, y0 + (hw - 4 if i == 0 else 0)), (cx + hw, y1)], t['muted'])
        ys.append((y0 + y1) / 2)
        y = y1
        if i < 3:
            c.rect(cx - hw, y, cx + hw, y + gap, fill=t['insul'])
            y += gap
    c.rect(cx - hw - 6, y, cx + hw + 6, y + 10, fill=t['collar'], r=2)
    c.rect(cx - hw - 6, y + 10, cx + hw + 6, y + 68, fill=t['body'], r=6)
    return ys


def pinouts(t):
    c = Canvas(950, 500, t)
    c.rect(150, 14, 386, 486, fill=t['pick'], outline=t['pick_edge'], width=2, r=10)
    rows = [106, 166, 226, 286]
    for name, y in zip(CONTACTS, rows):
        c.text(132, y + 5, name, 14, t['muted'], bold=True, anchor='rs')
        c.line([(142, y), (938, y)], t['guide'], dash=4)
    subs = {'CTIA': 'Mini DVR, Apple, most phones', 'OMTP': 'Older Nokia, some generic cables',
            'Camcorder AV': 'Camera AV cables'}
    verdict = {'CTIA': (True, 'Plugs straight into', 'the DVR'),
               'OMTP': (False, 'Video and ground swapped:', 'adapter or re-solder'),
               'Camcorder AV': (False, 'Video and right swapped:', 'swap two RCA plugs')}
    for k, (name, sigs) in enumerate(PINOUTS.items()):
        cx = 192 + 262 * k
        c.text(cx - 20, 42, name, 21, t['text'], bold=True)
        c.text(cx - 20, 62, subs[name], 13, t['muted'])
        plug(c, cx, 80, sigs)
        for i, s in enumerate(sigs):
            if s != PINOUTS['CTIA'][i]:                   # differs from what the DVR expects
                c.rect(cx + 26, rows[i] - 22, cx + 196, rows[i] + 24, outline=t['bad'], width=2, r=6)
            c.text(cx + 34, rows[i] + 1, NAME[s], 16, t['sig'][s], bold=True)
            phone = s == 'video' and name != 'Camcorder AV'   # the mic contact on a phone headset
            c.text(cx + 34, rows[i] + 18, RCA[s] + (' · phone mic' if phone else ''), 12, t['muted'])
        good, l1, l2 = verdict[name]
        col = t['ok'] if good else t['bad']
        c.text(cx - 20, 434, ('✓ ' if good else '✗ ') + l1, 14, col, bold=True)
        c.text(cx - 20, 454, '   ' + l2, 14, col, bold=True)
    c.save(f'av-pinouts-{theme}.png')


def rcaplug(c, x, y, s):
    """Small horizontal RCA plug pointing right: shell, coloured ring, centre pin."""
    t = c.t
    c.rect(x, y - 9, x + 34, y + 9, fill=t['body'], r=4)
    c.rect(x + 34, y - 11, x + 46, y + 11, fill=FILL[s] if s != 'gnd' else t['muted'], r=2)
    c.rect(x + 46, y - 3, x + 62, y + 3, fill=t['collar'], r=2)


def rewire(t):
    W, H = 1240, 650
    c = Canvas(W, H, t)
    c.text(28, 42, 'Re-soldering a cable to CTIA (what the Mini DVR takes)', 22, t['text'], bold=True)
    c.text(28, 66, 'Cut the cable, find each wire with a multimeter (the colours inside vary), join them as shown, '
                   'insulate every joint.', 14, t['muted'])
    panels = (('OMTP cable', 'OMTP', ('left', 'right', 'video', 'gnd'),
               ['Ring 2 and sleeve trade places.', 'No soldering: a CTIA↔OMTP headset adapter does the same.']),
              ('Camcorder AV cable', 'Camcorder AV', ('left', 'video', 'gnd', 'right'),
               ['Ring 1 and sleeve trade places.', 'No soldering: put the camera\'s video into the red RCA plug',
                'and its right audio into the yellow one.']))
    for k, (title, key, rca_order, notes) in enumerate(panels):
        x0 = 28 + k * 606
        c.rect(x0, 90, x0 + 578, H - 22, outline=t['card'], width=1, r=10)
        c.text(x0 + 22, 124, title + ' → CTIA', 18, t['text'], bold=True)
        px = x0 + 110
        c.text(px, 150, 'plug side', 12, t['muted'], anchor='ms')
        ys = plug(c, px, 168, PINOUTS['CTIA'], seg=62, gap=8)
        # the plug's segments sit on the rows; label the contacts on the left
        for name, y in zip(CONTACTS, ys):
            c.text(px - 30, y + 5, name, 13, t['muted'], bold=True, anchor='rs')
        jl, jr = x0 + 220, x0 + 400                       # the two sides of the cut
        c.text((jl + jr) / 2, 150, 'cut and re-join', 12, t['muted'], anchor='ms')
        c.text(x0 + 470, 150, 'RCA side', 12, t['muted'], anchor='ms')
        side = {s: y for s, y in zip(rca_order, ys)}      # as bought, each RCA wire sits across from its old contact
        for i, (s, y) in enumerate(zip(PINOUTS['CTIA'], ys)):
            c.line([(px + 16, y), (jl, y)], FILL[s] if s != 'left' else t['muted'], width=5)
        for s, y in side.items():
            c.line([(jr, y), (x0 + 450, y)], FILL[s] if s != 'left' else t['muted'], width=5)
            rcaplug(c, x0 + 446, y, s)
            c.text(x0 + 520, y + 5, {'left': 'white', 'right': 'red', 'video': 'yellow', 'gnd': 'shields'}[s], 13,
                   t['sig'][s], bold=True)
        for s, y in zip(PINOUTS['CTIA'], ys):              # new joins: contact -> the RCA wire it must carry
            y2 = side[s]
            col = t['sig'][s]
            if y2 == y:
                c.line([(jl, y), (jr, y)], col, width=3)
            else:
                c.line([(jl, y), (jl + 40, y), (jr - 40, y2), (jr, y2)], col, width=4)
            c.dot(jl, y, 6, col); c.dot(jr, y2, 6, col)
        swapped = [i for i, (s, y) in enumerate(zip(PINOUTS['CTIA'], ys)) if side[s] != y]
        c.text((jl + jr) / 2, ys[swapped[1]] + 34, '↑ swap ↑', 13, t['bad'], bold=True, anchor='ms')
        for i, line in enumerate(notes):
            c.text(x0 + 22, 556 + 22 * i, line, 14, t['text'] if i == 0 else t['muted'], bold=i == 0)
    c.save(f'av-rewire-{theme}.png')


for theme, t in THEMES.items():
    pinouts(t)
    rewire(t)
