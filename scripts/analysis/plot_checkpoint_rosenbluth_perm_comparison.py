#!/usr/bin/env python3
"""Plot Rosenbluth/PERM convergence directly from checkpoint CSV files.

Partition sums for long walks can exceed IEEE-754 float64 range.  Therefore
partition-sum columns are read as strings and handled with ``decimal.Decimal``.
The partition-sum figure is plotted as log10(Z_N), while relative uncertainty
is evaluated as SE(Z_N) / Z_N without converting either value to float first.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation, localcontext
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
    "sample_count",
    "nonzero_tours",
    "branch_weight_ess",
    "tour_weight_ess",
}

DECIMAL_COLUMNS = {
    "partition_sum_estimate",
    "partition_sum_standard_error",
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

    frame = pd.read_csv(
        path,
        dtype={column: "string" for column in DECIMAL_COLUMNS},
    )
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


def parse_decimal(value: object) -> Decimal | None:
    if value is None or pd.isna(value):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite():
        return None
    return parsed


def decimal_is_positive(value: object) -> bool:
    parsed = parse_decimal(value)
    return parsed is not None and parsed > 0


def decimal_log10(value: object) -> float:
    parsed = parse_decimal(value)
    if parsed is None or parsed <= 0:
        return np.nan
    with localcontext() as context:
        context.prec = 50
        return float(parsed.log10())


def decimal_ratio(numerator: object, denominator: object) -> float:
    numerator_decimal = parse_decimal(numerator)
    denominator_decimal = parse_decimal(denominator)
    if (
        numerator_decimal is None
        or denominator_decimal is None
        or numerator_decimal < 0
        or denominator_decimal <= 0
    ):
        return np.nan
    with localcontext() as context:
        context.prec = 50
        return float(numerator_decimal / denominator_decimal)


def partition_log_values(frame: pd.DataFrame) -> np.ndarray:
    return np.asarray(
        [decimal_log10(value) for value in frame["partition_sum_estimate"]],
        dtype=float,
    )


def partition_log_errors(frame: pd.DataFrame) -> np.ndarray:
    lower_errors: list[float] = []
    upper_errors: list[float] = []

    for estimate_raw, error_raw in zip(
        frame["partition_sum_estimate"],
        frame["partition_sum_standard_error"],
        strict=True,
    ):
        estimate = parse_decimal(estimate_raw)
        error = parse_decimal(error_raw)
        if estimate is None or error is None or estimate <= 0 or error < 0:
            lower_errors.append(np.nan)
            upper_errors.append(np.nan)
            continue

        with localcontext() as context:
            context.prec = 50
            center = estimate.log10()
            upper = (estimate + error).log10() - center
            if error < estimate:
                lower = center - (estimate - error).log10()
            else:
                lower = Decimal("NaN")

        lower_errors.append(float(lower) if lower.is_finite() else np.nan)
        upper_errors.append(float(upper) if upper.is_finite() else np.nan)

    return np.asarray([lower_errors, upper_errors], dtype=float)


def relative_uncertainty(frame: pd.DataFrame) -> np.ndarray:
    return np.asarray(
        [
            decimal_ratio(error, estimate)
            for error, estimate in zip(
                frame["partition_sum_standard_error"],
                frame["partition_sum_estimate"],
                strict=True,
            )
        ],
        dtype=float,
    )


def finite_nonnegative(values: pd.Series) -> np.ndarray:
    array = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    return np.where(np.isfinite(array) & (array >= 0.0), array, np.nan)


def positive_numeric_mask(values: pd.Series | np.ndarray) -> np.ndarray:
    array = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
    return np.isfinite(array) & (array > 0.0)


def finite_numeric_mask(values: pd.Series | np.ndarray) -> np.ndarray:
    array = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
    return np.isfinite(array)


def terminal_available(frame: pd.DataFrame) -> np.ndarray:
    sample_count = pd.to_numeric(frame["sample_count"], errors="coerce").to_numpy()
    nonzero_tours = pd.to_numeric(frame["nonzero_tours"], errors="coerce").to_numpy()
    positive_estimate = np.asarray(
        [decimal_is_positive(value) for value in frame["partition_sum_estimate"]],
        dtype=bool,
    )
    return (
        np.isfinite(sample_count)
        & np.isfinite(nonzero_tours)
        & (sample_count > 0)
        & (nonzero_tours > 0)
        & positive_estimate
    )


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
        y = partition_log_values(frame)
        mask = terminal_available(frame) & np.isfinite(y)
        if not mask.any():
            unavailable.append(label)
            continue

        tours = frame["checkpoint_tours"].to_numpy(dtype=float)
        yerr = partition_log_errors(frame)
        ax.errorbar(
            tours[mask],
            y[mask],
            yerr=yerr[:, mask],
            marker="o",
            capsize=4,
            label=label,
        )

    ax.set_xscale("log")
    ax.set_xlabel("Number of completed tours")
    ax.set_ylabel(rf"$\log_{{10}} \hat{{Z}}_{{{walk_length}}}$")
    ax.set_title(f"Partition sum convergence at N={walk_length}")
    ax.grid(True, which="both", alpha=0.35)
    if ax.lines:
        ax.legend()
    add_unavailable_note(ax, unavailable)
    save_figure(fig, output_dir / "partition_sum_convergence.png", dpi)


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
        mask = terminal_available(frame) & np.isfinite(relative) & (relative > 0)
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
    if ax.lines:
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


def plot_positive_numeric_series(
    ax: plt.Axes,
    frame: pd.DataFrame,
    y_column: str,
    label: str,
    *,
    linestyle: str = "-",
) -> bool:
    mask = positive_numeric_mask(frame[y_column]) & terminal_available(frame)
    if not mask.any():
        return False
    x = frame.loc[mask, "checkpoint_tours"].to_numpy(dtype=float)
    y = pd.to_numeric(frame.loc[mask, y_column], errors="coerce").to_numpy(dtype=float)
    ax.plot(x, y, marker="o", linestyle=linestyle, label=label)
    return True


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
        if not plot_positive_numeric_series(
            ax, frame, column, label, linestyle=linestyle
        ):
            unavailable.append(label)

    ax.set_xscale("log")
    if ax.lines:
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
        mask = finite_numeric_mask(frame["weighted_mean_r2"]) & terminal_available(frame)
        if not mask.any():
            unavailable.append(label)
            continue
        ax.errorbar(
            frame.loc[mask, "checkpoint_tours"],
            pd.to_numeric(frame.loc[mask, "weighted_mean_r2"], errors="coerce"),
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
    ros["partition_sum_log10"] = partition_log_values(ros)
    perm["partition_sum_log10"] = partition_log_values(perm)
    ros["partition_sum_relative_uncertainty"] = relative_uncertainty(ros)
    perm["partition_sum_relative_uncertainty"] = relative_uncertainty(perm)
    ros["terminal_available"] = terminal_available(ros)
    perm["terminal_available"] = terminal_available(perm)

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

    ros_ess = pd.to_numeric(merged["ros_tour_weight_ess"], errors="coerce").to_numpy()
    perm_tour_ess = pd.to_numeric(
        merged["perm_tour_weight_ess"], errors="coerce"
    ).to_numpy()
    perm_branch_ess = pd.to_numeric(
        merged["perm_branch_weight_ess"], errors="coerce"
    ).to_numpy()
    merged["perm_to_ros_tour_ess_ratio"] = np.divide(
        perm_tour_ess,
        ros_ess,
        out=np.full(len(merged), np.nan),
        where=np.isfinite(ros_ess) & (ros_ess > 0),
    )
    merged["perm_branch_to_tour_ess_ratio"] = np.divide(
        perm_branch_ess,
        perm_tour_ess,
        out=np.full(len(merged), np.nan),
        where=np.isfinite(perm_tour_ess) & (perm_tour_ess > 0),
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

    ros_available = int(terminal_available(ros).sum())
    perm_available = int(terminal_available(perm).sum())
    print(
        f"Completed checkpoint comparison for N={args.walk_length}. "
        f"Available terminal checkpoints: Rosenbluth={ros_available}/{len(ros)}, "
        f"PERM={perm_available}/{len(perm)}."
    )


if __name__ == "__main__":
    main()
