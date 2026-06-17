#!/bin/bash

MODE=$1
DIM_NAME=$2
CASE_DIR=$3

if [ -z "$MODE" ]; then
  echo "Usage:"
  echo "  bash scripts/run_analysis.sh fit_rw 2d L512_N1000_T10000"
  echo "  bash scripts/run_analysis.sh fit_rw 3d L128_N5000_T1000"
  echo "  bash scripts/run_analysis.sh fit_survival 2d L512_N1000_T10000"
  exit 1
fi

case "$MODE" in

  fit_rw)
    DIM_NAME=${2:-2d}
    CASE_DIR=$3

    if [ -z "$CASE_DIR" ]; then
      echo "Usage:"
      echo "  bash scripts/run_analysis.sh fit_rw 2d L512_N1000_T10000"
      exit 1
    fi

    DATA_DIR="data/${DIM_NAME}/random_walk/${CASE_DIR}"

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
    CASE_DIR=$3

    if [ -z "$CASE_DIR" ]; then
      echo "Usage:"
      echo "  bash scripts/run_analysis.sh fit_survival 2d L512_N1000_T10000"
      exit 1
    fi

    DATA_DIR="data/${DIM_NAME}/random_walk/${CASE_DIR}"

    echo "[Analysis] Fit survival probability"
    echo "[Data] ${DATA_DIR}"

    python scripts/analysis/fit_survival.py \
      --input "${DATA_DIR}/saw.csv" \
      --out-prefix "${DATA_DIR}/survival"
    ;;

  *)
    echo "Unknown analysis mode: $MODE"
    echo "Available:"
    echo "  fit_rw"
    echo "  fit_survival"
    exit 1
    ;;
esac