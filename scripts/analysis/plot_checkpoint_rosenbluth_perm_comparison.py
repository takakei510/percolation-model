#!/usr/bin/env python3
"""Plot Rosenbluth/PERM convergence directly from checkpoint CSV files.

The script compares the requested terminal step N.  Long Rosenbluth walks may
have no surviving samples at that step, so zero/NaN estimates are treated as
"unavailable" rather than causing logarithmic plots to fail.
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
        description="Compare Rosenbluth and PERM convergence from checkpoints."
    )
    parser.add_argument("--rosenbluth", required=True, type=Path)
    parser.add_argument("--perm", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--walk-length", required=True, type=int)
    parser.add_argument("--dpi", type=int, default=300)
    return parser.parse_args()


def load_terminal_step(path: Path, walk_length: int, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} input not found: {path}")

    frame = pd.read_csv(path)
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"{label} input is missing columns: {sorted(missing)}")

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
        raise ValueError(f"{label} input has duplicate checkpoints: {duplicates}")

    terminal = terminal.sort_values("checkpoint_tours").reset_index(drop=True)
    if (terminal["checkpoint_tours"] <= 0).any():
        raise ValueError(f"{label} checkpoint_tours must be positive.")
    return terminal


def finite_nonnegative(values: pd.Series) -> np.ndarray:
    array = values.to_numpy(dtype=float)
    return np.where(np.isfinite(array) & (array >= 0.0), array, np.nan)


def positive_mask(values: pd.Series | np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    return np.isfinite(array) & (array > 0.0)


def finite_mask(values: pd.Series | np.ndarray) -> np.ndarray:
    return np.isfinite(np.asarray(values, dtype=float))


def save_figure(fig: plt.Figure, path: Path, dpi: int) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def add_unavailable_note(ax: plt.Axes, labels: list[str]) -> None:
    if labels:
        ax.text(
            0.02,
            0.03,
            "Unavailable at terminal step: " + ", ".join(labels),
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=10,
            bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "0.7"},
        )


def plot_positive_series(
    ax: plt.Axes,
    frame: pd.DataFrame,
    y_column: str,
    label: str,
    *,
    yerr_column: str | None = None,
    linestyle: str = "-",
) -> bool:
    mask = positive_mask(frame[y_column])
    if not mask.any():
        return False

    x = frame.loc[mask, "checkpoint_tours"].to_numpy(dtype=float)
    y = frame.loc[mask, y_column].to_numpy(dtype=float)
    if yerr_column is None:
        ax.plot(x, y, marker="o", linestyle=linestyle, label=label)
    else:
        yerr = finite_nonnegative(frame.loc[mask, yerr_column])
        ax.errorbar(
            x,
            y,
            yerr=yerr,
            marker="o",
            linestyle=linestyle,
            capsize=4,
            label=label,
        )
    return True


def plot_partition_sum(
    ros: pd.DataFrame,
    perm: pd.DataFrame,
    walk_length: int,
    output_dir: Path,
    dpi: int,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 7))
    unavailable: list[str] = []

    for label, frame in (("Rosenbluth", ros), ("PERM", perm)):
        ok = plot_positive_series(
            ax,
            frame,
            "partition_sum_estimate",
            label,
            yerr_column="partition_sum_standard_error",
        )
        if not ok:
            unavailable.append(label)

    ax.set_xscale("log")
    if len(unavailable) < 2:
        ax.set_yscale("log")
    ax.set_xlabel("Number of completed tours")
    ax.set_ylabel(rf"Partition sum estimate $\hat{{Z}}_{{{walk_length}}}$")
    ax.set_title(f"Partition sum convergence at N={walk_length}")
    ax.grid(True, which="both", alpha=0.35)
    if ax.lines:
        ax.legend()
    add_unavailable_note(ax, unavailable)
    save_figure(fig, output_dir / "partition_sum_convergence.png", dpi)


def relative_uncertainty(frame: pd.DataFrame) -> np.ndarray:
    estimate = frame["partition_sum_estimate"].to_numpy(dtype=float)
    standard_error = frame["partition_sum_standard_error"].to_numpy(dtype=float)
    return np.divide(
        standard_error,
        np.abs(estimate),
        out=np.full_like(standard_error, np.nan),
        where=(
            np.isfinite(standard_error)
            & np.isfinite(estimate)
            & (estimate > 0.0)
            & (standard_error >= 0.0)
        ),
    )


def plot_relative_uncertainty(
    ros: pd.DataFrame,
    perm: pd.DataFrame,
    walk_length: int,
    output_dir: Path,
    dpi: int,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 7))
    unavailable: list[str] = []
    plotted_reference = False

    for label, frame in (("Rosenbluth", ros), ("PERM", perm)):
        relative = relative_uncertainty(frame)
        mask = positive_mask(relative)
        if not mask.any():
            unavailable.append(label)
            continue

        tours = frame["checkpoint_tours"].to_numpy(dtype=float)
        ax.plot(tours[mask], relative[mask], marker="o", label=label)

        if not plotted_reference:
            first = np.flatnonzero(mask)[0]
            reference = relative[first] * np.sqrt(tours[first] / tours)
            ax.plot(
                tours,
                reference,
                linestyle="--",
                label=r"$\propto N_{\mathrm{tours}}^{-1/2}$ reference",
            )
            plotted_reference = True

    ax.set_xscale("log")
    if len(unavailable) < 2:
        ax.set_yscale("log")
    ax.set_xlabel("Number of completed tours")
    ax.set_ylabel(rf"Relative uncertainty of $\hat{{Z}}_{{{walk_length}}}$")
    ax.set_title(f"Partition-sum relative uncertainty at N={walk_length}")
    ax.grid(True, which="both", alpha=0.35)
    if ax.lines:
        ax.legend()
    add_unavailable_note(ax, unavailable)
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
    unavailable: list[str] = []

    series = (
        ("Rosenbluth ESS", ros, "tour_weight_ess", "-"),
        ("PERM branch-weight ESS", perm, "branch_weight_ess", "-"),
        ("PERM tour-weight ESS", perm, "tour_weight_ess", "--"),
    )
    for label, frame, column, linestyle in series:
        if not plot_positive_series(
            ax, frame, column, label, linestyle=linestyle
        ):
            unavailable.append(label)

    ax.set_xscale("log")
    if len(unavailable) < len(series):
        ax.set_yscale("log")
    ax.set_xlabel("Number of completed tours")
    ax.set_ylabel("Effective sample size")
    ax.set_title(f"Effective sample size at N={walk_length}")
    ax.grid(True, which="both", alpha=0.35)
    if ax.lines:
        ax.legend()
    add_unavailable_note(ax, unavailable)
    save_figure(fig, output_dir / "ess_comparison.png", dpi)


def plot_weighted_mean_r2(
    ros: pd.DataFrame,
    perm: pd.DataFrame,
    walk_length: int,
    output_dir: Path,
    dpi: int,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 7))
    unavailable: list[str] = []

    for label, frame in (("Rosenbluth", ros), ("PERM", perm)):
        mask = finite_mask(frame["weighted_mean_r2"])
        if not mask.any():
            unavailable.append(label)
            continue
        ax.errorbar(
            frame.loc[mask, "checkpoint_tours"],
            frame.loc[mask, "weighted_mean_r2"],
            yerr=finite_nonnegative(
                frame.loc[mask, "weighted_mean_r2_standard_error"]
            ),
            marker="o",
            capsize=4,
            label=label,
        )

    ax.set_xscale("log")
    ax.set_xlabel("Number of completed tours")
    ax.set_ylabel(rf"Weighted mean $\langle R_{{{walk_length}}}^2\rangle$")
    ax.set_title(rf"Weighted mean $\langle R^2\rangle$ convergence at N={walk_length}")
    ax.grid(True, which="both", alpha=0.35)
    if ax.lines:
        ax.legend()
    add_unavailable_note(ax, unavailable)
    save_figure(fig, output_dir / "weighted_mean_r2_convergence.png", dpi)


def write_comparison_csv(
    ros: pd.DataFrame,
    perm: pd.DataFrame,
    output_path: Path,
) -> None:
    ros = ros.copy()
    perm = perm.copy()
    ros["partition_sum_relative_uncertainty"] = relative_uncertainty(ros)
    perm["partition_sum_relative_uncertainty"] = relative_uncertainty(perm)

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

    ros_ess = merged["ros_tour_weight_ess"].to_numpy(dtype=float)
    perm_tour_ess = merged["perm_tour_weight_ess"].to_numpy(dtype=float)
    perm_branch_ess = merged["perm_branch_weight_ess"].to_numpy(dtype=float)
    merged["perm_to_ros_tour_ess_ratio"] = np.divide(
        perm_tour_ess,
        ros_ess,
        out=np.full(len(merged), np.nan),
        where=np.isfinite(ros_ess) & (ros_ess > 0.0),
    )
    merged["perm_branch_to_tour_ess_ratio"] = np.divide(
        perm_branch_ess,
        perm_tour_ess,
        out=np.full(len(merged), np.nan),
        where=np.isfinite(perm_tour_ess) & (perm_tour_ess > 0.0),
    )
    merged["ros_terminal_available"] = positive_mask(
        merged["ros_partition_sum_estimate"]
    )
    merged["perm_terminal_available"] = positive_mask(
        merged["perm_partition_sum_estimate"]
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
        raise ValueError(
            "Checkpoint sets differ: "
            f"Rosenbluth-only={sorted(ros_checkpoints - perm_checkpoints)}, "
            f"PERM-only={sorted(perm_checkpoints - ros_checkpoints)}."
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    plot_partition_sum(ros, perm, args.walk_length, args.output_dir, args.dpi)
    plot_relative_uncertainty(
        ros, perm, args.walk_length, args.output_dir, args.dpi
    )
    plot_ess(ros, perm, args.walk_length, args.output_dir, args.dpi)
    plot_weighted_mean_r2(
        ros, perm, args.walk_length, args.output_dir, args.dpi
    )
    write_comparison_csv(
        ros,
        perm,
        args.output_dir / "checkpoint_comparison.csv",
    )

    ros_available = int(positive_mask(ros["partition_sum_estimate"]).sum())
    perm_available = int(positive_mask(perm["partition_sum_estimate"]).sum())
    print(
        f"Completed checkpoint comparison for N={args.walk_length}. "
        f"Positive terminal estimates: Rosenbluth={ros_available}/{len(ros)}, "
        f"PERM={perm_available}/{len(perm)}."
    )


if __name__ == "__main__":
    main()
