import argparse
import pandas as pd
import matplotlib.pyplot as plt


def plot_final_step_hist(csv_path, out_prefix):
    df = pd.read_csv(csv_path)

    plt.figure(figsize=(8, 5))

    plt.hist(
        df["final_step"],
        bins=50
    )

    plt.xlabel("final step")
    plt.ylabel("count")
    plt.title("Final step distribution")

    plt.grid(True)

    plt.tight_layout()

    plt.savefig(
        f"{out_prefix}_final_step_hist.png",
        dpi=300
    )

    plt.close()


def plot_final_step_cdf(csv_path, out_prefix):
    df = pd.read_csv(csv_path)

    x = df["final_step"].sort_values().values
    y = range(1, len(x) + 1)

    plt.figure(figsize=(8, 5))

    plt.plot(
        x,
        [v / len(x) for v in y]
    )

    plt.xlabel("final step")
    plt.ylabel("CDF")
    plt.title("Final step cumulative distribution")

    plt.grid(True)

    plt.tight_layout()

    plt.savefig(
        f"{out_prefix}_final_step_cdf.png",
        dpi=300
    )

    plt.close()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True
    )

    parser.add_argument(
        "--out-prefix",
        required=True
    )

    args = parser.parse_args()

    plot_final_step_hist(
        args.input,
        args.out_prefix
    )

    plot_final_step_cdf(
        args.input,
        args.out_prefix
    )


if __name__ == "__main__":
    main()