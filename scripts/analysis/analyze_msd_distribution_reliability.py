#!/usr/bin/env python3

"""Analyze MSD distributions conditioned on surviving walks.

Supports three inputs:
- exact samples: trial, step, r2, lifetime, alive, trapped, boundary_dead, contact_dead
- reservoir samples: step, sample_index, r2, source_trial, lifetime
- streaming summary: step, n_alive, survival_probability, mean_r2, std_r2, variance_r2,
  standard_error_r2, relative_standard_error_r2, min_r2, max_r2, coefficient_of_variation

The streaming summary is treated as the exact source for mean/variance/SE/RSE/n_alive.
Reservoir samples are only used for quantiles and distribution plots.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator
import numpy as np
import pandas as pd

from msd_reliability_common import load_simulation_metadata, parse_bins_argument, parse_int_list, resolve_n_trials


EXACT_COLUMNS = ["trial", "step", "r2", "lifetime", "alive", "trapped", "boundary_dead", "contact_dead"]
RESERVOIR_COLUMNS = ["step", "sample_index", "r2", "source_trial", "lifetime"]
STREAMING_COLUMNS = [
    "step",
    "n_alive",
    "survival_probability",
    "mean_r2",
    "std_r2",
    "variance_r2",
    "standard_error_r2",
    "relative_standard_error_r2",
    "min_r2",
    "max_r2",
    "coefficient_of_variation",
    "sample_mode",
    "reservoir_size",
    "reservoir_stored_count",
]


def _ensure_output_dir(path):
    os.makedirs(path, exist_ok=True)


def _read_csv(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError(f"Input CSV contains no rows: {path}")
    return frame


def _detect_input_kind(frame):
    columns = set(frame.columns)
    if set(EXACT_COLUMNS).issubset(columns):
        return "exact"
    if set(RESERVOIR_COLUMNS).issubset(columns):
        return "reservoir"
    if {"step", "mean_r2", "n_alive"}.issubset(columns):
        return "streaming"
    raise ValueError("Input CSV does not match exact, reservoir, or streaming summary layouts")


def _validate_exact_frame(frame, input_path):
    validated = frame.copy()
    for column in EXACT_COLUMNS:
        if column == "r2":
            validated[column] = pd.to_numeric(validated[column], errors="coerce")
        else:
            validated[column] = pd.to_numeric(validated[column], errors="coerce")
    if validated[EXACT_COLUMNS].isna().any().any():
        raise ValueError(f"Input CSV contains invalid numeric values: {input_path}")
    return validated


def _validate_reservoir_frame(frame, input_path):
    validated = frame.copy()
    for column in RESERVOIR_COLUMNS:
        validated[column] = pd.to_numeric(validated[column], errors="coerce")
    if validated[RESERVOIR_COLUMNS].isna().any().any():
        raise ValueError(f"Input CSV contains invalid numeric values: {input_path}")
    return validated


def _validate_streaming_frame(frame, input_path):
    validated = frame.copy()
    for column in [
        "step",
        "n_alive",
        "survival_probability",
        "mean_r2",
        "std_r2",
        "variance_r2",
        "standard_error_r2",
        "relative_standard_error_r2",
        "min_r2",
        "max_r2",
        "coefficient_of_variation",
        "reservoir_size",
        "reservoir_stored_count",
    ]:
        if column in validated.columns:
            validated[column] = pd.to_numeric(validated[column], errors="coerce")
    if validated[["step", "n_alive", "survival_probability", "mean_r2"]].isna().any().any():
        raise ValueError(f"Input CSV contains invalid numeric values: {input_path}")
    return validated


def _summary_from_exact(frame, n_trials, fit_min_alive, fit_min_survival_probability, fit_max_relative_standard_error):
    rows = []
    for step, group in frame.sort_values(["step", "trial"]).groupby("step", sort=True):
        values = group["r2"].astype(float)
        n_alive = int(len(group))
        survival_probability = float(n_alive / n_trials)
        mean_r2 = float(values.mean())
        median_r2 = float(values.median())

        if n_alive > 1:
            std_r2 = float(values.std(ddof=1))
            variance_r2 = float(values.var(ddof=1))
            standard_error_r2 = float(std_r2 / math.sqrt(n_alive))
        else:
            std_r2 = float("nan")
            variance_r2 = float("nan")
            standard_error_r2 = float("nan")

        if mean_r2 > 0.0 and math.isfinite(standard_error_r2):
            relative_standard_error_r2 = float(standard_error_r2 / mean_r2)
            coefficient_of_variation = float(std_r2 / mean_r2)
        else:
            relative_standard_error_r2 = float("nan")
            coefficient_of_variation = float("nan")

        fit_eligible = int(
            (n_alive >= fit_min_alive)
            and (survival_probability >= fit_min_survival_probability)
            and math.isfinite(relative_standard_error_r2)
            and (relative_standard_error_r2 <= fit_max_relative_standard_error)
        )

        rows.append(
            {
                "step": int(step),
                "n_alive": n_alive,
                "survival_probability": survival_probability,
                "mean_r2": mean_r2,
                "median_r2": median_r2,
                "std_r2": std_r2,
                "variance_r2": variance_r2,
                "standard_error_r2": standard_error_r2,
                "relative_standard_error_r2": relative_standard_error_r2,
                "q10_r2": float(values.quantile(0.10)),
                "q25_r2": float(values.quantile(0.25)),
                "q75_r2": float(values.quantile(0.75)),
                "q90_r2": float(values.quantile(0.90)),
                "q95_r2": float(values.quantile(0.95)),
                "q99_r2": float(values.quantile(0.99)),
                "min_r2": float(values.min()),
                "max_r2": float(values.max()),
                "coefficient_of_variation": coefficient_of_variation,
                "sample_mode": "exact",
                "reservoir_size": 0,
                "reservoir_stored_count": 0,
                "quantile_source": "exact",
                "fit_eligible": fit_eligible,
            }
        )

    summary = pd.DataFrame(rows).sort_values("step").reset_index(drop=True)
    return summary


def _summary_from_streaming(streaming_frame):
    summary = streaming_frame.copy().sort_values("step").reset_index(drop=True)
    if "quantile_source" not in summary.columns:
        summary["quantile_source"] = "none"
    if "median_r2" not in summary.columns:
        summary["median_r2"] = np.nan
    for column in ["q10_r2", "q25_r2", "q75_r2", "q90_r2", "q95_r2", "q99_r2"]:
        if column not in summary.columns:
            summary[column] = np.nan
    if "fit_eligible" not in summary.columns:
        summary["fit_eligible"] = 0
    return summary


def _merge_streaming_and_samples(summary, sample_frame, sample_kind):
    if sample_frame is None:
        return summary

    sample_rows = []
    for step, group in sample_frame.groupby("step", sort=True):
        values = group["r2"].astype(float)
        row = {
            "step": int(step),
            "median_r2": float(values.median()),
            "q10_r2": float(values.quantile(0.10)),
            "q25_r2": float(values.quantile(0.25)),
            "q75_r2": float(values.quantile(0.75)),
            "q90_r2": float(values.quantile(0.90)),
            "q95_r2": float(values.quantile(0.95)),
            "q99_r2": float(values.quantile(0.99)),
            "min_r2": float(values.min()),
            "max_r2": float(values.max()),
            "quantile_source": sample_kind,
        }
        sample_rows.append(row)

    sample_df = pd.DataFrame(sample_rows)
    merged = summary.merge(sample_df, on="step", how="left", suffixes=("", "_sample"))
    for column in ["median_r2", "q10_r2", "q25_r2", "q75_r2", "q90_r2", "q95_r2", "q99_r2", "min_r2", "max_r2"]:
        merged[column] = merged[f"{column}_sample"].combine_first(merged[column])
        merged = merged.drop(columns=[f"{column}_sample"])
    if "quantile_source_sample" in merged.columns:
        merged["quantile_source"] = merged["quantile_source_sample"].combine_first(merged["quantile_source"])
        merged = merged.drop(columns=["quantile_source_sample"])
    return merged


def _load_inputs(samples_path, streaming_path, input_path, input_kind, fit_min_alive, fit_min_survival_probability, fit_max_relative_standard_error, n_trials):
    sample_frame = None
    sample_kind = None
    streaming_frame = None

    if samples_path is None and input_kind in {"exact", "reservoir"}:
        samples_path = input_path
    if streaming_path is None and input_kind == "streaming":
        streaming_path = input_path

    if samples_path is not None:
        raw_samples = _read_csv(samples_path)
        sample_kind = _detect_input_kind(raw_samples)
        if sample_kind == "exact":
            sample_frame = _validate_exact_frame(raw_samples, samples_path)
        elif sample_kind == "reservoir":
            sample_frame = _validate_reservoir_frame(raw_samples, samples_path)
        elif sample_kind == "streaming":
            streaming_frame = _validate_streaming_frame(raw_samples, samples_path)
            sample_frame = None
        else:
            raise ValueError(f"Unsupported sample format: {samples_path}")

    if streaming_path is not None and streaming_frame is None:
        raw_streaming = _read_csv(streaming_path)
        if _detect_input_kind(raw_streaming) != "streaming":
            raise ValueError(f"Streaming summary input must contain step, mean_r2, and n_alive: {streaming_path}")
        streaming_frame = _validate_streaming_frame(raw_streaming, streaming_path)

    if sample_frame is not None and sample_kind == "exact":
        summary = _summary_from_exact(sample_frame, n_trials, fit_min_alive, fit_min_survival_probability, fit_max_relative_standard_error)
    elif streaming_frame is not None:
        summary = _summary_from_streaming(streaming_frame)
        if sample_frame is not None and sample_kind == "reservoir":
            summary = _merge_streaming_and_samples(summary, sample_frame, "reservoir")
    elif sample_frame is not None and sample_kind == "reservoir":
        summary = _summary_from_exact(sample_frame, n_trials, fit_min_alive, fit_min_survival_probability, fit_max_relative_standard_error)
        summary["sample_mode"] = "reservoir"
        summary["quantile_source"] = "reservoir"
        summary["reservoir_size"] = len(sample_frame)
        summary["reservoir_stored_count"] = len(sample_frame)
    else:
        raise ValueError("No usable MSD samples or streaming summary were provided")

    if "sample_mode" not in summary.columns:
        summary["sample_mode"] = "exact" if sample_kind == "exact" else ("reservoir" if sample_kind == "reservoir" else "none")
    if "quantile_source" not in summary.columns:
        summary["quantile_source"] = "exact" if sample_kind == "exact" else ("reservoir" if sample_kind == "reservoir" else "none")

    return summary, sample_frame, sample_kind, streaming_frame


def _plot_histogram(sample_frame, summary, step, output_dir, bins, log_y, quantile_source):
    if sample_frame is None:
        return None

    group = sample_frame[sample_frame["step"] == step].copy()
    if group.empty:
        return None

    values = group["r2"].astype(float).to_numpy()
    row = summary[summary["step"] == step]
    if row.empty:
        return None
    row = row.iloc[0]

    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    ax.hist(values, bins=bins, density=True, edgecolor="black", alpha=0.8)
    ax.axvline(float(row["mean_r2"]), color="tab:blue", linewidth=2.0, label="mean")
    ax.axvline(float(row["median_r2"]), color="tab:orange", linewidth=2.0, label="median")
    ax.axvline(float(row["q90_r2"]), color="tab:green", linestyle="--", linewidth=1.8, label="q90")
    ax.axvline(float(row["q99_r2"]), color="tab:red", linestyle=":", linewidth=1.8, label="q99")
    ax.set_xlabel(r"$r^2$")
    ax.set_ylabel("probability density")
    title = f"Surviving walks at step t={int(step)}"
    if quantile_source == "reservoir":
        title += "\nquantiles estimated from reservoir sample"
    ax.set_title(title)
    ax.grid(True, which="both", alpha=0.3)
    if log_y:
        ax.set_yscale("log")

    n_alive = int(row["n_alive"])
    rse = float(row["relative_standard_error_r2"])
    reservoir_stored = int(row.get("reservoir_stored_count", 0))
    text = f"n_alive = {n_alive}\nreservoir = {reservoir_stored}\nRSE = {rse:.4g}\nsample_mode = {row.get('sample_mode', 'exact')}"
    ax.text(0.98, 0.98, text, transform=ax.transAxes, ha="right", va="top", fontsize=10,
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.85, edgecolor="none"))
    ax.legend(loc="best")
    fig.tight_layout()

    out_dir = os.path.join(output_dir, "histograms")
    _ensure_output_dir(out_dir)
    suffix = "_log" if log_y else ""
    out_path = os.path.join(out_dir, f"r2_hist_step_{int(step)}{suffix}.png")
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def _plot_summary_series(summary, x_key, y_key, output_path, title, ylabel, fit_start=None, fit_end=None, threshold_lines=None, log_x=False, log_y=False):
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    plot_df = summary.copy().sort_values("step")
    ax.plot(plot_df[x_key], plot_df[y_key], marker="o", linestyle="-", linewidth=1.6)
    ax.set_xlabel("step")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, which="both", alpha=0.3)

    if fit_start is not None and fit_end is not None:
        ax.axvspan(fit_start, fit_end, color="gray", alpha=0.12, label="fit range")

    if threshold_lines:
        for label, value, style in threshold_lines:
            if value is None or (isinstance(value, float) and math.isnan(value)):
                continue
            ax.axhline(value, linestyle=style, linewidth=1.2, label=label)

    if log_x:
        ax.set_xscale("log")
        ax.xaxis.set_major_locator(LogLocator(base=10))
    if log_y:
        ax.set_yscale("log")

    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="best")

    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    return output_path


def _plot_moment_summary(summary, output_path, fit_start=None, fit_end=None):
    fig, ax = plt.subplots(figsize=(8.4, 5.3))
    plot_df = summary.sort_values("step")
    ax.plot(plot_df["step"], plot_df["mean_r2"], marker="o", label="mean_r2")
    if "median_r2" in plot_df.columns:
        ax.plot(plot_df["step"], plot_df["median_r2"], marker="o", label="median_r2")
    if "q90_r2" in plot_df.columns:
        ax.plot(plot_df["step"], plot_df["q90_r2"], marker="o", label="q90_r2")
    if "q99_r2" in plot_df.columns:
        ax.plot(plot_df["step"], plot_df["q99_r2"], marker="o", label="q99_r2")
    if fit_start is not None and fit_end is not None:
        ax.axvspan(fit_start, fit_end, color="gray", alpha=0.12, label="fit range")
    ax.set_xlabel("step")
    ax.set_ylabel(r"$r^2$")
    ax.set_title(r"Mean, median, and high quantiles of $r^2$ by step")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    return output_path


def _plot_scatter_with_color(summary, output_path, color_key, color_label, fit_start=None, fit_end=None):
    plot_df = summary.copy()
    plot_df = plot_df[(plot_df["step"] > 0) & (plot_df["mean_r2"] > 0)].copy()

    fig, ax = plt.subplots(figsize=(8.4, 5.3))
    eligible = plot_df[plot_df["fit_eligible"] == 1]
    ineligible = plot_df[plot_df["fit_eligible"] == 0]

    if not eligible.empty:
        scatter = ax.scatter(
            eligible["step"],
            eligible["mean_r2"],
            c=eligible[color_key],
            cmap="viridis",
            s=42,
            marker="o",
            edgecolors="none",
            label="fit_eligible=1",
        )
    else:
        scatter = None

    if not ineligible.empty:
        ax.scatter(
            ineligible["step"],
            ineligible["mean_r2"],
            c=ineligible[color_key],
            cmap="viridis",
            s=46,
            marker="x",
            linewidths=1.3,
            label="fit_eligible=0",
        )

    if fit_start is not None and fit_end is not None:
        ax.axvspan(fit_start, fit_end, color="gray", alpha=0.12, label="fit range")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.xaxis.set_major_locator(LogLocator(base=10))
    ax.yaxis.set_major_locator(LogLocator(base=10))
    ax.set_xlabel("step")
    ax.set_ylabel(r"mean $r^2$")
    ax.set_title(f"MSD colored by {color_label}")
    ax.grid(True, which="both", alpha=0.3)
    if scatter is not None:
        colorbar = fig.colorbar(scatter, ax=ax)
        colorbar.set_label(color_label)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    return output_path


def _plot_boxplot(sample_frame, steps, output_path, log_scale=False, show_fliers=True):
    if sample_frame is None:
        return None

    data = []
    labels = []
    zero_removed = 0

    for step in steps:
        group = sample_frame[sample_frame["step"] == step].copy()
        if group.empty:
            continue
        values = group["r2"].astype(float).to_numpy()
        if log_scale:
            nonzero = values[values > 0]
            zero_removed += int((values <= 0).sum())
            values = nonzero
            if len(values) == 0:
                continue
        data.append(values)
        labels.append(str(int(step)))

    if not data:
        return None

    fig, ax = plt.subplots(figsize=(max(8.0, 1.1 * len(data)), 5.5))
    ax.boxplot(data, tick_labels=labels, showfliers=show_fliers)
    ax.set_xlabel("step")
    ax.set_ylabel(r"$r^2$")
    ax.set_title(r"$r^2$ boxplot by step")
    ax.grid(True, which="both", axis="y", alpha=0.3)
    if log_scale:
        ax.set_yscale("log")
        if zero_removed > 0:
            ax.text(
                0.99,
                0.02,
                f"zero-valued samples removed: {zero_removed}",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=9,
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.85, edgecolor="none"),
            )
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    return output_path


def _default_steps(summary):
    return summary["step"].astype(int).tolist()


def _write_analysis_metadata(output_dir, input_path, samples_path, streaming_path, metadata, args, n_trials, metadata_path, quantile_source, sample_mode):
    output_path = os.path.join(output_dir, "analysis_metadata.json")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_file": os.path.abspath(input_path) if input_path else None,
        "samples_file": os.path.abspath(samples_path) if samples_path else None,
        "streaming_summary_file": os.path.abspath(streaming_path) if streaming_path else None,
        "output_dir": os.path.abspath(output_dir),
        "output_summary": os.path.abspath(os.path.join(output_dir, "msd_distribution_summary.csv")),
        "n_trials": int(n_trials),
        "fit_start": args.fit_start,
        "fit_end": args.fit_end,
        "fit_min_alive": args.fit_min_alive,
        "fit_min_survival_probability": args.fit_min_survival_probability,
        "fit_max_relative_standard_error": args.fit_max_relative_standard_error,
        "histogram_steps": args.histogram_steps,
        "boxplot_steps": args.boxplot_steps,
        "bins": args.bins,
        "hist_log_y": bool(args.hist_log_y),
        "show_fliers": bool(args.show_fliers),
        "simulation_metadata_path": metadata_path,
        "simulation_metadata": metadata,
        "quantile_source": quantile_source,
        "sample_mode": sample_mode,
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return output_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", nargs="?")
    parser.add_argument("--samples")
    parser.add_argument("--streaming-summary")
    parser.add_argument("--metadata")
    parser.add_argument("--n-trials", type=int)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--fit-start", type=int)
    parser.add_argument("--fit-end", type=int)
    parser.add_argument("--fit-min-alive", type=int, default=1)
    parser.add_argument("--fit-min-survival-probability", type=float, default=0.0)
    parser.add_argument("--fit-max-relative-standard-error", type=float, default=math.inf)
    parser.add_argument("--histogram-steps")
    parser.add_argument("--boxplot-steps")
    parser.add_argument("--bins", default="fd")
    parser.add_argument("--hist-log-y", action="store_true")
    fliers = parser.add_mutually_exclusive_group()
    fliers.add_argument("--show-fliers", action="store_true")
    fliers.add_argument("--hide-fliers", action="store_true")
    args = parser.parse_args()

    if args.fit_start is not None and args.fit_end is not None and args.fit_start > args.fit_end:
        raise ValueError("--fit-start must be less than or equal to --fit-end")
    if (args.fit_start is None) != (args.fit_end is None):
        raise ValueError("--fit-start and --fit-end must be provided together")

    _ensure_output_dir(args.output_dir)

    input_path = args.input_csv
    samples_path = args.samples or input_path
    streaming_path = args.streaming_summary

    sample_frame = None
    streaming_frame = None
    sample_kind = None

    if samples_path:
        raw_samples = _read_csv(samples_path)
        sample_kind = _detect_input_kind(raw_samples)
        if sample_kind == "exact":
            sample_frame = _validate_exact_frame(raw_samples, samples_path)
        elif sample_kind == "reservoir":
            sample_frame = _validate_reservoir_frame(raw_samples, samples_path)
        elif sample_kind == "streaming":
            streaming_frame = _validate_streaming_frame(raw_samples, samples_path)
            sample_frame = None
            streaming_path = samples_path if streaming_path is None else streaming_path
        else:
            raise ValueError(f"Unsupported sample format: {samples_path}")

    if streaming_path:
        raw_streaming = _read_csv(streaming_path)
        if _detect_input_kind(raw_streaming) != "streaming":
            raise ValueError(f"Streaming summary input must contain step, mean_r2, and n_alive: {streaming_path}")
        streaming_frame = _validate_streaming_frame(raw_streaming, streaming_path)

    if input_path and not samples_path and streaming_path is None:
        raw_input = _read_csv(input_path)
        kind = _detect_input_kind(raw_input)
        if kind == "streaming":
            streaming_frame = _validate_streaming_frame(raw_input, input_path)
        elif kind == "exact":
            sample_frame = _validate_exact_frame(raw_input, input_path)
        elif kind == "reservoir":
            sample_frame = _validate_reservoir_frame(raw_input, input_path)

    if sample_frame is None and streaming_frame is None:
        raise ValueError("No usable MSD input was provided")

    metadata, metadata_path = load_simulation_metadata(samples_path or streaming_path or input_path)
    if metadata is None:
        metadata = {}
    n_trials, _, _ = resolve_n_trials(samples_path or streaming_path or input_path, args.n_trials)

    if sample_frame is not None and sample_kind == "exact":
        summary = _summary_from_exact(sample_frame, n_trials, args.fit_min_alive, args.fit_min_survival_probability, args.fit_max_relative_standard_error)
        quantile_source = "exact"
        sample_mode = "exact"
    elif streaming_frame is not None:
        summary = _summary_from_streaming(streaming_frame)
        quantile_source = "reservoir" if sample_frame is not None and sample_kind == "reservoir" else "exact"
        sample_mode = str(summary["sample_mode"].iloc[0]) if "sample_mode" in summary.columns and len(summary) > 0 else "none"
        if sample_frame is not None and sample_kind == "reservoir":
            summary = _merge_streaming_and_samples(summary, sample_frame, "reservoir")
    elif sample_frame is not None and sample_kind == "reservoir":
        summary = _summary_from_exact(sample_frame, n_trials, args.fit_min_alive, args.fit_min_survival_probability, args.fit_max_relative_standard_error)
        summary["sample_mode"] = "reservoir"
        summary["quantile_source"] = "reservoir"
        summary["reservoir_size"] = len(sample_frame)
        summary["reservoir_stored_count"] = len(sample_frame)
        quantile_source = "reservoir"
        sample_mode = "reservoir"
    else:
        raise ValueError("Unable to determine input mode")

    summary = summary.sort_values("step").reset_index(drop=True)
    summary_csv = os.path.join(args.output_dir, "msd_distribution_summary.csv")
    summary.to_csv(summary_csv, index=False)

    analysis_metadata_path = _write_analysis_metadata(
        args.output_dir,
        input_path,
        samples_path,
        streaming_path,
        metadata,
        args,
        n_trials,
        metadata_path,
        quantile_source,
        sample_mode,
    )

    histogram_steps = parse_int_list(args.histogram_steps)
    if not histogram_steps:
        histogram_steps = _default_steps(summary)

    boxplot_steps = parse_int_list(args.boxplot_steps)
    if not boxplot_steps:
        boxplot_steps = _default_steps(summary)

    bins = parse_bins_argument(args.bins)
    show_fliers = True if args.show_fliers or not args.hide_fliers else False

    histogram_paths = []
    for step in histogram_steps:
        path = _plot_histogram(sample_frame, summary, step, args.output_dir, bins=bins, log_y=args.hist_log_y, quantile_source=quantile_source)
        if path is not None:
            histogram_paths.append(path)

    summary_dir = os.path.join(args.output_dir, "summary")
    _ensure_output_dir(summary_dir)

    moment_path = os.path.join(summary_dir, "mean_median_quantiles_vs_step.png")
    _plot_moment_summary(summary, moment_path, fit_start=args.fit_start, fit_end=args.fit_end)

    _plot_summary_series(
        summary,
        "step",
        "n_alive",
        os.path.join(summary_dir, "n_alive_vs_step.png"),
        "n_alive vs step",
        "n_alive",
        fit_start=args.fit_start,
        fit_end=args.fit_end,
        threshold_lines=[("fit_min_alive", args.fit_min_alive, "--")],
    )
    _plot_summary_series(
        summary,
        "step",
        "survival_probability",
        os.path.join(summary_dir, "survival_probability_vs_step.png"),
        "survival_probability vs step",
        "survival_probability",
        fit_start=args.fit_start,
        fit_end=args.fit_end,
        threshold_lines=[("fit_min_survival_probability", args.fit_min_survival_probability, "--")],
    )
    _plot_summary_series(
        summary,
        "step",
        "standard_error_r2",
        os.path.join(summary_dir, "standard_error_r2_vs_step.png"),
        "standard_error_r2 vs step",
        "standard_error_r2",
        fit_start=args.fit_start,
        fit_end=args.fit_end,
    )
    _plot_summary_series(
        summary,
        "step",
        "relative_standard_error_r2",
        os.path.join(summary_dir, "relative_standard_error_r2_vs_step.png"),
        "relative_standard_error_r2 vs step",
        "relative_standard_error_r2",
        fit_start=args.fit_start,
        fit_end=args.fit_end,
        threshold_lines=[("fit_max_relative_standard_error", args.fit_max_relative_standard_error, "--")],
    )
    _plot_summary_series(
        summary,
        "step",
        "coefficient_of_variation",
        os.path.join(summary_dir, "coefficient_of_variation_vs_step.png"),
        "coefficient_of_variation vs step",
        "coefficient_of_variation",
        fit_start=args.fit_start,
        fit_end=args.fit_end,
    )

    if "mean_median_ratio" in summary.columns:
        _plot_summary_series(
            summary,
            "step",
            "mean_median_ratio",
            os.path.join(summary_dir, "mean_median_ratio_vs_step.png"),
            "mean_median_ratio vs step",
            "mean_median_ratio",
            fit_start=args.fit_start,
            fit_end=args.fit_end,
        )

    scatter_summary = summary.copy()
    scatter_summary["log10_n_alive"] = np.log10(scatter_summary["n_alive"].astype(float).clip(lower=1.0))
    _plot_scatter_with_color(
        scatter_summary,
        os.path.join(summary_dir, "msd_colored_by_log10_n_alive.png"),
        color_key="log10_n_alive",
        color_label="log10(n_alive)",
        fit_start=args.fit_start,
        fit_end=args.fit_end,
    )
    _plot_scatter_with_color(
        summary,
        os.path.join(summary_dir, "msd_colored_by_relative_standard_error.png"),
        color_key="relative_standard_error_r2",
        color_label="relative_standard_error_r2",
        fit_start=args.fit_start,
        fit_end=args.fit_end,
    )

    boxplot_linear = _plot_boxplot(sample_frame, boxplot_steps, os.path.join(summary_dir, "r2_boxplot_linear.png"), log_scale=False, show_fliers=show_fliers)
    boxplot_log = _plot_boxplot(sample_frame, boxplot_steps, os.path.join(summary_dir, "r2_boxplot_log.png"), log_scale=True, show_fliers=show_fliers)

    print(f"Saved: {summary_csv}")
    print(f"Saved: {analysis_metadata_path}")
    for path in histogram_paths:
        print(f"Saved: {path}")
    print(f"Saved: {moment_path}")
    print(f"Saved: {os.path.join(summary_dir, 'n_alive_vs_step.png')}")
    print(f"Saved: {os.path.join(summary_dir, 'survival_probability_vs_step.png')}")
    print(f"Saved: {os.path.join(summary_dir, 'standard_error_r2_vs_step.png')}")
    print(f"Saved: {os.path.join(summary_dir, 'relative_standard_error_r2_vs_step.png')}")
    print(f"Saved: {os.path.join(summary_dir, 'coefficient_of_variation_vs_step.png')}")
    if "mean_median_ratio" in summary.columns:
        print(f"Saved: {os.path.join(summary_dir, 'mean_median_ratio_vs_step.png')}")
    print(f"Saved: {os.path.join(summary_dir, 'msd_colored_by_log10_n_alive.png')}")
    print(f"Saved: {os.path.join(summary_dir, 'msd_colored_by_relative_standard_error.png')}")
    if boxplot_linear:
        print(f"Saved: {boxplot_linear}")
    if boxplot_log:
        print(f"Saved: {boxplot_log}")


if __name__ == "__main__":
    main()