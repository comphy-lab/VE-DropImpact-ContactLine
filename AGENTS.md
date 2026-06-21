# VE-DropImpact-ContactLine — Development Guidelines

Axisymmetric viscoelastic / purely elastic drop impact on a solid
substrate with a **time-switched contact line**, built on Basilisk C.
The viscoelastic formulation is reused from
[MultiRheoFlow](https://github.com/comphy-lab/MultiRheoFlow); the
drop-impact geometry and the contact-angle switching are adapted from the
CoMPhy elastocapillary Worthington-jet drop-bounce study.

## Project Structure
- `src-local/`: project-specific Basilisk headers.
  - `log-conform-viscoelastic-scalar-2D.h`: log-conformation viscoelastic
    solver (2D / axisymmetric, scalar storage). Unifies regimes through
    `lambda`: finite -> viscoelastic, `1e30` -> purely elastic, `0` ->
    Newtonian. The `lambda != 0` guard keeps the non-polymer phase safe.
  - `two-phaseVE.h`: two-phase VOF solver binding per-phase moduli `G1/G2`
    and relaxation times `lambda1/lambda2` to the solver fields.
  - `case-params.h`: `key = value` parameter-file parser.
- `simulationCases/dropImpactVE.c`: the simulation entry point.
- `postProcess/`: facet/field extraction and axisymmetric video tools.
- `runSimulation.sh`: root runner (`--case`, `--input`).
- `default-VE.params`, `default-elastic.params`: default parameter files.
- `basilisk/`: optional local Basilisk checkout (untracked).

## Contact-line model
The substrate is the **left** boundary (axisymmetric convention: bottom is
the symmetry axis). The contact angle is imposed via height functions
(`contact.h`, `f.height = h`, `h.t[left] = contact_angle(theta0)`). The
angle is held at `thetaInit` until `ttheta`, then ramped at `thetaRate`
deg/time down to the wetting value `thetaE`. The `h.t[left]` closure
re-reads the global `theta0` every step, so the `contactAngle` event
live-updates the enforced angle. Do **not** pin `f` at the wall — the drop
must wet it.

## Include order (do not reorder)
`axi.h` -> `navier-stokes/centered.h` -> VE solver header -> `#define
FILTERED` -> `contact.h` -> `two-phaseVE.h` -> `navier-stokes/conserving.h`
-> `tension.h` -> `reduced.h` -> `case-params.h`. The VE header must
precede `two-phaseVE.h` (which binds `Gp`/`lambda`); `contact.h` must
precede the two-phase layer.

## Dimensionless mapping
`mu = Oh/sqrt(We)`, polymer modulus `G1 = Ec/We`, relaxation
`lambda1 = De*sqrt(We)` (or `1e30` when `purelyElastic = 1`), surface
tension `sigma = 1/We`, gravity `G.x = -Bo/(2 We)`.

## Build & Run
- Compile: `qcc -O2 -Wall -disable-dimensions -I$PWD/src-local \
  simulationCases/dropImpactVE.c -o dropImpactVE -lm`
- Run (defaults): `bash runSimulation.sh`
- Run with params: `bash runSimulation.sh --input default-elastic.params`
- The runner compiles against `src-local/` and executes in a per-case
  subdirectory; snapshots go to `intermediate/`, restart to `restart`.

## Code Style
- 2-space indentation, no tabs; lines <= 80 chars.
- Markdown comments starting with `/**` (rendered by the docs pipeline).
- `snake_case` for variables, `camelCase` for functions.
- Never hardcode machine-local `qcc` paths; resolve with `$BASILISK` /
  `which qcc`. Do not commit `basilisk/`, `intermediate/`, or run output.
