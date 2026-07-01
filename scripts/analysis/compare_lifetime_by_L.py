import argparse
import os
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PATH_PATTERN = re.compile(
    r"^(?P<prefix>.*?)/(?P<dim>2d|3d)/random_walk/(?P<model>[^/]+)/(?P<case>[^/]+)/final_steps\.csv$"
)
CASE_PATTERN = re.compile(r"^L(?P<L>\d+)_N(?P<N>\d+)_T(?P<T>\d+)(?:_(?P<suffix>.+))?$")


def parse_metadata_from_path(path, model_override=None):
    normalized = os.path.normpath(path)
    match = PATH_PATTERN.search(normalized)
    if not match:
        raise ValueError(
            "Input path must match data/<dim>/random_walk/<model>/<case>/final_steps.csv: "
            f"{path}"
        )

    dim_name = match.group("dim")
    dim = int(dim_name[0])
    model = model_override or match.group("model")
    case = match.group("case")

    case_match = CASE_PATTERN.match(case)
    if not case_match:
        raise ValueError(f"Could not parse L/N/T metadata from case directory: {case}")

    metadata = {
        "dim_name": dim_name,
        "dim": dim,
        "model": model,
        "case": case,
        "L": int(case_match.group("L")),
        "N": int(case_match.group("N")),
        "T": int(case_match.group("T")),
    }
    return metadata


def _to_numeric_series(df, column):
    if column not in df.columns:
        return None
    series = pd.to_numeric(df[column], errors="coerce")
    if series.isna().all():
        return None
    return series.fillna(0)


def load_input(path, model_override=None):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")

    df = pd.read_csv(path)
    if "final_step" not in df.columns:
        raise ValueError(f"Input CSV {path} is missing required column: final_step")

    if df.empty:
        raise ValueError(f"Input CSV contains no rows: {path}")

    metadata = parse_metadata_from_path(path, model_override=model_override)

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

    trapped_series = _to_numeric_series(df, "trapped")
    boundary_dead_series = _to_numeric_series(df, "boundary_dead")
    contact_dead_series = _to_numeric_series(df, "contact_dead")

    trapped_count = int(trapped_series.sum()) if trapped_series is not None else 0
    boundary_dead_count = int(boundary_dead_series.sum()) if boundary_dead_series is not None else 0
    contact_dead_count = int(contact_dead_series.sum()) if contact_dead_series is not None else 0

    censored_count = int((final_step == int(metadata["T"])).sum())
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
        "trapped_count": trapped_count,
        "boundary_dead_count": boundary_dead_count,
        "contact_dead_count": contact_dead_count,
        "trapped_fraction": float(trapped_count / n_trials) if n_trials > 0 else 0.0,
        "boundary_dead_fraction": float(boundary_dead_count / n_trials) if n_trials > 0 else 0.0,
        "contact_dead_fraction": float(contact_dead_count / n_trials) if n_trials > 0 else 0.0,
        "censored_count": censored_count,
        "censored_fraction": censored_fraction,
        "source_file": path,
    }
    raw_df = pd.DataFrame(
        {
            "L": [metadata["L"]] * n_trials,
            "final_step": final_step.astype(float).values,
        }
    )
    return pd.Series(row), raw_df


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

    if fit_values is not None and y_key == "max_lifetime":
        fit_x = np.linspace(x.min(), x.max(), 200)
        fit_y = fit_values["A"] * fit_x ** fit_values["z"]
        plt.loglog(
            fit_x,
            fit_y,
            linestyle="--",
            color="gray",
            label=f"fit: z={fit_values['z']:.3f}",
        )

    pretty_name = y_key.replace("_", " ")
    plt.xlabel("L")
    plt.ylabel(pretty_name)
    plt.title(f"{pretty_name.title()} vs L")
    plt.grid(True, which="both")
    plt.tight_layout()

    suffix = f"{y_key}_vs_L"
    if loglog:
        suffix += "_loglog"
    out_path = f"{plot_prefix}_{suffix}.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    return out_path


def fit_max_lifetime(df):
    fit_df = df.copy()
    fit_df = fit_df[fit_df["L"] != ""].copy()
    fit_df["L"] = fit_df["L"].astype(float)
    fit_df["max_lifetime"] = fit_df["max_lifetime"].astype(float)
    fit_df = fit_df.dropna(subset=["L", "max_lifetime"])
    fit_df = fit_df[(fit_df["L"] > 0) & (fit_df["max_lifetime"] > 0)]

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

    return {
        "z": float(slope),
        "intercept": float(intercept),
        "A": float(np.exp(intercept)),
        "r2": r2,
        "n_points": int(len(fit_df)),
    }


def save_fit_csv(fit_values, output_path):
    fit_df = pd.DataFrame([fit_values])
    fit_df.to_csv(output_path, index=False)
    return output_path


