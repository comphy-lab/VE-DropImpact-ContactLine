#!/usr/bin/env python3
"""Extract a row-by-row interface radius profile directly from a rendered
PNG (by detecting the magenta interface line), to check for a genuine
neck/bulge (bead-on-string) structure when the jet tip is too thin or too
close to the domain edge for the eye (or the render's contour tracer) to
resolve reliably. Complements, doesn't replace, visual inspection --
use when a render looks ambiguous near a thin/high-aspect-ratio feature.

Usage: python3 radius_profile_from_render.py <image.png> [<image2.png> ...]
Prints, per row (top to bottom), the radius (in px, relative to the detected
symmetry axis) of each detected interface segment. A neck shows as a local
minimum in radius sandwiched between two larger values above and below.
"""
import numpy as np
from PIL import Image
import sys, os

def get_mask(path):
    im = Image.open(path).convert('RGB')
    arr = np.array(im)
    r = arr[:,:,0].astype(int); g = arr[:,:,1].astype(int); b = arr[:,:,2].astype(int)
    mask = (r>180) & (b>180) & (g<120)
    return mask

def segments_in_row(xs, gap=4):
    if len(xs)==0: return []
    xs = np.sort(xs)
    segs = []
    start = xs[0]; prev = xs[0]
    for x in xs[1:]:
        if x - prev > gap:
            segs.append((start, prev))
            start = x
        prev = x
    segs.append((start, prev))
    return segs

def analyze(path, nrows=45):
    mask = get_mask(path)
    ys, xs = np.where(mask)
    if len(ys)==0:
        print(f"{os.path.basename(path)}: NO MAGENTA"); return
    ymin, ymax = ys.min(), ys.max()
    center = np.median(xs)  # approx axis of symmetry
    print(f"\n=== {os.path.basename(path)} === y[{ymin},{ymax}] span={ymax-ymin} center_x~{center:.0f}")
    step = max(1, (ymax-ymin)//nrows)
    for y in range(ymin, ymax+1, step):
        row_xs = xs[ys==y]
        right_xs = row_xs[row_xs>=center]
        segs = segments_in_row(right_xs)
        # convert to radius (distance from center)
        radii = [(round(a-center),round(b-center)) for a,b in segs]
        frac = (y-ymin)/(ymax-ymin+1e-9)
        print(f"  y={y:5d} top_frac={frac:4.2f} n_r_segs={len(segs)}  radius_ranges: {radii}")

if __name__=='__main__':
    for p in sys.argv[1:]:
        analyze(p)
