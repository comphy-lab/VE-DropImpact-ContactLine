#!/bin/bash
#SBATCH --job-name=veD025
#SBATCH --array=0-9%3
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=48:00:00
#SBATCH --partition=genoa
#SBATCH --mail-type=FAIL
#SBATCH --mail-user=vatsal.sanjay@comphy-lab.org
#SBATCH --output=.snellius-logs/veD025-%A_%a.out
#SBATCH --error=.snellius-logs/veD025-%A_%a.err

# Figure-2 De=0.25 regime-map slice on Snellius.
#
# Usage:
#   # validation case only
#   sbatch --array=0-0 runSnellius_figure2_De025.sbatch
#
#   # full sweep, 10 cases with at most 3 running at once
#   sbatch runSnellius_figure2_De025.sbatch
#
# Optional overrides:
#   sbatch --export=ALL,OMP_THREADS=24,MAXLEVEL=11 runSnellius_figure2_De025.sbatch
#   sbatch --ntasks=16 --cpus-per-task=1 --export=ALL,RUN_MODE=mpi runSnellius_figure2_De025.sbatch
#   sbatch --array=1-1 --export=ALL,DTMAX=2e-5,OUT_SUBDIR=figure2-De025-DT2e-5 runSnellius_figure2_De025.sbatch
#   DRY_RUN=1 bash runSnellius_figure2_De025.sbatch
#
# MPI note:
#   The first Snellius validation attempts with Basilisk MPI failed in VOF
#   advection for c2501/We=15 (jobs 24376152, 24376239, 24376351), while
#   the same case runs under the non-MPI/OpenMP path. Keep MPI opt-in until
#   the VOF/contact-line MPI instability is understood.

set -euo pipefail

PROJECT_DIR="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
cd "$PROJECT_DIR"

WE_VALUES=(15 20 25 30 35 40 45 50 55 60)
CASE_START=2501

DE="${DE:-0.25}"
OHS="${OHS:-0.0029}"
BETA="${BETA:-0.1}"
OHA="${OHA:-2.9e-05}"
MAXLEVEL="${MAXLEVEL:-10}"
LDOMAIN="${LDOMAIN:-8.0}"
TMAX="${TMAX:-20.0}"
DTMAX="${DTMAX:-1e-5}"
KEMAX="${KEMAX:-1e2}"
KEMIN="${KEMIN:-1e-8}"
BO="${BO:-1.0}"
THETA_INIT="${THETA_INIT:-160.0}"
THETA_E="${THETA_E:-60.0}"
TTHETA="${TTHETA:-8.0}"
THETA_RATE="${THETA_RATE:-100.0}"
BASILISK_REF="${BASILISK_REF:-v2026-01-13}"
BASILISK_INSTALL_URL="https://raw.githubusercontent.com/comphy-lab/basilisk-C/main/reset_install_basilisk-ref-locked.sh"

derive_ec() {
  awk -v o="$OHS" -v b="$BETA" -v d="$DE" 'BEGIN{printf "%.10g", o*(1-b)/(b*d)}'
}

derive_lambda() {
  local we_value="$1"
  awk -v d="$DE" -v w="$we_value" 'BEGIN{printf "%.10g", d*sqrt(w)}'
}

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo "Figure-2 De=0.25 sweep plan: ${#WE_VALUES[@]} cases"
  printf '%-6s %-6s %-8s %-12s %-12s %-12s\n' Index CaseNo We Ec lambda Oh_total
  for i in "${!WE_VALUES[@]}"; do
    we_i="${WE_VALUES[$i]}"
    case_i=$((CASE_START + i))
    ec_i=$(derive_ec)
    lam_i=$(derive_lambda "$we_i")
    oh_total=$(awk -v o="$OHS" -v b="$BETA" 'BEGIN{printf "%.10g", o/b}')
    printf '%-6s %-6s %-8s %-12s %-12s %-12s\n' "$i" "$case_i" "$we_i" "$ec_i" "$lam_i" "$oh_total"
  done
  exit 0
fi

