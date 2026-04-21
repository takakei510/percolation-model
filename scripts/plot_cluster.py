import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


def main():
    csv_path = Path("data/cluster_coords.csv")
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return

    df = pd.read_csv(csv_path)

    print("csv path =",csv_path)
    print("columns =",df.columns.tolist())

    if {"x", "y", "z"}.issubset(df.columns):
        fig = plt.figure(figsize=(8, 6))
        ax = fig.add_subplot(111, projection="3d")

        for rank in sorted(df["cluster_rank"].unique()):
            group =df[df["cluster_rank"] == rank]

            if rank == 1:
                ax.scatter(
                    group["x"],group["y"],group["z"],
                    s=4,
                    color="tab:blue",
                    alpha=0.45,
                    label="Largest cluster"
                )
            elif rank == 2:
                ax.scatter(
                    group["x"],group["y"],group["z"],
                    s=4,
                    color="red",
                    alpha=0.75,
                    label="Second cluster"
                )                

        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        ax.set_title("Largest and Second cluster (3D)")
        ax.legend()
        plt.tight_layout()
        plt.show()

    elif {"x", "y"}.issubset(df.columns):
        plt.figure(figsize=(6, 6))

        for rank in sorted(df["cluster_rank"].unique()):
            group =df[df["cluster_rank"] == rank]

            if rank == 1:
                plt.scatter(
                    group["x"],group["y"],
                    s=8,
                    color="tab:blue",
                    alpha=0.45,
                    label="Largest cluster"
                )
            elif rank == 2:
                plt.scatter(
                    group["x"],group["y"],
                    s=8,
                    color="red",
                    alpha=0.75,
                    label="Second cluster"
                )

        plt.xlabel("x")
        plt.ylabel("y")
        plt.title("Largest and Second cluster (2D)")
        plt.gca().set_aspect("equal", adjustable="box")
        plt.legend()
        plt.tight_layout()
        plt.show()

    else:
        print("CSV format is not supported. Expected x,y or x,y,z columns.")


if __name__ == "__main__":
    main()