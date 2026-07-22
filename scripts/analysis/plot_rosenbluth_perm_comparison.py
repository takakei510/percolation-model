#!/usr/bin/env python3
"""Plot Rosenbluth/PERM convergence and efficiency comparisons."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "n_tours",
    "ros_partition_sum_estimate_mean",
    "ros_partition_sum_estimate_std",
    "perm_partition_sum_estimate_mean",
    "perm_partition_sum_estimate_std",
    "ros_weighted_mean_r2_mean",
    "ros_weighted_mean_r2_std",
    "perm_weighted_mean_r2_mean",
    "perm_weighted_mean_r2_std",
    "ros_branch_weight_ess_mean",
    "ros_tour_weight_ess_mean",
    "perm_branch_weight_ess_mean",
    "perm_tour_weight_ess_mean",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare Rosenbluth and PERM convergence."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to the aggregated convergence CSV.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory in which PNG files are saved.",
    )
    parser.add_argument(
        "--walk-length",
        required=True,
        type=int,
        help="Maximum walk length N represented by the input CSV.",
    )
    parser.add_argument(
        "--n-seeds",
        type=int,
        default=5,
        help="Number of seeds used to construct the aggregate CSV.",
    )
    return parser.parse_args()


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")

    frame = pd.read_csv(path)

    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(
            "Required columns are missing:\n"
            + "\n".join(sorted(missing))
        )

    frame = frame.sort_values("n_tours").reset_index(drop=True)

    if (frame["n_tours"] <= 0).any():
        raise ValueError("n_tours must be positive.")

    return frame


def seed_mean_standard_error(
    standard_deviation: pd.Series,
    n_seeds: int,
) -> np.ndarray:
    if n_seeds < 2:
        return np.full(len(standard_deviation), np.nan)

    return standard_deviation.to_numpy(dtype=float) / np.sqrt(n_seeds)


def save_figure(fig: plt.Figure, output_path: Path) -> None:
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_partition_sum(
    frame: pd.DataFrame,
    output_dir: Path,
    n_seeds: int,
    walk_length: int,
) -> None:
    tours = frame["n_tours"].to_numpy(dtype=float)

    ros_mean = frame["ros_partition_sum_estimate_mean"].to_numpy(dtype=float)
    perm_mean = frame["perm_partition_sum_estimate_mean"].to_numpy(dtype=float)

    ros_se = seed_mean_standard_error(
        frame["ros_partition_sum_estimate_std"],
        n_seeds,
    )
    perm_se = seed_mean_standard_error(
        frame["perm_partition_sum_estimate_std"],
        n_seeds,
    )

    fig, ax = plt.subplots(figsize=(10, 7))

    ax.errorbar(
        tours,
        ros_mean,
        yerr=ros_se,
        marker="o",
        capsize=4,
        label="Rosenbluth",
    )
    ax.errorbar(
        tours,
        perm_mean,
        yerr=perm_se,
        marker="o",
        capsize=4,
        label="PERM",
    )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Number of tours")
    ax.set_ylabel(rf"Partition sum estimate $\hat{{Z}}_{{{walk_length}}}$")
    ax.set_title(f"Partition sum convergence at N={walk_length}")
    ax.grid(True, which="both", alpha=0.35)
    ax.legend()

    save_figure(
        fig,
        output_dir / "partition_sum_convergence.png",
    )


def plot_partition_sum_relative_uncertainty(
    frame: pd.DataFrame,
    output_dir: Path,
    n_seeds: int,
    walk_length: int,
) -> None:
    tours = frame["n_tours"].to_numpy(dtype=float)

    ros_mean = frame["ros_partition_sum_estimate_mean"].to_numpy(dtype=float)
    perm_mean = frame["perm_partition_sum_estimate_mean"].to_numpy(dtype=float)

    ros_se = seed_mean_standard_error(
        frame["ros_partition_sum_estimate_std"],
        n_seeds,
    )
    perm_se = seed_mean_standard_error(
        frame["perm_partition_sum_estimate_std"],
        n_seeds,
    )

    ros_relative_se = np.divide(
        ros_se,
        np.abs(ros_mean),
        out=np.full_like(ros_se, np.nan),
        where=ros_mean != 0,
    )
    perm_relative_se = np.divide(
        perm_se,
        np.abs(perm_mean),
        out=np.full_like(perm_se, np.nan),
        where=perm_mean != 0,
    )

    fig, ax = plt.subplots(figsize=(10, 7))

    ax.plot(
        tours,
        ros_relative_se,
        marker="o",
        label="Rosenbluth",
    )
    ax.plot(
        tours,
        perm_relative_se,
        marker="o",
        label="PERM",
    )

    finite_ros = np.isfinite(ros_relative_se) & (ros_relative_se > 0)
    if finite_ros.any():
        first_index = np.flatnonzero(finite_ros)[0]
        reference = (
            ros_relative_se[first_index]
            * np.sqrt(tours[first_index] / tours)
        )
        ax.plot(
            tours,
            reference,
            linestyle="--",
            label=r"$\propto N_{\mathrm{tours}}^{-1/2}$ reference",
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Number of tours")
    ax.set_ylabel(rf"Relative uncertainty of $\hat{{Z}}_{{{walk_length}}}$")
    ax.set_title(
        f"Relative partition-sum uncertainty at N={walk_length}"
    )
    ax.grid(True, which="both", alpha=0.35)
    ax.legend()

    save_figure(
        fig,
        output_dir / "partition_sum_relative_uncertainty.png",
    )


def plot_ess(
    frame: pd.DataFrame,
    output_dir: Path,
    walk_length: int,
) -> None:
    tours = frame["n_tours"].to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(10, 7))

    ax.plot(
        tours,
        frame["ros_branch_weight_ess_mean"],
        marker="o",
        label="Rosenbluth: ESS",
    )
    ax.plot(
        tours,
        frame["perm_branch_weight_ess_mean"],
        marker="o",
        label="PERM: branch-weight ESS",
    )
    ax.plot(
        tours,
        frame["perm_tour_weight_ess_mean"],
        marker="o",
        linestyle="--",
        label="PERM: tour-weight ESS",
    )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Number of tours")
    ax.set_ylabel("Effective sample size")
    ax.set_title(f"Effective sample size at N={walk_length}")
    ax.grid(True, which="both", alpha=0.35)
    ax.legend()

    save_figure(
        fig,
        output_dir / "ess_comparison.png",
    )


def plot_weighted_mean_r2(
    frame: pd.DataFrame,
    output_dir: Path,
    n_seeds: int,
    walk_length: int,
) -> None:
    tours = frame["n_tours"].to_numpy(dtype=float)

    ros_mean = frame["ros_weighted_mean_r2_mean"].to_numpy(dtype=float)
    perm_mean = frame["perm_weighted_mean_r2_mean"].to_numpy(dtype=float)

    ros_se = seed_mean_standard_error(
        frame["ros_weighted_mean_r2_std"],
        n_seeds,
    )
    perm_se = seed_mean_standard_error(
        frame["perm_weighted_mean_r2_std"],
        n_seeds,
    )

    fig, ax = plt.subplots(figsize=(10, 7))

    ax.errorbar(
        tours,
        ros_mean,
        yerr=ros_se,
        marker="o",
        capsize=4,
        label="Rosenbluth",
    )
    ax.errorbar(
        tours,
        perm_mean,
        yerr=perm_se,
        marker="o",
        capsize=4,
        label="PERM",
    )

    ax.set_xscale("log")
    ax.set_xlabel("Number of tours")
    ax.set_ylabel(
        rf"Weighted mean $\langle R_{{{walk_length}}}^2\rangle$"
    )
    ax.set_title(
        rf"Weighted mean $\langle R^2\rangle$ convergence "
        f"at N={walk_length}"
    )
    ax.grid(True, which="both", alpha=0.35)
    ax.legend()

    save_figure(
        fig,
        output_dir / "weighted_mean_r2_convergence.png",
    )


def main() -> None:
    args = parse_args()

    if args.walk_length <= 0:
        raise ValueError("--walk-length must be positive.")
    if args.n_seeds <= 0:
        raise ValueError("--n-seeds must be positive.")

    frame = load_data(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    plot_partition_sum(
        frame,
        args.output_dir,
        args.n_seeds,
        args.walk_length,
    )
    plot_partition_sum_relative_uncertainty(
        frame,
        args.output_dir,
        args.n_seeds,
        args.walk_length,
    )
    plot_ess(
        frame,
        args.output_dir,
        args.walk_length,
    )
    plot_weighted_mean_r2(
        frame,
        args.output_dir,
        args.n_seeds,
        args.walk_length,
    )

    print(
        f"\nCompleted Rosenbluth/PERM comparison plots "
        f"for N={args.walk_length}."
    )


if __name__ == "__main__":
    main()