#!/bin/bash
#SBATCH --job-name=veRegimeOMP
#SBATCH --nodes=1
#SBATCH --ntasks=12
#SBATCH --cpus-per-task=16
#SBATCH --exclusive
#SBATCH --hint=nomultithread
#SBATCH --time=5-00:00:00
#SBATCH --partition=genoa
#SBATCH --mail-type=FAIL
#SBATCH --mail-user=vatsal.sanjay@comphy-lab.org
#SBATCH --output=.snellius-logs/veRegimeOMP-%A_%a.out
#SBATCH --error=.snellius-logs/veRegimeOMP-%A_%a.err

# One array element owns one Genoa node and packs 12 independent OpenMP cases
# with 16 threads each. Submit each physics grid separately, for example:
#
#   sbatch --array=0-2 --export=ALL,SWEEP_CONFIG=sweep-fixedBeta.params,\
#     OUT_SUBDIR=figure2-full-map-contact-fixed-openmp-20260710/fixedBeta,\
#     BASILISK_SRC_OVERRIDE=/path/to/basilisk/src \
#     runSnellius_regime_map_openmp_packed.sbatch
#
# The fixed-Ec grid uses the same command with its config and output subdir.

set -euo pipefail

PROJECT_DIR="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
cd "$PROJECT_DIR"

SWEEP_CONFIG="${SWEEP_CONFIG:-sweep-fixedBeta.params}"
OUT_SUBDIR="${OUT_SUBDIR:-figure2-full-map-contact-fixed-openmp-20260710/fixedBeta}"
BASILISK_SRC_OVERRIDE="${BASILISK_SRC_OVERRIDE:-}"
CASES_PER_NODE="${CASES_PER_NODE:-12}"
OMP_THREADS="${OMP_THREADS:-16}"
NODE_INDEX="${SLURM_ARRAY_TASK_ID:-0}"

case "$OUT_SUBDIR" in
  /*|*".."*) echo "ERROR: invalid OUT_SUBDIR: $OUT_SUBDIR" >&2; exit 1 ;;
esac
[[ -f "$SWEEP_CONFIG" ]] || { echo "ERROR: missing sweep config: $SWEEP_CONFIG" >&2; exit 1; }
[[ -d "$BASILISK_SRC_OVERRIDE" ]] || {
  echo "ERROR: set BASILISK_SRC_OVERRIDE to the tested Snellius Basilisk src tree." >&2
  exit 1
}
[[ "$CASES_PER_NODE" =~ ^[0-9]+$ ]] && [[ "$OMP_THREADS" =~ ^[0-9]+$ ]] || {
  echo "ERROR: CASES_PER_NODE and OMP_THREADS must be positive integers." >&2
  exit 1
}
(( CASES_PER_NODE > 0 && OMP_THREADS > 0 )) || exit 1
(( CASES_PER_NODE * OMP_THREADS == 192 )) || {
  echo "ERROR: packing must use all 192 Genoa CPUs; got ${CASES_PER_NODE}x${OMP_THREADS}." >&2
  exit 1
}

config_value() {
  awk -F= -v key="$1" '
    { sub(/[#;].*/, "") }
    { gsub(/^[ \t]+|[ \t]+$/, "", $1) }
    $1 == key {
      value = $2
      gsub(/^[ \t]+|[ \t]+$/, "", value)
      print value
      exit
    }' "$SWEEP_CONFIG"
}

