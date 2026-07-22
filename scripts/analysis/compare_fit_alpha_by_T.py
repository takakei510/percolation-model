#!/usr/bin/env python3

import argparse
import os
import re
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator
import numpy as np
import pandas as pd

from msd_reliability_common import attach_reliability_metrics, find_reliability_summary_path, load_reliability_summary


PATH_PATTERN = re.compile(
    r"^(?P<prefix>.*?)/(?P<dim>2d|3d)/random_walk/(?P<model>[^/]+)/(?P<case>[^/]+)/(?P<file>[^/]+\.csv)$"
)
LEGACY_PATH_PATTERN = re.compile(
    r"^(?P<prefix>.*?)/(?P<dim>2d|3d)/random_walk/(?P<case>[^/]+)/(?P<file>[^/]+\.csv)$"
)
CASE_PATTERN = re.compile(r"^(?:L(?P<L>\d+)_)?N(?P<N>\d+)_T(?P<T>\d+)(?:_(?P<suffix>.+))?$")
VALUE_COLUMNS = ["mean_r2", "msd", "r2_mean", "mean_squared_displacement"]


def parse_metadata_from_path(path, walk_type=None):
    normalized = os.path.normpath(path)
    match = PATH_PATTERN.search(normalized)
    if match:
        dim_name = match.group("dim")
        case = match.group("case")
    else:
        legacy_match = LEGACY_PATH_PATTERN.search(normalized)
        if not legacy_match:
            raise ValueError(
                "Input path must match data/<dim>/random_walk/<model>/<case>/<file>.csv: "
                f"{path}"
            )
        dim_name = legacy_match.group("dim")
        case = legacy_match.group("case")

    case_match = CASE_PATTERN.match(case)
    if not case_match:
        raise ValueError(f"Could not parse L/N/T metadata from case directory: {case}")

    return {
        "dim_name": dim_name,
        "dim": int(dim_name[0]),
        "walk_type": walk_type,
        "case": case,
        "L": int(case_match.group("L")) if case_match.group("L") is not None else None,
        "N": int(case_match.group("N")),
        "T": int(case_match.group("T")),
    }


def detect_value_column(df):
    for column in VALUE_COLUMNS:
        if column in df.columns:
            series = pd.to_numeric(df[column], errors="coerce")
            if not series.isna().all():
                return column
    raise ValueError(
        "Input CSV is missing a usable MSD column. Expected one of: "
        + ", ".join(VALUE_COLUMNS)
    )


def _reliability_metrics(fit_df, reliability_summary):
    defaults = {
        "fit_n_alive_min": float("nan"),
        "fit_n_alive_median": float("nan"),
        "fit_max_relative_standard_error": float("nan"),
        "fit_all_points_eligible": 0,
        "fit_reliability_point_count": 0,
        "fit_reliability_complete": 0,
    }

    if reliability_summary is None or fit_df.empty:
        return defaults

    merged = attach_reliability_metrics(fit_df[["step"]].copy(), reliability_summary)
    return {
        "fit_n_alive_min": float(merged["fit_n_alive_min"].iloc[0]),
        "fit_n_alive_median": float(merged["fit_n_alive_median"].iloc[0]),
        "fit_max_relative_standard_error": float(merged["fit_max_relative_standard_error"].iloc[0]),
        "fit_all_points_eligible": int(merged["fit_all_points_eligible"].iloc[0]),
        "fit_reliability_point_count": int(merged["fit_reliability_point_count"].iloc[0]),
        "fit_reliability_complete": int(merged["fit_reliability_complete"].iloc[0]),
    }


def read_input(input_path):
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)
    if df.empty:
        raise ValueError(f"Input CSV contains no rows: {input_path}")

    if "step" not in df.columns:
        raise ValueError(f"Input CSV {input_path} is missing required column: step")

    value_column = detect_value_column(df)
    metadata = parse_metadata_from_path(input_path)

    columns = ["step", value_column]
    if "n_alive" in df.columns:
        columns.append("n_alive")

    fit_df = df[columns].copy()
    fit_df["step"] = pd.to_numeric(fit_df["step"], errors="coerce")
    fit_df["value"] = pd.to_numeric(fit_df[value_column], errors="coerce")
    if "n_alive" in fit_df.columns:
        fit_df["n_alive"] = pd.to_numeric(fit_df["n_alive"], errors="coerce")
    fit_df = fit_df.dropna(subset=["step", "value"])

    return metadata, fit_df


