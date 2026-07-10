# Post-processing

`VideoAxi.py` creates deterministic, mirrored-axis frames from the snapshots
actually present in a case. It compiles the Basilisk extractors once, then
renders independent frames in batches of `--cpus` workers (default: four).

```bash
python3 postProcess/VideoAxi.py \
  --case-dir simulationCases/dropImpactVE/<case> --cpus 4
```

Use `--skip-video` to retain PNG frames only, and `--left-field trA` to plot
the conformation trace rather than `D2` on the left half of the cross-section.
By default, `D2` uses `hot_r` with its colourbar on the left, `|u|` uses
`Blues` with dark blue fixed at the imposed impact speed `U0 = 1`, and
liquid-only streamlines are overlaid. Use `--no-streamlines` to suppress them
or `--impact-speed` when a run uses a different velocity scale.

`render_one.py` is deliberately serial and renders the latest available
snapshot by default. Select a particular dump with `--snapshot` or the nearest
available time with `--time`.

```bash
python3 postProcess/render_one.py \
  --case-dir simulationCases/dropImpactVE/<case> \
  --time 1.6 -o latest.png
```

Both helper programs restore the full VE/contact-line solver state and write
their machine-readable output to standard output. They currently target
single-process/OpenMP snapshots; distributed MPI dumps need extraction with the
same MPI restore layout that produced them.
