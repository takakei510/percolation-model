#!/usr/bin/env python3

import argparse
import os
import re
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd


CASE_PATTERN = re.compile(r"^L(?P<L>\d+)_N(?P<N>\d+)_T(?P<T>\d+)(?:_(?P<suffix>.+))?$")
DEFAULT_FIT_STARTS = [1, 10, 30, 50, 75, 100, 150, 200]
DEFAULT_FIT_ENDS = [100, 150, 200, 250, 300, 400, 500, 600, 800]
MIN_ALIVE_THRESHOLD = 0.0


def parse_case_metadata(path):
    normalized = os.path.normpath(path)
    case = os.path.basename(os.path.dirname(normalized))
    match = CASE_PATTERN.match(case)
    if not match:
        raise ValueError(f"Could not parse L/N/T metadata from case directory: {case}")

    return {
        "case": case,
        "L": int(match.group("L")),
        "N": int(match.group("N")),
        "T": int(match.group("T")),
    }


def parse_fit_ranges(text):
    ranges = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"Invalid fit range format: {item}")
        start_text, end_text = item.split(":", 1)
        fit_start = int(start_text)
        fit_end = int(end_text)
        if fit_start >= fit_end:
            raise ValueError(f"fit_start must be smaller than fit_end: {item}")
        ranges.append((fit_start, fit_end))

    if not ranges:
        raise ValueError("No fit ranges were provided.")

    return ranges


def parse_fit_points(text):
    values = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        values.append(int(item))

    if not values:
        raise ValueError("No fit points were provided.")

    return sorted(set(values))


def build_fit_ranges(fit_ranges_text=None, fit_starts_text=None, fit_ends_text=None):
    if fit_ranges_text:
        return parse_fit_ranges(fit_ranges_text)

    if bool(fit_starts_text) != bool(fit_ends_text):
        raise ValueError("Both --fit-starts and --fit-ends are required when --fit-ranges is not used.")

    if fit_starts_text and fit_ends_text:
        fit_starts = parse_fit_points(fit_starts_text)
        fit_ends = parse_fit_points(fit_ends_text)
    else:
        fit_starts = DEFAULT_FIT_STARTS
        fit_ends = DEFAULT_FIT_ENDS

    ranges = [(fit_start, fit_end) for fit_start in fit_starts for fit_end in fit_ends if fit_start < fit_end]
    if not ranges:
        raise ValueError("No valid fit ranges could be generated.")
    return ranges


def read_input(input_path):
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)
    required_columns = ["step", "mean_r2", "n_alive"]
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"Input CSV is missing required columns: {', '.join(missing)}")

    if df.empty:
        raise ValueError(f"Input CSV contains no rows: {input_path}")

    df = df.copy()
    df["step"] = pd.to_numeric(df["step"], errors="coerce")
    df["mean_r2"] = pd.to_numeric(df["mean_r2"], errors="coerce")
    df["n_alive"] = pd.to_numeric(df["n_alive"], errors="coerce")
    if df[["step", "mean_r2", "n_alive"]].isna().any().any():
        raise ValueError(f"Input CSV contains invalid numeric values: {input_path}")

    return df


def _closest_value(frame, target_step, column):
    if frame.empty:
        return float("nan")
    index = (frame["step"] - target_step).abs().idxmin()
    return float(frame.loc[index, column])


