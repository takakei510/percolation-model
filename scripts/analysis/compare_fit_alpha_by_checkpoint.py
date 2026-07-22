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


CASE_PATTERN = re.compile(r"^L(?P<L>\d+)_N(?P<N>\d+)_T(?P<T>\d+)(?:_(?P<suffix>.+))?$")
CHECKPOINT_PATTERN = re.compile(r"^T(?P<T>\d+)$")
VALUE_COLUMNS = ["mean_r2", "msd", "r2_mean", "mean_squared_displacement"]


def parse_run_metadata(run_dir):
    case = os.path.basename(os.path.normpath(run_dir))
    match = CASE_PATTERN.match(case)
    if not match:
        raise ValueError(f"Could not parse L/N/T metadata from run directory: {run_dir}")

    return {
        "case": case,
        "L": int(match.group("L")),
        "n_trials": int(match.group("N")),
        "T": int(match.group("T")),
    }


def parse_checkpoint_t(path):
    name = os.path.basename(os.path.normpath(path))
    match = CHECKPOINT_PATTERN.match(name)
    if not match:
        return None
    return int(match.group("T"))


def detect_value_column(df):
    for column in VALUE_COLUMNS:
        if column in df.columns:
            series = pd.to_numeric(df[column], errors="coerce")
            if not series.isna().all():
                return column
    return None


def load_curve_from_file(path):
    if not os.path.exists(path):
        return None, f"missing file: {path}"

    df = pd.read_csv(path)
    if df.empty:
        return None, f"empty file: {path}"

    if "step" not in df.columns:
        return None, f"missing step column: {path}"

    if "trial" in df.columns and "r2" in df.columns:
        work = df.copy()
        work["step"] = pd.to_numeric(work["step"], errors="coerce")
        work["r2"] = pd.to_numeric(work["r2"], errors="coerce")
        if "alive" in work.columns:
            work["alive"] = pd.to_numeric(work["alive"], errors="coerce")
        work = work.dropna(subset=["step", "r2"])
        if work.empty:
            return None, f"no valid step/r2 rows: {path}"

        rows = []
        for step, group in work.sort_values(["step", "trial"]).groupby("step", sort=True):
            r2 = group["r2"].astype(float)
            if "alive" in group.columns:
                alive_series = pd.to_numeric(group["alive"], errors="coerce")
                n_alive = float(alive_series.fillna(0).sum())
            else:
                n_alive = float(len(group))
            rows.append(
                {
                    "step": int(step),
                    "value": float(r2.mean()),
                    "n_alive": n_alive,
                }
            )
        return pd.DataFrame(rows), None

    value_column = detect_value_column(df)
    if value_column is None:
        return None, f"could not infer MSD column: {path}"

    work = df.copy()
    work["step"] = pd.to_numeric(work["step"], errors="coerce")
    work["value"] = pd.to_numeric(work[value_column], errors="coerce")
    if "n_alive" in work.columns:
        work["n_alive"] = pd.to_numeric(work["n_alive"], errors="coerce")
    work = work.dropna(subset=["step", "value"])
    if work.empty:
        return None, f"no valid step/value rows: {path}"

    if "value_column" not in work.columns:
        work["value_column"] = value_column
    return work[["step", "value"] + (["n_alive"] if "n_alive" in work.columns else [])], None


def load_curve_from_candidates(candidates):
    errors = []
    for path in candidates:
        curve, error = load_curve_from_file(path)
        if curve is not None:
            return path, curve, None
        if error:
            errors.append(error)
    return None, None, "; ".join(errors) if errors else "no usable MSD source found"


def load_checkpoint_curve(run_dir, checkpoint_t, final_t):
    checkpoint_dir = os.path.join(run_dir, "checkpoints", f"T{checkpoint_t}")
    candidates = [
        os.path.join(checkpoint_dir, "saw.csv"),
        os.path.join(checkpoint_dir, "msd_distribution_summary.csv"),
        os.path.join(checkpoint_dir, "msd_distribution.csv"),
    ]

    if checkpoint_t == final_t:
        candidates.extend(
            [
                os.path.join(run_dir, "saw.csv"),
                os.path.join(run_dir, "msd_distribution_summary.csv"),
                os.path.join(run_dir, "msd_distribution.csv"),
            ]
        )

    source_file, curve, error = load_curve_from_candidates(candidates)
    if curve is None:
        return {
            "source_file": os.path.join(checkpoint_dir, "final_steps.csv"),
            "curve": None,
            "warning": error,
        }

    return {
        "source_file": source_file,
        "curve": curve,
        "warning": None,
    }


def compute_fit(curve, fit_start, fit_end):
    fit_df = curve[
        (curve["step"] >= fit_start)
        & (curve["step"] <= fit_end)
        & (curve["step"] > 0)
        & (curve["value"] > 0)
    ].copy()
    fit_df = fit_df.sort_values("step").reset_index(drop=True)

    n_points = int(len(fit_df))
    if "n_alive" in fit_df.columns and n_points > 0:
        n_alive_min = float(fit_df["n_alive"].min())
    else:
        n_alive_min = float("nan")

    mean_r2_start = float("nan")
    mean_r2_end = float("nan")
    if n_points > 0:
        start_index = (fit_df["step"] - fit_start).abs().idxmin()
        end_index = (fit_df["step"] - fit_end).abs().idxmin()
        mean_r2_start = float(fit_df.loc[start_index, "value"])
        mean_r2_end = float(fit_df.loc[end_index, "value"])

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
        }

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
    }


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


