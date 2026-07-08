#!/bin/bash

MODE=$1
DIM_NAME=$2
CASE_DIR=$3

PYTHON_BIN="./venv/bin/python"
if [ ! -x "${PYTHON_BIN}" ]; then
  PYTHON_BIN="python3"
fi

split_export_option() {
  EXPORT_SPEC=""
  PARSED_ARGS=()

  while [ $# -gt 0 ]; do
    case "$1" in
      --export)
        if [ $# -lt 2 ]; then
          echo "Missing value for --export"
          return 1
        fi
        EXPORT_SPEC="$2"
        shift 2
        ;;
      --export=*)
        EXPORT_SPEC="${1#--export=}"
        shift
        ;;
      *)
        PARSED_ARGS+=("$1")
        shift
        ;;
    esac
  done

  return 0
}

normalize_export_dir() {
  local export_spec="$1"

  if [ -z "$export_spec" ]; then
    printf '%s' ""
    return 0
  fi

  case "$export_spec" in
    figures/*)
      printf '%s' "$export_spec"
      ;;
    /*)
      printf '%s' "$export_spec"
      ;;
    *)
      printf 'figures/%s' "$export_spec"
      ;;
  esac
}

collect_pngs_with_prefix() {
  local prefix="$1"
  local files=()

  shopt -s nullglob
  files=("${prefix}"*.png)
  shopt -u nullglob

  printf '%s\n' "${files[@]}"
}

export_pngs() {
  local export_spec="$1"
  local copy_tag="$2"
  shift 2

  if [ -z "$export_spec" ]; then
    return 0
  fi

  local export_dir
  export_dir="$(normalize_export_dir "$export_spec")"
  mkdir -p "$export_dir"

  local copied=()
  local src
  for src in "$@"; do
    if [ ! -f "$src" ]; then
      continue
    fi

    local base dest_name dest_path
    base=$(basename "$src" .png)
    dest_name="${base}_${copy_tag}.png"
    dest_path="${export_dir}/${dest_name}"
    cp "$src" "$dest_path"
    copied+=("$dest_name")
  done

  if [ ${#copied[@]} -eq 0 ]; then
    return 0
  fi

  echo "[Export figures]"
  echo "Destination: ${export_dir}"
  echo "Copied:"
  for src in "${copied[@]}"; do
    echo "  - ${src}"
  done
}

if [ -z "$MODE" ]; then
  echo "Usage:"
  echo "  bash scripts/run_analysis.sh fit_rw 2d kgw L512_N1000_T10000"
  echo "  bash scripts/run_analysis.sh fit_rw 3d kgw L128_N5000_T1000"
  echo "  bash scripts/run_analysis.sh fit_survival 2d death_on_contact L512_N1000_T10000"
  echo "  bash scripts/run_analysis.sh fit_lifetime 2d death_on_contact L512_N1000_T10000"
  echo "  bash scripts/run_analysis.sh compare_lifetime_summary 2d L <input1> [input2 ...]"
  echo "  bash scripts/run_analysis.sh compare_diffusion_L 2d saw mean_r2 <input1> [input2 ...]"
  echo "  bash scripts/run_analysis.sh compare_lifetime_by_L 2d death_on_contact <input1> [input2 ...]"
  echo "  bash scripts/run_analysis.sh compare_lifetime_by_T 2d saw <input1> [input2 ...]"
  echo "  bash scripts/run_analysis.sh compare_lifetime_by_N 2d saw <input1> [input2 ...] (deprecated alias)"
  echo "  bash scripts/run_analysis.sh analyze_msd_distribution 2d saw <msd_distribution.csv>"
  echo "  bash scripts/run_analysis.sh analyze_lifetime_distribution 2d saw <final_steps.csv>"
  echo "  bash scripts/run_analysis.sh compare_msd_alpha_by_T 2d saw <input1> [input2 ...] --fit-start <int> --fit-end <int> [--export <dir>]"
  exit 1
fi

case "$MODE" in

  fit_rw)
    DIM_NAME=${2:-2d}
    MODEL=$3
    CASE_DIR=$4

    if [ -z "$MODEL" ] || [ -z "$CASE_DIR" ]; then
      echo "Usage:"
      echo "  bash scripts/run_analysis.sh fit_rw 2d kgw L512_N1000_T10000"
      exit 1
    fi

    DATA_DIR="data/${DIM_NAME}/random_walk/${MODEL}/${CASE_DIR}"
    if [ ! -d "$DATA_DIR" ] && [ -d "data/${DIM_NAME}/random_walk/${CASE_DIR}" ]; then
      DATA_DIR="data/${DIM_NAME}/random_walk/${CASE_DIR}"
      echo "[Warning] using legacy fit_rw layout: ${DATA_DIR}"
    fi

    echo "[Analysis] Fit RW/SAW MSD and Rg2"
    echo "[Data] ${DATA_DIR}"

    if [ "$DIM_NAME" = "2d" ]; then
      STEP_MAX=50
    else
      STEP_MAX=300
    fi

    "${PYTHON_BIN}" scripts/analysis/fit_diffusion_exponent.py \
      --rw "${DATA_DIR}/rw.csv" \
      --saw "${DATA_DIR}/saw.csv" \
      --step-min 1 \
      --step-max ${STEP_MAX} \
      --out-prefix "${DATA_DIR}/fit_${DIM_NAME}"
    ;;

  fit_survival)
    DIM_NAME=${2:-2d}
    MODEL=$3
    CASE_DIR=$4

    if [ -z "$MODEL" ] || [ -z "$CASE_DIR" ]; then
      echo "Usage:"
      echo "  bash scripts/run_analysis.sh fit_survival 2d death_on_contact L512_N1000_T10000"
      exit 1
    fi

    DATA_DIR="data/${DIM_NAME}/random_walk/${MODEL}/${CASE_DIR}"
    if [ ! -d "$DATA_DIR" ] && [ -d "data/${DIM_NAME}/random_walk/${CASE_DIR}" ]; then
      DATA_DIR="data/${DIM_NAME}/random_walk/${CASE_DIR}"
      echo "[Warning] using legacy fit_survival layout: ${DATA_DIR}"
    fi

    echo "[Analysis] Fit survival probability"
    echo "[Data] ${DATA_DIR}"

    "${PYTHON_BIN}" scripts/analysis/fit_survival.py \
      --input "${DATA_DIR}/saw.csv" \
      --out-prefix "${DATA_DIR}/survival"
    ;;

  fit_lifetime)
    DIM_NAME=${2:-2d}
    MODEL=$3
    CASE_DIR=$4

    if [ -z "$MODEL" ] || [ -z "$CASE_DIR" ]; then
      echo "Usage:"
      echo "  bash scripts/run_analysis.sh fit_lifetime 2d death_on_contact L512_N1000_T10000"
      exit 1
    fi

    DATA_DIR="data/${DIM_NAME}/random_walk/${MODEL}/${CASE_DIR}"
    if [ ! -d "$DATA_DIR" ] && [ -d "data/${DIM_NAME}/random_walk/${CASE_DIR}" ]; then
      DATA_DIR="data/${DIM_NAME}/random_walk/${CASE_DIR}"
      echo "[Warning] using legacy fit_lifetime layout: ${DATA_DIR}"
    fi

    echo "[Analysis] Fit lifetime distribution"
    echo "[Data] ${DATA_DIR}"

    "${PYTHON_BIN}" scripts/analysis/fit_lifetime_distribution.py \
      --input "${DATA_DIR}/final_steps.csv" \
      --out-prefix "${DATA_DIR}/fit_lifetime" \
      ${MAX_STEP:+--max-step ${MAX_STEP}}
    ;;

  compare_lifetime_summary)
    DIM_NAME=${2:-2d}
    X=${3:-L}
    shift 3
    INPUTS=("$@")

    if [ -z "$DIM_NAME" ] || [ -z "$X" ] || [ ${#INPUTS[@]} -eq 0 ]; then
      echo "Usage:"
      echo "  bash scripts/run_analysis.sh compare_lifetime_summary 2d L <input1> [input2 ...]"
      exit 1
    fi

    OUTPUT_DIR="data/${DIM_NAME}/random_walk/comparisons/lifetime"
    mkdir -p "${OUTPUT_DIR}"

    FIRST_INPUT="${INPUTS[0]}"
    MODEL="$(echo "${FIRST_INPUT}" | sed -E 's#.*/random_walk/([^/]+)/.*#\1#')"
    if [ -z "${MODEL}" ]; then
      MODEL="summary"
    fi

    OUTPUT_CSV="${OUTPUT_DIR}/lifetime_comparison_${MODEL}.csv"
    PLOT_PREFIX="${OUTPUT_DIR}/lifetime_comparison_${MODEL}"

    echo "[Analysis] Compare lifetime summary"
    echo "[Output dir] ${OUTPUT_DIR}"
    echo "[Model] ${MODEL}"
    echo "[X-axis] ${X}"
    echo "[Inputs] ${INPUTS[*]}"

    "${PYTHON_BIN}" scripts/analysis/compare_lifetime_summary.py \
      --inputs "${INPUTS[@]}" \
      --output-csv "${OUTPUT_CSV}" \
      --plot-prefix "${PLOT_PREFIX}" \
      --x "${X}"
    ;;

  compare_diffusion_L)
    DIM_NAME=${2:-2d}
    MODEL=$3
    QUANTITY=$4
    shift 4
    INPUTS=("$@")

    if [ -z "$MODEL" ] || [ -z "$QUANTITY" ] || [ ${#INPUTS[@]} -eq 0 ]; then
      echo "Usage:"
      echo "  bash scripts/run_analysis.sh compare_diffusion_L 2d saw mean_r2 <input1> [input2 ...]"
      exit 1
    fi

    OUTPUT_DIR="data/${DIM_NAME}/random_walk/comparisons/diffusion"
    mkdir -p "${OUTPUT_DIR}"

    OUTPUT_CSV="${OUTPUT_DIR}/${MODEL}_${QUANTITY}_L_comparison.csv"
    PLOT_PREFIX="${OUTPUT_DIR}/${MODEL}_${QUANTITY}_L_comparison"

    echo "[Analysis] Compare diffusion across L"
    echo "[Output dir] ${OUTPUT_DIR}"
    echo "[Model] ${MODEL}"
    echo "[Quantity] ${QUANTITY}"
    echo "[Inputs] ${INPUTS[*]}"

    "${PYTHON_BIN}" scripts/analysis/compare_diffusion_by_L.py \
      --inputs "${INPUTS[@]}" \
      --output-csv "${OUTPUT_CSV}" \
      --plot-prefix "${PLOT_PREFIX}" \
      --quantity "${QUANTITY}" \
      --alpha-ymin 0.5 \
      --alpha-ymax 2.2 \
      --split-L \
      --split-threshold 512 \
      --large-L-min 1024
    ;;

  compare_saw_lifetime)
    DIM_NAME=${2:-2d}
    MODEL=$3
    shift 3
    INPUTS=("$@")

    if [ -z "$MODEL" ] || [ ${#INPUTS[@]} -eq 0 ]; then
      echo "Usage:"
      echo "  bash scripts/run_analysis.sh compare_saw_lifetime 2d saw <input1> [input2 ...]"
      exit 1
    fi

    OUTPUT_DIR="data/${DIM_NAME}/random_walk/comparisons/lifetime"
    mkdir -p "${OUTPUT_DIR}"

    OUTPUT_CSV="${OUTPUT_DIR}/${MODEL}_lifetime_comparison.csv"
    PLOT_PREFIX="${OUTPUT_DIR}/${MODEL}_lifetime"

    echo "[Analysis] Compare SAW lifetime across L"
    echo "[Output dir] ${OUTPUT_DIR}"
    echo "[Model] ${MODEL}"
    echo "[Inputs] ${INPUTS[*]}"

    "${PYTHON_BIN}" scripts/analysis/compare_lifetime_by_L.py \
      --inputs "${INPUTS[@]}" \
      --output-csv "${OUTPUT_CSV}" \
      --plot-prefix "${PLOT_PREFIX}" \
      --model "${MODEL}" \
      --fit-max \
      --plot-distribution
    ;;

  compare_lifetime_by_L)
    DIM_NAME=${2:-2d}
    MODEL=$3
    shift 3
    split_export_option "$@"
    INPUTS=("${PARSED_ARGS[@]}")

    if [ -z "$MODEL" ] || [ ${#INPUTS[@]} -eq 0 ]; then
      echo "Usage:"
      echo "  bash scripts/run_analysis.sh compare_lifetime_by_L 2d death_on_contact <input1> [input2 ...]"
      exit 1
    fi

    OUTPUT_DIR="data/${DIM_NAME}/random_walk/comparisons/lifetime"
    mkdir -p "${OUTPUT_DIR}"

    OUTPUT_CSV="${OUTPUT_DIR}/${MODEL}_lifetime_comparison.csv"
    PLOT_PREFIX="${OUTPUT_DIR}/${MODEL}_lifetime"

    echo "[Analysis] Compare lifetime across L"
    echo "[Output dir] ${OUTPUT_DIR}"
    echo "[Model] ${MODEL}"
    echo "[Inputs] ${INPUTS[*]}"

    FIRST_CASE_TAG=$(basename "$(dirname "${INPUTS[0]}")")

    "${PYTHON_BIN}" scripts/analysis/compare_lifetime_by_L.py \
      --inputs "${INPUTS[@]}" \
      --output-csv "${OUTPUT_CSV}" \
      --plot-prefix "${PLOT_PREFIX}" \
      --model "${MODEL}" \
      --fit-max \
      --plot-distribution

    split_export_option "$@"
    export_pngs "$EXPORT_SPEC" "${FIRST_CASE_TAG}" $(collect_pngs_with_prefix "$PLOT_PREFIX")
    ;;

  compare_lifetime_by_T)
    DIM_NAME=${2:-2d}
    MODEL=$3
    shift 3
    split_export_option "$@"
    INPUTS=("${PARSED_ARGS[@]}")

    if [ -z "$MODEL" ] || [ ${#INPUTS[@]} -eq 0 ]; then
      echo "Usage:"
      echo "  bash scripts/run_analysis.sh compare_lifetime_by_T 2d saw <input1> [input2 ...]"
      exit 1
    fi

    OUTPUT_DIR="data/${DIM_NAME}/random_walk/comparisons/lifetime"
    mkdir -p "${OUTPUT_DIR}"

    OUTPUT_CSV="${OUTPUT_DIR}/${MODEL}_lifetime_by_T_summary.csv"
    PLOT_PREFIX="${OUTPUT_DIR}/${MODEL}_lifetime_by_T"

    echo "[Analysis] Compare lifetime across n_trials"
    echo "[Output dir] ${OUTPUT_DIR}"
    echo "[Model] ${MODEL}"
    echo "[Inputs] ${INPUTS[*]}"

    FIRST_CASE_TAG=$(basename "$(dirname "${INPUTS[0]}")")

    "${PYTHON_BIN}" scripts/analysis/compare_lifetime_by_T.py \
      --inputs "${INPUTS[@]}" \
      --output-csv "${OUTPUT_CSV}" \
      --plot-prefix "${PLOT_PREFIX}" \
      --model "${MODEL}"

    export_pngs "$EXPORT_SPEC" "${FIRST_CASE_TAG}" $(collect_pngs_with_prefix "$PLOT_PREFIX")
    ;;

  compare_msd_alpha_by_T)
    DIM_NAME=${2:-2d}
    MODEL=$3
    shift 3
    split_export_option "$@"

    FIT_START=""
    FIT_END=""
    INPUTS=()

    for arg in "${PARSED_ARGS[@]}"; do
      case "$arg" in
        --fit-start=*)
          FIT_START="${arg#--fit-start=}"
          ;;
        --fit-start)
          EXPECT_FIT_START_VALUE=1
          ;;
        --fit-end=*)
          FIT_END="${arg#--fit-end=}"
          ;;
        --fit-end)
          EXPECT_FIT_END_VALUE=1
          ;;
        *)
          if [ "${EXPECT_FIT_START_VALUE:-0}" -eq 1 ]; then
            FIT_START="$arg"
            EXPECT_FIT_START_VALUE=0
          elif [ "${EXPECT_FIT_END_VALUE:-0}" -eq 1 ]; then
            FIT_END="$arg"
            EXPECT_FIT_END_VALUE=0
          else
            INPUTS+=("$arg")
          fi
          ;;
      esac
    done

    if [ "${EXPECT_FIT_START_VALUE:-0}" -eq 1 ]; then
      echo "Missing value for --fit-start"
      exit 1
    fi

    if [ "${EXPECT_FIT_END_VALUE:-0}" -eq 1 ]; then
      echo "Missing value for --fit-end"
      exit 1
    fi

    if [ -z "$MODEL" ] || [ ${#INPUTS[@]} -eq 0 ] || [ -z "$FIT_START" ] || [ -z "$FIT_END" ]; then
      echo "Usage:"
      echo "  bash scripts/run_analysis.sh compare_msd_alpha_by_T 2d saw <input1> [input2 ...] --fit-start <int> --fit-end <int> [--export <dir>]"
      exit 1
    fi

    OUTPUT_DIR="data/${DIM_NAME}/random_walk/comparisons/msd"
    mkdir -p "${OUTPUT_DIR}"

    OUTPUT_CSV="${OUTPUT_DIR}/${MODEL}_msd_alpha_by_T.csv"
    PLOT_PREFIX="${OUTPUT_DIR}/${MODEL}_msd_alpha_by_T"

    echo "[Analysis] Compare MSD alpha across T"
    echo "[Output dir] ${OUTPUT_DIR}"
    echo "[Model] ${MODEL}"
    echo "[Fit range] ${FIT_START}..${FIT_END}"
    echo "[Inputs] ${INPUTS[*]}"

    FIRST_CASE_TAG=$(basename "$(dirname "${INPUTS[0]}")")

    "${PYTHON_BIN}" scripts/analysis/compare_msd_alpha_by_T.py \
      --inputs "${INPUTS[@]}" \
      --fit-start "$FIT_START" \
      --fit-end "$FIT_END" \
      --output-csv "${OUTPUT_CSV}" \
      --plot-prefix "${PLOT_PREFIX}" \
      --model "${MODEL}"

    export_pngs "$EXPORT_SPEC" "$FIRST_CASE_TAG" $(collect_pngs_with_prefix "$PLOT_PREFIX")
    ;;

  compare_lifetime_by_N)
    echo "[Deprecated] compare_lifetime_by_N is an alias for compare_lifetime_by_T"
    exec "$0" compare_lifetime_by_T "${@:2}"
    ;;

  analyze_msd_distribution)
    DIM_NAME=${2:-2d}
    MODEL=$3
    shift 3
    split_export_option "$@"
    INPUT=""
    BIN_WIDTH=0
    EXPECT_BIN_WIDTH_VALUE=0

    for arg in "${PARSED_ARGS[@]}"; do
      if [ "$EXPECT_BIN_WIDTH_VALUE" -eq 1 ]; then
        BIN_WIDTH="$arg"
        EXPECT_BIN_WIDTH_VALUE=0
        continue
      fi

      case "$arg" in
        --bin-width=*)
          BIN_WIDTH="${arg#--bin-width=}"
          ;;
        --bin-width)
          EXPECT_BIN_WIDTH_VALUE=1
          ;;
        *)
          if [ -z "$INPUT" ]; then
            INPUT="$arg"
          else
            echo "Unexpected extra argument: $arg"
            exit 1
          fi
          ;;
      esac
    done

    if [ "$EXPECT_BIN_WIDTH_VALUE" -eq 1 ]; then
      echo "Missing value for --bin-width"
            echo "  compare_msd_alpha_by_T"
      exit 1
    fi

    if [ -z "$MODEL" ] || [ -z "$INPUT" ]; then
      echo "Usage:"
      echo "  bash scripts/run_analysis.sh analyze_msd_distribution 2d saw <msd_distribution.csv> [--bin-width <int>] [--export <dir>]"
      exit 1
    fi

    OUTPUT_DIR=$(dirname "$INPUT")
    BASE_NAME=$(basename "$INPUT" .csv)
    if [ "$BIN_WIDTH" -gt 0 ] 2>/dev/null; then
      BASE_NAME="${BASE_NAME}_binned_w${BIN_WIDTH}"
    fi
    OUTPUT_CSV="${OUTPUT_DIR}/${BASE_NAME}_summary.csv"
    PLOT_PREFIX="${OUTPUT_DIR}/${BASE_NAME}"

    echo "[Analysis] MSD distribution summary"
    echo "[Output dir] ${OUTPUT_DIR}"
    echo "[Model] ${MODEL}"
    echo "[Input] ${INPUT}"

    CASE_TAG=$(basename "$(dirname "$INPUT")")

    if [ "$BIN_WIDTH" -gt 0 ] 2>/dev/null; then
      "${PYTHON_BIN}" scripts/analysis/analyze_msd_distribution.py \
        --input "$INPUT" \
        --output-csv "$OUTPUT_CSV" \
        --plot-prefix "$PLOT_PREFIX" \
        --bin-width "$BIN_WIDTH"
    else
      "${PYTHON_BIN}" scripts/analysis/analyze_msd_distribution.py \
        --input "$INPUT" \
        --output-csv "$OUTPUT_CSV" \
        --plot-prefix "$PLOT_PREFIX"
    fi

    export_pngs "$EXPORT_SPEC" "$CASE_TAG" $(collect_pngs_with_prefix "$PLOT_PREFIX")
    ;;

  analyze_lifetime_distribution)
    DIM_NAME=${2:-2d}
    MODEL=$3
    INPUT=$4

    shift 4
    split_export_option "$@"

    if [ ${#PARSED_ARGS[@]} -gt 0 ]; then
      echo "Unexpected extra argument: ${PARSED_ARGS[*]}"
      exit 1
    fi

    if [ -z "$MODEL" ] || [ -z "$INPUT" ]; then
      echo "Usage:"
      echo "  bash scripts/run_analysis.sh analyze_lifetime_distribution 2d saw <final_steps.csv> [--export <dir>]"
      exit 1
    fi

    OUTPUT_DIR=$(dirname "$INPUT")
    PLOT_PREFIX="${OUTPUT_DIR}/${MODEL}_lifetime"

    echo "[Analysis] Lifetime distribution summary"
    echo "[Output dir] ${OUTPUT_DIR}"
    echo "[Model] ${MODEL}"
    echo "[Input] ${INPUT}"

    "${PYTHON_BIN}" scripts/analysis/analyze_lifetime_distribution.py \
      --input "$INPUT" \
      --output-dir "$OUTPUT_DIR" \
      --plot-prefix "$PLOT_PREFIX" \
      --model "$MODEL"

    CASE_TAG=$(basename "$(dirname "$INPUT")")
    export_pngs "$EXPORT_SPEC" "$CASE_TAG" $(collect_pngs_with_prefix "$PLOT_PREFIX")
    ;;

  *)
    echo "Unknown analysis mode: $MODE"
    echo "Available:"
    echo "  fit_rw"
    echo "  fit_survival"
    echo "  fit_lifetime"
    echo "  compare_lifetime_summary"
    echo "  compare_diffusion_L"
    echo "  compare_lifetime_by_L"
    echo "  compare_lifetime_by_T"
    echo "  compare_lifetime_by_N (deprecated alias)"
    echo "  compare_msd_alpha_by_T"
    echo "  analyze_msd_distribution"
    echo "  analyze_lifetime_distribution"
    exit 1
    ;;
esac