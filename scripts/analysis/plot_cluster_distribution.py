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


def log_bin_sizes(sizes, n_bins=25):
    sizes = np.asarray(sizes)
    sizes = sizes[sizes > 0]

    # 最大クラスタを除外
    if len(sizes) > 1:
        sizes = np.sort(sizes)[::-1][1:]

    if len(sizes) == 0:
        return np.array([]), np.array([])

    s_min = sizes.min()
    s_max = sizes.max()

    if s_min == s_max:
        return np.array([s_min]), np.array([len(sizes)])

    bin_edges = np.logspace(
        np.log10(s_min),
        np.log10(s_max),
        n_bins + 1
    )

    counts, edges = np.histogram(sizes, bins=bin_edges)

    centers = np.sqrt(edges[:-1] * edges[1:])
    widths = np.diff(edges)

    density = counts / widths

    mask = density > 0

    return centers[mask], density[mask]

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
    parser.add_argument("--bins", type=int, default=25)
    parser.add_argument(
        "--mode",
        choices=["raw", "bin", "compare"],
        default="bin",
        help="raw: raw log-log, bin: log-binned, compare: raw + log-binned"
    )

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

        sizes = df["size"].to_numpy()

        # raw log-log plot
        if args.mode in ["raw", "compare"]:
            count = pd.Series(sizes).value_counts().sort_index()
            s_raw = count.index.to_numpy()
            n_raw = count.values

            raw_alpha = 0.65 if args.mode == "raw" else 0.25
            raw_size = 4 if args.mode == "raw" else 3

            plt.loglog(
                s_raw,
                n_raw,
                marker="o",
                linestyle="none",
                markersize=raw_size,
                alpha=raw_alpha,
                label=f"L={L} raw"
            )

        # log-binned plot + tau estimation
        if args.mode in ["bin", "compare"]:
            s_bin, n_bin = log_bin_sizes(sizes, n_bins=args.bins)

            plt.loglog(
                s_bin,
                n_bin,
                marker="o",
                linestyle="none",
                label=f"L={L} log-bin"
            )

            tau, s_fit, fit_n = estimate_tau(
                s_bin,
                n_bin,
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

    if args.fit_min is not None and args.fit_max is not None:
        plt.axvspan(
            args.fit_min,
            args.fit_max,
            alpha=0.12,
            label="fit range"
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