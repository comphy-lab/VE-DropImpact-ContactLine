#!/usr/bin/env python3
"""Render VE drop-impact snapshots into mirrored axisymmetric PNG frames.

The helpers are compiled once, then each independent snapshot is rendered by
one worker.  Snapshot times are parsed from the files actually present; no
synthetic time grid is assumed.
"""

from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

np: Any = None
plt: Any = None
LineCollection: Any = None

FIELD_INDEX = {"D2": 2, "vel": 3, "trA": 4, "ux": 5, "uy": 6, "f": 7}
FIELD_LABEL = {
    "D2": r"$\log_{10}\!\left(\|\mathcal{D}\|^2\right)$",
    "vel": r"$|\mathbf{u}|$",
    "trA": r"$\log_{10}\!\left(\mathrm{tr}(\mathbf{A})/3-1\right)$",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render VE drop-impact snapshots and optionally assemble an MP4."
    )
    parser.add_argument("--case-dir", type=Path,
                        help="Directory containing intermediate/snapshot-* files.")
    parser.add_argument("--snap-glob", default="intermediate/snapshot-*")
    parser.add_argument("--ny", type=int, default=320,
                        help="Physical radial samples per frame (default: 320).")
    parser.add_argument("--cpus", "--CPUs", dest="cpus", type=int, default=4,
                        help="Independent rendering workers (default: 4).")
    parser.add_argument("--frames-dir", type=Path,
                        help="PNG directory; default is case-dir/Video.")
    parser.add_argument("-o", "--output", default="video-axisymmetric.mp4")
    parser.add_argument("--fps", type=float)
    parser.add_argument("--duration", type=float, default=10.)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--skip-video", action="store_true")
    parser.add_argument("--max-frames", type=int)
    parser.add_argument("--start-time", type=float)
    parser.add_argument("--end-time", type=float)
    parser.add_argument("--no-clean-frames", dest="clean_frames",
                        action="store_false", default=True)
    parser.add_argument("--left-field", choices=("D2", "trA"), default="D2")
    parser.add_argument("--xmin", type=float,
                        help="Minimum axial coordinate; defaults to facets.")
    parser.add_argument("--xmax", type=float,
                        help="Maximum axial coordinate; defaults to facets.")
    parser.add_argument("--ymin", type=float,
                        help="Minimum plotted radius; defaults to facets.")
    parser.add_argument("--ymax", type=float,
                        help="Maximum plotted radius; defaults to facets.")
    parser.add_argument("--impact-speed", type=float, default=1.,
                        help="Reference impact speed U0 for |u| scaling (default: 1).")
    parser.add_argument("--vel-vmin", type=float)
    parser.add_argument("--vel-vmax", type=float)
    parser.add_argument("--left-vmin", type=float)
    parser.add_argument("--left-vmax", type=float)
    parser.add_argument("--no-streamlines", dest="streamlines", action="store_false",
                        default=True, help="Do not overlay liquid-phase streamlines.")
    parser.add_argument("--streamline-density", type=float, default=1.15,
                        help="Matplotlib streamline density (default: 1.15).")
    return parser.parse_args()


def configure_worker_environment(cache_root: Path | None) -> None:
    """Give every renderer its own Matplotlib and TeX caches."""
    if cache_root is None:
        return
    root = cache_root / f"worker-{os.getpid()}"
    for name, env_name in (("mpl", "MPLCONFIGDIR"), ("texmf-var", "TEXMFVAR"),
                           ("texmf-config", "TEXMFCONFIG")):
        path = root / name
        path.mkdir(parents=True, exist_ok=True)
        os.environ[env_name] = str(path)
    os.environ["OMP_NUM_THREADS"] = "1"


def ensure_plotting() -> None:
    global np, plt, LineCollection
    if np is not None:
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as _plt
    import numpy as _np
    from matplotlib.collections import LineCollection as _LineCollection

    matplotlib.rcParams.update({
        "font.family": "serif",
        "mathtext.fontset": "cm",
        "axes.linewidth": 1.2,
    })
    np, plt, LineCollection = _np, _plt, _LineCollection


def snapshot_time(path: Path) -> float:
    try:
        return float(path.name.split("snapshot-", 1)[1])
    except (IndexError, ValueError):
        return math.inf


def list_snapshots(case_dir: Path, pattern: str) -> list[Path]:
    return sorted((p for p in case_dir.glob(pattern) if p.is_file()),
                  key=snapshot_time)


def auto_detect_case_dir(cwd: Path, pattern: str) -> Path:
    if list_snapshots(cwd, pattern):
        return cwd
    candidates = sorted(
        (p for p in (cwd / "simulationCases").glob("**/*")
         if p.is_dir() and list_snapshots(p, pattern)),
        key=lambda p: (p.stat().st_mtime, str(p)),
    ) if (cwd / "simulationCases").is_dir() else []
    return candidates[-1] if candidates else cwd