def evaluate_range(df, fit_start, fit_end, metadata, walk_type, dimension):
    fit_df = df[
        (df["step"] >= fit_start)
        & (df["step"] <= fit_end)
        & (df["step"] > 0)
        & (df["mean_r2"] > 0)
    ].copy()

    fit_df = fit_df.sort_values("step").reset_index(drop=True)
    n_points = int(len(fit_df))

    if n_points > 0:
        n_alive_min = float(fit_df["n_alive"].min())
        mean_r2_start = _closest_value(fit_df, fit_start, "mean_r2")
        mean_r2_end = _closest_value(fit_df, fit_end, "mean_r2")
    else:
        n_alive_min = float("nan")
        mean_r2_start = float("nan")
        mean_r2_end = float("nan")

    if n_points < 3:
        warnings.warn(
            f"Skipping fit range {fit_start}:{fit_end} because it has only {n_points} valid points.",
            RuntimeWarning,
        )
        return {
            "walk_type": walk_type,
            "dimension": dimension,
            "L": metadata["L"],
            "n_trials": metadata["N"],
            "fit_start": fit_start,
            "fit_end": fit_end,
            "alpha": float("nan"),
            "intercept": float("nan"),
            "r2_score": float("nan"),
            "n_points": n_points,
            "n_alive_min": n_alive_min,
            "mean_r2_start": mean_r2_start,
            "mean_r2_end": mean_r2_end,
        }

    x = np.log(fit_df["step"].to_numpy(dtype=float))
    y = np.log(fit_df["mean_r2"].to_numpy(dtype=float))
    alpha, intercept = np.polyfit(x, y, 1)
    y_pred = alpha * x + intercept

    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2_score = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")

    return {
        "walk_type": walk_type,
        "dimension": dimension,
        "L": metadata["L"],
        "n_trials": metadata["N"],
        "fit_start": fit_start,
        "fit_end": fit_end,
        "alpha": float(alpha),
        "intercept": float(intercept),
        "r2_score": r2_score,
        "n_points": n_points,
        "n_alive_min": n_alive_min,
        "mean_r2_start": mean_r2_start,
        "mean_r2_end": mean_r2_end,
    }


def _line_plot(ax, frame, x_key, y_key, series_key, title, xlabel):
    for series_value, group in frame.groupby(series_key):
        group = group.sort_values(x_key)
        ax.plot(group[x_key], group[y_key], marker="o", linestyle="-", label=f"{series_key}={series_value}")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("alpha")
    ax.grid(True, which="both")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(fontsize=8)


def _heatmap(ax, matrix, x_values, y_values, title, cbar_label, cmap="viridis"):
    masked = np.ma.masked_invalid(matrix)
    cmap_obj = plt.get_cmap(cmap).copy()
    cmap_obj.set_bad(color="lightgray")
    im = ax.pcolormesh(x_values, y_values, masked, shading="auto", cmap=cmap_obj)
    ax.set_title(title)
    ax.set_xlabel("fit_end")
    ax.set_ylabel("fit_start")
    ax.grid(False)
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label(cbar_label)
    return im


