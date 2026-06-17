import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def fit_exponential(df):

    survival = 1.0 - df["trapped_rate"]

    mask = (
        (df["step"] > 0)
        &
        (survival > 0)
    )

    x = df["step"][mask].values
    y = np.log(survival[mask].values)

    slope, intercept = np.polyfit(x, y, 1)

    tau = -1.0 / slope

    return slope, intercept, tau
    
def plot_exponential_fit(df, out_prefix):

    survival = 1.0 - df["trapped_rate"]

    mask = (
        (df["step"] > 0)
        &
        (survival > 0)
    )

    x = df["step"][mask].values
    y = survival[mask].values

    slope, intercept, tau = fit_exponential(df)

    fit_y = np.exp(intercept + slope * x)

    plt.figure()

    plt.semilogy(
        x,
        y,
        label="data"
    )

    plt.semilogy(
        x,
        fit_y,
        "--",
        label=f"tau={tau:.1f}"
    )

    plt.xlabel("step")
    plt.ylabel("P_survival")

    plt.legend()
    plt.grid(True)

    plt.tight_layout()

    plt.savefig(
        f"{out_prefix}_survival_exp_fit.png",
        dpi=300
    )

    plt.close()

    print(f"tau = {tau:.4f}")

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--input", required=True)
    parser.add_argument("--out-prefix", required=True)

    args = parser.parse_args()

    df = pd.read_csv(args.input)

    plot_exponential_fit(
        df,
        args.out_prefix
    )

if __name__ == "__main__":
    main()