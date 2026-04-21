import matplotlib
matplotlib.use("TkAgg")

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


def main():
    df = pd.read_csv("data/summary.csv")
    df = df.sort_values("p")

    # 正規化
    df["largest_ratio"] = df["mean_largest"] / df["n_sites"]
    df["second_ratio"] = df["mean_second"] / df["n_sites"]

    df["std_largest_ratio"] = df["std_largest"] / df["n_sites"]
    df["std_second_ratio"] = df["std_second"] / df["n_sites"]

    # ==============================
    # ① 第2クラスタ（メイン）
    # ==============================
    plt.figure(figsize=(8, 5))

    plt.errorbar(
        df["p"],
        df["second_ratio"],
        yerr=df["std_second_ratio"],
        fmt="o-",
        markersize=4,
        capsize=3,
        linewidth=1.5,
        label="Second cluster (normalized)"
    )

    plt.xlabel("p")
    plt.ylabel("second / n_sites")
    plt.title("Second cluster (normalized) with error bars")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

    # ==============================
    # ② 正規化（両方）
    # ==============================
    fig, ax1 = plt.subplots(figsize=(8, 5))

    # 最大クラスタ
    ax1.errorbar(
        df["p"],
        df["largest_ratio"],
        yerr=df["std_largest_ratio"],
        fmt="o-",
        color="tab:blue",
        markersize=4,
        capsize=3,
        linewidth=1.5,
        label="Largest / n_sites"
    )

    ax1.set_xlabel("p")
    ax1.set_ylabel("largest / n_sites", color="tab:blue")
    ax1.tick_params(axis="y", labelcolor="tab:blue")
    ax1.grid(True)

    # 第2クラスタ（右軸）
    ax2 = ax1.twinx()

    ax2.errorbar(
        df["p"],
        df["second_ratio"],
        yerr=df["std_second_ratio"],
        fmt="s--",
        color="tab:orange",
        markersize=4,
        capsize=3,
        linewidth=1.2,
        label="Second / n_sites"
    )

    ax2.set_ylabel("second / n_sites", color="tab:orange")
    ax2.tick_params(axis="y", labelcolor="tab:orange")

    # 凡例
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2)

    plt.title("Normalized cluster sizes vs p (with error bars)")
    plt.tight_layout()
    plt.show()

    # ==============================
    # ③ 臨界点ズーム（超重要）
    # ==============================
    df_zoom = df[(df["p"] >= 0.28) & (df["p"] <= 0.34)]

    plt.figure(figsize=(8, 5))

    plt.errorbar(
        df_zoom["p"],
        df_zoom["second_ratio"],
        yerr=df_zoom["std_second_ratio"],
        fmt="o-",
        markersize=5,
        capsize=4,
        linewidth=2,
        color="tab:red",
        label="Second cluster (zoom)"
    )

    plt.xlabel("p")
    plt.ylabel("second / n_sites")
    plt.title("Critical region (zoom)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()