#!/usr/bin/env python3
"""Render the latest available snapshot from every case in a regime-map root."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import math
import os
import shutil
import tempfile
from concurrent.futures import ProcessPoolExecutor
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
    parser = argparse.ArgumentParser(
        description="Render the latest snapshot from each case directory."
    )
    parser.add_argument("--case-root", type=Path, required=True,
                        help="Directory containing numbered case subdirectories.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cpus", "--CPUs", dest="cpus", type=int, default=4)
    parser.add_argument("--ny", type=int, default=320)
    parser.add_argument("--left-field", choices=("D2", "trA"), default="trA")
    parser.add_argument("--zmin", type=float, default=0.)
    parser.add_argument("--zmax", type=float, default=4.)
    parser.add_argument("--rmax", type=float, default=4.)
    parser.add_argument("--impact-speed", type=float, default=1.)
    parser.add_argument("--vel-vmin", type=float)
    parser.add_argument("--vel-vmax", type=float)
    parser.add_argument("--left-vmin", type=float)
    parser.add_argument("--left-vmax", type=float)
    parser.add_argument("--no-streamlines", dest="streamlines", action="store_false",
                        default=True)
    parser.add_argument("--streamline-density", type=float, default=1.15)
    return parser.parse_args()


def latest_snapshot(video: Any, case_dir: Path) -> Path | None:
    snapshots = video.list_snapshots(case_dir, "intermediate/snapshot-*")
    return snapshots[-1] if snapshots else None


def render_task(case_dir: Path, snapshot: Path, output: Path, facet_bin: Path,
                data_bin: Path, options: dict[str, Any], cache_root: Path) -> tuple[str, float, Path]:
    video = load_video()
    video.configure_worker_environment(cache_root)
    video.ensure_plotting()
    args = SimpleNamespace(**options)
    args.xmin, args.xmax, args.ymin, args.ymax = video.requested_window(args)
    left_limits = (-3., 1.) if args.left_field == "D2" else (-1., 1.)
    limits = (
        args.vel_vmin if args.vel_vmin is not None else 0.,
        args.vel_vmax if args.vel_vmax is not None else args.impact_speed,
        args.left_vmin if args.left_vmin is not None else left_limits[0],
        args.left_vmax if args.left_vmax is not None else left_limits[1],
    )
    video.render_frame(output, snapshot, facet_bin, data_bin, case_dir, args, limits)
    return case_dir.name, video.snapshot_time(snapshot), output


def main() -> int:
    args = parse_args()
    if args.cpus <= 0 or args.ny <= 2 or args.rmax <= 0 or args.zmax <= args.zmin:
        raise SystemExit("Invalid --cpus, --ny, --rmax, or z bounds")
    if shutil.which("qcc") is None:
        raise SystemExit("qcc is not on PATH")

    video = load_video()
    case_root = args.case_root.resolve()
    cases = [(case, snapshot) for case in sorted(case_root.iterdir())
             if case.is_dir() and (snapshot := latest_snapshot(video, case))]
    if not cases:
        raise SystemExit(f"No case snapshots found below {case_root}")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    options = vars(args).copy()
    options.update(xmin=None, xmax=None, ymin=None, ymax=None)

    with tempfile.TemporaryDirectory(prefix="ve-latest-cases-tools-", dir=case_root) as build:
        with tempfile.TemporaryDirectory(prefix="ve-latest-cases-cache-", dir=case_root) as cache:
            video.configure_worker_environment(Path(cache))
            video.ensure_plotting()
            facet_bin, data_bin = video.precompile_helpers(Path(__file__).resolve().parent,
                                                            Path(build))
            tasks = []
            for case, snapshot in cases:
                time = video.snapshot_time(snapshot)
                output = output_dir / f"case-{case.name}-t{time:.4f}.png"
                tasks.append((case, snapshot, output))
            with ProcessPoolExecutor(max_workers=args.cpus) as executor:
                futures = [executor.submit(render_task, case, snapshot, output,
                                           facet_bin, data_bin, options, Path(cache))
                           for case, snapshot, output in tasks]
                results = sorted((future.result() for future in futures), key=lambda item: item[0])

    # Preserve the previous monitoring image until its replacement succeeds.
    for case, _, image in results:
        for stale in output_dir.glob(f"case-{case}-t*.png"):
            if stale != image:
                stale.unlink()

    with (output_dir / "latest-render-manifest.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("case", "time", "image"))
        writer.writerows((case, f"{time:.6f}", image.name) for case, time, image in results)
    for case, time, image in results:
        print(f"WROTE case={case} t={time:.4f} image={image}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
