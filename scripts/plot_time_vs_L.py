import argparse

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dim", type=int, choices=[2, 3], default=2)
    args = parser.parse_args()

    csv_path = f"data/{args.dim}d/time_vs_L.csv"
    df = pd.read_csv(csv_path)

    print(f"Loaded: {csv_path}")
    print(df)

    plt.figure(figsize=(7, 5))

    plt.loglog(df["L"], df["time_sec"], marker="o", label="Measured")

    log_L = np.log(df["L"])
    log_T = np.log(df["time_sec"])

    slope, intercept = np.polyfit(log_L, log_T, 1)

    fit_T = np.exp(intercept) * df["L"] ** slope
    plt.loglog(df["L"], fit_T, linestyle="--", label=f"slope = {slope:.3f}")

    plt.xlabel("System size L")
    plt.ylabel("Computation time (sec)")
    plt.title(f"Scaling behavior ({args.dim}D)")
    plt.grid(True, which="both")
    plt.legend()
    plt.tight_layout()

    plt.show()


if __name__ == "__main__":
    main()