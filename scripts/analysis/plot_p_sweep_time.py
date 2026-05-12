import argparse
import pandas as pd
import matplotlib.pyplot as plt

from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, default="data")
    parser.add_argument("--dim",type=int,choices=[2, 3],default=2)
    parser.add_argument("--mode",choices=["step", "total"],default="total")

    args = parser.parse_args()

    data_dir = Path(args.root) / f"{args.dim}d"/"p_sweep_time"
    
    series = []

    for filename, label in [
        ("bfs.csv", "BFS"),
        ("bfs_fast.csv", "BFS fast"),
        ("union_find.csv", "Union-Find"),
    ]:
        path = data_dir / filename

        if path.exists():
            df = pd.read_csv(path)
            series.append((df, label))
            print(f"Loaded: {path}")
        else:
            print(f"Skipped: {path}")

    plt.figure(figsize=(7, 5))

    if args.mode == "step":
        y = "step_time"
        ylabel = "Step time [sec]"
        title = f"Step time vs p ({args.dim}D)"
    else:
        y = "total_time"
        ylabel = "Cumulative time [sec]"
        title = f"Cumulative time vs p ({args.dim}D)"

    for df, label in series:
        plt.plot(
            df["p"],
            df[y],
            marker="o",
            markersize=3,
            linewidth=1.5,
            label=label
        )

    plt.xlabel("p")
    plt.ylabel(ylabel)

    plt.title(title)

    plt.grid(True)

    plt.legend()

    plt.tight_layout()

    plt.show()


if __name__ == "__main__":
    main()