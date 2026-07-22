#!/usr/bin/env python3
"""Plot Rosenbluth/PERM convergence directly from checkpoint CSV files.

Each input is a ``weighted_convergence.csv`` produced by one simulation run.
The script extracts the requested terminal walk step N and compares the
checkpoint estimates as functions of completed tours.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "checkpoint_tours",
    "step",
    "weighted_mean_r2",
    "weighted_mean_r2_standard_error",
    "partition_sum_estimate",
    "partition_sum_standard_error",
    "branch_weight_ess",
    "tour_weight_ess",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare Rosenbluth and PERM convergence using two "
            "weighted_convergence.csv files."
        )
    )
    parser.add_argument(
        "--rosenbluth",
        required=True,
        type=Path,
        help="Rosenbluth weighted_convergence.csv.",
    )
    parser.add_argument(
        "--perm",
        required=True,
        type=Path,
        help="PERM weighted_convergence.csv.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory in which figures and the comparison CSV are saved.",
    )
    parser.add_argument(
        "--walk-length",
        required=True,
        type=int,
        help="Terminal walk step N to extract from both input files.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="PNG resolution (default: 300).",
    )
    return parser.parse_args()


def load_terminal_step(path: Path, walk_length: int, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} input not found: {path}")

    frame = pd.read_csv(path)
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(
            f"{label} input is missing columns: {sorted(missing)}"
        )

    terminal = frame.loc[frame["step"] == walk_length].copy()
    if terminal.empty:
        available_max = frame["step"].max() if not frame.empty else None
        raise ValueError(
            f"{label} input has no step={walk_length}; "
            f"maximum available step is {available_max}."
        )

    if terminal["checkpoint_tours"].duplicated().any():
        duplicates = terminal.loc[
            terminal["checkpoint_tours"].duplicated(keep=False),
            "checkpoint_tours",
        ].tolist()
        raise ValueError(
            f"{label} input has duplicate checkpoint rows: {duplicates}"
        )

    terminal = terminal.sort_values("checkpoint_tours").reset_index(drop=True)
    if (terminal["checkpoint_tours"] <= 0).any():
        raise ValueError(f"{label} checkpoint_tours must be positive.")

    return terminal


def finite_error(values: pd.Series) -> np.ndarray:
    array = values.to_numpy(dtype=float)
    return np.where(np.isfinite(array) & (array >= 0.0), array, np.nan)


def save_figure(fig: plt.Figure, path: Path, dpi: int) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_partition_sum(
    ros: pd.DataFrame,
    perm: pd.DataFrame,
    walk_length: int,
    output_dir: Path,
    dpi: int,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 7))

    for label, frame in (("Rosenbluth", ros), ("PERM", perm)):
        ax.errorbar(
            frame["checkpoint_tours"],
            frame["partition_sum_estimate"],
            yerr=finite_error(frame["partition_sum_standard_error"]),
            marker="o",
            capsize=4,
            label=label,
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Number of completed tours")
    ax.set_ylabel(rf"Partition sum estimate $\hat{{Z}}_{{{walk_length}}}$")
    ax.set_title(f"Partition sum convergence at N={walk_length}")
    ax.grid(True, which="both", alpha=0.35)
    ax.legend()
    save_figure(fig, output_dir / "partition_sum_convergence.png", dpi)


def relative_uncertainty(frame: pd.DataFrame) -> np.ndarray:
    estimate = frame["partition_sum_estimate"].to_numpy(dtype=float)
    standard_error = frame["partition_sum_standard_error"].to_numpy(dtype=float)
    return np.divide(
        standard_error,
        np.abs(estimate),
        out=np.full_like(standard_error, np.nan),
        where=np.isfinite(standard_error) & np.isfinite(estimate) & (estimate != 0.0),
    )


def plot_relative_uncertainty(
    ros: pd.DataFrame,
    perm: pd.DataFrame,
    walk_length: int,
    output_dir: Path,
    dpi: int,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 7))

    ros_relative = relative_uncertainty(ros)
    perm_relative = relative_uncertainty(perm)

    ax.plot(
        ros["checkpoint_tours"],
        ros_relative,
        marker="o",
        label="Rosenbluth",
    )
    ax.plot(
        perm["checkpoint_tours"],
        perm_relative,
        marker="o",
        label="PERM",
    )

    finite = np.isfinite(ros_relative) & (ros_relative > 0.0)
    if finite.any():
        first = np.flatnonzero(finite)[0]
        tours = ros["checkpoint_tours"].to_numpy(dtype=float)
        reference = ros_relative[first] * np.sqrt(tours[first] / tours)
        ax.plot(
            tours,
            reference,
            linestyle="--",
            label=r"$\propto N_{\mathrm{tours}}^{-1/2}$ reference",
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Number of completed tours")
    ax.set_ylabel(rf"Relative uncertainty of $\hat{{Z}}_{{{walk_length}}}$")
    ax.set_title(f"Partition-sum relative uncertainty at N={walk_length}")
    ax.grid(True, which="both", alpha=0.35)
    ax.legend()
    save_figure(
        fig,
        output_dir / "partition_sum_relative_uncertainty.png",
        dpi,
    )


def plot_ess(
    ros: pd.DataFrame,
    perm: pd.DataFrame,
    walk_length: int,
    output_dir: Path,
    dpi: int,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 7))

    # Rosenbluth has one branch per tour, so branch and tour ESS coincide.
    ax.plot(
        ros["checkpoint_tours"],
        ros["tour_weight_ess"],
        marker="o",
        label="Rosenbluth ESS",
    )
    ax.plot(
        perm["checkpoint_tours"],
        perm["branch_weight_ess"],
        marker="o",
        label="PERM branch-weight ESS",
    )
    ax.plot(
        perm["checkpoint_tours"],
        perm["tour_weight_ess"],
        marker="o",
        linestyle="--",
        label="PERM tour-weight ESS",
    )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Number of completed tours")
    ax.set_ylabel("Effective sample size")
    ax.set_title(f"Effective sample size at N={walk_length}")
    ax.grid(True, which="both", alpha=0.35)
    ax.legend()
    save_figure(fig, output_dir / "ess_comparison.png", dpi)


def plot_weighted_mean_r2(
    ros: pd.DataFrame,
    perm: pd.DataFrame,
    walk_length: int,
    output_dir: Path,
    dpi: int,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 7))

    for label, frame in (("Rosenbluth", ros), ("PERM", perm)):
        ax.errorbar(
            frame["checkpoint_tours"],
            frame["weighted_mean_r2"],
            yerr=finite_error(frame["weighted_mean_r2_standard_error"]),
            marker="o",
            capsize=4,
            label=label,
        )

    ax.set_xscale("log")
    ax.set_xlabel("Number of completed tours")
    ax.set_ylabel(rf"Weighted mean $\langle R_{{{walk_length}}^2\rangle$")
    ax.set_title(rf"Weighted mean $\langle R^2\rangle$ convergence at N={walk_length}")
    ax.grid(True, which="both", alpha=0.35)
    ax.legend()
    save_figure(fig, output_dir / "weighted_mean_r2_convergence.png", dpi)


def write_comparison_csv(
    ros: pd.DataFrame,
    perm: pd.DataFrame,
    output_path: Path,
) -> None:
    ros_columns = {
        column: f"ros_{column}"
        for column in ros.columns
        if column not in {"checkpoint_tours", "step"}
    }
    perm_columns = {
        column: f"perm_{column}"
        for column in perm.columns
        if column not in {"checkpoint_tours", "step"}
    }

    merged = ros.rename(columns=ros_columns).merge(
        perm.rename(columns=perm_columns),
        on=["checkpoint_tours", "step"],
        how="outer",
        validate="one_to_one",
    )
    merged = merged.sort_values("checkpoint_tours").reset_index(drop=True)

    merged["ros_partition_sum_relative_uncertainty"] = relative_uncertainty(ros)
    merged["perm_partition_sum_relative_uncertainty"] = relative_uncertainty(perm)
    merged["perm_to_ros_tour_ess_ratio"] = np.divide(
        merged["perm_tour_weight_ess"],
        merged["ros_tour_weight_ess"],
        out=np.full(len(merged), np.nan, dtype=float),
        where=merged["ros_tour_weight_ess"].to_numpy(dtype=float) != 0.0,
    )
    merged["perm_branch_to_tour_ess_ratio"] = np.divide(
        merged["perm_branch_weight_ess"],
        merged["perm_tour_weight_ess"],
        out=np.full(len(merged), np.nan, dtype=float),
        where=merged["perm_tour_weight_ess"].to_numpy(dtype=float) != 0.0,
    )

    merged.to_csv(output_path, index=False)
    print(f"Saved: {output_path}")


def main() -> None:
    args = parse_args()
    if args.walk_length <= 0:
        raise ValueError("--walk-length must be positive.")
    if args.dpi <= 0:
        raise ValueError("--dpi must be positive.")

    ros = load_terminal_step(args.rosenbluth, args.walk_length, "Rosenbluth")
    perm = load_terminal_step(args.perm, args.walk_length, "PERM")

    ros_checkpoints = set(ros["checkpoint_tours"].tolist())
    perm_checkpoints = set(perm["checkpoint_tours"].tolist())
    if ros_checkpoints != perm_checkpoints:
        only_ros = sorted(ros_checkpoints - perm_checkpoints)
        only_perm = sorted(perm_checkpoints - ros_checkpoints)
        raise ValueError(
            "Checkpoint sets differ: "
            f"Rosenbluth-only={only_ros}, PERM-only={only_perm}."
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    plot_partition_sum(ros, perm, args.walk_length, args.output_dir, args.dpi)
    plot_relative_uncertainty(
        ros,
        perm,
        args.walk_length,
        args.output_dir,
        args.dpi,
    )
    plot_ess(ros, perm, args.walk_length, args.output_dir, args.dpi)
    plot_weighted_mean_r2(
        ros,
        perm,
        args.walk_length,
        args.output_dir,
        args.dpi,
    )
    write_comparison_csv(
        ros,
        perm,
        args.output_dir / "checkpoint_comparison.csv",
    )

    print(
        f"Completed checkpoint comparison for N={args.walk_length} "
        f"with {len(ros)} checkpoints."
    )


if __name__ == "__main__":
    main()
