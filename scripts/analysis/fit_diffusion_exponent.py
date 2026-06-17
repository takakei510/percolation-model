import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def fit_powerlaw(df, column, step_min, step_max):
    fit_df = df[
        (df["step"] >= step_min) &
        (df["step"] <= step_max) &
        (df["step"] > 0) &
        (df[column] > 0)
    ]

    if "n_alive" in fit_df.columns:
        fit_df = fit_df[fit_df["n_alive"] > 0]

    if len(fit_df) < 2:
        raise ValueError(
            f"Not enough data points for fitting: column={column}"
        )

    x = np.log(fit_df["step"].values)
    y = np.log(fit_df[column].values)

    alpha, intercept = np.polyfit(x, y, 1)

    return fit_df, alpha, intercept


def plot_fit(df, column, label, step_min, step_max, output_prefix):
    plot_df = df[
        (df["step"] > 0) &
        (df[column] > 0)
    ]

    fit_df, alpha, intercept = fit_powerlaw(
        df,
        column,
        step_min,
        step_max
    )

    fit_y = np.exp(intercept) * fit_df["step"] ** alpha

    plt.figure(figsize=(7, 5))

    plt.loglog(
        plot_df["step"],
        plot_df[column],
        label=f"{label} data"
    )

    plt.loglog(
        fit_df["step"],
        fit_y,
        "--",
        label=f"fit: alpha={alpha:.3f}"
    )

    plt.xlabel("step")
    plt.ylabel(column)
    plt.title(f"{label} {column} fit")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    safe_label = label.replace(" ", "_").lower()

    plt.savefig(
        f"{output_prefix}_{safe_label}_{column}_alpha_fit.png",
        dpi=300
    )

    plt.close()

    return alpha, intercept, len(fit_df)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rw", required=True)
    parser.add_argument("--saw", required=True)
    parser.add_argument("--step-min", type=int, default=1)
    parser.add_argument("--step-max", type=int, default=200)
    parser.add_argument("--out-prefix", required=True)

    args = parser.parse_args()

    rw = pd.read_csv(args.rw)
    saw = pd.read_csv(args.saw)

    results = []

    # RW MSD
    alpha, intercept, n_fit = plot_fit(
        rw,
        "mean_r2",
        "RW",
        args.step_min,
        args.step_max,
        args.out_prefix
    )

    results.append({
        "walk_type": "RW",
        "quantity": "mean_r2",
        "average": "normal",
        "alpha": alpha,
        "intercept": intercept,
        "step_min": args.step_min,
        "step_max": args.step_max,
        "n_fit": n_fit,
    })

    # SAW alive MSD
    alpha, intercept, n_fit = plot_fit(
        saw,
        "mean_r2",
        "SAW alive",
        args.step_min,
        args.step_max,
        args.out_prefix
    )

    results.append({
        "walk_type": "SAW",
        "quantity": "mean_r2",
        "average": "alive",
        "alpha": alpha,
        "intercept": intercept,
        "step_min": args.step_min,
        "step_max": args.step_max,
        "n_fit": n_fit,
    })

    # SAW all MSD
    if "mean_r2_all" in saw.columns:
        alpha, intercept, n_fit = plot_fit(
            saw,
            "mean_r2_all",
            "SAW all",
            args.step_min,
            args.step_max,
            args.out_prefix
        )

        results.append({
            "walk_type": "SAW",
            "quantity": "mean_r2_all",
            "average": "all",
            "alpha": alpha,
            "intercept": intercept,
            "step_min": args.step_min,
            "step_max": args.step_max,
            "n_fit": n_fit,
        })

    out_csv = f"{args.out_prefix}_alpha_summary.csv"

    summary = pd.DataFrame(results)
    summary.to_csv(out_csv, index=False)

    print(summary)
    print(f"Saved: {out_csv}")


if __name__ == "__main__":
    main()