#!/usr/bin/env python3
"""Composite already-rendered per-frame PNGs into one labeled contact sheet.

Takes N rendered snapshot images (from render_one.py) for a single case and
lays them out side by side under a title banner stating the case number,
(We, De), and the assigned regime -- so a human reviewer can see exactly the
evidence a classification was based on without re-deriving it.

Usage:
    python3 make_labeled_contact_sheet.py \
        --images render_t9.png render_t13.png render_t17.png render_t19.9.png \
        --grid fixedBeta --case 090 --we 35 --de 0.25 --regime deposition_beads \
        --status completed --note "neck at t=13-17, reabsorbed by t=19.9" \
        -o classification-review/fixedBeta/090.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg


REGIME_COLORS = {
    "rebound": "#1c2b5e",
    "partial_rebound": "#e8e6b8",
    "deposition": "#e0a866",
    "deposition_beads": "#c0392b",
    "unresolved": "#8c8c8c",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--images", nargs="+", required=True, type=Path,
                    help="Rendered frame PNGs, in chronological order.")
    p.add_argument("--grid", required=True, choices=("fixedBeta", "fixedEc", "newtonianDe0", "newtonianDe0-bigdomain"))
    p.add_argument("--case", required=True)
    p.add_argument("--we", required=True, type=float)
    p.add_argument("--de", required=True, type=float)
    p.add_argument("--regime", required=True)
    p.add_argument("--status", default="completed")
    p.add_argument("--note", default="")
    p.add_argument("-o", "--output", required=True, type=Path)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    n = len(args.images)
    fig, axes = plt.subplots(1, n, figsize=(4.2 * n, 5.2))
    if n == 1:
        axes = [axes]

    for ax, img_path in zip(axes, args.images):
        img = mpimg.imread(img_path)
        ax.imshow(img)
        ax.set_title(img_path.stem.replace("render_", "").replace("_", " "), fontsize=11)
        ax.axis("off")

    color = REGIME_COLORS.get(args.regime, "#ffffff")
    title = (f"{args.grid}/{args.case}   We={args.we:g}  De={args.de:g}   "
             f"status={args.status}   →   REGIME: {args.regime.upper()}")
    fig.suptitle(title, fontsize=16, fontweight="bold",
                 bbox=dict(boxstyle="round,pad=0.4", facecolor=color, alpha=0.35))
    if args.note:
        fig.text(0.5, 0.02, args.note, ha="center", va="bottom", fontsize=10, style="italic", wrap=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"WROTE {args.output}")


if __name__ == "__main__":
    main()
