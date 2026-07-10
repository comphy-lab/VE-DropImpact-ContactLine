# Post-processing

`VideoAxi.py` creates deterministic, mirrored-axis frames from the snapshots
actually present in a case. It compiles the Basilisk extractors once, then
renders independent frames in batches of `--cpus` workers (default: four).

```bash
python3 postProcess/VideoAxi.py \
  --case-dir simulationCases/dropImpactVE/<case> --cpus 4
```

Use `--skip-video` to retain PNG frames only. By default the left half shows
`log10(tr(A) - 3)`, the scalar excess polymer stretch above equilibrium; use
`--left-field D2` to plot the deformation-rate invariant instead. The
conformation tensor is `A = I` at equilibrium, so `tr(A) - 3` is a rotationally
invariant measure of the total polymer extension. In the Oldroyd-B limit it is
proportional to the trace of the polymeric extra stress. It does not identify
the direction of stretching or distinguish it from shear-induced anisotropy.
Non-positive values (including equilibrium) and the gas are masked, because
they are outside the domain of the logarithm rather than small physical values.

The trace diagnostic uses perceptually ordered `magma` (dark low stretch to
bright high stretch); `D2` retains `hot_r`. Both use the colourbar on the left.
`|u|` uses `Blues` with dark blue fixed at the imposed impact speed `U0 = 1`,
and liquid-only streamlines are overlaid. Use `--no-streamlines` to suppress
them or `--impact-speed` when a run uses a different velocity scale.
The default range for both logarithmic left diagnostics is `[-3, 1]`; only
explicit `--left-vmin` and `--left-vmax` options override it.
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

Both helper programs restore the full VE/contact-line solver state and write
their machine-readable output to standard output. A serial helper built against
the producing Basilisk tree can read the present MPI snapshots for visual
inspection. In contrast, the MPI helper restore path currently fails inside
`restore_mpi()` even for the `t = 0` dump, so it is not used for rendering.
The fresh four-rank run reached `t = 2.33026` and wrote 24 readable snapshots
before exiting with status 1, but produced no solver-side diagnostic or stack
trace. Host NIC hardware-hang messages appeared in the same period; that is a
correlation to investigate, not an established cause of the solver exit.
