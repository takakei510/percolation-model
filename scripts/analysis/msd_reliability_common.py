import json
import math
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd


SAMPLE_REQUIRED_COLUMNS = [
    "trial",
    "step",
    "r2",
    "lifetime",
    "alive",
    "trapped",
    "boundary_dead",
    "contact_dead",
]

SUMMARY_REQUIRED_COLUMNS = [
    "step",
    "n_alive",
    "survival_probability",
]


def _to_numeric_series(df, column, *, integer=False):
    series = pd.to_numeric(df[column], errors="coerce")
    if integer:
        if series.isna().any():
            return None
        if not np.all(np.equal(series, np.floor(series))):
            return None
        return series.astype(np.int64)
    return series


def load_simulation_metadata(input_path):
    metadata_path = os.path.join(os.path.dirname(os.path.abspath(input_path)), "simulation_metadata.json")
    if not os.path.exists(metadata_path):
        return None, metadata_path

    with open(metadata_path, "r", encoding="utf-8") as handle:
        metadata = json.load(handle)

    return metadata, metadata_path


def resolve_n_trials(input_path, explicit_n_trials=None):
    metadata, metadata_path = load_simulation_metadata(input_path)
    if metadata is not None and metadata.get("n_trials") is not None:
        n_trials = int(metadata["n_trials"])
        if explicit_n_trials is not None and int(explicit_n_trials) != n_trials:
            return n_trials, metadata_path, True
        return n_trials, metadata_path, False

    if explicit_n_trials is None:
        raise ValueError(
            "n_trials could not be read from simulation_metadata.json; provide --n-trials explicitly"
        )

    return int(explicit_n_trials), metadata_path, False


def validate_sample_frame(df, input_path):
    missing = [column for column in SAMPLE_REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Input CSV is missing required columns: {', '.join(missing)}")

    if df.empty:
        raise ValueError(f"Input CSV contains no rows: {input_path}")

    frame = df.copy()
    frame["trial"] = _to_numeric_series(frame, "trial", integer=True)
    frame["step"] = _to_numeric_series(frame, "step", integer=True)
    frame["r2"] = pd.to_numeric(frame["r2"], errors="coerce")
    frame["lifetime"] = _to_numeric_series(frame, "lifetime", integer=True)
    frame["alive"] = _to_numeric_series(frame, "alive", integer=True)
    frame["trapped"] = _to_numeric_series(frame, "trapped", integer=True)
    frame["boundary_dead"] = _to_numeric_series(frame, "boundary_dead", integer=True)
    frame["contact_dead"] = _to_numeric_series(frame, "contact_dead", integer=True)

    if frame[["trial", "step", "r2", "lifetime", "alive", "trapped", "boundary_dead", "contact_dead"]].isna().any().any():
        raise ValueError(f"Input CSV contains invalid numeric values: {input_path}")

    if (frame["trial"] < 0).any():
        raise ValueError("Input CSV contains negative trial indices")
    if (frame["step"] < 0).any():
        raise ValueError("Input CSV contains negative step values")
    if (frame["r2"] < 0).any() or not np.isfinite(frame["r2"]).all():
        raise ValueError("Input CSV contains non-finite or negative r2 values")
    if (frame["lifetime"] < frame["step"]).any():
        raise ValueError("Input CSV contains rows with lifetime < step")
    if not (frame["alive"] == 1).all():
        raise ValueError("Input CSV contains rows where alive != 1")

    if frame.duplicated(subset=["trial", "step"]).any():
        raise ValueError("Input CSV contains duplicate trial/step rows")

    return frame


def compute_summary_by_step(frame, n_trials, fit_min_alive, fit_min_survival_probability, fit_max_relative_standard_error):
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

        mean_median_ratio = float(mean_r2 / median_r2) if median_r2 > 0.0 else float("nan")

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
                "mean_median_ratio": mean_median_ratio,
                "fit_eligible": fit_eligible,
            }
        )

    if not rows:
        raise ValueError("No step groups were found in the input data")

    summary = pd.DataFrame(rows).sort_values("step").reset_index(drop=True)
    return summary


