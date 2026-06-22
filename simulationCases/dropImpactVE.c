/**
# Viscoelastic drop impact on a solid substrate with a dynamic contact line

Axisymmetric impact of a viscoelastic (or purely elastic) drop onto a
solid wall. The polymer rheology uses the log-conformation formulation
from [MultiRheoFlow](https://github.com/comphy-lab/MultiRheoFlow); the
substrate is a genuine wetting boundary whose **contact angle is switched
in time** -- the drop first sees a non-wetting wall (so it impacts and
recoils) and, after a brief hold, the imposed angle is ramped down to a
wetting equilibrium value so the drop deposits.

The constitutive model is unified across regimes through the relaxation
time `lambda` (see `log-conform-viscoelastic-scalar-2D.h`):

- finite `lambda`  -> viscoelastic (Oldroyd-B relaxation),
- `lambda = 1e30`  -> purely elastic limit (relaxation frozen),
- `lambda = 0`     -> Newtonian (no polymer; the air phase).

## Author
Vatsal Sanjay (vatsal.sanjay@comphy-lab.org), CoMPhy Lab.

Viscoelastic formulation reused from MultiRheoFlow; drop-impact geometry
and time-switched contact line adapted from the elastocapillary
Worthington-jet drop-bounce setup.
*/

#include "axi.h"
#include "navier-stokes/centered.h"
#include "log-conform-viscoelastic-scalar-2D.h"
#define FILTERED // smear density / viscosity jumps
#include "contact.h"
#include "two-phaseVE.h"
#include "navier-stokes/conserving.h"
#include "tension.h"
#include "reduced.h"
#include "case-params.h"

#define logFile "logAxi-scalar.dat"

/**
## Output cadence
*/
#define tsnap (0.1)

/**
## Adaptivity tolerances

- `fErr`   : VOF error for `f`
- `KErr`   : curvature (height-function) error
- `VelErr` : velocity error
- `AErr`   : conformation-tensor error (refines on polymer stretch)
*/
#define fErr (1e-3)
#define KErr (1e-6)
#define VelErr (1e-2)
#define AErr (1e-2)

/**
## Geometry

Drop of unit radius released a small distance `xDist` above the substrate
at `x = 0`. Symmetry axis is the bottom boundary; the wall is the left
boundary (axisymmetric convention).
*/
#define xDist (5e-2)
#define R2Drop(x,y) (sq(x - 1. - xDist) + sq(y))

/**
## Height field for the contact line

The interface height field `h` is required by `contact.h` to impose the
contact angle and to compute curvature near the wall.
*/
vector h[];

/**
## Boundary conditions

Left = solid substrate: no-slip plus the (time-dependent) contact angle.
Right and top are outflow. Bottom is the axis of symmetry (handled by
`axi.h`). Note that `f` is **not** pinned at the wall: the drop wets it.
*/
double theta0; // live contact angle (degrees), updated each step

u.t[left] = dirichlet(0.0);
h.t[left] = contact_angle(theta0*pi/180.);

u.n[right] = neumann(0.);
p[right]   = dirichlet(0.0);
u.n[top]   = neumann(0.);
p[top]     = dirichlet(0.0);

/**
## Dimensionless groups

- `We`  : drop Weber number
- `Ohs` : solvent Ohnesorge number
- `Oha` : air Ohnesorge number
- `De`  : Deborah number (relaxation time)
- `Ec`  : elasto-capillary number (polymer modulus)
- `Bo`  : Bond number (gravity)

## Contact-line switching

- `thetaInit` : initial (non-wetting) angle, held until `ttheta`
- `thetaE`    : final (wetting) equilibrium angle
- `ttheta`    : time at which the angle starts to switch
- `thetaRate` : ramp rate (degrees per unit time) of the switch

- `purelyElastic` : if 1, set `lambda = 1e30` (frozen relaxation); else
  `lambda = De*sqrt(We)`.
*/
int MAXlevel = 9;
int purelyElastic = 0;
double We = 5.0, Ohs = 1e-2, Oha = 1e-4, De = 1.0, Ec = 1.0, Bo = 1.0;
double tmax = 4.0, Ldomain = 4.0;
double thetaInit = 160.0, thetaE = 60.0, ttheta = 1.0, thetaRate = 100.0;

char nameOut[80], dumpFile[80];

