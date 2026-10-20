#!/usr/bin/env python3
"""Make the README banner: two product photos on a transparent background plus the project name.

Writes docs/banner-dark.png (light text) and docs/banner-light.png (dark text); the README picks one with <picture>.
Photos must be on a plain white background (it's cut away from the edges inwards).

Usage: banner.py BACK_PHOTO FRONT_PHOTO FONT.ttf|woff [--title open-minidvr-50i]
"""
import argparse, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

ap = argparse.ArgumentParser()
ap.add_argument('back'); ap.add_argument('front'); ap.add_argument('font')
ap.add_argument('--title', default='open-minidvr-50i')
args = ap.parse_args()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs')
W, H, S = 1280, 400, 2                                   # output size; drawn at 2x and scaled down for smooth edges


def cutout(path, height):
    """Photo on white -> RGBA cropped to the object (largest non-background blob), scaled to `height` px."""
    im = Image.open(path).convert('RGB')
    a = np.asarray(im).astype(np.int16)
    whiteish = (a.min(axis=2) > 232) & (a.max(axis=2) - a.min(axis=2) < 22)
    lab, _ = ndimage.label(whiteish)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(edge))                        # white connected to the border = background
    obj, n = ndimage.label(~bg)
    sizes = ndimage.sum(np.ones_like(obj), obj, range(1, n + 1))
    keep = obj == (1 + int(np.argmax(sizes)))
    keep = ndimage.binary_fill_holes(keep)
    keep = ndimage.binary_erosion(keep, iterations=max(2, im.width // 150))  # drop the white-tinted rim (halo on dark)
    alpha = Image.fromarray((keep * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    rgba = im.convert('RGBA'); rgba.putalpha(alpha)
    rgba = rgba.crop(Image.fromarray(keep.astype(np.uint8) * 255).getbbox())
    return rgba.resize((round(rgba.width * height / rgba.height), height), Image.LANCZOS)


def shadow(img, blur, opacity):
    sh = Image.new('RGBA', img.size, (0, 0, 0, 0))
    sh.putalpha(img.getchannel('A').point(lambda v: v * opacity // 255))
    pad = blur * 3
    canvas = Image.new('RGBA', (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    canvas.paste(sh, (pad, pad))
    return canvas.filter(ImageFilter.GaussianBlur(blur)), pad


back = cutout(args.back, 270 * S)
front = cutout(args.front, 235 * S)
back = back.rotate(-6, resample=Image.BICUBIC, expand=True)
front = front.rotate(5, resample=Image.BICUBIC, expand=True)

for theme, color in (('dark', (236, 236, 232)), ('light', (29, 29, 27))):
    c = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0))
    x0, y0 = 30 * S, 14 * S
    x1, y1 = x0 + int(back.width * 0.48), H * S - front.height - 18 * S
    for img, (x, y) in ((back, (x0, y0)), (front, (x1, y1))):
        sh, pad = shadow(img, 14 * S, 90 if theme == 'light' else 150)
        c.alpha_composite(sh, (x - pad + 6 * S, y - pad + 12 * S))
        c.alpha_composite(img, (x, y))
    d = ImageDraw.Draw(c)
    tx = x1 + front.width + 50 * S
    size = 76 * S
    font = ImageFont.truetype(args.font, size)
    while d.textlength(args.title, font=font) > W * S - tx - 30 * S and size > 20:
        size -= 2; font = ImageFont.truetype(args.font, size)
    box = d.textbbox((0, 0), args.title, font=font)
    d.text((tx, (H * S - (box[3] - box[1])) // 2 - box[1]), args.title, font=font, fill=color + (255,))
    out = c.resize((W, H), Image.LANCZOS)
    path = os.path.join(OUT, f'banner-{theme}.png')
    out.save(path, optimize=True)
    print(path, out.size)