def project_root(script_dir: Path) -> Path:
    return script_dir.parent


def compile_helper(source: Path, output: Path, root: Path) -> None:
    subprocess.run([
        "qcc", "-O2", "-Wall", "-disable-dimensions",
        f"-I{root / 'src-local'}", source.name, "-o", str(output), "-lm",
    ], cwd=source.parent, check=True)


def precompile_helpers(script_dir: Path, build_dir: Path) -> tuple[Path, Path]:
    if shutil.which("qcc") is None:
        raise RuntimeError("qcc is not on PATH.")
    root = project_root(script_dir)
    facet, data = build_dir / "getFacet2D", build_dir / "getData-elastic-scalar2D"
    compile_helper(script_dir / "getFacet2D.c", facet, root)
    compile_helper(script_dir / "getData-elastic-scalar2D.c", data, root)
    return facet, data


def run_capture(command: list[str], cwd: Path) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout


def snapshot_argument(snapshot: Path, case_dir: Path) -> str:
    try:
        return str(snapshot.relative_to(case_dir))
    except ValueError:
        return str(snapshot)


def parse_facet_segments(raw: str) -> Any:
    ensure_plotting()
    points: list[list[float]] = []
    for line in raw.splitlines():
        values = line.split()
        if len(values) < 2:
            continue
        try:
            points.append([float(values[0]), float(values[1])])
        except ValueError:
            continue
    usable = len(points) - len(points) % 2
    return np.asarray(points[:usable], dtype=float).reshape(-1, 2, 2) \
        if usable else np.empty((0, 2, 2), dtype=float)


def get_facets(snapshot: Path, facet_bin: Path, case_dir: Path) -> Any:
    return parse_facet_segments(run_capture(
        [str(facet_bin), snapshot_argument(snapshot, case_dir)], case_dir
    ))


def get_field_grid(snapshot: Path, data_bin: Path, case_dir: Path, xmin: float,
                   ymin: float, xmax: float, ymax: float, ny: int) -> tuple[Any, Any, dict[str, Any]]:
    ensure_plotting()
    raw = run_capture([
        str(data_bin), snapshot_argument(snapshot, case_dir), f"{xmin:.16g}",
        f"{ymin:.16g}", f"{xmax:.16g}", f"{ymax:.16g}", str(ny),
    ], case_dir)
    rows: list[list[float]] = []
    for line in raw.splitlines():
        values = line.split()
        if len(values) < 8:
            continue
        try:
            rows.append([float(value) for value in values[:8]])
        except ValueError:
            continue
    if not rows:
        raise RuntimeError(f"No scalar data parsed from {snapshot}")
    values = np.asarray(rows, dtype=float)
    xs, ys = np.unique(values[:, 0]), np.unique(values[:, 1])
    ix, iy = np.searchsorted(xs, values[:, 0]), np.searchsorted(ys, values[:, 1])
    fields: dict[str, Any] = {}
    for name, col in FIELD_INDEX.items():
        grid = np.full((len(xs), len(ys)), np.nan)
        grid[ix, iy] = values[:, col]
        invalid = ~np.isfinite(grid) | (np.abs(grid) > 1e20)
        fields[name] = np.ma.masked_where(invalid, grid)
    return xs, ys, fields


def resolve_window(facets: Any, xmin: float | None, xmax: float | None,
                   ymin: float | None, ymax: float | None) -> tuple[float, float, float, float]:
    ensure_plotting()
    if len(facets) == 0:
        if None in (xmin, xmax, ymin, ymax):
            raise RuntimeError("No facets found: provide --xmin/--xmax/--ymin/--ymax.")
        return float(xmin), float(xmax), float(ymin), float(ymax)
    x, y = facets[..., 0], facets[..., 1]
    pad = max(float(x.max() - x.min()) * 0.03, 1e-3)
    radial = max(float(np.abs(y).max()) * 1.08, 1e-3)
    answer = (float(x.min()) - pad if xmin is None else xmin,
              float(x.max()) + pad if xmax is None else xmax,
              -radial if ymin is None else ymin,
              radial if ymax is None else ymax)
    if answer[0] >= answer[1] or answer[2] >= answer[3]:
        raise ValueError("Resolved plot bounds are invalid.")
    return answer


def finite_limits(field: Any) -> tuple[float | None, float | None]:
    ensure_plotting()
    values = field.compressed()
    values = values[np.isfinite(values)]
    if not values.size:
        return None, None
    lo, hi = (float(v) for v in np.percentile(values, [2., 98.]))
    if not math.isfinite(lo) or not math.isfinite(hi) or lo == hi:
        return None, None
    return lo, hi