def _closest_value(frame, target_step, column):
    if frame.empty:
        return float("nan")
    index = (frame["step"] - target_step).abs().idxmin()
    return float(frame.loc[index, column])


def fit_loglog(frame, fit_start, fit_end):
    fit_df = frame[
        (frame["step"] >= fit_start)
        & (frame["step"] <= fit_end)
        & (frame["step"] > 0)
        & (frame["value"] > 0)
    ].copy()
    fit_df = fit_df.sort_values("step").reset_index(drop=True)

    n_points = int(len(fit_df))
    n_alive_min = float(fit_df["n_alive"].min()) if "n_alive" in fit_df.columns and n_points > 0 else float("nan")
    mean_r2_start = _closest_value(fit_df, fit_start, "value") if n_points > 0 else float("nan")
    mean_r2_end = _closest_value(fit_df, fit_end, "value") if n_points > 0 else float("nan")

    if n_points < 3:
        warnings.warn(
            f"Skipping fit range [{fit_start}, {fit_end}] because it has only {n_points} valid points.",
            RuntimeWarning,
        )
        return {
            "alpha": float("nan"),
            "intercept": float("nan"),
            "r2_score": float("nan"),
            "n_points": n_points,
            "n_alive_min": n_alive_min,
            "mean_r2_start": mean_r2_start,
            "mean_r2_end": mean_r2_end,
        }, fit_df

    x = np.log(fit_df["step"].to_numpy(dtype=float))
    y = np.log(fit_df["value"].to_numpy(dtype=float))
    alpha, intercept = np.polyfit(x, y, 1)
    y_pred = alpha * x + intercept
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2_score = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")

    return {
        "alpha": float(alpha),
        "intercept": float(intercept),
        "r2_score": r2_score,
        "n_points": n_points,
        "n_alive_min": n_alive_min,
        "mean_r2_start": mean_r2_start,
        "mean_r2_end": mean_r2_end,
    }, fit_df


def build_summary_dataframe(input_paths, fit_start, fit_end, walk_type=None):
    rows = []
    curves = []

    for input_path in input_paths:
        metadata, frame = read_input(input_path)
        fit_result, fit_df = fit_loglog(frame, fit_start, fit_end)
        reliability_summary_path = find_reliability_summary_path(input_path)
        reliability_summary = load_reliability_summary(reliability_summary_path) if reliability_summary_path else None
        fit_result.update(_reliability_metrics(fit_df, reliability_summary))
        row = {
            "walk_type": walk_type or metadata["walk_type"],
            "dimension": metadata["dim_name"],
            "L": metadata["L"],
            "n_trials": metadata["N"],
            "T": metadata["T"],
            "fit_start": int(fit_start),
            "fit_end": int(fit_end),
        }
        row.update(fit_result)
        rows.append(row)
        curves.append((metadata, frame, fit_df))

    if not rows:
        raise ValueError("No valid input files were loaded.")

    summary = pd.DataFrame(rows).sort_values("T").reset_index(drop=True)
    summary = summary[
        [
            "walk_type",
            "dimension",
            "L",
            "n_trials",
            "T",
            "fit_start",
            "fit_end",
            "alpha",
            "intercept",
            "r2_score",
            "n_points",
            "n_alive_min",
            "mean_r2_start",
            "mean_r2_end",
            "fit_n_alive_min",
            "fit_n_alive_median",
            "fit_max_relative_standard_error",
            "fit_all_points_eligible",
            "fit_reliability_point_count",
            "fit_reliability_complete",
        ]
    ]
    return summary, curves


