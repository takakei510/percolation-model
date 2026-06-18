#!/bin/bash

MODE=$1
DIM_NAME=$2
CASE_DIR=$3

if [ -z "$MODE" ]; then
  echo "Usage:"
  echo "  bash scripts/run_analysis.sh fit_rw 2d kgw L512_N1000_T10000"
  echo "  bash scripts/run_analysis.sh fit_rw 3d kgw L128_N5000_T1000"
  echo "  bash scripts/run_analysis.sh fit_survival 2d death_on_contact L512_N1000_T10000"
  echo "  bash scripts/run_analysis.sh fit_lifetime 2d death_on_contact L512_N1000_T10000"
  echo "  bash scripts/run_analysis.sh compare_lifetime_summary 2d L <input1> [input2 ...]"
  echo "  bash scripts/run_analysis.sh compare_diffusion_L 2d saw mean_r2 <input1> [input2 ...]"
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

    python scripts/analysis/fit_diffusion_exponent.py \
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

    python scripts/analysis/fit_survival.py \
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

    python scripts/analysis/fit_lifetime_distribution.py \
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

    python scripts/analysis/compare_lifetime_summary.py \
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

    python scripts/analysis/compare_diffusion_by_L.py \
      --inputs "${INPUTS[@]}" \
      --output-csv "${OUTPUT_CSV}" \
      --plot-prefix "${PLOT_PREFIX}" \
      --quantity "${QUANTITY}" \
      --alpha-ymin 0.5 \
      --alpha-ymax 2.2 \
      --split-L \
      --split-threshold 512
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

    python scripts/analysis/compare_saw_lifetime.py \
      --inputs "${INPUTS[@]}" \
      --output-csv "${OUTPUT_CSV}" \
      --plot-prefix "${PLOT_PREFIX}" \
      --fit-max
    ;;

  *)
    echo "Unknown analysis mode: $MODE"
    echo "Available:"
    echo "  fit_rw"
    echo "  fit_survival"
    echo "  fit_lifetime"
    echo "  compare_lifetime_summary"
    echo "  compare_diffusion_L"
    exit 1
    ;;
esac