TASK_ID="${SLURM_ARRAY_TASK_ID:-${CASE_INDEX:-0}}"
if [[ ! "$TASK_ID" =~ ^[0-9]+$ ]] || (( TASK_ID < 0 || TASK_ID >= ${#WE_VALUES[@]} )); then
  echo "ERROR: task index must be 0..$((${#WE_VALUES[@]} - 1)), got '${TASK_ID}'." >&2
  exit 1
fi

case_no=$((CASE_START + TASK_ID))
we="${WE_VALUES[$TASK_ID]}"
ec=$(derive_ec)
lambda=$(derive_lambda "$we")
run_mode="${RUN_MODE:-openmp}"
if [[ "$run_mode" != "openmp" && "$run_mode" != "serial" && "$run_mode" != "mpi" ]]; then
  echo "ERROR: RUN_MODE must be openmp, serial, or mpi; got '${run_mode}'." >&2
  exit 1
fi
ntasks="${NTASKS:-${SLURM_NTASKS:-1}}"
omp_threads="${OMP_THREADS:-${SLURM_CPUS_PER_TASK:-16}}"
if [[ "$run_mode" == "serial" ]]; then
  omp_threads=1
fi
case_label=$(printf 'c%04d-We%02d-De025' "$case_no" "$we")
out_subdir="${OUT_SUBDIR:-figure2-De025}"
case_dir="${PROJECT_DIR}/simulationCases/${out_subdir}/${case_label}"
param_file="${case_dir}/case.params"
build_dir="${PROJECT_DIR}/.snellius-build/${out_subdir}"
binary="${build_dir}/dropImpactVE_${run_mode}"
log_dir="${PROJECT_DIR}/.snellius-logs"

print_case() {
  cat <<CASEINFO
Case:      ${case_label}
Index:     ${TASK_ID}
We:        ${we}
De:        ${DE}
Ohs:       ${OHS}
beta:      ${BETA}
Oh_total:  $(awk -v o="$OHS" -v b="$BETA" 'BEGIN{printf "%.10g", o/b}')
Oha:       ${OHA}
Ec:        ${ec}
lambda:    ${lambda}
MAXlevel:    ${MAXLEVEL}
tmax:        ${TMAX}
DTmax:       ${DTMAX}
KEmax:       ${KEMAX}
run_mode:    ${run_mode}
ntasks:      ${ntasks}
omp_threads: ${omp_threads}
out_subdir:  ${out_subdir}
case_dir:    ${case_dir}
CASEINFO
}

mkdir -p "$case_dir" "$build_dir" "$log_dir"

echo "============================================="
echo "VE-DropImpact-ContactLine figure-2 De=0.25"
echo "============================================="
echo "Started:   $(date)"
echo "Node:      $(hostname)"
echo "Job ID:    ${SLURM_JOB_ID:-local}"
echo "Array ID:  ${SLURM_ARRAY_JOB_ID:-none} task ${TASK_ID}"
print_case
echo "============================================="

module purge
module load 2024
module load OpenMPI/5.0.3-GCC-13.3.0

export CC99='mpicc -std=c99 -D_GNU_SOURCE=1'
export MPI_LAUNCHER=srun
export MPI_LAUNCHER_NFLAG=-n
export OMP_NUM_THREADS="$omp_threads"

lock_ref=""
if [[ -f "${PROJECT_DIR}/basilisk/.comphy-lock" ]]; then
  lock_ref=$(awk -F= '$1 == "ref" {print $2; exit}' "${PROJECT_DIR}/basilisk/.comphy-lock" 2>/dev/null || true)
fi
if [[ ! -f "${PROJECT_DIR}/.project_config" || "$lock_ref" != "$BASILISK_REF" ]]; then
  echo "Installing ref-locked Basilisk (${BASILISK_REF}); current ref='${lock_ref:-none}'..."
  exec 9>"${PROJECT_DIR}/.basilisk-install.lock"
  flock 9
  lock_ref=""
  if [[ -f "${PROJECT_DIR}/basilisk/.comphy-lock" ]]; then
    lock_ref=$(awk -F= '$1 == "ref" {print $2; exit}' "${PROJECT_DIR}/basilisk/.comphy-lock" 2>/dev/null || true)
  fi
  if [[ ! -f "${PROJECT_DIR}/.project_config" || "$lock_ref" != "$BASILISK_REF" ]]; then
    export TMPDIR="${PROJECT_DIR}/.installtmp"
    mkdir -p "$TMPDIR"
    curl -fsSL "$BASILISK_INSTALL_URL" | bash -s -- --ref="$BASILISK_REF" --hard
    if [[ ! -x "${PROJECT_DIR}/basilisk/src/qcc" ]]; then
      ( cd "${PROJECT_DIR}/basilisk/src" && rm -f config && ln -s config.gcc config && { make -k >/dev/null 2>&1 || true; } && make )
    fi
    if [[ ! -f "${PROJECT_DIR}/.project_config" ]]; then
      cat > "${PROJECT_DIR}/.project_config" <<CFG
export BASILISK="${PROJECT_DIR}/basilisk/src"
if [ ! -d "\$BASILISK" ]; then echo "Error: BASILISK not found" >&2; return 1 2>/dev/null || exit 1; fi
_PATH=":\$PATH:"; _PATH="\${_PATH//:\$BASILISK:/:}"; _PATH="\${_PATH#:}"; _PATH="\${_PATH%:}"
export PATH="\$BASILISK\${_PATH:+:\$_PATH}"; unset _PATH
hash -r 2>/dev/null || true
CFG
    fi
    rm -rf "${PROJECT_DIR}/.installtmp"
  fi
  flock -u 9
fi

# shellcheck disable=SC1091
source "${PROJECT_DIR}/.project_config"
command -v qcc >/dev/null || { echo "ERROR: qcc not found after .project_config" >&2; exit 1; }
if [[ "$run_mode" == "mpi" ]]; then
  command -v mpicc >/dev/null || { echo "ERROR: mpicc not found after module load" >&2; exit 1; }
fi
echo "qcc:   $(command -v qcc)"
if command -v mpicc >/dev/null; then
  echo "mpicc: $(command -v mpicc)"
fi

cat > "$param_file" <<PARAMS
# Figure-2 De=0.25 sweep case generated by runSnellius_figure2_De025.sbatch
MAXlevel = ${MAXLEVEL}
Ldomain = ${LDOMAIN}
tmax = ${TMAX}
DTmax = ${DTMAX}
KEmax = ${KEMAX}
KEmin = ${KEMIN}
We = ${we}
Ohs = ${OHS}
Oha = ${OHA}
De = ${DE}
Ec = ${ec}
Bo = ${BO}
purelyElastic = 0
thetaInit = ${THETA_INIT}
thetaE = ${THETA_E}
ttheta = ${TTHETA}
thetaRate = ${THETA_RATE}
PARAMS
echo "Parameter file: ${param_file}"
cat "$param_file"

exec 8>"${build_dir}/.compile.lock"
flock 8
if [[ ! -x "$binary" || "${PROJECT_DIR}/simulationCases/dropImpactVE.c" -nt "$binary" || "${PROJECT_DIR}/src-local/two-phaseVE.h" -nt "$binary" || "${PROJECT_DIR}/src-local/log-conform-viscoelastic-scalar-2D.h" -nt "$binary" ]]; then
  echo "Compiling ${run_mode} binary..."
  cp "${PROJECT_DIR}/simulationCases/dropImpactVE.c" "${build_dir}/dropImpactVE.c"
  case "$run_mode" in
    mpi)
      ( cd "$build_dir" && qcc -D_MPI=1 -I"${PROJECT_DIR}/src-local" -O2 -Wall \
          -disable-dimensions dropImpactVE.c -o "$binary" -lm )
      ;;
    openmp)
      ( cd "$build_dir" && qcc -fopenmp -I"${PROJECT_DIR}/src-local" -O2 -Wall \
          -disable-dimensions dropImpactVE.c -o "$binary" -lm )
      ;;
    serial)
      ( cd "$build_dir" && qcc -I"${PROJECT_DIR}/src-local" -O2 -Wall \
          -disable-dimensions dropImpactVE.c -o "$binary" -lm )
      ;;
  esac
