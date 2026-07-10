# VE-DropImpact-ContactLine

_Axisymmetric viscoelastic and purely elastic drop impact on a solid
substrate with a time-switched contact line, built on
[Basilisk C](http://basilisk.fr)._

## Overview

A drop of a viscoelastic (or purely elastic) liquid impacts a solid wall.
The wall starts **non-wetting**, so the drop impacts and recoils; after a
brief hold the imposed contact angle is **switched** down to a wetting
equilibrium value, so the drop deposits and spreads. This combines:

- the **log-conformation viscoelastic formulation** from
  [comphy-lab/MultiRheoFlow](https://github.com/comphy-lab/MultiRheoFlow),
  which unifies the elastic and viscoelastic regimes in a single solver, and
- the **drop-impact geometry and dynamic contact line** from the CoMPhy
  elastocapillary Worthington-jet drop-bounce study.

Developed at the
[Computational Multiphase Physics (CoMPhy) Lab](https://comphy-lab.org/),
Durham University.

## Associated publication

This repository is the simulation code accompanying:

> U. Sen, V. Sanjay, K. Zinelis, O. K. Matar, M. Jalaal, D. Lohse,
> _Transient dynamics of elastocapillary Worthington jets_
> (in preparation, 2026).

A DOI / preprint link will be added here upon publication.

The contact-line switching protocol, the axisymmetric domain (size
`8 R0`, axis on the bottom boundary, substrate on the left), the
Oldroyd-B constitutive model, and the dimensionless groups
(`We`, `Ohs`, `De`, `Ec`, `Bo`) follow the Methods of that paper.

## Physics

The polymer stress uses the log-conformation method, kept robust at high
elasticity. A single relaxation time `lambda` spans the regimes:

| Regime | Setting | `lambda` |
| --- | --- | --- |
| Viscoelastic (Oldroyd-B) | `purelyElastic = 0`, finite `De` | `De*sqrt(We)` |
| Purely elastic (neo-Hookean) | `purelyElastic = 1` | `1e30` (relaxation frozen) |
| Newtonian (air phase) | — | `0` (guarded, no division) |

Dimensionless mapping: viscosities `mu = Oh/sqrt(We)`, polymer modulus
`G1 = Ec/We`, relaxation `lambda1 = De*sqrt(We)`, surface tension
`sigma = 1/We`, gravity `G.x = -Bo/(2 We)`.

### Time-switched contact line

The substrate is the left boundary (the bottom boundary is the symmetry
axis). The contact angle is imposed through height functions and switched
in time:

```
theta0(t) = thetaInit,                                   t <= ttheta
theta0(t) = max(thetaE, thetaInit - thetaRate*(t-ttheta)), t >  ttheta
```

With the defaults (`thetaInit = 160`, `thetaE = 60`, `ttheta = 1`,
`thetaRate = 100`) the angle is held at 160 deg, then ramps to 60 deg over
one time unit starting at `t = 1`.

## Requirements

- [Basilisk C](http://basilisk.fr/src/INSTALL) (`qcc` on `PATH`).
- A C compiler and `make`; `gnuplot`/`ffmpeg`/`python3` for post-processing.

## Quick start

```
# default viscoelastic run
bash runSimulation.sh

# purely elastic run
bash runSimulation.sh --input default-elastic.params

# custom case / params
bash runSimulation.sh --case simulationCases/dropImpactVE.c --input my.params
```

Or compile directly:

```
qcc -O2 -Wall -disable-dimensions -I$PWD/src-local \
  simulationCases/dropImpactVE.c -o dropImpactVE -lm
./dropImpactVE default-VE.params
```

Snapshots are written to `intermediate/`, a restart dump to `restart`, and
a `i dt t ke theta0` log to `logAxi-scalar.dat`.

## Parameter sweeps (We-De regime map)

`runParameterSweep.sh` reproduces the experimental `We`-`De` regime map by
sweeping over a grid of Weber and Deborah numbers. Two physically distinct
sweeps are provided:

- `sweep-fixedBeta.params` -- **fixed `Ohs` and fixed `beta`** (solvent
  fraction). The total Ohnesorge number `Oh = Ohs/beta` is held constant
  and the elasto-capillary number is derived per case from the Oldroyd-B
  relation `Oh_p = Ec*De = Ohs*(1-beta)/beta`, i.e.
  `Ec = Ohs*(1-beta)/(beta*De)` (fixed polymer concentration, varying De).
- `sweep-fixedEc.params` -- **fixed `Ohs` and fixed `Ec`**. The elastic
  modulus is held constant while `We` and `De` vary (so `beta` drifts),
  isolating the role of the relaxation time.

In both, `De = 0` is the Newtonian baseline (`Ec = 0`). The contact-line
switch is set to the paper protocol (`thetaInit = 160`, `thetaE = 60`,
`ttheta = 8`, `thetaRate = 100`).

```
# preview the generated cases without running
bash runParameterSweep.sh --config sweep-fixedBeta.params --dry-run

# run the full fixed-beta sweep (compiles once, runs each case in its
# own simulationCases/dropImpactVE/<CaseNo>/ directory)
bash runParameterSweep.sh --config sweep-fixedBeta.params

# run a subset (e.g. cases 7-12) -- handy for HPC array jobs
bash runParameterSweep.sh --config sweep-fixedEc.params --start 7 --end 12
```

Each case is written to `simulationCases/dropImpactVE/<CaseNo>/case.params`
and consumed by the same `case-params.h` parser as a single run.

## Parameters

| Key | Meaning | Default |
| --- | --- | --- |
| `MAXlevel` | max adaptive refinement level | 9 |
| `Ldomain` / `L0` | domain size | 4.0 |
| `tmax` | end time | 4.0 |
| `We` | Weber number | 5.0 |
| `Ohs` | solvent Ohnesorge number | 1e-2 |
| `Oha` | air Ohnesorge number | 1e-4 |
| `De` | Deborah number | 1.0 |
| `Ec` | elasto-capillary number | 1.0 |
| `Bo` | Bond number (gravity) | 1.0 |
| `purelyElastic` | 0 = viscoelastic, 1 = purely elastic | 0 |
| `thetaInit` | initial (non-wetting) angle, deg | 160 |
| `thetaE` | final (wetting) angle, deg | 60 |
| `ttheta` | time the switch begins | 1.0 |
| `thetaRate` | switch ramp rate, deg/time | 100 |

## Repository structure

```
src-local/ - project-specific Basilisk headers
src-local/log-conform-viscoelastic-scalar-2D.h - log-conformation viscoelastic solver (2D/axi)
src-local/two-phaseVE.h - two-phase VOF solver with per-phase elastic moduli
src-local/case-params.h - key=value parameter-file parser
simulationCases/ - simulation entry points
simulationCases/dropImpactVE.c - viscoelastic drop impact with switched contact line
postProcess/ - post-processing utilities
postProcess/getFacet2D.c - extract interface facets from a snapshot
postProcess/getData-elastic-scalar2D.c - extract fields (velocity, stress) from a snapshot
postProcess/VideoAxi.py - parallel axisymmetric frame/video renderer
postProcess/render_one.py - serial one-off renderer for the latest/specified snapshot
postProcess/README.md - rendering commands and options
runSimulation.sh - root runner for a single case (--case, --input)
runParameterSweep.sh - root runner for We-De sweeps (--config, --start, --end, --dry-run)
default-VE.params - default viscoelastic parameters
default-elastic.params - default purely elastic parameters
sweep-fixedBeta.params - We-De sweep at fixed Ohs and fixed beta (Ec derived)
sweep-fixedEc.params - We-De sweep at fixed Ohs and fixed Ec
AGENTS.md - developer/agent guidelines
LICENSE - GNU GPLv3
```

## Acknowledgements

Viscoelastic solver from
[MultiRheoFlow](https://github.com/comphy-lab/MultiRheoFlow) (CoMPhy Lab),
itself an extension of
[ElastoFlow](https://github.com/comphy-lab/Viscoelastic3D). Built on the
[Basilisk](http://basilisk.fr) log-conformation framework.

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).
