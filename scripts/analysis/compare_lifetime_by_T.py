import argparse
import os
import re

import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator
import numpy as np
import pandas as pd


PATH_PATTERN = re.compile(
    r"^(?P<prefix>.*?)/(?P<dim>2d|3d)/random_walk/(?P<model>[^/]+)/(?P<case>[^/]+)/final_steps\.csv$"
)
CASE_PATTERN = re.compile(r"^L(?P<L>\d+)_N(?P<N>\d+)_T(?P<T>\d+)(?:_(?P<suffix>.+))?$")


def parse_metadata_from_path(path, model_override=None):
    normalized = os.path.normpath(path)
    match = PATH_PATTERN.search(normalized)
    if not match:
        raise ValueError(
            "Input path must match data/<dim>/random_walk/<model>/<case>/final_steps.csv: "
            f"{path}"
        )

    dim_name = match.group("dim")
    dim = int(dim_name[0])
    model = model_override or match.group("model")
    case = match.group("case")

    case_match = CASE_PATTERN.match(case)
    if not case_match:
        raise ValueError(f"Could not parse L/N/T metadata from case directory: {case}")

    return {
        "dim_name": dim_name,
        "dim": dim,
        "model": model,
        "case": case,
        "L": int(case_match.group("L")),
        "N": int(case_match.group("N")),
        "T": int(case_match.group("T")),
    }


def _to_numeric_series(df, column):
    if column not in df.columns:
        return None
    series = pd.to_numeric(df[column], errors="coerce")
    if series.isna().all():
        return None
    return series.fillna(0)


def load_input(path, model_override=None):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")

    df = pd.read_csv(path)
    if "final_step" not in df.columns:
        raise ValueError(f"Input CSV {path} is missing required column: final_step")

    if df.empty:
        raise ValueError(f"Input CSV contains no rows: {path}")

    metadata = parse_metadata_from_path(path, model_override=model_override)

    final_step = pd.to_numeric(df["final_step"], errors="coerce")
    if final_step.isna().any():
        raise ValueError(f"Input CSV {path} contains invalid final_step values")

    n_trials = int(len(final_step))
    q90_lifetime = float(final_step.quantile(0.90))
    q99_lifetime = float(final_step.quantile(0.99))
    mean_lifetime = float(final_step.mean())

    trapped_series = _to_numeric_series(df, "trapped")
    boundary_dead_series = _to_numeric_series(df, "boundary_dead")
    contact_dead_series = _to_numeric_series(df, "contact_dead")

    trapped_count = int(trapped_series.sum()) if trapped_series is not None else 0
    boundary_dead_count = int(boundary_dead_series.sum()) if boundary_dead_series is not None else 0
    contact_dead_count = int(contact_dead_series.sum()) if contact_dead_series is not None else 0

    censored_count = int((final_step == int(metadata["T"])).sum())
    censored_fraction = float(censored_count / n_trials) if n_trials > 0 else 0.0

    row = {
        "dim_name": metadata["dim_name"],
        "dim": metadata["dim"],
        "model": metadata["model"],
        "case": metadata["case"],
        "L": metadata["L"],
        "N": metadata["N"],
        "T": metadata["T"],
        "n_trials": n_trials,
        "q90_lifetime": q90_lifetime,
        "q99_lifetime": q99_lifetime,
        "mean_lifetime": mean_lifetime,
        "trapped_count": trapped_count,
        "boundary_dead_count": boundary_dead_count,
        "contact_dead_count": contact_dead_count,
        "trapped_fraction": float(trapped_count / n_trials) if n_trials > 0 else 0.0,
        "boundary_dead_fraction": float(boundary_dead_count / n_trials) if n_trials > 0 else 0.0,
        "contact_dead_fraction": float(contact_dead_count / n_trials) if n_trials > 0 else 0.0,
        "censored_count": censored_count,
        "censored_fraction": censored_fraction,
    }
    return pd.Series(row)


def build_summary_dataframe(input_paths, model_override=None):
    rows = [load_input(input_path, model_override=model_override) for input_path in input_paths]
    if not rows:
        raise ValueError("No valid input files were loaded.")

    combined = pd.DataFrame(rows)
    if combined.empty:
        raise ValueError("No valid summary rows were loaded from inputs.")

    combined = combined.sort_values(by="T")
    columns = [
        "T",
        "q90_lifetime",
        "q99_lifetime",
        "mean_lifetime",
    ]
    return combined.reindex(columns=columns)


def plot_vs_T(df, y_key, plot_prefix, logx=False):
    plot_df = df.copy()
    plot_df = plot_df[plot_df["T"] != ""].copy()
    plot_df["T"] = plot_df["T"].astype(float)
    plot_df = plot_df.sort_values(by="T")

    x = plot_df["T"].values
    y = plot_df[y_key].astype(float).values

    plt.figure(figsize=(8, 5))
    plt.plot(x, y, marker="o", linestyle="-")
    ax = plt.gca()
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(LogLocator(base=10))

    plt.xlabel(r"Time $T$")
    plt.ylabel(y_key.replace("_", " "))
    plt.title(f"{y_key.replace('_', ' ').title()} vs Time $T$")
    plt.grid(True, which="both")
    plt.tight_layout()

    suffix = f"{y_key}_vs_T"
    if logx:
        suffix += "_logx"
    out_path = f"{plot_prefix}_{suffix}.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    return out_path


def plot_q90_q99_mean(df, plot_prefix):
    plot_df = df.copy()
    plot_df["T"] = plot_df["T"].astype(float)
    plot_df = plot_df.sort_values(by="T")

    x = plot_df["T"].values
    plt.figure(figsize=(8, 5))
    plt.plot(x, plot_df["q90_lifetime"].astype(float).values, marker="o", linestyle="-", label="q90_lifetime")
    plt.plot(x, plot_df["q99_lifetime"].astype(float).values, marker="o", linestyle="-", label="q99_lifetime")
    plt.plot(x, plot_df["mean_lifetime"].astype(float).values, marker="o", linestyle="-", label="mean_lifetime")
    ax = plt.gca()
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(LogLocator(base=10))
    plt.xlabel(r"Time $T$")
    plt.ylabel("lifetime")
    plt.title("Lifetime statistics vs Time T")
    plt.grid(True, which="both")
    plt.legend()
    plt.tight_layout()
    out_path = f"{plot_prefix}_q90_q99_mean_vs_T.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--plot-prefix", required=True)
    parser.add_argument("--model")
    args = parser.parse_args()

    summary = build_summary_dataframe(args.inputs, model_override=args.model)
    summary_csv = f"{args.plot_prefix}_summary.csv"
    summary.to_csv(summary_csv, index=False)
    print(f"Saved: {summary_csv}")

    csv_copy_path = args.output_csv
    if csv_copy_path != summary_csv:
        summary.to_csv(csv_copy_path, index=False)
        print(f"Saved: {csv_copy_path}")

    plot_paths = []
    plot_paths.append(plot_vs_T(summary, "mean_lifetime", args.plot_prefix, logx=False))
    plot_paths.append(plot_vs_T(summary, "mean_lifetime", args.plot_prefix, logx=True))
    plot_paths.append(plot_q90_q99_mean(summary, args.plot_prefix))

    for path in plot_paths:
        print(f"Saved: {path}")


if __name__ == "__main__":
    main()