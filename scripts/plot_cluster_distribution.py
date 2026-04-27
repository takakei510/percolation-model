import argparse
import glob
import re

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def extract_L(filename):
    match = re.search(r"L_(\d+)", filename)
    if match is None:
        raise ValueError(f"L value not found in filename: {filename}")
    return int(match.group(1))


def estimate_tau(s_values, n_values, fit_min=None, fit_max=None):
    s_values = np.asarray(s_values)
    n_values = np.asarray(n_values)

    mask = n_values > 0

    if fit_min is not None:
        mask &= s_values >= fit_min
    if fit_max is not None:
        mask &= s_values <= fit_max

    s_fit = s_values[mask]
    n_fit = n_values[mask]

    if len(s_fit) < 2:
        return None, None, None

    log_s = np.log(s_fit)
    log_n = np.log(n_fit)

    slope, intercept = np.polyfit(log_s, log_n, 1)
    tau = -slope

    fit_n = np.exp(intercept) * s_fit ** slope

    return tau, s_fit, fit_n


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dim", type=int, choices=[2, 3], default=2)
    parser.add_argument("--L", type=int, default=None)
    parser.add_argument("--fit-min", type=float, default=None)
    parser.add_argument("--fit-max", type=float, default=None)
    args = parser.parse_args()

    data_dir = f"data/{args.dim}d/size_sweep_cluster_sizes"

    if args.L is None:
        files = sorted(
            glob.glob(f"{data_dir}/cluster_sizes_L_*.csv"),
            key=extract_L
        )
    else:
        files = [f"{data_dir}/cluster_sizes_L_{args.L}.csv"]

    if not files:
        raise FileNotFoundError(f"No cluster size files found in {data_dir}")

    plt.figure(figsize=(7, 5))

    for file in files:
        L = extract_L(file)
        df = pd.read_csv(file)

        sizes = df["size"]
        count = sizes.value_counts().sort_index()

        s = count.index.to_numpy()
        n_s = count.values

        plt.loglog(
            s,
            n_s,
            marker="o",
            linestyle="none",
            label=f"L={L}"
        )

        tau, s_fit, fit_n = estimate_tau(
            s,
            n_s,
            fit_min=args.fit_min,
            fit_max=args.fit_max
        )

        if tau is not None:
            print(f"L={L}: tau ≈ {tau:.3f}")

            if args.L is not None:
                plt.loglog(
                    s_fit,
                    fit_n,
                    linestyle="--",
                    label=f"fit: tau={tau:.3f}"
                )

    plt.xlabel("Cluster size s")
    plt.ylabel("Number of clusters n_s")
    plt.title(f"Cluster size distribution ({args.dim}D)")
    plt.grid(True, which="both")
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()