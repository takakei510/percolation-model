import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def plot_one(csv_path, label):
    df = pd.read_csv(csv_path)

    print(f"Loaded: {csv_path}")
    print(df)

    plt.loglog(df["L"], df["time_sec"], marker="o", label=label)

    log_L = np.log(df["L"])
    log_T = np.log(df["time_sec"])

    slope, intercept = np.polyfit(log_L, log_T, 1)

    fit_T = np.exp(intercept) * df["L"] ** slope
    plt.loglog(
        df["L"],
        fit_T,
        linestyle="--",
        label=f"{label} slope={slope:.3f}"
    )

    return slope


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, default="data")
    parser.add_argument("--dim", type=int, choices=[2, 3], default=2)
    parser.add_argument("--method", type=str, default="bfs")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()

    plt.figure(figsize=(7, 5))

    if args.compare:
        methods = ["bfs", "union_find"]

        for method in methods:
            base_dir = Path(args.root) / f"{args.dim}d" / "time_vs_L"
            csv_path = base_dir / f"{method}.csv"
            
            if not csv_path.exists():
                print(f"File not found: {csv_path}")
                continue

            plot_one(csv_path, method)

        title = f"Computation time comparison ({args.dim}D)"

    else:
        base_dir = Path(args.root) / f"{args.dim}d" / "time_vs_L"
        csv_path = base_dir / f"{args.method}.csv"

        if not csv_path.exists():
            print(f"File not found: {csv_path}")
            return

        plot_one(csv_path, args.method)
        title = f"Scaling behavior ({args.dim}D, {args.method})"

    plt.xlabel("System size L")
    plt.ylabel("Computation time (sec)")
    plt.title(title)
    plt.grid(True, which="both")
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()