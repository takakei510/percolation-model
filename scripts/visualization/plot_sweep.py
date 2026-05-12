import argparse
import re
from pathlib import Path

import matplotlib
matplotlib.use("TkAgg")

import pandas as pd
import matplotlib.pyplot as plt


def extract_L(path):
    match = re.search(r"L_(\d+)", str(path))
    if match is None:
        raise ValueError(f"L value not found in filename: {path}")
    return int(match.group(1))


def load_sweep_files(dim, L=None):
    sweep_dir = Path(f"data/{dim}d/sweep")

    if L is None:
        files = sorted(
            sweep_dir.glob("summary_L_*.csv"),
            key=extract_L
        )
    else:
        files = [sweep_dir / f"summary_L_{L}.csv"]

    files = [f for f in files if f.exists()]

    if not files:
        print(f"No summary files found in {sweep_dir}")
        return []

    return files


def prepare_dataframe(csv_path):
    df = pd.read_csv(csv_path)
    df = df.sort_values("p")

    required_columns = {
        "p",
        "n_sites",
        "mean_largest",
        "mean_second",
        "std_largest",
        "std_second",
    }

    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in {csv_path}: {sorted(missing)}")

    df["largest_ratio"] = df["mean_largest"] / df["n_sites"]
    df["second_ratio"] = df["mean_second"] / df["n_sites"]
    df["std_largest_ratio"] = df["std_largest"] / df["n_sites"]
    df["std_second_ratio"] = df["std_second"] / df["n_sites"]

    return df


def plot_second_cluster(files, dim):
    plt.figure(figsize=(8, 5))

    for csv_path in files:
        L = extract_L(csv_path)
        df = prepare_dataframe(csv_path)

        plt.errorbar(
            df["p"],
            df["second_ratio"],
            yerr=df["std_second_ratio"],
            fmt="o-",
            markersize=4,
            capsize=3,
            linewidth=1.5,
            label=f"L={L}"
        )

        peak_idx = df["second_ratio"].idxmax()
        peak_p = df.loc[peak_idx, "p"]
        print(f"[{dim}D] L={L}: peak p ≈ {peak_p:.6f}")

    plt.xlabel("p")
    plt.ylabel("second / n_sites")
    plt.title(f"Second cluster vs p ({dim}D)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


def plot_largest_and_second(files, dim):
    fig, ax1 = plt.subplots(figsize=(8, 5))

    for csv_path in files:
        L = extract_L(csv_path)
        df = prepare_dataframe(csv_path)

        ax1.errorbar(
            df["p"],
            df["largest_ratio"],
            yerr=df["std_largest_ratio"],
            fmt="o-",
            color="tab:blue",
            alpha=0.75,
            markersize=4,
            capsize=3,
            linewidth=1.5,
            label=f"Largest L={L}"
        )

    ax1.set_xlabel("p")
    ax1.set_ylabel("largest / n_sites", color="tab:blue")
    ax1.tick_params(axis="y", labelcolor="tab:blue")
    ax1.grid(True)

    ax2 = ax1.twinx()

    for csv_path in files:
        L = extract_L(csv_path)
        df = prepare_dataframe(csv_path)

        ax2.errorbar(
            df["p"],
            df["second_ratio"],
            yerr=df["std_second_ratio"],
            fmt="s--",
            color="tab:orange",
            alpha=0.9,
            markersize=4,
            capsize=3,
            linewidth=1.5,
            label=f"Second L={L}"
        )

    ax2.set_ylabel("second / n_sites", color="tab:orange")
    ax2.tick_params(axis="y", labelcolor="tab:orange")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=8)

    plt.title(f"Normalized cluster sizes vs p ({dim}D)")
    plt.tight_layout()
    plt.show()

def plot_zoom(files, dim, zoom_width):
    for csv_path in files:
        L = extract_L(csv_path)
        df = prepare_dataframe(csv_path)

        peak_idx = df["second_ratio"].idxmax()
        peak_p = df.loc[peak_idx, "p"]

        df_zoom = df[
            (df["p"] >= peak_p - zoom_width) &
            (df["p"] <= peak_p + zoom_width)
        ]

        if len(df_zoom) < 8:
            print(
                f"[zoom skipped] {dim}D L={L}: only {len(df_zoom)} points "
                f"around p={peak_p:.6f}. Use smaller dp."
            )
            continue

        plt.figure(figsize=(8, 5))

        plt.plot(
            df_zoom["p"],
            df_zoom["second_ratio"],
            color="tab:red",
            linewidth=2,
            marker="o",
            markersize=4,
            label=f"Second cluster L={L}, peak p={peak_p:.6f}"
        )

        lower = df_zoom["second_ratio"] - df_zoom["std_second_ratio"]
        upper = df_zoom["second_ratio"] + df_zoom["std_second_ratio"]

        plt.fill_between(
            df_zoom["p"],
            lower,
            upper,
            color="tab:red",
            alpha=0.2,
            label="±1 std"
        )

        plt.xlabel("p")
        plt.ylabel("second / n_sites")
        plt.title(f"Critical region zoom ({dim}D, L={L})")
        plt.grid(True)
        plt.legend()

        ymax = upper.max()
        plt.ylim(bottom=0, top=ymax * 1.1)

        plt.tight_layout()
        plt.show()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, default="data")
    parser.add_argument("--dim", type=int, choices=[2, 3], default=2)
    parser.add_argument("--L", type=int, default=None)
    parser.add_argument("--zoom-width", type=float, default=0.015)
    args = parser.parse_args()

    data_dir = Path(args.root) / f"{args.dim}d" / "sweep"
    files = sorted(data_dir.glob("summary_L_*.csv"), key=extract_L)
    
    if not files:
        return

    print("Loaded files:")
    for f in files:
        print(f"  {f}")

    plot_second_cluster(files, args.dim)
    plot_largest_and_second(files, args.dim)
    plot_zoom(files, args.dim, args.zoom_width)


if __name__ == "__main__":
    main()