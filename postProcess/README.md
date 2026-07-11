# Post-processing

`VideoAxi.py` creates deterministic, mirrored-axis frames from the snapshots
actually present in a case. It compiles the Basilisk extractors once, then
renders independent frames in batches of `--cpus` workers (default: four).

```bash
python3 postProcess/VideoAxi.py \
  --case-dir simulationCases/dropImpactVE/<case> --cpus 4
```

Use `--skip-video` to retain PNG frames only. By default the left half shows
`log10(tr(A)/3)`, the normalised isotropic polymer extension; use
`--left-field D2` to plot the deformation-rate invariant instead. The
conformation tensor is `A = I` at equilibrium, so `log10(tr(A)/3) = 0` there.
Negative values indicate a reduced total extension relative to equilibrium,
and positive values an increased extension. This scalar is rotationally
invariant, but does not identify the stretch direction or distinguish it from
shear-induced anisotropy. Only a non-positive trace and the gas are masked,
because they are outside the logarithm's domain.

The trace diagnostic uses the diverging `PuOr` scale, with compression and
stretch placed symmetrically about zero; `D2` retains `hot_r`. Both use the
colourbar on the left. `|u|` uses `Blues` with dark blue fixed at the imposed
impact speed `U0 = 1`, and lime-green liquid-only streamlines are overlaid.
Use `--no-streamlines` to suppress them or `--impact-speed` when a run uses a
different velocity scale. The default range is `[-1, 1]` for the trace and
`[-3, 1]` for `D2`; explicit `--left-vmin` and `--left-vmax` override it.
The VOF interface is a single magenta line, chosen to remain visible on both
the `hot_r` and `Blues` halves without a contrasting under-stroke.

The default impact window is `r in [-4, 4]`, `z in [0, 4]`. The compact
colourbars are centred beside the image and limited to 72% of the image-box
height. Override the window with `--rmax`, `--zmin`, `--zmax`, or individual
`--xmin`/`--xmax`/`--ymin`/`--ymax` bounds.

`render_one.py` is deliberately serial and renders the latest available
snapshot by default. Select a particular dump with `--snapshot` or the nearest
available time with `--time`.

```bash
python3 postProcess/render_one.py \
  --case-dir simulationCases/dropImpactVE/<case> \
  --time 1.6 -o latest.png
```

`render_latest_cases.py` renders one latest snapshot per numbered case under a
regime-map root.  It compiles the extractors once and distributes independent
cases across workers; this is the monitor entry point for a live sweep.

```bash
python3 postProcess/render_latest_cases.py \
  --case-root /path/to/staged/fixedBeta \
  --output-dir /path/to/latest-images --cpus 4 --ny 320
```

It writes files named `case-<id>-t<time>.png` and a
`latest-render-manifest.csv`.  It uses the same signed trace, velocity,
streamline, and impact-window defaults as `VideoAxi.py`.

Both helper programs restore the full VE/contact-line solver state and write
their machine-readable output to standard output. A serial helper built against
the producing Basilisk tree can read the present MPI snapshots for visual
inspection. In contrast, the MPI helper restore path currently fails inside
`restore_mpi()` even for the `t = 0` dump, so it is not used for rendering.
The fresh four-rank run reached `t = 2.33026` and wrote 24 readable snapshots
before exiting with status 1, but produced no solver-side diagnostic or stack
trace. Host NIC hardware-hang messages appeared in the same period; that is a
correlation to investigate, not an established cause of the solver exit.

## MPI inspection workflow

For the saved four-rank dumps, stage the `snapshot-*` files under an
`intermediate/` directory and use the same serial post-processing commands.
The current project configuration restores the checked `t = 0` through `2.3`
MPI dumps this way, while retaining the reliable process-based parallelism in
the Python renderer.

```bash
python3 postProcess/VideoAxi.py \
  --case-dir ~/Documents/Projects-cowork/share-files/EC-jets/mpi \
  --frames-dir ~/Documents/Projects-cowork/share-files/EC-jets/mpi/frames \
  --cpus 4 --output mpi-diagnostics-evolution.mp4

python3 postProcess/render_one.py \
  --case-dir ~/Documents/Projects-cowork/share-files/EC-jets/mpi \
  --snapshot intermediate/snapshot-2.3000 -o latest-diagnostics.png
```