else
  echo "Using existing binary: ${binary}"
fi
flock -u 8

cp "$binary" "${case_dir}/dropImpactVE_${run_mode}"
cd "$case_dir"

rc=0
case "$run_mode" in
  mpi)
    echo "Launching with srun -n ${ntasks} ./dropImpactVE_mpi case.params"
    srun -n "$ntasks" ./dropImpactVE_mpi case.params || rc=$?
    ;;
  openmp)
    echo "Launching with OMP_NUM_THREADS=${omp_threads} srun --ntasks=1 --cpus-per-task=${omp_threads} ./dropImpactVE_openmp case.params"
    srun --exclusive --ntasks=1 --cpus-per-task="$omp_threads" ./dropImpactVE_openmp case.params || rc=$?
    ;;
  serial)
    echo "Launching serial ./dropImpactVE_serial case.params"
    ./dropImpactVE_serial case.params || rc=$?
    ;;
esac

echo "============================================="
echo "Finished: $(date) rc=${rc}"
echo "Case dir: ${case_dir}"
echo "Log:      ${case_dir}/logAxi-scalar.dat"
if [[ -f "${case_dir}/simulation.status" ]]; then
  echo "Status:   $(cat "${case_dir}/simulation.status")"
  if grep -q '^guard_stop ' "${case_dir}/simulation.status"; then
    rc=20
  fi
else
  echo "Status:   missing simulation.status"
  if [[ "$rc" -eq 0 ]]; then
    rc=21
  fi
fi
echo "============================================="
exit "$rc"
