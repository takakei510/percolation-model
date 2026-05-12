import argparse
import glob
import os
import re
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from pathlib import Path


def extract_L(filename):
    match = re.search(r"L_(\d+)", filename)
    return int(match.group(1))


def load_config(path):
    cfg = {}
    with open(path) as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=")
                cfg[k.strip()] = v.strip()
    return cfg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, default="data")
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    # -------------------------
    # config読み込み
    # -------------------------
    if args.config:
        cfg = load_config(args.config)
        dim = int(cfg["dim"])
        p = float(cfg["p"])
    else:
        dim = 2
        p = None

    data_dir = Path(args.root) / f"{args.dim}d"/"size_sweep_clusters"
    output_dir = f"data/{dim}d/animations"
    os.makedirs(output_dir, exist_ok=True)

    files = sorted(
        glob.glob(f"{data_dir}/cluster_coords_L_*.csv"),
        key=extract_L
    )

    if dim == 2:
        fig, ax = plt.subplots(figsize=(6, 6))
    else:
        fig = plt.figure(figsize=(7, 7))
        ax = fig.add_subplot(111, projection="3d")

    def update(frame):
        ax.clear()

        csv_path = files[frame]
        L = extract_L(csv_path)
        df = pd.read_csv(csv_path)

        largest = df[df["cluster_rank"] == 1]
        second = df[df["cluster_rank"] == 2]

        if dim == 2:
            if not largest.empty:
                ax.scatter(largest["x"], largest["y"], s=4, color="blue", alpha=0.6)
            if not second.empty:
                ax.scatter(second["x"], second["y"], s=10, color="red", alpha=1.0)

            ax.set_xlim(0, L)
            ax.set_ylim(0, L)
            ax.set_aspect("equal")

        else:
            if not largest.empty:
                ax.scatter(largest["x"], largest["y"], largest["z"],
                           s=2, color="blue", alpha=0.4)
            if not second.empty:
                ax.scatter(second["x"], second["y"], second["z"],
                           s=8, color="red", alpha=1.0)

            ax.set_xlim(0, L)
            ax.set_ylim(0, L)
            ax.set_zlim(0, L)

        ax.set_title(f"p={p}, L={L}")

    ani = FuncAnimation(fig, update, frames=len(files), interval=800)

    if args.save:
        ani.save(f"{output_dir}/clusters.gif", writer="pillow", fps=1)

    if args.show or not args.save:
        plt.show()


if __name__ == "__main__":
    main()