def discover_checkpoints(run_dir):
    checkpoints_root = os.path.join(run_dir, "checkpoints")
    if not os.path.isdir(checkpoints_root):
        return []

    checkpoints = []
    for name in os.listdir(checkpoints_root):
        path = os.path.join(checkpoints_root, name)
        if not os.path.isdir(path):
            continue
        checkpoint_t = parse_checkpoint_t(path)
        if checkpoint_t is None:
            continue
        checkpoints.append((checkpoint_t, path))

    return sorted(checkpoints, key=lambda item: item[0])


def build_summary_dataframe(run_dir, fit_start, fit_end, walk_type, dimension):
    metadata = parse_run_metadata(run_dir)
    checkpoints = discover_checkpoints(run_dir)

    if not checkpoints:
        warnings.warn(
            f"No checkpoint directories were found under {os.path.join(run_dir, 'checkpoints')}. Falling back to the run directory itself.",
            RuntimeWarning,
        )
        checkpoints = [(metadata["T"], run_dir)]

    rows = []
    for checkpoint_t, checkpoint_dir in checkpoints:
        source = load_checkpoint_curve(run_dir, checkpoint_t, metadata["T"])
        curve = source["curve"]
        reliability_summary_path = find_reliability_summary_path(source["source_file"])
        reliability_summary = load_reliability_summary(reliability_summary_path) if reliability_summary_path else None

        row = {
            "walk_type": walk_type,
            "dimension": dimension,
            "L": metadata["L"],
            "n_trials": metadata["n_trials"],
            "T": checkpoint_t,
            "fit_start": int(fit_start),
            "fit_end": int(fit_end),
            "alpha": float("nan"),
            "intercept": float("nan"),
            "r2_score": float("nan"),
            "n_points": 0,
            "n_alive_min": float("nan"),
            "mean_r2_start": float("nan"),
            "mean_r2_end": float("nan"),
            "source_file": source["source_file"],
            "fit_n_alive_min": float("nan"),
            "fit_n_alive_median": float("nan"),
            "fit_max_relative_standard_error": float("nan"),
            "fit_all_points_eligible": 0,
            "fit_reliability_point_count": 0,
            "fit_reliability_complete": 0,
        }

        if curve is None:
            warnings.warn(
                f"Checkpoint T{checkpoint_t} does not contain a usable MSD source ({source['source_file']}). Alpha is not computed.",
                RuntimeWarning,
            )
            rows.append(row)
            continue

        fit_result = compute_fit(curve, fit_start, fit_end)
        fit_result.update(_reliability_metrics(curve[(curve["step"] >= fit_start) & (curve["step"] <= fit_end)].copy(), reliability_summary))
        row.update(fit_result)
        rows.append(row)

    summary = pd.DataFrame(rows)
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
            "source_file",
        ]
    ]
    summary = summary.sort_values("T").reset_index(drop=True)
    return summary


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
        rf"MSD fit exponent $\alpha$ vs checkpoint Time $T$ (fit [{int(plot_df['fit_start'].iloc[0])}, {int(plot_df['fit_end'].iloc[0])}])"
    )
    ax.grid(True, which="both")
    fig.tight_layout()
    out_path = os.path.join(output_dir, "alpha_vs_checkpoint_T.png")
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
        rf"MSD fit exponent $\alpha$ vs $\log_{{10}}$ checkpoint $T$ (fit [{int(plot_df['fit_start'].iloc[0])}, {int(plot_df['fit_end'].iloc[0])}])"
    )
    ax.grid(True, which="both")
    fig.tight_layout()
    out_path = os.path.join(output_dir, "alpha_vs_log10_checkpoint_T.png")
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
        rf"Fit quality vs checkpoint Time $T$ (fit [{int(plot_df['fit_start'].iloc[0])}, {int(plot_df['fit_end'].iloc[0])}])"
    )
    ax.grid(True, which="both")
    fig.tight_layout()
    out_path = os.path.join(output_dir, "r2_vs_checkpoint_T.png")
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
        rf"Minimum alive trials within fit range vs checkpoint Time $T$ (fit [{int(plot_df['fit_start'].iloc[0])}, {int(plot_df['fit_end'].iloc[0])}])"
    )
    ax.grid(True, which="both")
    fig.tight_layout()
    out_path = os.path.join(output_dir, "n_alive_min_vs_checkpoint_T.png")
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--fit-start", type=int, required=True)
    parser.add_argument("--fit-end", type=int, required=True)
    parser.add_argument("--walk-type", required=True)
    parser.add_argument("--dimension", required=True)
    args = parser.parse_args()

    if args.fit_start > args.fit_end:
        raise ValueError("--fit-start must be less than or equal to --fit-end")

    metadata = parse_run_metadata(args.run_dir)
    os.makedirs(args.output_dir, exist_ok=True)

    summary = build_summary_dataframe(
        args.run_dir,
        args.fit_start,
        args.fit_end,
        args.walk_type,
        args.dimension,
    )

    summary.to_csv(args.output_csv, index=False)
    print(f"Saved: {args.output_csv}")

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