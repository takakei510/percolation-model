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

    if "random_walk" not in parts:
        raise ValueError(f"Input path must include 'random_walk': {path}")

    rw_index = parts.index("random_walk")
    model = ""
    case = ""

    if len(parts) > rw_index + 3:
        model = parts[rw_index + 1]
        case = parts[rw_index + 2]
    elif len(parts) > rw_index + 2:
        case = parts[rw_index + 1]

    if not case:
        raise ValueError(f"Could not infer case from path: {path}")

    pattern = re.compile(
        r"^L(?P<L>\d+)_N(?P<N>\d+)_T(?P<T>\d+)(?:_(?P<model>.+))?$"
    )
    match = pattern.match(case)
    if not match:
        raise ValueError(
            f"Case name does not match expected format L<digits>_N<digits>_T<digits>[_{model}]: {case}"
        )

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
        "L": L,
        "N": N,
        "T": T,
    }


def compute_local_exponent(step, value, window):
    step = step.astype(float)
    value = value.astype(float)
    alpha = pd.Series([float("nan")] * len(step), index=step.index)

    if len(step) < 2 * window + 1:
        return alpha

    log_step = np.log(step)
    log_value = np.log(value)

    for i in range(window, len(step) - window):
        if step.iloc[i - window] <= 0 or step.iloc[i + window] <= 0:
            continue
        if value.iloc[i - window] <= 0 or value.iloc[i + window] <= 0:
            continue

        denom = log_step.iloc[i + window] - log_step.iloc[i - window]
        if denom == 0:
            continue

        alpha.iloc[i] = (
            log_value.iloc[i + window] - log_value.iloc[i - window]
        ) / denom

    return alpha


def load_input(path, quantity, window, min_alive):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")

    df = pd.read_csv(path)
    missing = [col for col in (["step", quantity]) if col not in df.columns]
    if missing:
        raise ValueError(
            f"Input CSV {path} is missing required columns: {', '.join(missing)}"
        )

    metadata = parse_metadata_from_path(path)

    df = df.copy()
    df = df[df["step"] > 0]
    df = df[df[quantity] > 0]

    if df.empty:
        raise ValueError(f"No valid data found in input file: {path}")

    df = df.sort_values("step").reset_index(drop=True)
    df["quantity"] = quantity
    df["value"] = df[quantity].astype(float)

    if "n_alive" in df.columns:
        df["n_alive"] = df["n_alive"].astype(float)
    else:
        df["n_alive"] = float("nan")

    df["local_exponent"] = compute_local_exponent(df["step"], df["value"], window)

    if min_alive is not None:
        df.loc[df["n_alive"] < min_alive, "local_exponent"] = float("nan")

    for key, value in metadata.items():
        df[key] = value

    return df[[
        "dim_name",
        "dim",
        "model",
        "case",
        "L",
        "N",
        "T",
        "step",
        "quantity",
        "value",
        "n_alive",
        "local_exponent",
    ]]


def plot_msd(df, plot_prefix, quantity, highlight_L):
    plt.figure(figsize=(8, 5))
    unique_L = sorted(df["L"].unique())
    cmap = plt.get_cmap("viridis")
    norm = plt.Normalize(vmin=0, vmax=max(len(unique_L) - 1, 1))

    for idx, L in enumerate(unique_L):
        group = df[df["L"] == L]
        if group.empty:
            continue
        color = cmap(norm(idx))
        if L in highlight_L:
            alpha = 1.0
            linewidth = 3
        else:
            alpha = 0.25
            linewidth = 1
        plt.loglog(
            group["step"],
            group["value"],
            marker="o",
            linestyle="-",
            label=f"L={L}",
            color=color,
            alpha=alpha,
            linewidth=linewidth,
        )

    plt.xlabel("step")
    plt.ylabel(quantity)
    plt.title(f"{quantity} vs step")
    plt.legend()
    plt.grid(True, which="both")
    plt.tight_layout()
    out_path = f"{plot_prefix}_msd_vs_step_loglog.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    return out_path


