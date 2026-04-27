#!/bin/bash

MODE=$1
CONFIG=$2

if [ -z "$MODE" ]; then
  echo "Usage:"
  echo "  bash scripts/run_plot.sh basic"
  echo "  bash scripts/run_plot.sh time"
  echo "  bash scripts/run_plot.sh scaling"
  echo "  bash scripts/run_plot.sh anim configs/xxx.txt"
  echo "  bash scripts/run_plot.sh dist"
  echo "  bash scripts/run_plot.sh mean"
  exit 1
fi

case "$MODE" in

  basic)
    echo "[Plot] Basic plot"
    python scripts/plot.py
    ;;

  time)
    echo "[Plot] Time vs L"
    python scripts/plot_time_vs_L.py --dim 2
    ;;

  time3d)
    echo "[Plot] Time vs L (3D)"
    python scripts/plot_time_vs_L.py --dim 3
    ;;

  scaling)
    echo "[Plot] Cluster scaling"
    python scripts/plot_cluster_scaling.py
    ;;

  anim)
    if [ -z "$CONFIG" ]; then
      echo "Please provide config file."
      exit 1
    fi
    echo "[Plot] Animation"
    python scripts/animate_clusters_vs_L.py --config "$CONFIG" --save --show
    ;;

  dist)
    echo "[Plot] Cluster size distribution"
    python scripts/plot_cluster_distribution.py --dim 2
    ;;

  dist3d)
    echo "[Plot] Cluster size distribution (3D)"
    python scripts/plot_cluster_distribution.py --dim 3
    ;;

  mean)
    echo "[Plot] Mean cluster size"
    python scripts/plot_mean_cluster_size.py --dim 2
    ;;

  mean3d)
    echo "[Plot] Mean cluster size (3D)"
    python scripts/plot_mean_cluster_size.py --dim 3
    ;;

  *)
    echo "Unknown mode: $MODE"
    echo "Usage:"
    echo "  basic / time / time3d / scaling / anim"
    ;;
esac