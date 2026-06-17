import argparse
import glob
import re

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


def extract_L(filename):
    match = re.search(r"L_(\d+)", filename)
    return int(match.group(1))


def compute_S(sizes):
    # 最大クラスタ除く
    sizes = sizes[1:]

    numerator = (sizes**2).sum()
    denominator = sizes.sum()

    if denominator == 0:
        return 0

    return numerator / denominator


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, default="data")
    parser.add_argument("--dim", type=int, choices=[2, 3], default=2)
    args = parser.parse_args()

    data_dir = Path(args.root) / f"{args.dim}d"/"size_sweep_cluster_sizes"

    files = sorted(
        glob.glob(f"{data_dir}/cluster_sizes_L_*.csv"),
        key=extract_L
    )

    L_list = []
    S_list = []

    for file in files:
        L = extract_L(file)
        df = pd.read_csv(file)

        sizes = df["size"].values

        S = compute_S(sizes)

        L_list.append(L)
        S_list.append(S)

        print(f"L={L}, S={S:.3f}")

    plt.figure()

    plt.loglog(L_list, S_list, marker="o")

    plt.xlabel("L")
    plt.ylabel("Mean cluster size S")
    plt.title(f"Mean cluster size ({args.dim}D)")

    plt.grid(True, which="both")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()