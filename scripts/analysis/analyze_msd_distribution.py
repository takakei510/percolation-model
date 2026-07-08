import argparse
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REQUIRED_COLUMNS = ["trial", "step", "r2", "alive", "trapped", "boundary_dead", "contact_dead"]


def read_input(input_path):
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Input CSV is missing required columns: {', '.join(missing)}")

    if df.empty:
        raise ValueError(f"Input CSV contains no rows: {input_path}")

    df = df.copy()
    df["trial"] = pd.to_numeric(df["trial"], errors="coerce")
    df["step"] = pd.to_numeric(df["step"], errors="coerce")
    df["r2"] = pd.to_numeric(df["r2"], errors="coerce")
    if df[["trial", "step", "r2"]].isna().any().any():
        raise ValueError(f"Input CSV contains invalid numeric values: {input_path}")

    return df


def summarize_by_step(df):
    rows = []
    for step, group in df.sort_values(["step", "trial"]).groupby("step", sort=True):
        r2 = group["r2"].astype(float)
        rows.append({
            "step": int(step),
            "count": int(len(group)),
            "mean_r2": float(r2.mean()),
            "std_r2": float(r2.std(ddof=0)),
            "median_r2": float(r2.median()),
            "q90_r2": float(r2.quantile(0.90)),
            "q99_r2": float(r2.quantile(0.99)),
            "max_r2": float(r2.max()),
        })

    if not rows:
        raise ValueError("No step groups were found in the input data")

    return pd.DataFrame(rows).sort_values("step").reset_index(drop=True)


def select_step_bin(df, target_step, bin_width):
    if bin_width <= 0:
        return df[df["step"] == target_step]

    half_width = bin_width / 2.0
    bin_start = int(np.ceil(target_step - half_width))
    bin_end = int(np.floor(target_step + half_width))
    return df[(df["step"] >= bin_start) & (df["step"] <= bin_end)]


def summarize_binned_step(df, target_step, bin_width):
    selected = select_step_bin(df, target_step, bin_width)
    if selected.empty:
        return None

    r2 = selected["r2"].astype(float)
    if bin_width <= 0:
        bin_start = int(target_step)
        bin_end = int(target_step)
    else:
        half_width = bin_width / 2.0
        bin_start = int(np.ceil(target_step - half_width))
        bin_end = int(np.floor(target_step + half_width))

    return {
        "step": int(target_step),
        "bin_start": bin_start,
        "bin_end": bin_end,
        "bin_width": int(bin_width),
        "count": int(len(selected)),
        "mean_r2": float(r2.mean()),
        "std_r2": float(r2.std(ddof=0)),
        "median_r2": float(r2.median()),
        "q90_r2": float(r2.quantile(0.90)),
        "q99_r2": float(r2.quantile(0.99)),
        "max_r2": float(r2.max()),
    }


def summarize_with_binning(df, bin_width):
    rows = []
    for step in sorted(df["step"].dropna().astype(int).unique()):
        row = summarize_binned_step(df, step, bin_width)
        if row is not None:
            rows.append(row)

    if not rows:
        raise ValueError("No step groups were found in the input data")

    columns = [
        "step",
        "bin_start",
        "bin_end",
        "bin_width",
        "count",
        "mean_r2",
        "std_r2",
        "median_r2",
        "q90_r2",
        "q99_r2",
        "max_r2",
    ]
    return pd.DataFrame(rows)[columns]


def save_summary_csv(summary_df, output_csv):
    summary_df.to_csv(output_csv, index=False)
    return output_csv


def _subplot_grid(n_items):
    n_cols = 2
    n_rows = int(math.ceil(n_items / n_cols))
    return n_rows, n_cols


def _bin_label(bin_width):
    if bin_width <= 0:
        return ""
    return f" (binned, width={bin_width})"


def plot_histograms(df, plot_prefix, bin_width, logy=False):
    steps = sorted(df["step"].unique())
    n_rows, n_cols = _subplot_grid(len(steps))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(12, 4 * n_rows), squeeze=False)
    label_suffix = _bin_label(bin_width)

    for index, step in enumerate(steps):
        row = index // n_cols
        col = index % n_cols
        ax = axes[row][col]
        values = select_step_bin(df, step, bin_width)["r2"].astype(float).values
        ax.hist(values, bins=30, edgecolor="black")
        if logy:
            ax.set_yscale("log")
        ax.set_title(f"step={int(step)}{label_suffix}")
        ax.set_xlabel(r"$r^2$")
        ax.set_ylabel("count")
        ax.grid(True, which="both")

    for index in range(len(steps), n_rows * n_cols):
        row = index // n_cols
        col = index % n_cols
        fig.delaxes(axes[row][col])

    fig.tight_layout()
    suffix = "r2_hist_logy_by_step" if logy else "r2_hist_by_step"
    out_path = f"{plot_prefix}_{suffix}.png"
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def plot_boxplot(df, plot_prefix, bin_width):
    steps = sorted(df["step"].unique())
    data = [select_step_bin(df, step, bin_width)["r2"].astype(float).values for step in steps]
    label_suffix = _bin_label(bin_width)

    fig, ax = plt.subplots(figsize=(max(8, 1.2 * len(steps)), 5))
    ax.boxplot(data, tick_labels=[str(int(step)) for step in steps], showfliers=True)
    ax.set_xlabel(f"step{label_suffix}")
    ax.set_ylabel(r"$r^2$")
    ax.set_title(rf"$r^2$ boxplot by step{label_suffix}")
    ax.grid(True, which="both", axis="y")
    fig.tight_layout()

    suffix = "r2_boxplot_by_step"
    out_path = f"{plot_prefix}_{suffix}.png"
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def plot_moment_curves(summary_df, plot_prefix, bin_width):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(summary_df["step"], summary_df["mean_r2"], marker="o", label="mean_r2")
    ax.plot(summary_df["step"], summary_df["median_r2"], marker="o", label="median_r2")
    ax.plot(summary_df["step"], summary_df["q90_r2"], marker="o", label="q90_r2")
    ax.plot(summary_df["step"], summary_df["q99_r2"], marker="o", label="q99_r2")
    ax.plot(summary_df["step"], summary_df["max_r2"], marker="o", label="max_r2")
    ax.set_xlabel("step")
    ax.set_ylabel(r"$r^2$")
    title_suffix = _bin_label(bin_width)
    ax.set_title(rf"$r^2$ summary statistics by step{title_suffix}")
    ax.grid(True, which="both")
    ax.legend()
    fig.tight_layout()

    suffix = "r2_moments_by_step"
    out_path = f"{plot_prefix}_{suffix}.png"
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--plot-prefix", required=True)
    parser.add_argument("--bin-width", type=int, default=0)
    args = parser.parse_args()

    df = read_input(args.input)
    if args.bin_width > 0:
        summary_df = summarize_with_binning(df, args.bin_width)
    else:
        summary_df = summarize_by_step(df)

    summary_csv = save_summary_csv(summary_df, args.output_csv)
    hist_png = plot_histograms(df, args.plot_prefix, args.bin_width, logy=False)
    hist_log_png = plot_histograms(df, args.plot_prefix, args.bin_width, logy=True)
    boxplot_png = plot_boxplot(df, args.plot_prefix, args.bin_width)
    moments_png = plot_moment_curves(summary_df, args.plot_prefix, args.bin_width)

    print(f"Saved: {summary_csv}")
    print(f"Saved: {hist_png}")
    print(f"Saved: {hist_log_png}")
    print(f"Saved: {boxplot_png}")
    print(f"Saved: {moments_png}")


if __name__ == "__main__":
    main()