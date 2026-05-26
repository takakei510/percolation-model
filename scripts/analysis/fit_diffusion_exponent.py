import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def fit_alpha(csv_path, step_min, step_max, label, output_prefix):
    df = pd.read_csv(csv_path)

    df = df[(df["step"] > 0) & (df["mean_r2"] > 0) & (df["n_alive"] > 0)]

    fit_df = df[(df["step"] >= step_min) & (df["step"] <= step_max)]

    if len(fit_df) < 2:
        raise ValueError("Not enough data points for fitting.")

    x = np.log(fit_df["step"].values)
    y = np.log(fit_df["mean_r2"].values)

    alpha, intercept = np.polyfit(x, y, 1)

    print(f"[{label}]")
    print(f"alpha = {alpha:.6f}")
    print(f"intercept = {intercept:.6f}")
    print(f"fit range: step {step_min} to {step_max}")
    print()

    plt.figure()
    plt.loglog(df["step"], df["mean_r2"], label=f"{label} data")
    plt.loglog(
        fit_df["step"],
        np.exp(intercept) * fit_df["step"] ** alpha,
        "--",
        label=f"fit: alpha={alpha:.3f}"
    )
    plt.xlabel("step")
    plt.ylabel("mean_r2")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{output_prefix}_{label}_alpha_fit.png", dpi=300)
    plt.close()

    return alpha, intercept


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rw", required=True)
    parser.add_argument("--saw", required=True)
    parser.add_argument("--step-min", type=int, default=10)
    parser.add_argument("--step-max", type=int, default=200)
    parser.add_argument("--out-prefix", required=True)
    args = parser.parse_args()

    rw_alpha, _ = fit_alpha(
        args.rw,
        args.step_min,
        args.step_max,
        "RW",
        args.out_prefix
    )

    saw_alpha, _ = fit_alpha(
        args.saw,
        args.step_min,
        args.step_max,
        "SAW",
        args.out_prefix
    )

    out_csv = f"{args.out_prefix}_alpha_summary.csv"

    summary = pd.DataFrame([
        {"walk_type": "RW", "alpha": rw_alpha, "step_min": args.step_min, "step_max": args.step_max},
        {"walk_type": "SAW", "alpha": saw_alpha, "step_min": args.step_min, "step_max": args.step_max},
    ])

    summary.to_csv(out_csv, index=False)
    print(f"Saved: {out_csv}")


if __name__ == "__main__":
    main()