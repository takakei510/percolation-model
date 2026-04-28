import argparse
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file",
        type=str,
        default="data/cluster_coords.csv",
        help="Path to cluster_coords CSV"
    )
    args = parser.parse_args()

    csv_path = Path(args.file)

    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return

    df = pd.read_csv(csv_path)

    print("csv path =", csv_path)
    print("columns =", df.columns.tolist())

    if {"x", "y", "z"}.issubset(df.columns):
        fig = plt.figure(figsize=(8, 6))
        ax = fig.add_subplot(111, projection="3d")

        for rank in sorted(df["cluster_rank"].unique()):
            group = df[df["cluster_rank"] == rank]

            if rank == 1:
                ax.scatter(group["x"], group["y"], group["z"],
                           s=4, color="tab:blue", alpha=0.45)
            elif rank == 2:
                ax.scatter(group["x"], group["y"], group["z"],
                           s=4, color="red", alpha=0.65)

        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        ax.set_title("Largest and Second cluster (3D)")
        plt.tight_layout()
        plt.show()

    elif {"x", "y"}.issubset(df.columns):
        plt.figure(figsize=(6, 6))

        for rank in sorted(df["cluster_rank"].unique()):
            group = df[df["cluster_rank"] == rank]

            if rank == 1:
                plt.scatter(group["x"], group["y"],
                            s=8, color="tab:blue", alpha=0.45)
            elif rank == 2:
                plt.scatter(group["x"], group["y"],
                            s=8, color="red", alpha=0.75)

        plt.xlabel("x")
        plt.ylabel("y")
        plt.title("Largest and Second cluster (2D)")
        plt.gca().set_aspect("equal", adjustable="box")
        plt.tight_layout()
        plt.show()

    else:
        print("CSV format is not supported.")


if __name__ == "__main__":
    main()