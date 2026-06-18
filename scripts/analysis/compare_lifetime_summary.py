import argparse
import os
import re

import matplotlib.pyplot as plt
import pandas as pd


REQUIRED_COLUMNS = [
    "mean_lifetime",
    "p",
    "censored_count",
    "censored_fraction",
]


def parse_metadata_from_path(path):
    path = os.path.normpath(path)
    parts = path.split(os.sep)

    dim_name = None
    if "2d" in parts:
        dim_name = "2d"
    elif "3d" in parts:
        dim_name = "3d"

    dim = None
    if dim_name is not None:
        dim = int(dim_name[0])

    case = ""
    model = ""
    L = None
    N = None
    T = None

    if "random_walk" in parts:
        rw_index = parts.index("random_walk")
        if len(parts) > rw_index + 3:
            model = parts[rw_index + 1]
            case = parts[rw_index + 2]
        elif len(parts) > rw_index + 2:
            case = parts[rw_index + 1]

    if case:
        pattern = re.compile(
            r"^L(?P<L>\d+)_N(?P<N>\d+)_T(?P<T>\d+)(?:_(?P<model>.+))?$"
        )
        match = pattern.match(case)
        if match:
            L = int(match.group("L"))
            N = int(match.group("N"))
            T = int(match.group("T"))
            inferred_model = match.group("model") or ""
            if not model:
                model = inferred_model
        else:
            model = model or ""

    return {
        "dim_name": dim_name or "",
        "dim": dim if dim is not None else "",
        "case": case,
        "L": L if L is not None else "",
        "N": N if N is not None else "",
        "T": T if T is not None else "",
        "model": model,
    }


def load_summary(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")

    df = pd.read_csv(path)
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"Input CSV {path} is missing required columns: {', '.join(missing)}"
        )

    if df.empty:
        raise ValueError(f"Input CSV contains no rows: {path}")

    metadata = parse_metadata_from_path(path)
    result = df.copy()

    for key, value in metadata.items():
        result[key] = value

    result["source_file"] = path

    # ensure optional columns are present for consistent output
    for optional in ["std_lifetime", "max_lifetime", "mean_geometric"]:
        if optional not in result.columns:
            result[optional] = ""

    return result


def plot_comparison(df, x_key, plot_prefix):
    if x_key not in ["L", "dim", "case"]:
        raise ValueError("x must be one of: L, dim, case")

    plot_df = df.copy()
    x_label = x_key

    if x_key in ["L", "dim"]:
        plot_df = plot_df[plot_df[x_key] != ""].copy()
        plot_df[x_key] = plot_df[x_key].astype(float)
        plot_df = plot_df.sort_values(by=x_key)
        x_values = plot_df[x_key].values
        x_ticks = None
    else:
        plot_df = plot_df.reset_index(drop=True)
        x_values = plot_df.index.values
        x_ticks = plot_df[x_key].astype(str).values

    def save_plot(y_key, y_label):
        plt.figure(figsize=(8, 5))
        plt.plot(x_values, plot_df[y_key].astype(float), marker="o", linestyle="-", label=y_label)
        plt.xlabel(x_label)
        plt.ylabel(y_label)
        plt.title(f"{y_label} vs {x_label}")
        plt.grid(True)
        if x_ticks is not None:
            plt.xticks(ticks=x_values, labels=x_ticks, rotation=45, ha="right")
        plt.tight_layout()
        out_path = f"{plot_prefix}_{y_key}_vs_{x_key}.png"
        plt.savefig(out_path, dpi=300)
        plt.close()
        return out_path

    return [
        save_plot("mean_lifetime", "Mean lifetime"),
        save_plot("p", "Geometric death probability p"),
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--plot-prefix")
    parser.add_argument(
        "--x",
        choices=["L", "dim", "case"],
        default="L",
        help="X-axis field for plots",
    )
    args = parser.parse_args()

    rows = []
    for input_path in args.inputs:
        rows.append(load_summary(input_path))

    if not rows:
        raise ValueError("No valid summary rows were loaded from inputs.")

    combined = pd.concat(rows, ignore_index=True)

    if combined.empty:
        raise ValueError("No valid summary rows were loaded from inputs.")

    columns = [
        "dim_name",
        "dim",
        "case",
        "L",
        "N",
        "T",
        "model",
        "mean_lifetime",
        "std_lifetime",
        "max_lifetime",
        "p",
        "mean_geometric",
        "censored_count",
        "censored_fraction",
        "source_file",
    ]
    combined = combined.reindex(columns=columns)
    combined.to_csv(args.output_csv, index=False)
    print(f"Saved: {args.output_csv}")

    if args.plot_prefix:
        plot_paths = plot_comparison(combined, args.x, args.plot_prefix)
        for path in plot_paths:
            print(f"Saved: {path}")


if __name__ == "__main__":
    main()
