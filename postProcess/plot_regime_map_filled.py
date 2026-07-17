#!/usr/bin/env python3
"""Filled-background regime map (We vs De) for the elastocapillary Worthington
jet paper (unpublished manuscript draft "ec-worthington-jet-v2").

Companion to `plot_regime_map.py`: instead of (or in addition to) plotting
each numerics point as a discrete marker, this fills the background with the
nearest-neighbour-interpolated regime field from the `num_new` (this
campaign's) points -- meant for use once the numerics grid is dense enough
that a filled field reads as a genuine phase diagram rather than a scatter
(Vatsal, 2026-07-17). Experiments and prior numerics are still overlaid as
discrete markers on top, exactly as in `plot_regime_map.py`, since those
stay sparse by nature.

No scipy dependency -- nearest-neighbour lookup is done directly in numpy
(categorical regime labels have no sensible linear interpolation anyway, so
nearest-neighbour is the correct choice, not just the cheap one).

Data contract (CSV, header `source,De,We,regime`): identical to
`plot_regime_map.py` -- source is exp | num | num_new, regime is one of
rebound | partial_rebound | deposition | deposition_beads | unresolved.

Usage:
  python3 plot_regime_map_filled.py --csv points.csv --out fig/regime-map-filled.pdf \
      [--title "..."] [--demax 0.52] [--resolution 400]
"""
import argparse
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.colors import ListedColormap, BoundaryNorm

matplotlib.rcParams["font.family"] = "serif"
matplotlib.rcParams["font.serif"] = ["Computer Modern Roman"]
matplotlib.rcParams["mathtext.fontset"] = "cm"
try:
    import shutil
    if shutil.which("latex"):
        matplotlib.rcParams["text.usetex"] = True
        matplotlib.rcParams["text.latex.preamble"] = r"\usepackage{amsmath}"
except Exception:
    pass

REGIME = {
    "rebound":          ("#22355f", "rebound"),
    "partial_rebound":  ("#e9edc4", "partial rebound"),
    "deposition":       ("#e6c185", "deposition"),
    "deposition_beads": ("#c23a2b", "deposition + beads"),
    "unresolved":       ("#9aa0a6", "unresolved"),
}
ORDER = ["rebound", "partial_rebound", "deposition", "deposition_beads", "unresolved"]
CODE = {r: i for i, r in enumerate(ORDER)}


def load(path):
    rows = []
    with open(path) as f:
        for raw in f:
            s = raw.strip()
            if not s or s.startswith("#") or s.lower().startswith("source,"):
                continue
            src, de, we, regime = [c.strip() for c in s.split(",")[:4]]
            rows.append((src, float(de), float(we), regime))
    return rows


