import matplotlib
matplotlib.use("TkAgg")

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


def main():
    csv_path = Path("data/summary.csv")
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return

    df = pd.read_csv(csv_path)
    df = df.sort_values("p")

    required_columns = {
        "p",
        "n_sites",
        "mean_largest",
        "mean_second",
        "std_largest",
        "std_second",
    }
    missing = required_columns - set(df.columns)
    if missing:
        print(f"Missing columns in CSV: {sorted(missing)}")
        return

    # 正規化
    df["largest_ratio"] = df["mean_largest"] / df["n_sites"]
    df["second_ratio"] = df["mean_second"] / df["n_sites"]
    df["std_largest_ratio"] = df["std_largest"] / df["n_sites"]
    df["std_second_ratio"] = df["std_second"] / df["n_sites"]

    # ==============================
    # ① 第2クラスタ（正規化, エラーバー）
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
    # ② 正規化（両方, 右軸）
    # ==============================
    fig, ax1 = plt.subplots(figsize=(8, 5))

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

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2)

    plt.title("Normalized cluster sizes vs p (with error bars)")
    plt.tight_layout()
    plt.show()

    # ==============================
    # ③ 臨界点ズーム（自動ピーク検出 + 帯表示）
    # ==============================
    peak_idx = df["second_ratio"].idxmax()
    peak_p = df.loc[peak_idx, "p"]

    zoom_width = 0.015
    df_zoom = df[(df["p"] >= peak_p - zoom_width) & (df["p"] <= peak_p + zoom_width)]

    # 点数が少なすぎる場合は案内だけ出す
    if len(df_zoom) < 8:
        print(
            f"[zoom skipped] Only {len(df_zoom)} points around p={peak_p:.3f}. "
            "Use a finer config (for example dp=0.002 or 0.001) to get a useful zoom plot."
        )
    else:
        plt.figure(figsize=(8, 5))

        plt.plot(
            df_zoom["p"],
            df_zoom["second_ratio"],
            color="tab:red",
            linewidth=2,
            marker="o",
            markersize=4,
            label=f"Second cluster (zoom around p={peak_p:.3f})"
        )

        lower = df_zoom["second_ratio"] - df_zoom["std_second_ratio"]
        upper = df_zoom["second_ratio"] + df_zoom["std_second_ratio"]

        plt.fill_between(
            df_zoom["p"],
            lower,
            upper,
            color="tab:red",
            alpha=0.2,
            label="±1 std"
        )

        plt.xlabel("p")
        plt.ylabel("second / n_sites")
        plt.title("Critical region (zoom)")
        plt.grid(True)
        plt.legend()

        ymax = upper.max()
        plt.ylim(bottom=0, top=ymax * 1.1)

        plt.tight_layout()
        plt.show()

if __name__ == "__main__":
    main()