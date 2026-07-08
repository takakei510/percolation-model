import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REQUIRED_COLUMNS = ["trial", "final_step"]
OPTIONAL_FLAG_COLUMNS = ["final_r2", "trapped", "boundary_dead", "contact_dead"]


def _read_numeric_series(df, column, *, required=False):
    if column not in df.columns:
        if required:
            raise ValueError(f"Input CSV is missing required column: {column}")
        return None

    series = pd.to_numeric(df[column], errors="coerce")
    if series.isna().any():
        raise ValueError(f"Input CSV contains invalid numeric values in column: {column}")

    return series


def read_input(input_path):
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)
    if df.empty:
        raise ValueError(f"Input CSV contains no rows: {input_path}")

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Input CSV is missing required columns: {', '.join(missing)}")

    trial = _read_numeric_series(df, "trial", required=True)
    final_step = _read_numeric_series(df, "final_step", required=True)

    if not np.allclose(trial.values, np.round(trial.values)):
        raise ValueError("Input CSV column 'trial' must contain integer values")
    if not np.allclose(final_step.values, np.round(final_step.values)):
        raise ValueError("Input CSV column 'final_step' must contain integer values")

    cleaned = df.copy()
    cleaned["trial"] = trial.astype(int)
    cleaned["final_step"] = final_step.astype(int)

    optional_columns = {}
    for column in OPTIONAL_FLAG_COLUMNS:
        if column in cleaned.columns:
            optional_columns[column] = _read_numeric_series(cleaned, column)

    return cleaned, optional_columns


def summarize_lifetime(df, optional_columns):
    final_step = df["final_step"].astype(int)
    n_trials = int(len(final_step))
    if n_trials == 0:
        raise ValueError("Input CSV contains no usable rows")

    trapped = optional_columns.get("trapped")
    boundary_dead = optional_columns.get("boundary_dead")
    contact_dead = optional_columns.get("contact_dead")

    trapped_fraction = float(trapped.sum() / n_trials) if trapped is not None else 0.0
    boundary_dead_fraction = float(boundary_dead.sum() / n_trials) if boundary_dead is not None else 0.0
    contact_dead_fraction = float(contact_dead.sum() / n_trials) if contact_dead is not None else 0.0

    return pd.DataFrame([
        {
            "n_trials": n_trials,
            "mean_lifetime": float(final_step.mean()),
            "std_lifetime": float(final_step.std(ddof=0)),
            "median_lifetime": float(final_step.median()),
            "q90_lifetime": float(final_step.quantile(0.90)),
            "q99_lifetime": float(final_step.quantile(0.99)),
            "max_lifetime": int(final_step.max()),
            "trapped_fraction": trapped_fraction,
            "boundary_dead_fraction": boundary_dead_fraction,
            "contact_dead_fraction": contact_dead_fraction,
        }
    ])


def build_survival_table(df):
    final_step = df["final_step"].astype(int).values
    if len(final_step) == 0:
        raise ValueError("Input CSV contains no usable rows")

    max_step = int(final_step.max())
    counts = np.bincount(final_step, minlength=max_step + 1)
    alive_from_step = np.cumsum(counts[::-1])[::-1].astype(float)
    survival = alive_from_step / float(len(final_step))

    steps = np.arange(0, max_step + 1, dtype=int)
    expected_alive_scales = [10**3, 10**4, 10**5, 10**6, 10**7]

    table = pd.DataFrame({
        "step": steps,
        "survival_probability": survival,
    })
    for scale in expected_alive_scales:
        column = f"expected_alive_{scale:.0e}".replace("e+0", "e")
        table[column] = scale * survival

    return table


def save_csv(df, output_path):
    df.to_csv(output_path, index=False)
    return output_path


def plot_histogram(final_step, output_path, logy=False):
    min_step = int(final_step.min())
    max_step = int(final_step.max())
    bins = np.arange(min_step, max_step + 2) - 0.5

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(final_step, bins=bins, edgecolor="black")
    if logy:
        ax.set_yscale("log")
    ax.set_xlabel("final_step")
    ax.set_ylabel("count")
    ax.set_title("Lifetime distribution" if not logy else "Lifetime distribution (semi-log)")
    ax.grid(True, which="both")
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    return output_path


def plot_survival_probability(table, output_path):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(table["step"], table["survival_probability"], marker="o", linewidth=1.5)
    ax.set_yscale("log")
    ax.set_xlabel("step")
    ax.set_ylabel("S(t)")
    ax.set_title("Survival probability")
    ax.grid(True, which="both")
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    return output_path


def plot_expected_alive(table, output_path):
    fig, ax = plt.subplots(figsize=(8, 5))
    for scale in [10**3, 10**4, 10**5, 10**6, 10**7]:
        column = f"expected_alive_{scale:.0e}".replace("e+0", "e")
        ax.plot(table["step"], table[column], marker="o", linewidth=1.2, label=f"N={scale:.0e}")

    ax.set_yscale("log")
    ax.set_xlabel("step")
    ax.set_ylabel("N_alive(t)")
    ax.set_title("Expected alive count")
    ax.grid(True, which="both")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    return output_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--plot-prefix", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    df, optional_columns = read_input(args.input)

    os.makedirs(args.output_dir, exist_ok=True)

    summary_df = summarize_lifetime(df, optional_columns)
    survival_df = build_survival_table(df)

    summary_csv = save_csv(summary_df, os.path.join(args.output_dir, "lifetime_summary.csv"))
    survival_csv = save_csv(survival_df, os.path.join(args.output_dir, "survival_probability.csv"))

    final_step = df["final_step"].astype(int).values
    histogram_png = plot_histogram(final_step, f"{args.plot_prefix}_lifetime_histogram.png", logy=False)
    histogram_semilog_png = plot_histogram(final_step, f"{args.plot_prefix}_lifetime_histogram_semilog.png", logy=True)
    survival_png = plot_survival_probability(survival_df, f"{args.plot_prefix}_survival_probability.png")
    expected_alive_png = plot_expected_alive(survival_df, f"{args.plot_prefix}_expected_alive.png")

    print(f"Saved: {summary_csv}")
    print(f"Saved: {survival_csv}")
    print(f"Saved: {histogram_png}")
    print(f"Saved: {histogram_semilog_png}")
    print(f"Saved: {survival_png}")
    print(f"Saved: {expected_alive_png}")


if __name__ == "__main__":
    main()