def load_reliability_summary(summary_path):
    if summary_path is None:
        return None

    if not os.path.exists(summary_path):
        raise FileNotFoundError(f"Reliability summary not found: {summary_path}")

    summary = pd.read_csv(summary_path)
    missing = [column for column in SUMMARY_REQUIRED_COLUMNS if column not in summary.columns]
    if missing:
        raise ValueError(f"Reliability summary is missing required columns: {', '.join(missing)}")

    summary = summary.copy()
    for column in SUMMARY_REQUIRED_COLUMNS:
        summary[column] = pd.to_numeric(summary[column], errors="coerce")

    if "relative_standard_error_r2" not in summary.columns:
        if "standard_error_r2" in summary.columns and "mean_r2" in summary.columns:
            summary["standard_error_r2"] = pd.to_numeric(summary["standard_error_r2"], errors="coerce")
            summary["mean_r2"] = pd.to_numeric(summary["mean_r2"], errors="coerce")
            summary["relative_standard_error_r2"] = summary["standard_error_r2"] / summary["mean_r2"]
        else:
            summary["relative_standard_error_r2"] = np.nan

    if "fit_eligible" not in summary.columns:
        summary["fit_eligible"] = 0

    summary["relative_standard_error_r2"] = pd.to_numeric(summary["relative_standard_error_r2"], errors="coerce")
    summary["fit_eligible"] = pd.to_numeric(summary["fit_eligible"], errors="coerce")

    if summary[SUMMARY_REQUIRED_COLUMNS].isna().any().any():
        raise ValueError(f"Reliability summary contains invalid numeric values: {summary_path}")

    return summary


def find_reliability_summary_path(input_path, explicit_summary=None):
    if explicit_summary:
        if os.path.isdir(explicit_summary):
            candidate = os.path.join(explicit_summary, "msd_streaming_summary.csv")
            if os.path.exists(candidate):
                return candidate
            candidate = os.path.join(explicit_summary, "msd_distribution_summary.csv")
            if os.path.exists(candidate):
                return candidate
            raise FileNotFoundError(f"Reliability summary not found under directory: {explicit_summary}")
        return explicit_summary

    parent_dir = os.path.dirname(os.path.abspath(input_path))
    candidates = [
        os.path.join(parent_dir, "msd_streaming_summary.csv"),
        os.path.join(parent_dir, "msd_distribution_summary.csv"),
        os.path.join(parent_dir, "msd_distribution_analysis", "msd_distribution_summary.csv"),
        os.path.join(parent_dir, "msd_distribution_analysis", "msd_streaming_summary.csv"),
        os.path.join(parent_dir, "analysis", "msd_distribution_summary.csv"),
        os.path.join(parent_dir, "analysis", "msd_streaming_summary.csv"),
    ]

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    return None


def attach_reliability_metrics(fit_frame, reliability_summary, fit_min_alive=None, fit_min_survival_probability=None, fit_max_relative_standard_error=None):
    result = fit_frame.copy()

    if reliability_summary is None:
        result["fit_n_alive_min"] = float("nan")
        result["fit_n_alive_median"] = float("nan")
        result["fit_max_relative_standard_error"] = float("nan")
        result["fit_all_points_eligible"] = 0
        result["fit_reliability_point_count"] = 0
        result["fit_reliability_complete"] = 0
        return result

    merge_columns = ["step", "n_alive", "relative_standard_error_r2"]
    if "fit_eligible" in reliability_summary.columns:
        merge_columns.append("fit_eligible")

    merged = result.merge(
        reliability_summary[merge_columns],
        on="step",
        how="left",
        suffixes=("", "_reliability"),
    )

    reliable_steps = merged[merged["n_alive"].notna()].copy()
    missing_steps = int((merged["n_alive"].isna()).sum())

    if len(reliable_steps) > 0:
        result["fit_n_alive_min"] = float(reliable_steps["n_alive"].min())
        result["fit_n_alive_median"] = float(reliable_steps["n_alive"].median())
        result["fit_max_relative_standard_error"] = float(reliable_steps["relative_standard_error_r2"].max())
        result["fit_reliability_point_count"] = int(len(reliable_steps))
        result["fit_reliability_complete"] = int(missing_steps == 0)
    else:
        result["fit_n_alive_min"] = float("nan")
        result["fit_n_alive_median"] = float("nan")
        result["fit_max_relative_standard_error"] = float("nan")
        result["fit_reliability_point_count"] = 0
        result["fit_reliability_complete"] = 0

    if "fit_eligible" in reliable_steps.columns and len(reliable_steps) == len(result):
        all_eligible = int((reliable_steps["fit_eligible"] == 1).all())
    else:
        all_eligible = 0

    result["fit_all_points_eligible"] = all_eligible

    if missing_steps > 0:
        result.attrs["missing_reliability_steps"] = missing_steps

    if fit_min_alive is not None:
        result.attrs["fit_min_alive_threshold"] = fit_min_alive
    if fit_min_survival_probability is not None:
        result.attrs["fit_min_survival_probability_threshold"] = fit_min_survival_probability
    if fit_max_relative_standard_error is not None:
        result.attrs["fit_max_relative_standard_error_threshold"] = fit_max_relative_standard_error

    return result


def parse_int_list(text):
    if text is None or str(text).strip() == "":
        return []

    values = []
    for item in str(text).split(","):
        item = item.strip()
        if not item:
            continue
        values.append(int(item))

    return sorted(set(values))


def parse_bins_argument(value):
    if isinstance(value, int):
        return value

    text = str(value).strip()
    if text.isdigit():
        return int(text)
    return text


def utc_now_isoformat():
    return datetime.now(timezone.utc).isoformat()