def mirrored(field: Any, radii: Any) -> tuple[Any, Any]:
    r = np.concatenate((-radii[::-1], radii))
    return r, np.ma.concatenate((field[:, ::-1], field), axis=1)


def mirrored_velocity(axial: Any, radial: Any, radii: Any) -> tuple[Any, Any, Any]:
    """Reflect the physical half-plane velocity into plotted ``(r, z)``."""
    r = np.concatenate((-radii[::-1], radii))
    axial_full = np.ma.concatenate((axial[:, ::-1], axial), axis=1)
    radial_full = np.ma.concatenate((-radial[:, ::-1], radial), axis=1)
    return r, axial_full, radial_full


def extent(centres: Any) -> tuple[float, float]:
    delta = float(np.median(np.diff(centres))) if len(centres) > 1 else 1.
    return float(centres[0] - delta/2.), float(centres[-1] + delta/2.)


def render_frame(output: Path, snapshot: Path, facet_bin: Path, data_bin: Path,
                 case_dir: Path, args: Any, limits: tuple[Any, Any, Any, Any]) -> Path:
    """Render a mirrored D2/trA and velocity diagnostic for one snapshot."""
    ensure_plotting()
    facets = get_facets(snapshot, facet_bin, case_dir)
    physical_ymin, physical_ymax = 0., max(abs(args.ymin), abs(args.ymax))
    xs, ys, fields = get_field_grid(snapshot, data_bin, case_dir, args.xmin,
                                    physical_ymin, args.xmax, physical_ymax, args.ny)
    radii, velocity = mirrored(fields["vel"], ys)
    _, left = mirrored(fields[args.left_field], ys)
    left[:, radii > 0.] = np.ma.masked
    _, axial_velocity, radial_velocity = mirrored_velocity(fields["ux"], fields["uy"], ys)
    _, liquid = mirrored(fields["f"], ys)
    x_extent, r_extent = extent(xs), extent(radii)
    figure, axis = plt.subplots(figsize=(7.2, 8.5), dpi=180)
    figure.subplots_adjust(left=.20, right=.80, bottom=.06, top=.91)
    velocity_image = axis.imshow(velocity, origin="lower", aspect="equal",
                                 extent=(*r_extent, *x_extent), cmap="Blues",
                                 vmin=limits[0], vmax=limits[1])
    left_image = axis.imshow(left, origin="lower", aspect="equal",
                             extent=(*r_extent, *x_extent),
                             cmap="hot_r" if args.left_field == "D2" else "RdBu_r",
                             vmin=limits[2], vmax=limits[3], alpha=.82)
    if args.streamlines:
        liquid_only = np.ma.masked_where(liquid < .5, radial_velocity)
        axial_liquid = np.ma.masked_where(liquid < .5, axial_velocity)
        stream_r = np.linspace(radii[0], radii[-1], len(radii))
        stream_z = np.linspace(xs[0], xs[-1], len(xs))
        axis.streamplot(stream_r, stream_z, liquid_only, axial_liquid,
                        density=args.streamline_density, color="white",
                        linewidth=.55, arrowsize=.55, zorder=4)
    if len(facets):
        segments = facets[..., [1, 0]]
        reflected = segments.copy()
        reflected[..., 0] *= -1.
        interface = np.concatenate((reflected, segments))
        axis.add_collection(LineCollection(interface, colors="white", linewidths=2.3))
        axis.add_collection(LineCollection(interface, colors="black", linewidths=1.1))
    axis.axvline(0., color="0.5", linestyle="--", linewidth=.8)
    axis.set(xlim=(args.ymin, args.ymax), ylim=(args.xmin, args.xmax),
             title=rf"$t={snapshot_time(snapshot):.4f}$")
    axis.set_axis_off()
    left_bar = figure.add_axes([.055, .17, .027, .64])
    left_colorbar = figure.colorbar(left_image, cax=left_bar,
                                    label=FIELD_LABEL[args.left_field])
    left_colorbar.ax.yaxis.set_ticks_position("left")
    left_colorbar.ax.yaxis.set_label_position("left")
    right_bar = figure.add_axes([.865, .17, .027, .64])
    figure.colorbar(velocity_image, cax=right_bar, label=FIELD_LABEL["vel"])
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, bbox_inches="tight")
    plt.close(figure)
    return output


def worker(index: int, snapshot: Path, case_dir: Path, frames_dir: Path,
           facet_bin: Path, data_bin: Path, args: Any, limits: tuple[Any, Any, Any, Any],
           cache_root: Path | None) -> tuple[int, Path]:
    configure_worker_environment(cache_root)
    return index, render_frame(frames_dir / f"frame_{index:06d}.png", snapshot,
                               facet_bin, data_bin, case_dir, args, limits)


