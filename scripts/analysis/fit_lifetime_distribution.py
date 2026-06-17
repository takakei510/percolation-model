import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def read_final_steps(input_path):
    df = pd.read_csv(input_path)
    if "final_step" not in df.columns:
        raise ValueError("Input CSV must contain 'final_step' column")

    return df["final_step"].dropna().astype(int).values


def compute_histogram(final_steps):
    if len(final_steps) == 0:
        raise ValueError("No final_step values found in input data")

    min_step = int(final_steps.min())
    max_step = int(final_steps.max())
    bins = np.arange(min_step, max_step + 2)
    counts, _ = np.histogram(final_steps, bins=bins)
    steps = np.arange(min_step, max_step + 1)
    probabilities = counts / counts.sum()

    return steps, counts, probabilities, min_step


def fit_geometric(final_steps, support_start):
    mean_lifetime = np.mean(final_steps)
    p = 1.0 / (mean_lifetime - support_start + 1.0)
    return p


def save_distribution_csv(out_prefix, steps, counts, probabilities, p, support_start):
    geometric_fit = (1.0 - p) ** (steps - support_start) * p
    out_csv = f"{out_prefix}_lifetime_distribution.csv"
    pd.DataFrame({
        "final_step": steps,
        "count": counts,
        "probability": probabilities,
        "geometric_fit": geometric_fit,
    }).to_csv(out_csv, index=False)
    return out_csv


def save_summary_csv(out_prefix, mean_lifetime, p, censored_count, censored_fraction, warning):
    out_csv = f"{out_prefix}_lifetime_fit_summary.csv"
    pd.DataFrame([{
        "mean_lifetime": mean_lifetime,
        "p": p,
        "censored_count": censored_count,
        "censored_fraction": censored_fraction,
        "warning": warning,
    }]).to_csv(out_csv, index=False)
    return out_csv


def plot_histogram(out_prefix, steps, counts):
    plt.figure(figsize=(8, 5))
    plt.bar(steps, counts, width=1.0, edgecolor="black")
    plt.xlabel("final step")
    plt.ylabel("count")
    plt.title("Lifetime distribution")
    plt.grid(True)
    plt.tight_layout()
    out_path = f"{out_prefix}_lifetime_hist.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    return out_path


def plot_semilog(out_prefix, steps, probabilities, p, support_start):
    geometric_fit = (1.0 - p) ** (steps - support_start) * p

    plt.figure(figsize=(8, 5))
    plt.semilogy(steps, probabilities, "o", label="observed P(T)")
    plt.semilogy(steps, geometric_fit, "--", label=f"geometric fit p={p:.4f}")
    plt.xlabel("final step")
    plt.ylabel("P(T)")
    plt.title("Lifetime distribution (semi-log)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    out_path = f"{out_prefix}_lifetime_semilog.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-prefix", required=True)
    parser.add_argument("--max-step", type=int, default=None)
    args = parser.parse_args()

    final_steps = read_final_steps(args.input)

    if args.max_step is not None:
        if np.any(final_steps > args.max_step):
            raise ValueError(
                f"Input contains final_step values greater than max_step={args.max_step}"
            )
        censored_count = int(np.sum(final_steps == args.max_step))
    else:
        censored_count = 0

    censored_fraction = censored_count / len(final_steps)
    support_start = int(final_steps.min())
    mean_lifetime = float(np.mean(final_steps))
    p = fit_geometric(final_steps, support_start)

    steps, counts, probabilities, _ = compute_histogram(final_steps)

    dist_csv = save_distribution_csv(
        args.out_prefix,
        steps,
        counts,
        probabilities,
        p,
        support_start,
    )

    warning = ""
    if censored_count > 0:
        warning = (
            "Geometric fit includes right-censored samples at max_step. "
            "Fit results should be interpreted with caution."
        )

    summary_csv = save_summary_csv(
        args.out_prefix,
        mean_lifetime,
        p,
        censored_count,
        censored_fraction,
        warning,
    )

    hist_png = plot_histogram(args.out_prefix, steps, counts)
    semilog_png = plot_semilog(
        args.out_prefix,
        steps,
        probabilities,
        p,
        support_start,
    )

    print(f"Saved: {dist_csv}")
    print(f"Saved: {summary_csv}")
    print(f"Saved: {hist_png}")
    print(f"Saved: {semilog_png}")


if __name__ == "__main__":
    main()
