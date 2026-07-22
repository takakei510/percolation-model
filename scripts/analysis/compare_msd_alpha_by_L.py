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
CASE_PATTERN = re.compile(r"^L(?P<L>\d+)_N(?P<N>\d+)_T(?P<T>\d+)(?:_(?P<suffix>.+))?$")
VALUE_COLUMNS = [
    "mean_r2",
    "msd",
    "r2_mean",
    "mean_squared_displacement",
]


def parse_metadata_from_path(path, model_override=None):
    normalized = os.path.normpath(path)
    match = PATH_PATTERN.search(normalized)
    if match:
        dim_name = match.group("dim")
        model = model_override or match.group("model")
        case = match.group("case")
    else:
        legacy_match = LEGACY_PATH_PATTERN.search(normalized)
        if not legacy_match:
            raise ValueError(
                "Input path must match data/<dim>/random_walk/<model>/<case>/<file>.csv: "
                f"{path}"
            )
        dim_name = legacy_match.group("dim")
        model = model_override or ""
        case = legacy_match.group("case")

    case_match = CASE_PATTERN.match(case)
    if not case_match:
        raise ValueError(f"Could not parse L/N/T metadata from case directory: {case}")

    return {
        "dim_name": dim_name,
        "dim": int(dim_name[0]),
        "model": model,
        "case": case,
        "L": int(case_match.group("L")),
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


def _numeric_series(df, column):
    if column not in df.columns:
        return None
    series = pd.to_numeric(df[column], errors="coerce")
    if series.isna().all():
        return None
    return series


def load_input(path, fit_start, fit_end, model_override=None, reliability_summary=None):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")

    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Input CSV contains no rows: {path}")

    if "step" not in df.columns:
        raise ValueError(f"Input CSV {path} is missing required column: step")

    value_column = detect_value_column(df)
    metadata = parse_metadata_from_path(path, model_override=model_override)

    columns = ["step", value_column]
    has_n_alive = "n_alive" in df.columns
    if has_n_alive:
        columns.append("n_alive")

    fit_df = df[columns].copy()
    fit_df["step"] = pd.to_numeric(fit_df["step"], errors="coerce")
    fit_df["value"] = pd.to_numeric(fit_df[value_column], errors="coerce")
    if has_n_alive:
        fit_df["n_alive"] = pd.to_numeric(fit_df["n_alive"], errors="coerce")
    fit_df = fit_df.dropna(subset=["step", "value"])
    fit_df = fit_df[
        (fit_df["step"] >= fit_start)
        & (fit_df["step"] <= fit_end)
        & (fit_df["step"] > 0)
        & (fit_df["value"] > 0)
    ].copy()

    fit_df = fit_df.sort_values("step").reset_index(drop=True)
    n_points = int(len(fit_df))
    reliability_metrics = _reliability_metrics(fit_df, reliability_summary)

    if n_points > 0 and has_n_alive:
        n_alive_min = float(fit_df["n_alive"].min())
    elif n_points > 0:
        n_alive_min = float("nan")
    else:
        n_alive_min = float("nan")

    if n_points > 0:
        mean_r2_start = _closest_value(fit_df, fit_start, "value")
        mean_r2_end = _closest_value(fit_df, fit_end, "value")
    else:
        mean_r2_start = float("nan")
        mean_r2_end = float("nan")

    if n_points < 3:
        warnings.warn(
            f"Skipping fit range [{fit_start}, {fit_end}] because it has only {n_points} valid points.",
            RuntimeWarning,
        )
        row = {
            "walk_type": model_override or metadata["model"],
            "dimension": metadata["dim_name"],
            "L": metadata["L"],
            "n_trials": metadata["N"],
            "T": metadata["T"],
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
        row.update(reliability_metrics)
        return row, df, value_column

    x = np.log(fit_df["step"].to_numpy(dtype=float))
    y = np.log(fit_df["value"].to_numpy(dtype=float))
    alpha, intercept = np.polyfit(x, y, 1)
    y_pred = alpha * x + intercept

    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2_score = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")

    row = {
        "walk_type": model_override or metadata["model"],
        "dimension": metadata["dim_name"],
        "L": metadata["L"],
        "n_trials": metadata["N"],
        "T": metadata["T"],
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
    row.update(reliability_metrics)
    return row, df, value_column


def _closest_value(frame, target_step, column):
    if frame.empty:
        return float("nan")
    index = (frame["step"] - target_step).abs().idxmin()
    return float(frame.loc[index, column])


def build_summary_dataframe(input_paths, fit_start, fit_end, model_override=None):
    entries = []
    for input_path in input_paths:
        reliability_summary_path = find_reliability_summary_path(input_path)
        reliability_summary = load_reliability_summary(reliability_summary_path) if reliability_summary_path else None
        row, df, value_column = load_input(
            input_path,
            fit_start,
            fit_end,
            model_override=model_override,
            reliability_summary=reliability_summary,
        )
        row["input_path"] = input_path
        entries.append((row, df, value_column))

    if not entries:
        raise ValueError("No valid input files were loaded.")

    entries.sort(key=lambda item: item[0]["L"])
    rows = [entry[0] for entry in entries]
    curves = [entry[1] for entry in entries]
    value_columns = [entry[2] for entry in entries]

    summary = pd.DataFrame(rows).sort_values("L").reset_index(drop=True)
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
    return summary, rows, curves, value_columns


def plot_alpha_vs_L(summary_df, output_dir):
    plot_df = summary_df.copy().sort_values("L")
    valid = plot_df[plot_df["alpha"].notna()].copy()

    fig, ax = plt.subplots(figsize=(8, 5))
    if not valid.empty:
        ax.plot(valid["L"], valid["alpha"], marker="o", linestyle="-", linewidth=1.5)
    else:
        ax.text(0.5, 0.5, "No valid fits", transform=ax.transAxes, ha="center", va="center")
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_locator(LogLocator(base=2))
    ax.set_xlabel("L")
    ax.set_ylabel(r"$\alpha$")
    ax.set_title(r"MSD fit exponent $\alpha$ vs L")
    ax.grid(True, which="both")
    fig.tight_layout()
    out_path = os.path.join(output_dir, "alpha_vs_L.png")
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def plot_alpha_vs_log2L(summary_df, output_dir):
    plot_df = summary_df.copy().sort_values("L")
    valid = plot_df[plot_df["alpha"].notna()].copy()

    fig, ax = plt.subplots(figsize=(8, 5))
    if not valid.empty:
        x = np.log2(valid["L"].astype(float).to_numpy())
        ax.plot(x, valid["alpha"], marker="o", linestyle="-", linewidth=1.5)
    else:
        ax.text(0.5, 0.5, "No valid fits", transform=ax.transAxes, ha="center", va="center")
    ax.set_xlabel(r"$\log_2 L$")
    ax.set_ylabel(r"$\alpha$")
    ax.set_title(r"MSD fit exponent $\alpha$ vs $\log_2 L$")
    ax.grid(True, which="both")
    fig.tight_layout()
    out_path = os.path.join(output_dir, "alpha_vs_log2L.png")
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def plot_r2_vs_L(summary_df, output_dir):
    plot_df = summary_df.copy().sort_values("L")
    valid = plot_df[plot_df["r2_score"].notna()].copy()

    fig, ax = plt.subplots(figsize=(8, 5))
    if not valid.empty:
        ax.plot(valid["L"], valid["r2_score"], marker="o", linestyle="-", linewidth=1.5)
    else:
        ax.text(0.5, 0.5, "No valid fits", transform=ax.transAxes, ha="center", va="center")
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_locator(LogLocator(base=2))
    ax.set_xlabel("L")
    ax.set_ylabel("r2_score")
    ax.set_title(r"Fit quality vs L")
    ax.grid(True, which="both")
    fig.tight_layout()
    out_path = os.path.join(output_dir, "r2_vs_L.png")
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def plot_n_alive_min_vs_L(summary_df, output_dir):
    plot_df = summary_df.copy().sort_values("L")
    valid = plot_df[plot_df["n_alive_min"].notna()].copy()

    fig, ax = plt.subplots(figsize=(8, 5))
    if not valid.empty:
        ax.plot(valid["L"], valid["n_alive_min"], marker="o", linestyle="-", linewidth=1.5)
    else:
        ax.text(0.5, 0.5, "No valid n_alive values", transform=ax.transAxes, ha="center", va="center")
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.xaxis.set_major_locator(LogLocator(base=2))
    ax.set_xlabel("L")
    ax.set_ylabel("n_alive_min")
    ax.set_title(r"Minimum alive trials within fit range vs L")
    ax.grid(True, which="both")
    fig.tight_layout()
    out_path = os.path.join(output_dir, "n_alive_min_vs_L.png")
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def plot_msd_vs_step_by_L(rows, curves, value_columns, output_dir):
    fig, ax = plt.subplots(figsize=(8, 5))

    for row, curve, value_column in zip(rows, curves, value_columns):
        plot_curve = curve.copy()
        plot_curve = plot_curve[(plot_curve["step"] > 0) & (plot_curve[value_column] > 0)]
        if plot_curve.empty:
            continue

        plot_curve = plot_curve.sort_values("step")
        ax.loglog(
            plot_curve["step"],
            plot_curve[value_column],
            linestyle="-",
            linewidth=1.5,
            label=f"L={int(row['L'])}",
        )

    ax.set_xlabel("Step")
    ax.set_ylabel("Mean Squared Displacement")
    ax.set_title("MSD vs Step (Comparison by L)")
    ax.grid(True, which="both")
    ax.xaxis.set_major_locator(LogLocator(base=10))
    ax.yaxis.set_major_locator(LogLocator(base=10))
    ax.legend()
    fig.tight_layout()

    out_path = os.path.join(output_dir, "msd_vs_step_by_L.png")
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

    summary, rows, curves, value_columns = build_summary_dataframe(
        args.inputs,
        args.fit_start,
        args.fit_end,
        model_override=args.model,
    )

    summary.to_csv(args.output_csv, index=False)
    print(f"Saved: {args.output_csv}")

    # Curves are loaded here so this script can be extended later without changing the API.
    msd_path = plot_msd_vs_step_by_L(rows, curves, value_columns, args.output_dir)
    print(f"Saved: {msd_path}")

    alpha_vs_l_path = plot_alpha_vs_L(summary, args.output_dir)
    print(f"Saved: {alpha_vs_l_path}")

    alpha_vs_log2l_path = plot_alpha_vs_log2L(summary, args.output_dir)
    print(f"Saved: {alpha_vs_log2l_path}")

    r2_path = plot_r2_vs_L(summary, args.output_dir)
    print(f"Saved: {r2_path}")

    n_alive_path = plot_n_alive_min_vs_L(summary, args.output_dir)
    print(f"Saved: {n_alive_path}")


if __name__ == "__main__":
    main()