def build_plots(summary_df, plot_prefix):
    plot_df = summary_df.copy()
    threshold_df = plot_df.copy()
    threshold_df.loc[threshold_df["n_alive_min"] < MIN_ALIVE_THRESHOLD, "alpha"] = np.nan
    threshold_valid = threshold_df[threshold_df["alpha"].notna()].copy()

    fig, ax = plt.subplots(figsize=(8, 5))
    if not threshold_valid.empty:
        _line_plot(
            ax,
            threshold_valid,
            "fit_end",
            "alpha",
            "fit_start",
            "alpha vs fit_end",
            "fit_end",
        )
    else:
        ax.set_title("alpha vs fit_end")
        ax.set_xlabel("fit_end")
        ax.set_ylabel("alpha")
        ax.text(0.5, 0.5, "No valid fits", transform=ax.transAxes, ha="center", va="center")
    fig.tight_layout()
    out_path = f"{plot_prefix}_alpha_vs_fit_end.png"
    fig.savefig(out_path, dpi=300)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    if not threshold_valid.empty:
        _line_plot(
            ax,
            threshold_valid,
            "fit_start",
            "alpha",
            "fit_end",
            "alpha vs fit_start",
            "fit_start",
        )
    else:
        ax.set_title("alpha vs fit_start")
        ax.set_xlabel("fit_start")
        ax.set_ylabel("alpha")
        ax.text(0.5, 0.5, "No valid fits", transform=ax.transAxes, ha="center", va="center")
    fig.tight_layout()
    out_path = f"{plot_prefix}_alpha_vs_fit_start.png"
    fig.savefig(out_path, dpi=300)
    plt.close(fig)

    unique_starts = np.array(sorted(plot_df["fit_start"].unique()))
    unique_ends = np.array(sorted(plot_df["fit_end"].unique()))

    alpha_matrix = np.full((len(unique_starts), len(unique_ends)), np.nan)
    n_alive_matrix = np.full((len(unique_starts), len(unique_ends)), np.nan)

    start_index = {value: idx for idx, value in enumerate(unique_starts)}
    end_index = {value: idx for idx, value in enumerate(unique_ends)}

    for _, row in plot_df.iterrows():
        i = start_index[row["fit_start"]]
        j = end_index[row["fit_end"]]
        if row["fit_start"] < row["fit_end"]:
            alpha_matrix[i, j] = row["alpha"]
            n_alive_matrix[i, j] = row["n_alive_min"]

    alpha_matrix = np.where(n_alive_matrix < MIN_ALIVE_THRESHOLD, np.nan, alpha_matrix)
    n_alive_matrix = np.where(n_alive_matrix < MIN_ALIVE_THRESHOLD, np.nan, n_alive_matrix)

    fig, ax = plt.subplots(figsize=(9, 6))
    _heatmap(
        ax,
        alpha_matrix,
        unique_ends,
        unique_starts,
        "alpha heatmap over fit range",
        "alpha",
        cmap="viridis",
    )
    fig.tight_layout()
    out_path = f"{plot_prefix}_alpha_heatmap_fit_range.png"
    fig.savefig(out_path, dpi=300)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 6))
    _heatmap(
        ax,
        n_alive_matrix,
        unique_ends,
        unique_starts,
        "n_alive_min heatmap over fit range",
        "n_alive_min",
        cmap="magma",
    )
    fig.tight_layout()
    out_path = f"{plot_prefix}_n_alive_min_heatmap_fit_range.png"
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--fit-ranges")
    parser.add_argument("--fit-starts")
    parser.add_argument("--fit-ends")
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--plot-prefix", required=True)
    parser.add_argument("--walk-type", required=True)
    parser.add_argument("--dimension", required=True)
    parser.add_argument("--L", type=int, required=True)
    parser.add_argument("--n-trials", type=int, required=True)
    parser.add_argument("--min-alive-threshold", type=float, default=0.0)
    args = parser.parse_args()

    metadata = parse_case_metadata(args.input)
    if metadata["L"] != args.L:
        warnings.warn(
            f"L from input path ({metadata['L']}) does not match --L ({args.L}). Using --L in output.",
            RuntimeWarning,
        )
    if metadata["N"] != args.n_trials:
        warnings.warn(
            f"N from input path ({metadata['N']}) does not match --n-trials ({args.n_trials}). Using --n-trials in output.",
            RuntimeWarning,
        )

    df = read_input(args.input)
    fit_ranges = build_fit_ranges(args.fit_ranges, args.fit_starts, args.fit_ends)

    global MIN_ALIVE_THRESHOLD
    MIN_ALIVE_THRESHOLD = float(args.min_alive_threshold)

    rows = []
    for fit_start, fit_end in fit_ranges:
        rows.append(
            evaluate_range(
                df,
                fit_start,
                fit_end,
                {"L": args.L, "N": args.n_trials},
                args.walk_type,
                args.dimension,
            )
        )

    summary_df = pd.DataFrame(rows)
    summary_df = summary_df[
        [
            "walk_type",
            "dimension",
            "L",
            "n_trials",
            "fit_start",
            "fit_end",
            "alpha",
            "intercept",
            "r2_score",
            "n_points",
            "n_alive_min",
            "mean_r2_start",
            "mean_r2_end",
        ]
    ]
    summary_df.to_csv(args.output_csv, index=False)
    print(f"Saved: {args.output_csv}")

    build_plots(summary_df, args.plot_prefix)
    print(f"Saved: {args.plot_prefix}_alpha_vs_fit_end.png")
    print(f"Saved: {args.plot_prefix}_alpha_vs_fit_start.png")
    print(f"Saved: {args.plot_prefix}_alpha_heatmap_fit_range.png")
    print(f"Saved: {args.plot_prefix}_n_alive_min_heatmap_fit_range.png")


if __name__ == "__main__":
    main()