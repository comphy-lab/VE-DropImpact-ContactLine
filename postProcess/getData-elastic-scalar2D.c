/**
# Scalar diagnostics for VE drop-impact snapshots

Restore the complete solver state and sample `D2`, velocity magnitude and
the conformation-trace deviation on a uniform physical half-plane grid.

```bash
getData-elastic-scalar2D snapshot xmin ymin xmax ymax ny > fields.dat
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
scalar D2c[], vel[], trA[];
scalar * list = NULL;

int main (int argc, char * argv[])
{
  if (argc != 7) {
    fprintf (stderr,
             "Usage: %s <snapshot> <xmin> <ymin> <xmax> <ymax> <ny>\n",
             argv[0]);
    return 1;
  }

  xmin = atof (argv[2]);
  ymin = atof (argv[3]);
  xmax = atof (argv[4]);
  ymax = atof (argv[5]);
  ny = atoi (argv[6]);
  if (ny < 1 || xmax <= xmin || ymax <= ymin) {
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
    trA[] = (A11[] + A22[] + AThTh[])/3. - 1.;
    trA[] = trA[] > 0. ? log10(trA[]) : -10.;
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
