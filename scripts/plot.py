import matplotlib
matplotlib.use("TkAgg")

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


def detect_columns(df: pd.DataFrame) -> tuple[str, str]:
    """
    summary.csv の列名を判定して、
    largest / second に対応する列名を返す。
    """
    if "mean_largest" in df.columns and "mean_second" in df.columns:
        return "mean_largest", "mean_second"
    if "largest_size" in df.columns and "second_size" in df.columns:
        return "largest_size", "second_size"

    raise ValueError(
        "CSV does not contain expected cluster columns. "
        "Expected either (mean_largest, mean_second) or (largest_size, second_size)."
    )


def main() -> None:
    csv_path = Path("data/summary.csv")

    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return

    df = pd.read_csv(csv_path)

    required_base_columns = {"p", "n_sites"}
    missing_base = required_base_columns - set(df.columns)
    if missing_base:
        print(f"Missing columns in CSV: {sorted(missing_base)}")
        return

    try:
        largest_col, second_col = detect_columns(df)
    except ValueError as e:
        print(str(e))
        return

    # 念のため p でソート
    df = df.sort_values("p")

    # 正規化列を作成
    df["largest_ratio"] = df[largest_col] / df["n_sites"]
    df["second_ratio"] = df[second_col] / df["n_sites"]

    # --------------------------------------------------
    # 1. 絶対値グラフ（右軸で第2連結成分）
    # --------------------------------------------------
    fig, ax1 = plt.subplots()

    # 最大クラスタ（左軸）
    ax1.plot(
        df["p"],
        df[largest_col],
        color="tab:blue",
        marker="o",
        linestyle="-",
        label="largest cluster"
    )
    ax1.set_xlabel("p")
    ax1.set_ylabel("largest cluster size", color="tab:blue")
    ax1.tick_params(axis="y", labelcolor="tab:blue")
    ax1.grid(True)

    # 第2クラスタ（右軸）
    ax2 = ax1.twinx()
    ax2.plot(
        df["p"],
        df[second_col],
        color="tab:orange",
        marker="s",
        linestyle="--",
        label="second cluster"
    )
    ax2.set_ylabel("second cluster size", color="tab:orange")
    ax2.tick_params(axis="y", labelcolor="tab:orange")

    # 凡例まとめ
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    plt.title("Largest and second cluster vs p")
    plt.tight_layout()
    plt.show()

    # --------------------------------------------------
    # 2. 正規化グラフ
    # --------------------------------------------------
# --------------------------------------------------
# 正規化グラフ（右軸付き）
# --------------------------------------------------
    fig, ax1 = plt.subplots()

    # 最大クラスタ（左軸）
    ax1.plot(
        df["p"],
        df["largest_ratio"],
        color="tab:blue",
        marker="o",
        linestyle="-",
        label="largest / n_sites"
    )
    ax1.set_xlabel("p")
    ax1.set_ylabel("largest / n_sites", color="tab:blue")
    ax1.tick_params(axis="y", labelcolor="tab:blue")
    ax1.grid(True)

    # 第2クラスタ（右軸）
    ax2 = ax1.twinx()
    ax2.plot(
        df["p"],
        df["second_ratio"],
        color="tab:orange",
        marker="s",
        linestyle="--",
        label="second / n_sites"
    )
    ax2.set_ylabel("second / n_sites", color="tab:orange")
    ax2.tick_params(axis="y", labelcolor="tab:orange")

    # 凡例まとめ
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    plt.title("Normalized cluster sizes vs p")
    plt.tight_layout()
    plt.show()
    # --------------------------------------------------
    # 3. 第2連結成分だけの単独グラフ
    # --------------------------------------------------
    '''
    plt.figure()
    plt.plot(
        df["p"],
        df[second_col],
        marker="o"
    )
    plt.xlabel("p")
    plt.ylabel("second cluster size")
    plt.title("Second cluster vs p")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # --------------------------------------------------
    # 4. 第2連結成分の正規化単独グラフ
    # --------------------------------------------------
    plt.figure()
    plt.plot(
        df["p"],
        df["second_ratio"],
        marker="o"
    )
    plt.xlabel("p")
    plt.ylabel("second cluster / n_sites")
    plt.title("Normalized second cluster vs p")
    plt.grid(True)
    plt.tight_layout()
    plt.show()
    '''

if __name__ == "__main__":
    main()