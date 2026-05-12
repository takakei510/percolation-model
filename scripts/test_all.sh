#!/bin/bash

ROOT=${1:-data}

echo "===== TEST START root=$ROOT ====="

echo "[1] sweep plot (2D)"
bash scripts/run_plot.sh sweep "$ROOT"

echo "[2] sweep plot (3D)"
bash scripts/run_plot.sh sweep3d "$ROOT"

echo "[3] distribution (2D)"
bash scripts/run_plot.sh dist "$ROOT"

echo "[4] distribution (3D)"
bash scripts/run_plot.sh dist3d "$ROOT"

echo "[5] mean cluster size (2D)"
bash scripts/run_plot.sh mean "$ROOT"

echo "[6] mean cluster size (3D)"
bash scripts/run_plot.sh mean3d "$ROOT"

echo "[7] time (2D BFS)"
bash scripts/run_plot.sh time bfs "$ROOT"

echo "[8] time (3D BFS)"
bash scripts/run_plot.sh time3d bfs "$ROOT"

echo "[9] time compare (2D)"
bash scripts/run_plot.sh time_compare "$ROOT"

echo "[10] time compare (3D)"
bash scripts/run_plot.sh time3d_compare "$ROOT"

echo "[11] p sweep total (2D)"
bash scripts/run_plot.sh p_time total "$ROOT"

echo "[12] p sweep step (2D)"
bash scripts/run_plot.sh p_time step "$ROOT"

echo "[13] p sweep total (3D)"
bash scripts/run_plot.sh p_time3d total "$ROOT"

echo "[14] p sweep step (3D)"
bash scripts/run_plot.sh p_time3d step "$ROOT"

echo "[15] scaling"
bash scripts/run_plot.sh scaling "$ROOT"

echo "===== TEST END ====="