def render_snapshots(snapshots: list[Path], case_dir: Path, frames_dir: Path,
                     facet_bin: Path, data_bin: Path, args: Any,
                     limits: tuple[Any, Any, Any, Any], cache_root: Path | None) -> None:
    tasks = list(enumerate(snapshots))
    if args.cpus == 1:
        for index, snapshot in tasks:
            _, output = worker(index, snapshot, case_dir, frames_dir, facet_bin,
                               data_bin, args, limits, cache_root)
            print(f"[{index + 1}/{len(tasks)}] wrote {output}", file=sys.stderr)
        return
    with ProcessPoolExecutor(max_workers=args.cpus) as executor:
        for start in range(0, len(tasks), args.cpus):
            batch = tasks[start:start + args.cpus]
            results = [executor.submit(worker, index, snapshot, case_dir, frames_dir,
                                       facet_bin, data_bin, args, limits, cache_root)
                       for index, snapshot in batch]
            for index, output in sorted((future.result() for future in results)):
                print(f"[{index + 1}/{len(tasks)}] wrote {output}", file=sys.stderr)


def main() -> int:
    args = parse_args()
    if args.cpus <= 0 or args.ny <= 2 or args.duration <= 0:
        print("--cpus, --ny and --duration must be positive (--ny > 2).", file=sys.stderr)
        return 1
    case_dir = args.case_dir.resolve() if args.case_dir else auto_detect_case_dir(
        Path.cwd().resolve(), args.snap_glob)
    snapshots = list_snapshots(case_dir, args.snap_glob)
    if args.start_time is not None:
        snapshots = [p for p in snapshots if snapshot_time(p) >= args.start_time]
    if args.end_time is not None:
        snapshots = [p for p in snapshots if snapshot_time(p) <= args.end_time]
    if args.max_frames is not None:
        snapshots = snapshots[:args.max_frames]
    if not snapshots:
        print(f"No snapshots found in {case_dir} matching {args.snap_glob!r}.", file=sys.stderr)
        return 1
    if not args.skip_video and shutil.which(args.ffmpeg) is None:
        print(f"ffmpeg is not available: {args.ffmpeg}", file=sys.stderr)
        return 1
    frames_dir = (args.frames_dir or case_dir / "Video")
    frames_dir = frames_dir if frames_dir.is_absolute() else case_dir / frames_dir
    frames_dir.mkdir(parents=True, exist_ok=True)
    if args.clean_frames:
        for frame in frames_dir.glob("frame_*.png"):
            frame.unlink()

    script_dir = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="ve-post-tools-", dir=case_dir) as build:
      with tempfile.TemporaryDirectory(prefix="ve-post-cache-", dir=case_dir) as cache:
        try:
            configure_worker_environment(Path(cache))
            ensure_plotting()
            print("Pre-processing: compiling get* helpers...", file=sys.stderr)
            facet_bin, data_bin = precompile_helpers(script_dir, Path(build))
            args.xmin, args.xmax, args.ymin, args.ymax = resolve_window(
                get_facets(snapshots[0], facet_bin, case_dir), args.xmin, args.xmax,
                args.ymin, args.ymax)
            _, _, fields = get_field_grid(
                snapshots[0], data_bin, case_dir, args.xmin, 0., args.xmax,
                max(abs(args.ymin), abs(args.ymax)), args.ny
            )
            vel_limits = (0., args.impact_speed)
            left_limits = finite_limits(fields[args.left_field])
            limits = (args.vel_vmin if args.vel_vmin is not None else vel_limits[0],
                      args.vel_vmax if args.vel_vmax is not None else vel_limits[1],
                      args.left_vmin if args.left_vmin is not None else left_limits[0],
                      args.left_vmax if args.left_vmax is not None else left_limits[1])
            render_snapshots(snapshots, case_dir, frames_dir, facet_bin, data_bin,
                             args, limits, Path(cache))
            if args.skip_video:
                print(f"Frames written to {frames_dir}", file=sys.stderr)
                return 0
            fps = args.fps if args.fps is not None else len(snapshots)/args.duration
            output = Path(args.output)
            output = output if output.is_absolute() else case_dir / output
            subprocess.run([args.ffmpeg, "-y", "-framerate", f"{fps:.6g}",
                            "-pattern_type", "glob", "-i", str(frames_dir / "frame_*.png"),
                            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264",
                            "-r", f"{fps:.6g}", "-pix_fmt", "yuv420p", str(output)], check=True)
            print(f"Wrote video: {output}", file=sys.stderr)
            return 0
        except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
          print(f"Error: {error}", file=sys.stderr)
          return 2


if __name__ == "__main__":
    raise SystemExit(main())
