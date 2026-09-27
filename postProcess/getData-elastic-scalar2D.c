/**
# Scalar diagnostics for VE drop-impact snapshots

Restore the complete solver state and sample `D2`, velocity, normalised
conformation trace, axial polymer stress, and liquid-fraction diagnostics
on a uniform physical half-plane grid. The optional final argument converts
stress from impact-pressure to capillary-pressure units.

```bash
getData-elastic-scalar2D snapshot xmin ymin xmax ymax ny [We] > fields.dat
```
*/

#include "axi.h"
#include "navier-stokes/centered.h"
#include "log-conform-viscoelastic-scalar-2D.h"
#define FILTERED
#include "contact-fixed.h"
#include "two-phaseVE.h"
#include "navier-stokes/conserving.h"
#include "tension.h"
#include "reduced.h"
#include "utils.h"
#include "output.h"

int nx, ny, len;
double xmin, ymin, xmax, ymax, Deltax, Deltay;
double stress_we;
scalar D2c[], vel[], trA[], ux[], uy[], sigma_p_zz[];
scalar * list = NULL;

int main (int argc, char * argv[])
{
  if (argc != 7 && argc != 8) {
    fprintf (stderr,
             "Usage: %s <snapshot> <xmin> <ymin> <xmax> <ymax> <ny> [We]\n",
             argv[0]);
    return 1;
  }

  xmin = atof (argv[2]);
  ymin = atof (argv[3]);
  xmax = atof (argv[4]);
  ymax = atof (argv[5]);
  ny = atoi (argv[6]);
  stress_we = argc == 8 ? atof (argv[7]) : 1.;
  if (ny < 1 || xmax <= xmin || ymax <= ymin ||
      !isfinite(stress_we) || stress_we <= 0.) {
    fprintf (stderr, "Invalid sampling bounds or resolution.\n");
    return 1;
  }
  if (!restore (file = argv[1])) {
    fprintf (stderr, "Could not restore snapshot: %s\n", argv[1]);
    return 2;
  }

  list = list_add (list, D2c);
  list = list_add (list, vel);
  list = list_add (list, trA);
  list = list_add (list, ux);
  list = list_add (list, uy);
  list = list_add (list, f);
  list = list_add (list, sigma_p_zz);

  foreach() {
    double D11 = (u.y[0,1] - u.y[0,-1])/(2.*Delta);
    double D22 = y != 0. ? u.y[]/y : 0.;
    double D33 = (u.x[1,0] - u.x[-1,0])/(2.*Delta);
    double D13 = 0.5*(u.y[1,0] - u.y[-1,0] +
                      u.x[0,1] - u.x[0,-1])/(2.*Delta);
    double D2 = sq(D11) + sq(D22) + sq(D33) + 2.*sq(D13);
    D2c[] = f[]*D2;
    D2c[] = D2c[] > 0. ? log10(D2c[]) : -10.;
    vel[] = sqrt(sq(u.x[]) + sq(u.y[]));
    ux[] = u.x[];
    uy[] = u.y[];
    // A = I at polymer equilibrium, hence log10(tr(A)/3) = 0 there.
    // Negative/positive values denote reduced/increased isotropic polymer
    // extension. Keep a sentinel only for the invalid log domain.
    trA[] = A11[] + A22[] + AThTh[];
    trA[] = trA[] > 1e-12 ? log10(trA[]/3.) : -10.;
    // The axial coordinate is x in axi.h; the solver stores
    // T11 = (Ec/We)*(A11 - 1) in impact-pressure units. Multiplying by
    // We yields Ec*(A11 - 1), the manuscript's capillary-pressure units.
    double stress = fabs(stress_we*T11[]);
    sigma_p_zz[] = stress > 1e-10 ? log10(stress) : -10.;
  }

  Deltay = (ymax - ymin)/ny;
  nx = (int) ((xmax - xmin)/Deltay);
  if (nx < 1) {
    fprintf (stderr, "Sampling grid has no x cells.\n");
    return 1;
  }
  Deltax = (xmax - xmin)/nx;
  len = list_len (list);
  double ** field = (double **) matrix_new (nx, ny + 1,
                                             len*sizeof(double));

  for (int i = 0; i < nx; i++) {
    double x = Deltax*(i + 0.5) + xmin;
    for (int j = 0; j < ny; j++) {
      double y = Deltay*(j + 0.5) + ymin;
      int k = 0;
      for (scalar s in list)
        field[i][len*j + k++] = interpolate (s, x, y);
    }
  }

  for (int i = 0; i < nx; i++) {
    double x = Deltax*(i + 0.5) + xmin;
    for (int j = 0; j < ny; j++) {
      double y = Deltay*(j + 0.5) + ymin;
      fprintf (stdout, "%g %g", x, y);
      int k = 0;
      for (scalar s in list)
        fprintf (stdout, " %g", field[i][len*j + k++]);
      fputc ('\n', stdout);
    }
  }
  fflush (stdout);
  matrix_free (field);
  return 0;
}
