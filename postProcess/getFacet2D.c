/**
# Facet Extraction (2D)

Restores a Basilisk snapshot and outputs VOF interface facets for
visualization or post-processing.

## Usage

```bash
./getFacet2D <input_file>
```

## Dependencies

- `utils.h`
- `output.h`
- `fractions.h`

## Author

Vatsal Sanjay (vatsal.sanjay@comphy-lab.org)
CoMPhy Lab
Date: 2025-05-13
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

/**
## Globals

- `f[]`: Volume fraction field (liquid phase)
- `filename`: Input snapshot filename
*/
const char * filename;

/**
### main()

Restores a snapshot and writes interface facets to `stderr`.

#### Args

- `a`: Number of CLI arguments.
- `arguments[1]`: Input snapshot filename.

#### Returns

- `0` on success.

#### Notes

- Output uses `output_facets()` and is written to `ferr`.
*/
int main(int a, char const *arguments[]) {
  if (a != 2) {
    fprintf (ferr, "Usage: %s <input_file>\n", arguments[0]);
    return 1;
  }

  // Parse command line argument for input filename
  filename = arguments[1];

  // Restore simulation state from file
  restore(file = filename);

  // Set output destination to stderr
  FILE * fp = ferr;

  // Extract and output facets from volume fraction field
  output_facets(f, fp);

  // Ensure all output is written
  fflush(fp);

  // Close file pointer (stderr alias)
  fclose(fp);

  return 0;
}
