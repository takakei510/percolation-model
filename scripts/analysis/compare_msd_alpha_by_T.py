#!/usr/bin/env python3

import argparse
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator
import numpy as np
import pandas as pd


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


def load_input(path, fit_start, fit_end, model_override=None):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")

    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Input CSV contains no rows: {path}")

    if "step" not in df.columns:
        raise ValueError(f"Input CSV {path} is missing required column: step")

    value_column = detect_value_column(df)
    metadata = parse_metadata_from_path(path, model_override=model_override)

    fit_df = df[["step", value_column]].copy()
    fit_df["step"] = pd.to_numeric(fit_df["step"], errors="coerce")
    fit_df["value"] = pd.to_numeric(fit_df[value_column], errors="coerce")
    fit_df = fit_df.dropna(subset=["step", "value"])
    fit_df = fit_df[
        (fit_df["step"] >= fit_start)
        & (fit_df["step"] <= fit_end)
        & (fit_df["step"] > 0)
        & (fit_df["value"] > 0)
    ].copy()

    if fit_df.empty:
        raise ValueError(
            f"No valid fit points remain after applying the step and positivity filters: {path}"
        )

    fit_df = fit_df.sort_values("step").reset_index(drop=True)
    if len(fit_df) < 2:
        raise ValueError(
            f"Not enough valid fit points in range [{fit_start}, {fit_end}] for: {path}"
        )

    x = np.log(fit_df["step"].to_numpy(dtype=float))
    y = np.log(fit_df["value"].to_numpy(dtype=float))
    alpha, intercept = np.polyfit(x, y, 1)
    y_pred = alpha * x + intercept

    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")

    row = {
        "dim_name": metadata["dim_name"],
        "dim": metadata["dim"],
        "model": metadata["model"],
        "case": metadata["case"],
        "L": metadata["L"],
        "N": metadata["N"],
        "T": metadata["T"],
        "fit_start": int(fit_start),
        "fit_end": int(fit_end),
        "alpha": float(alpha),
        "intercept": float(intercept),
        "r2": r2,
        "n_points": int(len(fit_df)),
    }
    return row, df, value_column


def build_summary_dataframe(input_paths, fit_start, fit_end, model_override=None):
    entries = []

    for input_path in input_paths:
        row, df, value_column = load_input(
            input_path,
            fit_start,
            fit_end,
            model_override=model_override,
        )
        row["input_path"] = input_path
        entries.append((row, df, value_column))

    if not entries:
        raise ValueError("No valid input files were loaded.")

    entries.sort(key=lambda item: item[0]["T"])
    rows = [entry[0] for entry in entries]
    curves = [entry[1] for entry in entries]
    value_columns = [entry[2] for entry in entries]

    summary = pd.DataFrame(rows).sort_values("T").reset_index(drop=True)
    summary = summary[
        [
            "T",
            "fit_start",
            "fit_end",
            "alpha",
            "intercept",
            "r2",
            "n_points",
        ]
    ]
    return summary, rows, curves, value_columns


def plot_msd_loglog_by_T(rows, curves, value_columns, fit_start, fit_end, plot_prefix):
    fig, ax = plt.subplots(figsize=(8, 5))
    cmap = plt.get_cmap("viridis")
    n_items = max(len(curves), 1)
    norm = plt.Normalize(vmin=0, vmax=max(n_items - 1, 1))

    for index, (row, curve, value_column) in enumerate(zip(rows, curves, value_columns)):
        color = cmap(norm(index))
        curve = curve.copy()
        curve = curve[(curve["step"] > 0) & (curve[value_column] > 0)]
        if curve.empty:
            continue

        curve = curve.sort_values("step")
        x = curve["step"].to_numpy(dtype=float)
        y = curve[value_column].to_numpy(dtype=float)

        ax.loglog(
            x,
            y,
            marker="o",
            linestyle="-",
            linewidth=1.5,
            markersize=3.5,
            alpha=0.8,
            color=color,
            label=f"T={int(row['T'])}",
        )

        fit_mask = (
            (curve["step"] >= fit_start)
            & (curve["step"] <= fit_end)
            & (curve["step"] > 0)
            & (curve[value_column] > 0)
        )
        fit_curve = curve.loc[fit_mask].copy()
        if len(fit_curve) >= 2:
            fit_x = fit_curve["step"].to_numpy(dtype=float)
            fit_y = np.exp(row["intercept"]) * np.power(fit_x, row["alpha"])
            ax.loglog(
                fit_x,
                fit_y,
                linestyle="--",
                linewidth=2.0,
                color=color,
                alpha=0.9,
            )

    ax.axvspan(fit_start, fit_end, color="gray", alpha=0.12, label="fit range")
    ax.set_xlabel("step")
    ax.set_ylabel("MSD")
    ax.set_title("MSD log-log curves by T")
    ax.xaxis.set_major_locator(LogLocator(base=10))
    ax.yaxis.set_major_locator(LogLocator(base=10))
    ax.grid(True, which="both")
    ax.legend()
    fig.tight_layout()

    out_path = f"{plot_prefix}_msd_loglog_by_T.png"
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def plot_alpha_vs_T(
    summary_df,
    plot_prefix,
):
    plot_df = summary_df.copy().sort_values("T")
    x = plot_df["T"].astype(float).to_numpy()
    y = plot_df["alpha"].astype(float).to_numpy()

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(x, y, marker="o", linestyle="-", linewidth=1.5)
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(LogLocator(base=10))
    ax.set_xlabel(r"Time $T$")
    ax.set_ylabel(r"$\alpha$")
    ax.set_title(r"MSD fit exponent $\alpha$ vs Time $T$")

    ax.grid(True, which="both")
    fig.tight_layout()

    out_path = f"{plot_prefix}_alpha_vs_T.png"
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--fit-start", type=int, required=True)
    parser.add_argument("--fit-end", type=int, required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--plot-prefix", required=True)
    parser.add_argument("--model")
    args = parser.parse_args()

    if args.fit_start > args.fit_end:
        raise ValueError("--fit-start must be less than or equal to --fit-end")

    summary, rows, curves, value_columns = build_summary_dataframe(
        args.inputs,
        args.fit_start,
        args.fit_end,
        model_override=args.model,
    )

    summary.to_csv(args.output_csv, index=False)
    print(f"Saved: {args.output_csv}")

    msd_path = plot_msd_loglog_by_T(
        rows,
        curves,
        value_columns,
        args.fit_start,
        args.fit_end,
        args.plot_prefix,
    )
    print(f"Saved: {msd_path}")

    alpha_path = plot_alpha_vs_T(
        summary,
        args.plot_prefix,
    )
    print(f"Saved: {alpha_path}")


if __name__ == "__main__":
    main()