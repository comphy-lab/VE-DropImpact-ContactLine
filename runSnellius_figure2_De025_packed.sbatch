#!/bin/bash
#SBATCH --job-name=veD025pack
#SBATCH --nodes=1
#SBATCH --ntasks=192
#SBATCH --cpus-per-task=1
#SBATCH --exclusive
#SBATCH --time=72:00:00
#SBATCH --partition=genoa
#SBATCH --mail-type=FAIL
#SBATCH --mail-user=vatsal.sanjay@comphy-lab.org
#SBATCH --output=.snellius-logs/veD025pack-%j.out
#SBATCH --error=.snellius-logs/veD025pack-%j.err

# Full-node packed serial launcher for the Figure-2 De=0.25 slice.
#
# This requests one exclusive Genoa node and launches multiple independent
# serial Basilisk cases inside that allocation. The single-case runner remains
# the source of case setup, parameter files, compile locking, and exit checks.
#
# Usage:
#   sbatch runSnellius_figure2_De025_packed.sbatch
#
# Useful overrides:
#   sbatch --export=ALL,DTMAX=2e-5,PACK_CONCURRENCY=10 runSnellius_figure2_De025_packed.sbatch
#   sbatch --export=ALL,CASE_INDICES=0,4,7,DTMAX=2e-5 runSnellius_figure2_De025_packed.sbatch
#   sbatch --export=ALL,BASILISK_SRC_OVERRIDE=/path/to/basilisk/src runSnellius_figure2_De025_packed.sbatch

set -euo pipefail

PROJECT_DIR="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
cd "$PROJECT_DIR"

mkdir -p .snellius-logs

CASE_INDICES="${CASE_INDICES:-0 1 2 3 4 5 6 7 8 9}"
CASE_INDICES="${CASE_INDICES//,/ }"
PACK_CONCURRENCY="${PACK_CONCURRENCY:-10}"
OUT_SUBDIR="${OUT_SUBDIR:-figure2-De025-prod-packed-dt2e-5-20260704}"
RUN_MODE="${RUN_MODE:-serial}"
DTMAX="${DTMAX:-2e-5}"
TMAX="${TMAX:-20.0}"
BASILISK_SRC_OVERRIDE="${BASILISK_SRC_OVERRIDE-}"

if [[ "$RUN_MODE" != "serial" ]]; then
  echo "ERROR: packed launcher is intended for RUN_MODE=serial; got '${RUN_MODE}'." >&2
  exit 1
fi
if [[ ! "$PACK_CONCURRENCY" =~ ^[0-9]+$ ]] || (( PACK_CONCURRENCY < 1 || PACK_CONCURRENCY > 192 )); then
  echo "ERROR: PACK_CONCURRENCY must be 1..192; got '${PACK_CONCURRENCY}'." >&2
  exit 1
fi

module purge
module load 2024
module load OpenMPI/5.0.3-GCC-13.3.0

echo "============================================="
echo "VE-DropImpact-ContactLine packed De=0.25 sweep"
echo "============================================="
echo "Started:             $(date)"
echo "Node:                $(hostname)"
echo "Job ID:              ${SLURM_JOB_ID:-local}"
echo "Allocated CPUs:      ${SLURM_NTASKS:-unknown}"
echo "CASE_INDICES:        ${CASE_INDICES}"
echo "PACK_CONCURRENCY:    ${PACK_CONCURRENCY}"
echo "OUT_SUBDIR:          ${OUT_SUBDIR}"
echo "RUN_MODE:            ${RUN_MODE}"
echo "DTMAX:               ${DTMAX}"
echo "TMAX:                ${TMAX}"
if [[ -n "$BASILISK_SRC_OVERRIDE" ]]; then
  echo "BASILISK override:   ${BASILISK_SRC_OVERRIDE}"
else
  echo "BASILISK source:     project .project_config"
fi
echo "============================================="

running=0
rc=0
pids=()
cases=()

wait_one() {
  local pid="${pids[0]}"
  local case_idx="${cases[0]}"
  local status=0
  set +e
  wait "$pid"
  status=$?
  set -e
  echo "Case index ${case_idx} finished with rc=${status}"
  if (( status != 0 )); then
    rc=1
  fi
  pids=("${pids[@]:1}")
  cases=("${cases[@]:1}")
  running=$((running - 1))
}

for case_idx in $CASE_INDICES; do
  if [[ ! "$case_idx" =~ ^[0-9]+$ ]] || (( case_idx < 0 || case_idx > 9 )); then
    echo "ERROR: case index must be 0..9, got '${case_idx}'." >&2
    exit 1
  fi

  while (( running >= PACK_CONCURRENCY )); do
    wait_one
  done

  out=".snellius-logs/veD025pack-${SLURM_JOB_ID:-local}_${case_idx}.out"
  err=".snellius-logs/veD025pack-${SLURM_JOB_ID:-local}_${case_idx}.err"
  echo "Launching case index ${case_idx}: out=${out} err=${err}"
  (
    export CASE_INDEX="$case_idx"
    export RUN_MODE OUT_SUBDIR DTMAX TMAX BASILISK_SRC_OVERRIDE
    export OMP_NUM_THREADS=1
    if command -v taskset >/dev/null 2>&1; then
      taskset -c "$case_idx" bash runSnellius_figure2_De025.sbatch
    else
      bash runSnellius_figure2_De025.sbatch
    fi
  ) >"$out" 2>"$err" &

  pids+=("$!")
  cases+=("$case_idx")
  running=$((running + 1))
done

while (( running > 0 )); do
  wait_one
done

echo "============================================="
echo "Finished: $(date) rc=${rc}"
echo "Output root: ${PROJECT_DIR}/simulationCases/${OUT_SUBDIR}"
echo "============================================="
exit "$rc"
