import matplotlib
matplotlib.use('TkAgg')

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


def main() -> None:
    csv_path = Path("data/summary.csv")

    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return

    df = pd.read_csv(csv_path)

    required_columns = {
        "p",
        "n_sites",
        "largest_size",
        "second_size",
    }
    missing = required_columns - set(df.columns)
    if missing:
        print(f"Missing columns in CSV: {sorted(missing)}")
        return

    # 正規化列を追加
    df["largest_ratio"] = df["largest_size"] / df["n_sites"]
    df["second_ratio"] = df["second_size"] / df["n_sites"]

    # pでソート（念のため）
    df = df.sort_values("p")

    # 最大・第2クラスタサイズ
    plt.figure()
    plt.plot(df["p"], df["largest_size"], marker="o", label="largest cluster")
    plt.plot(df["p"], df["second_size"], marker="o", label="second cluster")
    plt.xlabel("p")
    plt.ylabel("cluster size")
    plt.title("Cluster size vs p")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # 正規化版
    plt.figure()
    plt.plot(df["p"], df["largest_ratio"], marker="o", label="largest / n_sites")
    plt.plot(df["p"], df["second_ratio"], marker="o", label="second / n_sites")
    plt.xlabel("p")
    plt.ylabel("normalized cluster size")
    plt.title("Normalized cluster size vs p")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()