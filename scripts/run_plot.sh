#!/bin/bash

MODE=$1
CONFIG=$2

if [ -z "$MODE" ]; then
  echo "Usage:"
  echo "  bash scripts/run_plot.sh sweep"
  echo "  bash scripts/run_plot.sh sweep3d"
  echo "  bash scripts/run_plot.sh cluster [csv_file]"
  echo "  bash scripts/run_plot.sh anim configs/xxx.txt"
  echo "  bash scripts/run_plot.sh time"
  echo "  bash scripts/run_plot.sh time3d"
  echo "  bash scripts/run_plot.sh time_compare"
  echo "  bash scripts/run_plot.sh time3d_compare"
  echo "  bash scripts/run_plot.sh scaling"
  echo "  bash scripts/run_plot.sh dist"
  echo "  bash scripts/run_plot.sh dist3d"
  echo "  bash scripts/run_plot.sh mean"
  echo "  bash scripts/run_plot.sh mean3d"
  echo "  bash scripts/run_plot.sh random_walk 2d L---_N----_T----"
  echo "  bash scripts/run_plot.sh random_walk 3d L---_N----_T----"
  echo "  bash scripts/run_plot.sh fit_rw 2d L---_N----_T----"
  echo "  bash scripts/run_plot.sh final_step 2d L---_N----_T----"
  echo "  bash scripts/run_plot.sh final_step 3d L---_N----_T----"
  exit 1
fi

case "$MODE" in

  sweep)
    echo "[Plot] Sweep"
    python scripts/visualization/plot_sweep.py --dim 2
    ;;
  
  sweep3d)
    echo "[Plot] Sweep (3D)"
    python scripts/visualization/plot_sweep.py --dim 3
    ;;

  cluster)
    FILE=$2

    if [ -z "$FILE" ]; then
      FILE="data/cluster_coords.csv"
    fi

    echo "[Plot] Cluster visualization: $FILE"
    python scripts/visualization/plot_cluster.py --file "$FILE"
    ;;
  
  anim)
    if [ -z "$CONFIG" ]; then
      echo "Please provide config file."
      exit 1
    fi
    echo "[Plot] Animation"
    python scripts/visualization/animate_clusters_vs_L.py --config "$CONFIG" --save --show
    ;;

  time)
    METHOD=${2:-bfs}

    echo "[Plot] Time vs L ($METHOD)"
    python scripts/visualization/plot_time_vs_L.py \
      --dim 2 \
      --method "$METHOD"
    ;;

  time3d)
    METHOD=${2:-bfs}

    echo "[Plot] Time vs L 3D ($METHOD)"
    python scripts/visualization/plot_time_vs_L.py \
      --dim 3 \
      --method "$METHOD"
    ;;
    
  time_compare)
    ROOT=${2:-data}

    echo "[Plot] Time comparison BFS vs Union-Find root=$ROOT"
    python scripts/visualization/plot_time_vs_L.py \
      --dim 2 \
      --compare \
      --root "$ROOT"
    ;;

  time3d_compare)
    ROOT=${2:-data}

    echo "[Plot] Time comparison BFS vs Union-Find (3D) root=$ROOT"
    python scripts/visualization/plot_time_vs_L.py \
      --dim 3 \
      --compare \
      --root "$ROOT"
    ;;

  p_time)
    P_MODE=${2:-total}
    ROOT=${3:-data}

    echo "[Plot] p sweep time 2D mode=$P_MODE root=$ROOT"

    python scripts/visualization/plot_p_sweep_time.py \
      --dim 2 \
      --mode "$P_MODE" \
      --root "$ROOT"
    ;;

  p_time3d)
    P_MODE=${2:-total}
    ROOT=${3:-data}

    echo "[Plot] p sweep time 3D mode=$P_MODE root=$ROOT"

    python scripts/visualization/plot_p_sweep_time.py \
      --dim 3 \
      --mode "$P_MODE" \
      --root "$ROOT"
    ;;

  scaling)
    echo "[Plot] Cluster scaling"
    python scripts/visualization/plot_cluster_scaling.py
    ;;

  dist)
    echo "[Plot] Cluster size distribution"
    python scripts/visualization/plot_cluster_distribution.py --dim 2
    ;;

  dist3d)
    echo "[Plot] Cluster size distribution (3D)"
    python scripts/visualization/plot_cluster_distribution.py --dim 3
    ;;

  mean)
    echo "[Plot] Mean cluster size"
    python scripts/visualization/plot_mean_cluster_size.py --dim 2
    ;;

  mean3d)
    echo "[Plot] Mean cluster size (3D)"
    python scripts/visualization/plot_mean_cluster_size.py --dim 3
    ;;

  random_walk)
    DIM_NAME=${2:-2d}
    CASE_DIR=$3
    DIM=${DIM_NAME%d}

    if [ -z "$CASE_DIR" ]; then
      echo "Usage:"
      echo "  bash scripts/run_plot.sh random_walk 2d L512_N10000_T10000"
      echo "  bash scripts/run_plot.sh random_walk 3d L128_N5000_T1000"
      exit 1
    fi

    DATA_DIR="data/${DIM_NAME}/random_walk/${CASE_DIR}"

    echo "[Plot] Random walk dim=${DIM_NAME} case=${CASE_DIR}"
    echo "[Data] ${DATA_DIR}"

    python scripts/visualization/plot_random_walk.py \
      --rw ${DATA_DIR}/rw.csv \
      --saw ${DATA_DIR}/saw.csv \
      --rw-traj ${DATA_DIR}/rw_traj.csv \
      --saw-traj ${DATA_DIR}/saw_traj.csv \
      --dim "$DIM" \
      --out-prefix ${DATA_DIR}/compare_${DIM_NAME}
    ;;

  final_step)
    DIM_NAME=${2:-2d}
    CASE_DIR=$3

    if [ -z "$CASE_DIR" ]; then
      echo "Usage:"
      echo "  bash scripts/run_plot.sh final_step 2d L512_N1000_T10000"
      exit 1
    fi

    DATA_DIR="data/${DIM_NAME}/random_walk/${CASE_DIR}"

    echo "[Plot] Final step distribution"
    echo "[Data] ${DATA_DIR}"

    python scripts/visualization/plot_final_step.py \
      --input "${DATA_DIR}/final_steps.csv" \
      --out-prefix "${DATA_DIR}/final_step"
    ;;

  *)
    echo "Unknown mode: $MODE"
    echo "Usage:"
    echo "  sweep / sweep3d / cluster / anim / time / time3d / time_compare / time3d_compare / p_time / p_time3d / scaling / dist / dist3d / mean / mean3d / random_walk / final_step "
esac