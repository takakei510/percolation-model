#!/usr/bin/env python3
import argparse
import csv
import math
import os
import statistics
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import pandas as pd


N_STEPS = 100
N_TOURS_LIST = [1000, 10000, 100000, 1000000]
DEFAULT_SEEDS = [12345, 54321, 99999, 20260723, 314159]


@dataclass
class RunSummary:
    algorithm: str
    threshold_mode: str
    n_tours: int
    seed: int
    partition_sum_estimate: float
    partition_sum_standard_error: float
    weighted_mean_r2: float
    weighted_mean_r2_standard_error: float
    nonzero_tours: float
    branch_weight_ess: float
    tour_weight_ess: float
    pruning_count: int
    enrichment_count: int
    runtime_seconds: float
    output_csv: str
    tour_csv: str


def run_command(command: List[str], cwd: Path) -> float:
    start = os.times().elapsed
    subprocess.run(command, cwd=str(cwd), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = os.times().elapsed
    return end - start


def write_config(path: Path, algorithm: str, n_tours: int, seed: int, output_csv: Path, threshold_disabled: bool) -> None:
    lines = [
        "mode=random_walk",
        "walk_type=saw",
        f"walk_algorithm={algorithm}",
        "dim=2",
        "spatial_backend=hash",
        "boundary=infinite",
        f"n_steps={N_STEPS}",
        f"n_tours={n_tours}",
        f"seed={seed}",
        "perm_c_minus=0.2",
        "perm_c_plus=2.0",
        f"perm_min_tours_for_threshold={n_tours + 1 if threshold_disabled else 100}",
        "perm_threshold_scheme=basic",
        f"output={output_csv}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_last_step(csv_path: Path) -> Dict[str, float]:
    df = pd.read_csv(csv_path)
    row = df[df["step"] == N_STEPS]
    if row.empty:
        raise RuntimeError(f"step={N_STEPS} not found in {csv_path}")
    return row.iloc[0].to_dict()


def read_prune_enrich_counts(tour_csv: Path) -> Tuple[int, int]:
    if not tour_csv.exists():
        return 0, 0
    df = pd.read_csv(tour_csv)
    if "pruned_count" not in df.columns or "enriched_count" not in df.columns:
        return 0, 0
    return int(df["pruned_count"].sum()), int(df["enriched_count"].sum())


def make_summary(
    algorithm: str,
    threshold_mode: str,
    n_tours: int,
    seed: int,
    row: Dict[str, float],
    pruning_count: int,
    enrichment_count: int,
    runtime_seconds: float,
    output_csv: Path,
    tour_csv: Path,
) -> RunSummary:
    return RunSummary(
        algorithm=algorithm,
        threshold_mode=threshold_mode,
        n_tours=n_tours,
        seed=seed,
        partition_sum_estimate=float(row["partition_sum_estimate"]),
        partition_sum_standard_error=float(row["partition_sum_standard_error"]),
        weighted_mean_r2=float(row["weighted_mean_r2"]),
        weighted_mean_r2_standard_error=float(row["weighted_mean_r2_standard_error"]),
        nonzero_tours=float(row["nonzero_tours"]),
        branch_weight_ess=float(row["branch_weight_ess"]),
        tour_weight_ess=float(row["tour_weight_ess"]),
        pruning_count=pruning_count,
        enrichment_count=enrichment_count,
        runtime_seconds=runtime_seconds,
        output_csv=str(output_csv),
        tour_csv=str(tour_csv),
    )


def compute_z_score(perm_value: float, ros_value: float, perm_se: float, ros_se: float) -> float:
    denom = math.sqrt(max(0.0, perm_se * perm_se + ros_se * ros_se))
    if denom <= 0.0 or not math.isfinite(denom):
        return float("nan")
    return (perm_value - ros_value) / denom


def compare_threshold_disabled_stepwise(ros_csv: Path, perm_csv: Path) -> Tuple[bool, float, float]:
    ros = pd.read_csv(ros_csv)
    perm = pd.read_csv(perm_csv)

    merged = ros[["step", "sample_count", "partition_sum_estimate", "completed_tours"]].merge(
        perm[["step", "sample_count", "partition_sum_estimate", "completed_tours"]],
        on="step",
        suffixes=("_ros", "_perm"),
    )

    max_sample_count_diff = (merged["sample_count_ros"] - merged["sample_count_perm"]).abs().max()

    sum_weight_ros = merged["partition_sum_estimate_ros"] * merged["completed_tours_ros"]
    sum_weight_perm = merged["partition_sum_estimate_perm"] * merged["completed_tours_perm"]
    rel = (sum_weight_ros - sum_weight_perm).abs() / sum_weight_ros.replace(0.0, pd.NA)
    rel = rel.replace([float("inf"), float("-inf")], pd.NA).fillna(0.0)
    max_rel_weight_diff = float(rel.max())

    ok = max_sample_count_diff == 0 and max_rel_weight_diff <= 1e-12
    return ok, float(max_sample_count_diff), max_rel_weight_diff


def save_rows_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def plot_errorbar(df: pd.DataFrame, y_col: str, yerr_col: str, out: Path, title: str, ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    for algorithm, color in [("rosenbluth", "#1f77b4"), ("perm", "#d62728")]:
        sub = df[df["algorithm"] == algorithm].sort_values("n_tours")
        ax.errorbar(sub["n_tours"], sub[y_col], yerr=sub[yerr_col], marker="o", capsize=3, label=algorithm, color=color)
    ax.set_xscale("log")
    ax.set_xlabel("n_tours")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def plot_zscore(df: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    sub = df.sort_values("n_tours")
    ax.scatter(sub["n_tours"], sub["z_partition_sum"], marker="o", label="partition_sum", color="#2ca02c")
    ax.scatter(sub["n_tours"], sub["z_weighted_mean_r2"], marker="s", label="weighted_mean_r2", color="#ff7f0e")
    ax.axhline(0.0, color="black", linewidth=1)
    ax.set_xscale("log")
    ax.set_xlabel("n_tours")
    ax.set_ylabel("z-score")
    ax.set_title("PERM vs Rosenbluth z-score by n_tours")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def plot_tour_ess(df: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    for algorithm, color in [("rosenbluth", "#1f77b4"), ("perm", "#d62728")]:
        sub = df[df["algorithm"] == algorithm].sort_values("n_tours")
        ax.plot(sub["n_tours"], sub["tour_weight_ess_mean"], marker="o", label=algorithm, color=color)
    ax.set_xscale("log")
    ax.set_xlabel("n_tours")
    ax.set_ylabel("tour_weight_ess")
    ax.set_title("Tour-weight ESS by n_tours")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Rosenbluth/PERM unbiasedness at N=100")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output-dir", default="data/2d/random_walk/saw/comparisons/n100_unbiasedness")
    parser.add_argument("--seeds", default=",".join(str(s) for s in DEFAULT_SEEDS))
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    build_main = project_root / "build" / "main"
    if not build_main.exists():
        raise RuntimeError("build/main not found. Run make first.")

    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    out_dir = (project_root / args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    run_rows: List[RunSummary] = []
    threshold_checks: List[Dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="n100_perm_validate_") as tmp:
        tmp_path = Path(tmp)
        for n_tours in N_TOURS_LIST:
            for seed in seeds:
                for algorithm, threshold_mode in [("rosenbluth", "normal"), ("perm", "normal"), ("perm", "threshold_disabled")]:
                    alg_tag = "ros" if algorithm == "rosenbluth" else "perm"
                    mode_tag = "n" if threshold_mode == "normal" else "d"
                    label = f"a{alg_tag}_m{mode_tag}_N{N_STEPS}_T{n_tours}_S{seed}"
                    run_dir = out_dir / label
                    run_dir.mkdir(parents=True, exist_ok=True)
                    output_csv = run_dir / ("rosenbluth.csv" if algorithm == "rosenbluth" else "perm.csv")
                    tour_csv = run_dir / "perm_tours.csv"
                    cfg_path = tmp_path / f"{label}.cfg"

                    write_config(
                        path=cfg_path,
                        algorithm=algorithm,
                        n_tours=n_tours,
                        seed=seed,
                        output_csv=output_csv,
                        threshold_disabled=(threshold_mode == "threshold_disabled"),
                    )

                    runtime = run_command([str(build_main), str(cfg_path)], cwd=project_root)
                    row = read_last_step(output_csv)
                    prune_count, enrich_count = read_prune_enrich_counts(tour_csv)
                    if algorithm == "rosenbluth":
                        prune_count = 0
                        enrich_count = 0

                    run_rows.append(
                        make_summary(
                            algorithm=algorithm,
                            threshold_mode=threshold_mode,
                            n_tours=n_tours,
                            seed=seed,
                            row=row,
                            pruning_count=prune_count,
                            enrichment_count=enrich_count,
                            runtime_seconds=runtime,
                            output_csv=output_csv,
                            tour_csv=tour_csv,
                        )
                    )

                ros_run = out_dir / f"aros_mn_N{N_STEPS}_T{n_tours}_S{seed}" / "rosenbluth.csv"
                perm_disabled_run = out_dir / f"aperm_md_N{N_STEPS}_T{n_tours}_S{seed}" / "perm.csv"
                ok, max_sample_diff, max_rel_weight_diff = compare_threshold_disabled_stepwise(ros_run, perm_disabled_run)
                threshold_checks.append(
                    {
                        "n_tours": n_tours,
                        "seed": seed,
                        "match": int(ok),
                        "max_sample_count_diff": max_sample_diff,
                        "max_relative_sum_weight_diff": max_rel_weight_diff,
                    }
                )

    rows_dict = [r.__dict__ for r in run_rows]
    save_rows_csv(out_dir / "n100_runs.csv", rows_dict)
    save_rows_csv(out_dir / "n100_threshold_disabled_checks.csv", threshold_checks)

    runs_df = pd.DataFrame(rows_dict)

    normal_df = runs_df[runs_df["threshold_mode"] == "normal"].copy()
    grouped = (
        normal_df.groupby(["algorithm", "n_tours"], as_index=False)
        .agg(
            partition_sum_estimate_mean=("partition_sum_estimate", "mean"),
            partition_sum_estimate_std=("partition_sum_estimate", "std"),
            partition_sum_standard_error_mean=("partition_sum_standard_error", "mean"),
            weighted_mean_r2_mean=("weighted_mean_r2", "mean"),
            weighted_mean_r2_std=("weighted_mean_r2", "std"),
            weighted_mean_r2_standard_error_mean=("weighted_mean_r2_standard_error", "mean"),
            nonzero_tours_mean=("nonzero_tours", "mean"),
            branch_weight_ess_mean=("branch_weight_ess", "mean"),
            tour_weight_ess_mean=("tour_weight_ess", "mean"),
            pruning_count_mean=("pruning_count", "mean"),
            enrichment_count_mean=("enrichment_count", "mean"),
            runtime_seconds_mean=("runtime_seconds", "mean"),
        )
    )

    # z-score per seed and n_tours
    ros = normal_df[normal_df["algorithm"] == "rosenbluth"].copy()
    perm = normal_df[normal_df["algorithm"] == "perm"].copy()
    merged = ros.merge(perm, on=["n_tours", "seed"], suffixes=("_ros", "_perm"))
    merged["z_partition_sum"] = merged.apply(
        lambda r: compute_z_score(
            r["partition_sum_estimate_perm"],
            r["partition_sum_estimate_ros"],
            r["partition_sum_standard_error_perm"],
            r["partition_sum_standard_error_ros"],
        ),
        axis=1,
    )
    merged["z_weighted_mean_r2"] = merged.apply(
        lambda r: compute_z_score(
            r["weighted_mean_r2_perm"],
            r["weighted_mean_r2_ros"],
            r["weighted_mean_r2_standard_error_perm"],
            r["weighted_mean_r2_standard_error_ros"],
        ),
        axis=1,
    )

    z_summary = (
        merged.groupby("n_tours", as_index=False)
        .agg(
            z_partition_sum_mean=("z_partition_sum", "mean"),
            z_partition_sum_std=("z_partition_sum", "std"),
            z_weighted_mean_r2_mean=("z_weighted_mean_r2", "mean"),
            z_weighted_mean_r2_std=("z_weighted_mean_r2", "std"),
            z_partition_sum_sign_sum=("z_partition_sum", lambda s: int(sum(1 if x > 0 else (-1 if x < 0 else 0) for x in s))),
            z_weighted_mean_r2_sign_sum=("z_weighted_mean_r2", lambda s: int(sum(1 if x > 0 else (-1 if x < 0 else 0) for x in s))),
        )
    )

    # Merge summaries for the requested convergence CSV.
    conv_rows = []
    grouped_idx = {(row["algorithm"], int(row["n_tours"])): row for _, row in grouped.iterrows()}
    z_idx = {int(row["n_tours"]): row for _, row in z_summary.iterrows()}
    for n_tours in N_TOURS_LIST:
        row = {"n_tours": n_tours}
        for alg in ["rosenbluth", "perm"]:
            g = grouped_idx[(alg, n_tours)]
            prefix = "ros" if alg == "rosenbluth" else "perm"
            row[f"{prefix}_partition_sum_estimate_mean"] = float(g["partition_sum_estimate_mean"])
            row[f"{prefix}_partition_sum_estimate_std"] = float(g["partition_sum_estimate_std"])
            row[f"{prefix}_partition_sum_standard_error_mean"] = float(g["partition_sum_standard_error_mean"])
            row[f"{prefix}_weighted_mean_r2_mean"] = float(g["weighted_mean_r2_mean"])
            row[f"{prefix}_weighted_mean_r2_std"] = float(g["weighted_mean_r2_std"])
            row[f"{prefix}_weighted_mean_r2_standard_error_mean"] = float(g["weighted_mean_r2_standard_error_mean"])
            row[f"{prefix}_nonzero_tours_mean"] = float(g["nonzero_tours_mean"])
            row[f"{prefix}_branch_weight_ess_mean"] = float(g["branch_weight_ess_mean"])
            row[f"{prefix}_tour_weight_ess_mean"] = float(g["tour_weight_ess_mean"])
            row[f"{prefix}_pruning_count_mean"] = float(g["pruning_count_mean"])
            row[f"{prefix}_enrichment_count_mean"] = float(g["enrichment_count_mean"])
            row[f"{prefix}_runtime_seconds_mean"] = float(g["runtime_seconds_mean"])

        z = z_idx[n_tours]
        row["z_partition_sum_mean"] = float(z["z_partition_sum_mean"])
        row["z_partition_sum_std"] = float(z["z_partition_sum_std"])
        row["z_weighted_mean_r2_mean"] = float(z["z_weighted_mean_r2_mean"])
        row["z_weighted_mean_r2_std"] = float(z["z_weighted_mean_r2_std"])
        row["z_partition_sum_sign_sum"] = int(z["z_partition_sum_sign_sum"])
        row["z_weighted_mean_r2_sign_sum"] = int(z["z_weighted_mean_r2_sign_sum"])

        conv_rows.append(row)

    save_rows_csv(out_dir / "n100_convergence.csv", conv_rows)

    # plotting frames
    plot_frame = grouped.copy()
    plot_frame["partition_sum_errorbar"] = plot_frame["partition_sum_standard_error_mean"]
    plot_frame["weighted_mean_r2_errorbar"] = plot_frame["weighted_mean_r2_standard_error_mean"]

    plot_errorbar(
        plot_frame,
        y_col="partition_sum_estimate_mean",
        yerr_col="partition_sum_errorbar",
        out=out_dir / "partition_sum_vs_n_tours.png",
        title="N=100 partition sum convergence",
        ylabel="partition_sum_estimate",
    )
    plot_errorbar(
        plot_frame,
        y_col="weighted_mean_r2_mean",
        yerr_col="weighted_mean_r2_errorbar",
        out=out_dir / "weighted_mean_r2_vs_n_tours.png",
        title="N=100 weighted mean R^2 convergence",
        ylabel="weighted_mean_r2",
    )
    plot_zscore(merged[["n_tours", "seed", "z_partition_sum", "z_weighted_mean_r2"]], out_dir / "z_score_vs_n_tours.png")
    plot_tour_ess(grouped, out_dir / "tour_ess_vs_n_tours.png")

    check_df = pd.DataFrame(threshold_checks)
    all_match = bool((check_df["match"] == 1).all())

    print(f"output_dir={out_dir}")
    print(f"threshold_disabled_match_all={all_match}")
    print("zscore_sign_sums=")
    for _, r in z_summary.sort_values("n_tours").iterrows():
        print(
            f"  n_tours={int(r['n_tours'])}"
            f" z_partition_sum_sign_sum={int(r['z_partition_sum_sign_sum'])}"
            f" z_weighted_mean_r2_sign_sum={int(r['z_weighted_mean_r2_sign_sum'])}"
        )


if __name__ == "__main__":
    main()
