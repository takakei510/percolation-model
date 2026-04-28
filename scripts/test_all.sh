#!/bin/bash

echo "===== TEST START ====="

echo "[1] sweep plot (2D)"
bash scripts/run_plot.sh sweep

echo "[2] sweep plot (3D)"
bash scripts/run_plot.sh sweep3d

echo "[3] cluster (default)"
bash scripts/run_plot.sh cluster

echo "[4] distribution (2D)"
bash scripts/run_plot.sh dist

echo "[5] distribution (3D)"
bash scripts/run_plot.sh dist3d

echo "[6] mean cluster size (2D)"
bash scripts/run_plot.sh mean

echo "[7] mean cluster size (3D)"
bash scripts/run_plot.sh mean3d

echo "[8] time (2D)"
bash scripts/run_plot.sh time

echo "[9] time (3D)"
bash scripts/run_plot.sh time3d

echo "[10] scaling"
bash scripts/run_plot.sh scaling

echo "===== TEST END ====="