import argparse
import os
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


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

    return {
        "dim_name": dim_name or "",
        "dim": dim if dim is not None else "",
        "model": model,
        "case": case,
        "L": L if L is not None else "",
        "N": N if N is not None else "",
        "T": T if T is not None else "",
    }


def load_input(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")

    df = pd.read_csv(path)
    if "final_step" not in df.columns:
        raise ValueError(f"Input CSV {path} is missing required column: final_step")

    if df.empty:
        raise ValueError(f"Input CSV contains no rows: {path}")

    metadata = parse_metadata_from_path(path)
    if metadata["L"] == "" or metadata["T"] == "":
        raise ValueError(f"Could not parse L/T metadata from path: {path}")

    final_step = pd.to_numeric(df["final_step"], errors="coerce")
    if final_step.isna().any():
        raise ValueError(f"Input CSV {path} contains invalid final_step values")

    n_trials = int(len(final_step))
    mean_lifetime = float(final_step.mean())
    std_lifetime = float(final_step.std())
    min_lifetime = float(final_step.min())
    max_lifetime = float(final_step.max())
    median_lifetime = float(final_step.median())
    q25_lifetime = float(final_step.quantile(0.25))
    q75_lifetime = float(final_step.quantile(0.75))

    censored_count = int((final_step == int(metadata["T"])) .sum())
    censored_fraction = float(censored_count / n_trials) if n_trials > 0 else 0.0

    row = {
        "dim_name": metadata["dim_name"],
        "dim": metadata["dim"],
        "model": metadata["model"],
        "case": metadata["case"],
        "L": metadata["L"],
        "N": metadata["N"],
        "T": metadata["T"],
        "n_trials": n_trials,
        "mean_lifetime": mean_lifetime,
        "std_lifetime": std_lifetime,
        "min_lifetime": min_lifetime,
        "max_lifetime": max_lifetime,
        "median_lifetime": median_lifetime,
        "q25_lifetime": q25_lifetime,
        "q75_lifetime": q75_lifetime,
        "censored_count": censored_count,
        "censored_fraction": censored_fraction,
        "source_file": path,
    }
    return pd.Series(row)


def plot_vs_L(df, y_key, plot_prefix, loglog=False, fit_values=None):
    plot_df = df.copy()
    plot_df = plot_df[plot_df["L"] != ""].copy()
    plot_df["L"] = plot_df["L"].astype(float)
    plot_df = plot_df.sort_values(by="L")

    x = plot_df["L"].values
    y = plot_df[y_key].astype(float).values

    plt.figure(figsize=(8, 5))
    if loglog:
        plt.loglog(x, y, marker="o", linestyle="-", label=y_key)
    else:
        plt.plot(x, y, marker="o", linestyle="-", label=y_key)

    if fit_values is not None:
        fit_x = np.linspace(x.min(), x.max(), 200)
        fit_y = fit_values["A"] * fit_x ** fit_values["z"]
        plt.loglog(fit_x, fit_y, linestyle="--", color="gray", label=f"fit: z={fit_values['z']:.3f}")

    plt.xlabel("L")
    plt.ylabel(y_key.replace("_", " "))
    plt.title(f"{y_key.replace('_', ' ').title()} vs L")
    plt.grid(True)
    plt.tight_layout()
    out_path = f"{plot_prefix}_{y_key}_vs_L"
    out_path += ".png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    return out_path


def fit_max_lifetime(df):
    fit_df = df.copy()
    fit_df = fit_df[fit_df["L"] != ""].copy()
    fit_df["L"] = fit_df["L"].astype(float)
    fit_df["max_lifetime"] = fit_df["max_lifetime"].astype(float)
    fit_df = fit_df.dropna(subset=["L", "max_lifetime"])

    if len(fit_df) < 2:
        raise ValueError("Need at least 2 valid points to fit max lifetime.")

    x = fit_df["L"].values
    y = fit_df["max_lifetime"].values
    log_x = np.log(x)
    log_y = np.log(y)

    slope, intercept = np.polyfit(log_x, log_y, 1)
    predicted = slope * log_x + intercept
    ss_res = np.sum((log_y - predicted) ** 2)
    ss_tot = np.sum((log_y - np.mean(log_y)) ** 2)
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot != 0 else 0.0
    A = float(np.exp(intercept))

    return {
        "z": float(slope),
        "intercept": float(intercept),
        "A": A,
        "r2": r2,
        "n_points": int(len(fit_df)),
    }


def save_fit_csv(fit_values, output_path):
    fit_df = pd.DataFrame([fit_values])
    fit_df.to_csv(output_path, index=False)
    return output_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--plot-prefix", required=True)
    parser.add_argument("--fit-max", action="store_true")
    args = parser.parse_args()

    rows = []
    for input_path in args.inputs:
        rows.append(load_input(input_path))

    if not rows:
        raise ValueError("No valid input files were loaded.")

    combined = pd.DataFrame(rows)
    if combined.empty:
        raise ValueError("No valid summary rows were loaded from inputs.")

    combined = combined.sort_values(by="L")
    columns = [
        "dim_name",
        "dim",
        "model",
        "case",
        "L",
        "N",
        "T",
        "n_trials",
        "mean_lifetime",
        "std_lifetime",
        "min_lifetime",
        "max_lifetime",
        "median_lifetime",
        "q25_lifetime",
        "q75_lifetime",
        "censored_count",
        "censored_fraction",
        "source_file",
    ]
    combined = combined.reindex(columns=columns)
    combined.to_csv(args.output_csv, index=False)
    print(f"Saved: {args.output_csv}")

    plot_paths = []
    plot_paths.append(plot_vs_L(combined, "mean_lifetime", args.plot_prefix, loglog=False))
    plot_paths.append(plot_vs_L(combined, "max_lifetime", args.plot_prefix, loglog=False))
    plot_paths.append(plot_vs_L(combined, "mean_lifetime", args.plot_prefix, loglog=True))
    plot_paths.append(plot_vs_L(combined, "max_lifetime", args.plot_prefix, loglog=True))

    fit_values = None
    fit_path = None
    if args.fit_max:
        fit_values = fit_max_lifetime(combined)
        fit_path = save_fit_csv(fit_values, f"{args.plot_prefix}_max_lifetime_fit.csv")
        print(f"Saved: {fit_path}")
        # re-save the loglog max plot with fit line included
        plot_paths[-1] = plot_vs_L(combined, "max_lifetime", args.plot_prefix, loglog=True, fit_values=fit_values)

    for path in plot_paths:
        print(f"Saved: {path}")

    if args.fit_max and fit_path is None:
        raise ValueError("Max lifetime fitting failed.")


if __name__ == "__main__":
    main()