def plot_alpha_vs_T(summary_df, output_dir):
    plot_df = summary_df.sort_values("T")
    valid = plot_df[plot_df["alpha"].notna()].copy()

    fig, ax = plt.subplots(figsize=(8, 5))
    if not valid.empty:
        ax.plot(valid["T"], valid["alpha"], marker="o", linestyle="-", linewidth=1.5)
    else:
        ax.text(0.5, 0.5, "No valid fits", transform=ax.transAxes, ha="center", va="center")
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(LogLocator(base=10))
    ax.set_xlabel(r"Time $T$")
    ax.set_ylabel(r"$\alpha$")
    ax.set_title(
        rf"MSD fit exponent $\alpha$ vs Time $T$ (fit [{int(plot_df['fit_start'].iloc[0])}, {int(plot_df['fit_end'].iloc[0])}])"
    )
    ax.grid(True, which="both")
    fig.tight_layout()
    out_path = os.path.join(output_dir, "alpha_vs_T.png")
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def plot_alpha_vs_log10T(summary_df, output_dir):
    plot_df = summary_df.sort_values("T")
    valid = plot_df[plot_df["alpha"].notna()].copy()

    fig, ax = plt.subplots(figsize=(8, 5))
    if not valid.empty:
        x = np.log10(valid["T"].astype(float).to_numpy())
        ax.plot(x, valid["alpha"], marker="o", linestyle="-", linewidth=1.5)
    else:
        ax.text(0.5, 0.5, "No valid fits", transform=ax.transAxes, ha="center", va="center")
    ax.set_xlabel(r"$\log_{10} T$")
    ax.set_ylabel(r"$\alpha$")
    ax.set_title(
        rf"MSD fit exponent $\alpha$ vs $\log_{{10}} T$ (fit [{int(plot_df['fit_start'].iloc[0])}, {int(plot_df['fit_end'].iloc[0])}])"
    )
    ax.grid(True, which="both")
    fig.tight_layout()
    out_path = os.path.join(output_dir, "alpha_vs_log10T.png")
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def plot_r2_vs_T(summary_df, output_dir):
    plot_df = summary_df.sort_values("T")
    valid = plot_df[plot_df["r2_score"].notna()].copy()

    fig, ax = plt.subplots(figsize=(8, 5))
    if not valid.empty:
        ax.plot(valid["T"], valid["r2_score"], marker="o", linestyle="-", linewidth=1.5)
    else:
        ax.text(0.5, 0.5, "No valid fits", transform=ax.transAxes, ha="center", va="center")
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(LogLocator(base=10))
    ax.set_xlabel(r"Time $T$")
    ax.set_ylabel("r2_score")
    ax.set_title(
        rf"Fit quality vs Time $T$ (fit [{int(plot_df['fit_start'].iloc[0])}, {int(plot_df['fit_end'].iloc[0])}])"
    )
    ax.grid(True, which="both")
    fig.tight_layout()
    out_path = os.path.join(output_dir, "r2_vs_T.png")
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def plot_n_alive_min_vs_T(summary_df, output_dir):
    plot_df = summary_df.sort_values("T")
    valid = plot_df[plot_df["n_alive_min"].notna()].copy()

    fig, ax = plt.subplots(figsize=(8, 5))
    if not valid.empty:
        ax.plot(valid["T"], valid["n_alive_min"], marker="o", linestyle="-", linewidth=1.5)
    else:
        ax.text(0.5, 0.5, "No valid n_alive values", transform=ax.transAxes, ha="center", va="center")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.xaxis.set_major_locator(LogLocator(base=10))
    ax.set_xlabel(r"Time $T$")
    ax.set_ylabel("n_alive_min")
    ax.set_title(
        rf"Minimum alive trials vs Time $T$ (fit [{int(plot_df['fit_start'].iloc[0])}, {int(plot_df['fit_end'].iloc[0])}])"
    )
    ax.grid(True, which="both")
    fig.tight_layout()
    out_path = os.path.join(output_dir, "n_alive_min_vs_T.png")
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--fit-start", type=int, required=True)
    parser.add_argument("--fit-end", type=int, required=True)
    parser.add_argument("--walk-type", required=True)
    parser.add_argument("--dimension", required=True)
    parser.add_argument("--model")
    args = parser.parse_args()

    if args.fit_start > args.fit_end:
        raise ValueError("--fit-start must be less than or equal to --fit-end")

    os.makedirs(args.output_dir, exist_ok=True)

    summary, curves = build_summary_dataframe(
        args.inputs,
        args.fit_start,
        args.fit_end,
        walk_type=args.walk_type,
    )

    summary.to_csv(args.output_csv, index=False)
    print(f"Saved: {args.output_csv}")

    _ = curves

    alpha_path = plot_alpha_vs_T(summary, args.output_dir)
    print(f"Saved: {alpha_path}")

    alpha_log10_path = plot_alpha_vs_log10T(summary, args.output_dir)
    print(f"Saved: {alpha_log10_path}")

    r2_path = plot_r2_vs_T(summary, args.output_dir)
    print(f"Saved: {r2_path}")

    n_alive_path = plot_n_alive_min_vs_T(summary, args.output_dir)
    print(f"Saved: {n_alive_path}")


if __name__ == "__main__":
    main()