def nearest_neighbor_field(de_grid, we_grid, pts_de, pts_we, pts_code, de_scale, we_scale):
    """Assign each grid cell the regime code of its nearest data point,
    distances normalised by (de_scale, we_scale) so the two very
    differently-scaled axes contribute comparably to "nearest"."""
    gd = de_grid.ravel()[:, None] / de_scale
    gw = we_grid.ravel()[:, None] / we_scale
    pd = pts_de[None, :] / de_scale
    pw = pts_we[None, :] / we_scale
    d2 = (gd - pd) ** 2 + (gw - pw) ** 2
    nearest = np.argmin(d2, axis=1)
    return pts_code[nearest].reshape(de_grid.shape)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", required=True, help="output .pdf path (.png written alongside)")
    ap.add_argument("--title", default=None)
    ap.add_argument("--demax", type=float, default=0.52)
    ap.add_argument("--wemax", type=float, default=65.0)
    ap.add_argument("--wemin", type=float, default=5.0)
    ap.add_argument("--resolution", type=int, default=400,
                     help="grid points along each axis for the filled field")
    args = ap.parse_args()

    rows = load(args.csv)
    new_rows = [r for r in rows if r[0] == "num_new"]
    if not new_rows:
        raise SystemExit("no num_new points in CSV -- nothing to fill the background with")

    pts_de = np.array([r[1] for r in new_rows])
    pts_we = np.array([r[2] for r in new_rows])
    pts_code = np.array([CODE.get(r[3], CODE["unresolved"]) for r in new_rows])

    fig, ax = plt.subplots(figsize=(11.0, 8.5))

    de_lin = np.linspace(0.0, args.demax, args.resolution)
    we_lin = np.linspace(args.wemin, args.wemax, args.resolution)
    de_grid, we_grid = np.meshgrid(de_lin, we_lin)
    field = nearest_neighbor_field(de_grid, we_grid, pts_de, pts_we, pts_code,
                                    de_scale=args.demax, we_scale=(args.wemax - args.wemin))

    cmap = ListedColormap([REGIME[r][0] for r in ORDER])
    norm = BoundaryNorm(np.arange(-0.5, len(ORDER) + 0.5, 1), cmap.N)
    ax.pcolormesh(de_grid, we_grid, field, cmap=cmap, norm=norm, shading="auto", zorder=1)

    # this campaign's actual sample points, small markers so the underlying
    # grid density stays visible/auditable through the filled field
    ax.scatter(pts_de, pts_we, s=18, marker="s", facecolor="none",
               edgecolor="black", linewidth=0.6, alpha=0.55, zorder=3)

    # experiments + prior numerics stay as discrete markers -- they're sparse
    # by nature and should never be smeared into a filled field
    for src, de, we, regime in rows:
        colour = REGIME.get(regime, ("#9aa0a6", regime))[0]
        if src == "num":
            ax.scatter(de, we, s=230, marker="D", facecolor=colour,
                       edgecolor="black", linewidth=1.5, zorder=5)
        elif src == "exp":
            ax.scatter(de, we, s=250, marker="o", facecolor=colour,
                       edgecolor="black", linewidth=1.5, zorder=6)

    ax.set_xlim(-0.01, args.demax)
    ax.set_ylim(args.wemin, args.wemax)
    ax.set_xlabel(r"$De$", fontsize=30, labelpad=12)
    ax.set_ylabel(r"$We$", fontsize=30, labelpad=12)
    ax.tick_params(which="both", direction="out", width=2.2, labelsize=22, pad=8)
    ax.tick_params(which="major", length=10)
    ax.tick_params(which="minor", length=5)
    ax.minorticks_on()
    for spine in ax.spines.values():
        spine.set_linewidth(2.2)
    if args.title:
        ax.set_title(args.title, fontsize=20, pad=12)

    present = [r for r in ORDER if any(row[3] == r for row in rows)]
    reg_handles = [Line2D([0], [0], marker="s", linestyle="none", markersize=16,
                          markerfacecolor=REGIME[r][0], markeredgecolor="black",
                          label=REGIME[r][1]) for r in present]
    leg1 = ax.legend(handles=reg_handles, fontsize=15, loc="upper left",
                     bbox_to_anchor=(1.01, 1.0), frameon=False, title="regime (filled = nearest-neighbour\nfrom this campaign's grid)",
                     title_fontsize=13, handletextpad=0.4)
    ax.add_artist(leg1)
    shape_handles = [
        Line2D([0], [0], marker="o", linestyle="none", markersize=15,
               markerfacecolor="white", markeredgecolor="black", label="experiments"),
        Line2D([0], [0], marker="D", linestyle="none", markersize=14,
               markerfacecolor="white", markeredgecolor="black", label="numerics (prior, uncertain method)"),
        Line2D([0], [0], marker="s", linestyle="none", markersize=8,
               markerfacecolor="none", markeredgecolor="black", label="this campaign's sample points"),
    ]
    leg2 = ax.legend(handles=shape_handles, fontsize=14, loc="upper left",
                     bbox_to_anchor=(1.01, 0.38), frameon=False, handletextpad=0.4)

    extra = (leg1, leg2)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    fig.savefig(args.out, bbox_inches="tight", pad_inches=0.15,
                bbox_extra_artists=extra, dpi=300)
    png = os.path.splitext(args.out)[0] + ".png"
    fig.savefig(png, bbox_inches="tight", pad_inches=0.15,
                bbox_extra_artists=extra, dpi=200)
    plt.close(fig)
    print("wrote", args.out, "and", png, "from", len(new_rows), "num_new points")


if __name__ == "__main__":
    main()