int main(int argc, char const *argv[]) {

  dtmax = 1e-5;

  if (argc > 2) {
    fprintf(ferr, "Usage: %s [params_file]\n", argv[0]);
    return 1;
  }
  if (argc == 2) {
    paramEntry params[] = {
      {"MAXlevel", &MAXlevel, PARAM_KIND_INT, 0, 0},
      {"purelyElastic", &purelyElastic, PARAM_KIND_INT, 0, 0},
      {"Ldomain", &Ldomain, PARAM_KIND_DOUBLE, 0, 0},
      {"L0", &Ldomain, PARAM_KIND_DOUBLE, 0, 0},
      {"tmax", &tmax, PARAM_KIND_DOUBLE, 0, 0},
      {"We", &We, PARAM_KIND_DOUBLE, 0, 0},
      {"Ohs", &Ohs, PARAM_KIND_DOUBLE, 0, 0},
      {"Oha", &Oha, PARAM_KIND_DOUBLE, 0, 0},
      {"De", &De, PARAM_KIND_DOUBLE, 0, 0},
      {"Ec", &Ec, PARAM_KIND_DOUBLE, 0, 0},
      {"Bo", &Bo, PARAM_KIND_DOUBLE, 0, 0},
      {"thetaInit", &thetaInit, PARAM_KIND_DOUBLE, 0, 0},
      {"thetaE", &thetaE, PARAM_KIND_DOUBLE, 0, 0},
      {"ttheta", &ttheta, PARAM_KIND_DOUBLE, 0, 0},
      {"thetaRate", &thetaRate, PARAM_KIND_DOUBLE, 0, 0}
    };
    if (!parseCaseParams(argv[1], params,
                         sizeof(params)/sizeof(params[0])))
      return 1;
  }

  L0 = Ldomain;
  X0 = 0.; Y0 = 0.;
  init_grid (1 << 6);

  char comm[80];
  sprintf (comm, "mkdir -p intermediate");
  system(comm);
  sprintf (dumpFile, "restart");

  theta0 = thetaInit;

  rho1 = 1., rho2 = 1e-3;
  mu1 = Ohs/sqrt(We), mu2 = Oha/sqrt(We);
  G1 = Ec/We, G2 = 0.0;
  lambda1 = purelyElastic ? 1e30 : De*sqrt(We);
  lambda2 = 0.0;

  f.sigma = 1.0/We;
  f.height = h;
  // Advective scaling (impact speed = 1, sigma = 1/We): the dimensionless
  // body-force acceleration is Bo/We, directed toward the substrate (-x).
  G.x = -Bo/We;

  run();
}

/**
## Initial condition

A unit drop just above the wall, given a downward impact velocity
`u.x = -f`. Restart from `dumpFile` if present.
*/
event init (t = 0) {
  if (!restore (file = dumpFile)) {
    refine (R2Drop(x,y) < 1.1 && R2Drop(x,y) > 0.9 && level < MAXlevel);
    fraction (f, 1. - R2Drop(x,y));
    foreach() {
      u.x[] = -1.0*f[];
      u.y[] = 0.0;
    }
  }
}

/**
## Time-switched contact angle

The angle is held at `thetaInit` until `ttheta`, then ramped linearly at
`thetaRate` deg/time down to the wetting value `thetaE`. Because the
`h.t[left]` boundary closure re-reads `theta0` every step, mutating it
here live-updates the imposed contact angle.

With the advective scaling used here the simulation time `t` equals the
experimental `t_i U0/R0`, so the Sen et al. pinning protocol (ramp
160 deg -> 60 deg over one impact-time unit, completing at t_i U0/R0 = 9)
is reproduced exactly by `ttheta = 8`, `thetaRate = 100`.
*/
event contactAngle (i++) {
  theta0 = (t > ttheta)
    ? max(thetaE, thetaInit - thetaRate*(t - ttheta))
    : thetaInit;
}

/**
## Adaptive mesh refinement

Refine on interface, velocity, curvature, and polymer conformation.
*/
event adapt (i++) {
  scalar KAPPA[], trA[];
  curvature (f, KAPPA);
  foreach()
    trA[] = A11[] + A22[] + AThTh[];
  adapt_wavelet ((scalar *){f, u.x, u.y, KAPPA, trA},
      (double[]){fErr, VelErr, VelErr, KErr, AErr},
      MAXlevel, 4);
  unrefine (x > 0.98*Ldomain); // suppress backflow from the outflow side
}

/**
## Snapshots and restart
*/
event writingFiles (t = 0; t += tsnap; t <= tmax) {
  p.nodump = false;
  dump (file = dumpFile);
  sprintf (nameOut, "intermediate/snapshot-%5.4f", t);
  dump (file = nameOut);
}

event end (t = end) {
  if (pid() == 0)
    fprintf(ferr,
            "Level %d, We %2.1e, Ohs %2.1e, Oha %2.1e, "
            "De %2.1e, Ec %2.1e, Bo %2.1e, elastic %d\n",
            MAXlevel, We, Ohs, Oha, De, Ec, Bo, purelyElastic);
}

/**
## Log writing

Tracks kinetic energy and aborts on blow-up or full decay.
*/
event logWriting (i++) {

  double ke = 0.;
  foreach (reduction(+:ke))
    ke += (2*pi*y)*(0.5*rho(f[])*(sq(u.x[]) + sq(u.y[])))*sq(Delta);

  static FILE * fp;
  if (pid() == 0) {
    const char* mode = (i == 0) ? "w" : "a";
    fp = fopen(logFile, mode);
    if (fp == NULL) {
      fprintf(ferr, "Error opening log file\n");
      return 1;
    }
    if (i == 0) {
      fprintf(ferr, "i dt t ke theta0\n");
      fprintf(fp, "i dt t ke theta0\n");
    }
    fprintf(fp, "%d %g %g %g %g\n", i, dt, t, ke, theta0);
    fprintf(ferr, "%d %g %g %g %g\n", i, dt, t, ke, theta0);
    fflush(fp);
    fclose(fp);
  }

  assert(ke > -1e-10);

  if (i > 1e1 && pid() == 0 && (ke > 1e2 || ke < 1e-8)) {
    fprintf(ferr, "Kinetic energy %s. Stopping.\n",
            ke > 1e2 ? "blew up" : "vanished");
    dump (file = dumpFile);
    return 1;
  }
}
