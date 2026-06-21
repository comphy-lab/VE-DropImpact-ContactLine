#!/bin/bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: runSimulation.sh [--case simulationCases/SOME_CASE.c] [--input file.params]

Options:
  --case    Path to case source file (.c), optional.
  --input   Path to params file, optional.
  --help    Show this help.

Notes:
  - Defaults:
    --case  -> simulationCases/dropImpactVE.c
    --input -> default-VE.params
  - Default params are expected at repository root.
  - Compiles against src-local/ and runs in a per-case subdirectory.
EOF
}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT="$SCRIPT_DIR"

resolve_file() {
  local candidate="$1"
  if [ -f "$candidate" ]; then
    echo "$candidate"
  elif [ -f "${REPO_ROOT}/${candidate}" ]; then
    echo "${REPO_ROOT}/${candidate}"
  else
    echo ""
  fi
}

CASE_ARG="simulationCases/dropImpactVE.c"
INPUT_ARG=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --case)
      [ "$#" -lt 2 ] && { echo "Missing value for --case"; usage; exit 1; }
      CASE_ARG="$2"; shift 2 ;;
    --input)
      [ "$#" -lt 2 ] && { echo "Missing value for --input"; usage; exit 1; }
      INPUT_ARG="$2"; shift 2 ;;
    --help|-h)
      usage; exit 0 ;;
    *)
      echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

CASE_FILE=$(resolve_file "$CASE_ARG")
[ -z "$CASE_FILE" ] && { echo "Case source not found: ${CASE_ARG}"; exit 1; }

CASE_DIR=$(cd "$(dirname "$CASE_FILE")" && pwd)
CASE_FILE_NAME=$(basename "$CASE_FILE")
CASE_NAME="${CASE_FILE_NAME%.c}"
RUN_DIR="${CASE_DIR}/${CASE_NAME}"

if [ -n "$INPUT_ARG" ]; then
  PARAM_SOURCE=$(resolve_file "$INPUT_ARG")
  [ -z "$PARAM_SOURCE" ] && { echo "Parameter file not found: ${INPUT_ARG}"; exit 1; }
else
  PARAM_SOURCE="${REPO_ROOT}/default-VE.params"
  [ ! -f "$PARAM_SOURCE" ] && { echo "Default params not found: ${PARAM_SOURCE}"; exit 1; }
fi

mkdir -p "$RUN_DIR"
cp "$CASE_FILE" "$RUN_DIR/"
PARAM_BASENAME=$(basename "$PARAM_SOURCE")
cp "$PARAM_SOURCE" "$RUN_DIR/$PARAM_BASENAME"

cd "$RUN_DIR"

qcc -I"${REPO_ROOT}/src-local" -O2 -Wall \
  -disable-dimensions "$CASE_FILE_NAME" -o "$CASE_NAME" -lm

./"$CASE_NAME" "$PARAM_BASENAME"