read -r -a WE_VALUES <<< "$(config_value SWEEP_WE)"
read -r -a DE_VALUES <<< "$(config_value SWEEP_DE)"
TOTAL_CASES=$(( ${#WE_VALUES[@]} * ${#DE_VALUES[@]} ))
(( TOTAL_CASES > 0 )) || { echo "ERROR: empty We-De grid." >&2; exit 1; }

FIRST_CASE=$(( NODE_INDEX * CASES_PER_NODE + 1 ))
LAST_CASE=$(( FIRST_CASE + CASES_PER_NODE - 1 ))
if (( FIRST_CASE > TOTAL_CASES )); then
  echo "Node index ${NODE_INDEX} has no cases for ${TOTAL_CASES}-case grid."
  exit 0
fi
if (( LAST_CASE > TOTAL_CASES )); then
  LAST_CASE=$TOTAL_CASES
fi

CASE_ROOT="$PROJECT_DIR/simulationCases/$OUT_SUBDIR"
BUILD_DIR="$PROJECT_DIR/.snellius-build/$OUT_SUBDIR"
LOG_DIR="$PROJECT_DIR/.snellius-logs"

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo "Dry run: config=${SWEEP_CONFIG}, grid=${TOTAL_CASES}, node=${NODE_INDEX}, cases=${FIRST_CASE}..${LAST_CASE}."
  echo "Dry run: packing=${CASES_PER_NODE}x${OMP_THREADS}=192, output=${OUT_SUBDIR}."
  exit 0
fi

mkdir -p "$CASE_ROOT" "$BUILD_DIR" "$LOG_DIR"

module purge
module load 2024
module load OpenMPI/5.0.3-GCC-13.3.0
export CC99='mpicc -std=c99 -D_GNU_SOURCE=1'
export BASILISK="$BASILISK_SRC_OVERRIDE"
export PATH="$BASILISK:$PATH"
export OMP_NUM_THREADS="$OMP_THREADS"
export OMP_PROC_BIND=spread
export OMP_PLACES=cores
hash -r 2>/dev/null || true
command -v qcc >/dev/null || { echo "ERROR: qcc not found." >&2; exit 1; }

echo "============================================="
echo "VE full We-De OpenMP packed regime map"
echo "============================================="
echo "Job/array:      ${SLURM_JOB_ID:-local}/${NODE_INDEX}"
echo "Node:           $(hostname)"
echo "Config:         $SWEEP_CONFIG"
echo "Output:         $OUT_SUBDIR"
echo "Grid:           ${#WE_VALUES[@]} We x ${#DE_VALUES[@]} De = $TOTAL_CASES"
echo "Cases:          $FIRST_CASE..$LAST_CASE"
echo "Packing:        ${CASES_PER_NODE} cases x ${OMP_THREADS} OpenMP threads = 192 CPUs"
echo "Basilisk:       $BASILISK"
echo "============================================="

# Array elements share the same case root. Generate the full deterministic
# plan and compile once under an advisory lock before launching their slice.
exec 9>"$BUILD_DIR/.prepare.lock"
flock 9
bash runParameterSweep.sh --config "$SWEEP_CONFIG" --out-subdir "$OUT_SUBDIR" \
  --start 1 --end "$TOTAL_CASES" --generate-only

BINARY="$BUILD_DIR/dropImpactVE_openmp"
if [[ ! -x "$BINARY" || "$PROJECT_DIR/simulationCases/dropImpactVE.c" -nt "$BINARY" || \
      "$PROJECT_DIR/src-local/contact-fixed.h" -nt "$BINARY" || \
      "$PROJECT_DIR/src-local/two-phaseVE.h" -nt "$BINARY" || \
      "$PROJECT_DIR/src-local/log-conform-viscoelastic-scalar-2D.h" -nt "$BINARY" ]]; then
  echo "Compiling OpenMP solver once in $BUILD_DIR"
  cp "$PROJECT_DIR/simulationCases/dropImpactVE.c" "$BUILD_DIR/dropImpactVE.c"
  (
    cd "$BUILD_DIR"
    qcc -fopenmp -I"$PROJECT_DIR/src-local" -O2 -Wall -disable-dimensions \
      dropImpactVE.c -o "$BINARY" -lm
  )
fi
flock -u 9

running=0
rc=0
pids=()
case_numbers=()

wait_one() {
  local pid="${pids[0]}"
  local case_number="${case_numbers[0]}"
  local status=0
  set +e
  wait "$pid"
  status=$?
  set -e
  if [[ ! -f "$CASE_ROOT/$(printf '%03d' "$case_number")/simulation.status" ]]; then
    echo "Case ${case_number}: missing simulation.status" >&2
    status=1
  fi
  echo "Case ${case_number} finished with rc=${status}"
  (( status == 0 )) || rc=1
  pids=("${pids[@]:1}")
  case_numbers=("${case_numbers[@]:1}")
  running=$((running - 1))
}

for case_number in $(seq "$FIRST_CASE" "$LAST_CASE"); do
  case_dir="$CASE_ROOT/$(printf '%03d' "$case_number")"
  echo "Launching case ${case_number} in ${case_dir}"
  (
    cd "$case_dir"
    srun --exclusive --nodes=1 --ntasks=1 --cpus-per-task="$OMP_THREADS" \
      --cpu-bind=cores "$BINARY" case.params > run.stdout 2> run.stderr
  ) &
  pids+=("$!")
  case_numbers+=("$case_number")
  running=$((running + 1))
done

while (( running > 0 )); do
  wait_one
done

echo "Finished node slice ${FIRST_CASE}..${LAST_CASE} with rc=${rc}"
exit "$rc"