def plot_local_exponent(df, plot_prefix, dim_name, suffix, logx=False, ylim=None, highlight_L=None):
    plt.figure(figsize=(8, 5))
    unique_L = sorted(df["L"].unique())
    cmap = plt.get_cmap("viridis")
    norm = plt.Normalize(vmin=0, vmax=max(len(unique_L) - 1, 1))

    for idx, L in enumerate(unique_L):
        group = df[df["L"] == L]
        if group.empty:
            continue
        color = cmap(norm(idx))
        if highlight_L is not None and L in highlight_L:
            alpha = 1.0
            linewidth = 3
        elif highlight_L is not None:
            alpha = 0.25
            linewidth = 1
        else:
            alpha = 0.5
            linewidth = 1.2

        if logx:
            plt.semilogx(
                group["step"],
                group["local_exponent"],
                marker="o",
                linestyle="-",
                label=f"L={L}",
                color=color,
                alpha=alpha,
                linewidth=linewidth,
            )
        else:
            plt.plot(
                group["step"],
                group["local_exponent"],
                marker="o",
                linestyle="-",
                label=f"L={L}",
                color=color,
                alpha=alpha,
                linewidth=linewidth,
            )

    plt.xlabel("step")
    plt.ylabel("local exponent")
    title = "Local exponent vs step"
    if suffix.startswith("local_exponent_zoom"):
        title = "Local exponent zoom vs step"
    plt.title(title)
    plt.axhline(1.0, color="black", linestyle=":", label="alpha=1.0")
    if dim_name == "2d":
        plt.axhline(1.5, color="gray", linestyle=":", label="alpha=1.5")
    if ylim is not None:
        plt.ylim(ylim)
    plt.legend()
    plt.grid(True, which="both")
    plt.tight_layout()
    out_path = f"{plot_prefix}_{suffix}.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--plot-prefix", required=True)
    parser.add_argument(
        "--quantity",
        default="mean_r2",
        choices=["mean_r2", "mean_r2_all", "mean_rg2"],
    )
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--min-step", type=int, default=1)
    parser.add_argument("--min-alive", type=int, default=10)
    parser.add_argument("--alpha-ymin", type=float, default=0.5)
    parser.add_argument("--alpha-ymax", type=float, default=2.2)
    parser.add_argument("--split-L", action="store_true", dest="split_L")
    parser.add_argument("--split-threshold", type=int, default=512)
    parser.add_argument(
        "--highlight-L",
        nargs="+",
        type=int,
        default=[64, 512, 8192],
        help="L values to highlight with stronger styling",
    )
    args = parser.parse_args()

    rows = []
    for input_path in args.inputs:
        df = load_input(input_path, args.quantity, args.window, args.min_alive)
        rows.append(df)

    if not rows:
        raise ValueError("No valid input files were loaded.")

    combined = pd.concat(rows, ignore_index=True)
    if combined.empty:
        raise ValueError("No valid rows were loaded from inputs.")

    combined = combined[combined["step"] >= args.min_step].copy()
    if combined.empty:
        raise ValueError("No rows remain after applying min-step filter.")

    combined = combined.sort_values(["L", "step"])
    combined.to_csv(args.output_csv, index=False)
    print(f"Saved: {args.output_csv}")

    msd_path = plot_msd(combined, args.plot_prefix, args.quantity, args.highlight_L)
    print(f"Saved: {msd_path}")
    dim_name = combined["dim_name"].iloc[0]

    local_path = plot_local_exponent(
        combined,
        args.plot_prefix,
        dim_name,
        "local_exponent_vs_step",
        logx=False,
        highlight_L=args.highlight_L,
    )
    print(f"Saved: {local_path}")

    local_logx_path = plot_local_exponent(
        combined,
        args.plot_prefix,
        dim_name,
        "local_exponent_vs_step_logx",
        logx=True,
        highlight_L=args.highlight_L,
    )
    print(f"Saved: {local_logx_path}")

    zoom_path = plot_local_exponent(
        combined,
        args.plot_prefix,
        dim_name,
        "local_exponent_zoom_vs_step",
        logx=False,
        ylim=(args.alpha_ymin, args.alpha_ymax),
        highlight_L=args.highlight_L,
    )
    print(f"Saved: {zoom_path}")

    zoom_logx_path = plot_local_exponent(
        combined,
        args.plot_prefix,
        dim_name,
        "local_exponent_zoom_vs_step_logx",
        logx=True,
        ylim=(args.alpha_ymin, args.alpha_ymax),
        highlight_L=args.highlight_L,
    )
    print(f"Saved: {zoom_logx_path}")

    if args.split_L:
        small_df = combined[combined["L"] <= args.split_threshold]
        large_df = combined[combined["L"] > args.split_threshold]

        small_path = plot_local_exponent(
            small_df,
            args.plot_prefix,
            dim_name,
            "local_exponent_zoom_smallL_vs_step",
            logx=False,
            ylim=(args.alpha_ymin, args.alpha_ymax),
            highlight_L=args.highlight_L,
        )
        print(f"Saved: {small_path}")

        large_path = plot_local_exponent(
            large_df,
            args.plot_prefix,
            dim_name,
            "local_exponent_zoom_largeL_vs_step",
            logx=False,
            ylim=(args.alpha_ymin, args.alpha_ymax),
            highlight_L=args.highlight_L,
        )
        print(f"Saved: {large_path}")

        small_logx_path = plot_local_exponent(
            small_df,
            args.plot_prefix,
            dim_name,
            "local_exponent_zoom_smallL_vs_step_logx",
            logx=True,
            ylim=(args.alpha_ymin, args.alpha_ymax),
            highlight_L=args.highlight_L,
        )
        print(f"Saved: {small_logx_path}")

        large_logx_path = plot_local_exponent(
            large_df,
            args.plot_prefix,
            dim_name,
            "local_exponent_zoom_largeL_vs_step_logx",
            logx=True,
            ylim=(args.alpha_ymin, args.alpha_ymax),
            highlight_L=args.highlight_L,
        )
        print(f"Saved: {large_logx_path}")


if __name__ == "__main__":
    main()
