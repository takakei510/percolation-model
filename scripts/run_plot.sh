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
  echo "  bash scripts/run_plot.sh scaling"
  echo "  bash scripts/run_plot.sh dist"
  echo "  bash scripts/run_plot.sh dist3d"
  echo "  bash scripts/run_plot.sh mean"
  echo "  bash scripts/run_plot.sh mean3d"
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
    echo "[Plot] Time vs L"
    python scripts/analysis/plot_time_vs_L.py --dim 2
    ;;

  time3d)
    echo "[Plot] Time vs L (3D)"
    python scripts/analysis/plot_time_vs_L.py --dim 3
    ;;

  scaling)
    echo "[Plot] Cluster scaling"
    python scripts/analysis/plot_cluster_scaling.py
    ;;

  dist)
    echo "[Plot] Cluster size distribution"
    python scripts/analysis/plot_cluster_distribution.py --dim 2
    ;;

  dist3d)
    echo "[Plot] Cluster size distribution (3D)"
    python scripts/analysis/plot_cluster_distribution.py --dim 3
    ;;

  mean)
    echo "[Plot] Mean cluster size"
    python scripts/analysis/plot_mean_cluster_size.py --dim 2
    ;;

  mean3d)
    echo "[Plot] Mean cluster size (3D)"
    python scripts/analysis/plot_mean_cluster_size.py --dim 3
    ;;

  *)
    echo "Unknown mode: $MODE"
    echo "Usage:"
    echo "  sweep / sweep3d / cluster / anim / time / time3d / scaling / dist / dist3d / mean / mean3d"    ;;
esac