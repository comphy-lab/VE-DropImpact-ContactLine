/**
# Facet extractor for VE drop-impact snapshots

Restore one snapshot with the same Basilisk include stack as the solver and
write the liquid-interface facets to standard output.

```bash
getFacet2D intermediate/snapshot-0.1000 > facets.dat
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

int main (int argc, char * argv[])
{
  if (argc != 2) {
    fprintf (stderr, "Usage: %s <snapshot>\n", argv[0]);
    return 1;
  }
  if (!restore (file = argv[1])) {
    fprintf (stderr, "Could not restore snapshot: %s\n", argv[1]);
    return 2;
  }
  output_facets (f, stdout);
  fflush (stdout);
  return 0;
}