def plot_final_step_hist_overlay(raw_df, plot_prefix, logy=False):
    plt.figure(figsize=(8, 5))
    unique_L = sorted(raw_df["L"].unique())
    cmap = plt.get_cmap("viridis")
    norm = plt.Normalize(vmin=0, vmax=max(len(unique_L) - 1, 1))

    final_steps = raw_df["final_step"].astype(float).values
    bins = np.arange(final_steps.min(), final_steps.max() + 2) - 0.5

    for idx, L in enumerate(unique_L):
        group = raw_df[raw_df["L"] == L]
        if group.empty:
            continue
        color = cmap(norm(idx))
        plt.hist(
            group["final_step"].astype(float),
            bins=bins,
            density=True,
            histtype="step",
            label=f"L={L}",
            color=color,
            alpha=0.7,
            linewidth=1.5,
        )

    plt.xlabel("final_step")
    plt.ylabel("Probability density")
    plt.title("Final step distribution")
    if logy:
        plt.yscale("log")
    plt.grid(True, which="both")
    plt.legend()
    plt.tight_layout()
    out_path = f"{plot_prefix}_final_step_hist_overlay"
    if logy:
        out_path += "_logy"
    out_path += ".png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    return out_path


def plot_final_step_survival_overlay(raw_df, plot_prefix, logy=False):
    plt.figure(figsize=(8, 5))
    unique_L = sorted(raw_df["L"].unique())
    cmap = plt.get_cmap("viridis")
    norm = plt.Normalize(vmin=0, vmax=max(len(unique_L) - 1, 1))

    for idx, L in enumerate(unique_L):
        group = raw_df[raw_df["L"] == L]["final_step"].astype(int)
        if group.empty:
            continue
        max_t = int(group.max())
        counts = np.bincount(group, minlength=max_t + 1)
        survival = np.cumsum(counts[::-1])[::-1].astype(float) / len(group)
        t_values = np.arange(len(survival))
        color = cmap(norm(idx))
        plt.plot(
            t_values,
            survival,
            marker="o",
            linestyle="-",
            label=f"L={L}",
            color=color,
            alpha=0.7,
            linewidth=1.5,
        )

    plt.xlabel("t")
    plt.ylabel("Survival probability")
    plt.title("Final step survival")
    if logy:
        plt.yscale("log")
    plt.grid(True, which="both")
    plt.legend()
    plt.tight_layout()
    out_path = f"{plot_prefix}_final_step_survival_overlay"
    if logy:
        out_path += "_logy"
    out_path += ".png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    return out_path


def plot_final_step_boxplot(raw_df, plot_prefix):
    plt.figure(figsize=(8, 5))
    unique_L = sorted(raw_df["L"].unique())
    groups = [raw_df[raw_df["L"] == L]["final_step"].astype(float).values for L in unique_L]

    plt.boxplot(groups, labels=[str(L) for L in unique_L], patch_artist=True, boxprops={"linewidth": 1.2})
    plt.xlabel("L")
    plt.ylabel("final_step")
    plt.title("Final step distribution by L")
    plt.grid(True, which="both")
    plt.tight_layout()
    out_path = f"{plot_prefix}_final_step_boxplot.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    return out_path


def build_summary_dataframe(input_paths, model_override=None):
    rows = []
    raw_rows = []
    for input_path in input_paths:
        summary_row, raw_df = load_input(input_path, model_override=model_override)
        rows.append(summary_row)
        raw_rows.append(raw_df)

    if not rows:
        raise ValueError("No valid input files were loaded.")

    combined = pd.DataFrame(rows)
    if combined.empty:
        raise ValueError("No valid summary rows were loaded from inputs.")

    raw_combined = pd.concat(raw_rows, ignore_index=True)
    if raw_combined.empty:
        raise ValueError("No valid raw distribution rows were loaded from inputs.")

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
        "trapped_count",
        "boundary_dead_count",
        "contact_dead_count",
        "trapped_fraction",
        "boundary_dead_fraction",
        "contact_dead_fraction",
        "censored_count",
        "censored_fraction",
        "source_file",
    ]
    combined = combined.reindex(columns=columns)
    return combined, raw_combined


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--plot-prefix", required=True)
    parser.add_argument("--model")
    parser.add_argument("--fit-max", action="store_true")
    parser.add_argument("--plot-distribution", action="store_true", default=False)
    args = parser.parse_args()

    combined, raw_combined = build_summary_dataframe(args.inputs, model_override=args.model)
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
        plot_paths[-1] = plot_vs_L(combined, "max_lifetime", args.plot_prefix, loglog=True, fit_values=fit_values)

    for path in plot_paths:
        print(f"Saved: {path}")

    if args.plot_distribution:
        dist_paths = []
        dist_paths.append(plot_final_step_hist_overlay(raw_combined, args.plot_prefix, logy=False))
        dist_paths.append(plot_final_step_hist_overlay(raw_combined, args.plot_prefix, logy=True))
        dist_paths.append(plot_final_step_survival_overlay(raw_combined, args.plot_prefix, logy=False))
        dist_paths.append(plot_final_step_survival_overlay(raw_combined, args.plot_prefix, logy=True))
        dist_paths.append(plot_final_step_boxplot(raw_combined, args.plot_prefix))
        for path in dist_paths:
            print(f"Saved: {path}")

    if args.fit_max and fit_path is None:
        raise ValueError("Max lifetime fitting failed.")


if __name__ == "__main__":
    main()
