#!/usr/bin/env python3
"""Render one VE drop-impact snapshot, serially, using ``VideoAxi.py``."""

from __future__ import annotations

import argparse
import importlib.util
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any


def load_video() -> Any:
    path = Path(__file__).resolve().with_name("VideoAxi.py")
    spec = importlib.util.spec_from_file_location("ve_video", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render one VE snapshot (serial).")
    parser.add_argument("--case-dir", type=Path, required=True)
    parser.add_argument("--snap-glob", default="intermediate/snapshot-*")
    parser.add_argument("--snapshot", type=Path,
                        help="Snapshot path relative to --case-dir.")
    parser.add_argument("--time", type=float,
                        help="Render the available snapshot nearest this time.")
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--ny", type=int, default=400)
    parser.add_argument("--left-field", choices=("D2", "trA"), default="D2")
    parser.add_argument("--xmin", type=float)
    parser.add_argument("--xmax", type=float)
    parser.add_argument("--ymin", type=float)
    parser.add_argument("--ymax", type=float)
    parser.add_argument("--vel-vmin", type=float)
    parser.add_argument("--vel-vmax", type=float)
    parser.add_argument("--left-vmin", type=float)
    parser.add_argument("--left-vmax", type=float)
    parser.add_argument("--impact-speed", type=float, default=1.)
    parser.add_argument("--no-streamlines", dest="streamlines", action="store_false",
                        default=True)
    parser.add_argument("--streamline-density", type=float, default=1.15)
    return parser.parse_args()


def choose_snapshot(video: Any, case_dir: Path, args: argparse.Namespace) -> Path:
    if args.snapshot:
        path = args.snapshot if args.snapshot.is_absolute() else case_dir / args.snapshot
        if not path.is_file():
            raise FileNotFoundError(path)
        return path.resolve()
    snapshots = video.list_snapshots(case_dir, args.snap_glob)
    if not snapshots:
        raise FileNotFoundError(f"No snapshots match {args.snap_glob!r} in {case_dir}")
    return min(snapshots, key=lambda p: abs(video.snapshot_time(p) - args.time)) \
        if args.time is not None else snapshots[-1]


def main() -> int:
    args = parse_args()
    if args.ny <= 2:
        raise SystemExit("--ny must be > 2")
    video = load_video()
    case_dir = args.case_dir.resolve()
    snapshot = choose_snapshot(video, case_dir, args)
    with tempfile.TemporaryDirectory(prefix="ve-render-one-", dir=case_dir) as build:
        video.configure_worker_environment(Path(build))
        video.ensure_plotting()
        facet_bin, data_bin = video.precompile_helpers(Path(__file__).resolve().parent,
                                                        Path(build))
        facets = video.get_facets(snapshot, facet_bin, case_dir)
        xmin, xmax, ymin, ymax = video.resolve_window(facets, args.xmin, args.xmax,
                                                       args.ymin, args.ymax)
        _, _, fields = video.get_field_grid(
            snapshot, data_bin, case_dir, xmin, 0., xmax,
            max(abs(ymin), abs(ymax)), args.ny
        )
        left_limits = video.finite_limits(fields[args.left_field])
        output = args.output or case_dir / f"render-one-t{video.snapshot_time(snapshot):.4f}.png"
        output = output if output.is_absolute() else case_dir / output
        render_options = vars(args).copy()
        render_options.update(xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
        render_args = SimpleNamespace(**render_options)
        video.render_frame(output, snapshot, facet_bin, data_bin, case_dir, render_args,
                           (args.vel_vmin if args.vel_vmin is not None else 0.,
                            args.vel_vmax if args.vel_vmax is not None else args.impact_speed,
                            args.left_vmin if args.left_vmin is not None else left_limits[0],
                            args.left_vmax if args.left_vmax is not None else left_limits[1]))
    print(f"WROTE {output} t={video.snapshot_time(snapshot):.4f} snapshot={snapshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
