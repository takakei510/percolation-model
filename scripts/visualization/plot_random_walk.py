import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def compute_local_exponent(step, value, window=5):
    step = np.asarray(step)
    value = np.asarray(value)

    alpha = np.full(len(value), np.nan, dtype=float)

    for i in range(window, len(step) - window):
        s1 = step[i - window]
        s2 = step[i + window]
        v1 = value[i - window]
        v2 = value[i + window]

        if s1 <= 0 or s2 <= 0 or v1 <= 0 or v2 <= 0:
            continue

        alpha[i] = (np.log(v2) - np.log(v1)) / (np.log(s2) - np.log(s1))

    return alpha

def plot_local_exponent(saw_path, out_prefix, window=5):
    saw = pd.read_csv(saw_path)

    plt.figure(figsize=(7, 5))

    alive = saw[
        (saw["step"] > 0) &
        (saw["mean_r2"] > 0) &
        (saw["n_alive"] > 0)
    ]

    alpha_alive = compute_local_exponent(
        alive["step"].values,
        alive["mean_r2"].values,
        window=window
    )

    plt.plot(
        alive["step"],
        alpha_alive,
        label="alive avg"
    )

    if "mean_r2_all" in saw.columns:
        all_avg = saw[
            (saw["step"] > 0) &
            (saw["mean_r2_all"] > 0)
        ]

        alpha_all = compute_local_exponent(
            all_avg["step"].values,
            all_avg["mean_r2_all"].values,
            window=window
        )

        plt.plot(
            all_avg["step"],
            alpha_all,
            "--",
            label="all avg"
        )

    plt.axhline(1.0, linestyle=":", label="RW alpha=1")
    plt.axhline(1.5, linestyle=":", label="2D SAW alpha=1.5")

    plt.xlabel("step")
    plt.ylabel("local exponent alpha(t)")
    plt.title("Local exponent of MSD")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    plt.savefig(
        f"{out_prefix}_local_exponent_msd.png",
        dpi=300
    )

    plt.close()

def plot_local_exponent_logx(saw_path, out_prefix, window=5):
    saw = pd.read_csv(saw_path)

    plt.figure(figsize=(7, 5))

    alive = saw[
        (saw["step"] > 0) &
        (saw["mean_r2"] > 0) &
        (saw["n_alive"] > 0)
    ]

    alpha_alive = compute_local_exponent(
        alive["step"].values,
        alive["mean_r2"].values,
        window=window
    )

    plt.semilogx(
        alive["step"],
        alpha_alive,
        label="alive avg"
    )

    if "mean_r2_all" in saw.columns:
        all_avg = saw[
            (saw["step"] > 0) &
            (saw["mean_r2_all"] > 0)
        ]

        alpha_all = compute_local_exponent(
            all_avg["step"].values,
            all_avg["mean_r2_all"].values,
            window=window
        )

        plt.semilogx(
            all_avg["step"],
            alpha_all,
            "--",
            label="all avg"
        )

    plt.axhline(1.0, linestyle=":", label="RW alpha=1")
    plt.axhline(1.5, linestyle=":", label="2D SAW alpha=1.5")

    plt.xlabel("step")
    plt.ylabel("local exponent alpha(t)")
    plt.title("Local exponent of MSD")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    plt.savefig(
        f"{out_prefix}_local_exponent_msd_logx.png",
        dpi=300
    )

    plt.close()

def plot_summary(rw_path, saw_path, out_prefix):
    rw = pd.read_csv(rw_path)
    saw = pd.read_csv(saw_path)

    # step vs mean_r2
    plt.figure()
    plt.plot(rw["step"], rw["mean_r2"], label="RW")
    plt.plot(saw["step"], saw["mean_r2"], label="SAW alive avg")

    if "mean_r2_all" in saw.columns:
        plt.plot(
            saw["step"],
            saw["mean_r2_all"],
            "--",
            label="SAW all avg"
        )

    plt.xlabel("step")
    plt.ylabel("mean_r2")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_mean_r2.png", dpi=300)
    plt.close()

    # log-log
    rw2 = rw[rw["step"] > 0]
    saw2 = saw[(saw["step"] > 0) & (saw["n_alive"] > 0)]

    plt.figure()
    plt.loglog(rw2["step"], rw2["mean_r2"], label="RW")
    plt.loglog(saw2["step"], saw2["mean_r2"], label="SAW alive avg")

    if "mean_r2_all" in saw.columns:
        saw_all = saw[(saw["step"] > 0) & (saw["mean_r2_all"] > 0)]
        plt.loglog(
            saw_all["step"],
            saw_all["mean_r2_all"],
            "--",
            label="SAW all avg"
        )
    plt.xlabel("step")
    plt.ylabel("mean_r2")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_mean_r2_loglog.png", dpi=300)
    plt.close()

    # trapped rate
    plt.figure()
    plt.plot(saw["step"], saw["trapped_rate"])
    plt.xlabel("step")
    plt.ylabel("trapped_rate")
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_trapped_rate.png", dpi=300)
    plt.close()

def plot_summary_allavg(rw_path, saw_path, out_prefix):
    rw = pd.read_csv(rw_path)
    saw = pd.read_csv(saw_path)

    if "mean_r2_all" not in saw.columns:
        return

    # linear plot
    plt.figure()
    plt.plot(rw["step"], rw["mean_r2"], label="RW")
    plt.plot(saw["step"], saw["mean_r2_all"], "--", label="SAW all avg")
    plt.xlabel("step")
    plt.ylabel("mean_r2")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_mean_r2_allavg_only.png", dpi=300)
    plt.close()

    # log-log plot
    rw2 = rw[(rw["step"] > 0) & (rw["mean_r2"] > 0)]
    saw2 = saw[(saw["step"] > 0) & (saw["mean_r2_all"] > 0)]

    plt.figure()
    plt.loglog(rw2["step"], rw2["mean_r2"], label="RW")
    plt.loglog(saw2["step"], saw2["mean_r2_all"], "--", label="SAW all avg")
    plt.xlabel("step")
    plt.ylabel("mean_r2")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_mean_r2_allavg_only_loglog.png", dpi=300)
    plt.close()

def plot_traj(traj_path, out_path, dim):
    traj = pd.read_csv(traj_path)
    traj0 = traj[traj["trial"] == traj["trial"].min()]

    if dim == 2:
        plt.figure()
        plt.plot(traj0["x"], traj0["y"], marker="o", markersize=2, linewidth=1)
        plt.xlabel("x")
        plt.ylabel("y")
        plt.axis("equal")
        plt.tight_layout()
        plt.savefig(out_path, dpi=300)
        plt.close()
    else:
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        ax.plot(traj0["x"], traj0["y"], traj0["z"], marker="o", markersize=2, linewidth=1)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        plt.tight_layout()
        plt.savefig(out_path, dpi=300)
        plt.close()

def plot_rg2(rw_path, saw_path, out_prefix):
    rw = pd.read_csv(rw_path)
    saw = pd.read_csv(saw_path)

    plt.figure(figsize=(7, 5))

    if "mean_rg2" in rw.columns:
        plt.plot(rw["step"], rw["mean_rg2"], label="RW Rg²")

    if "mean_rg2" in saw.columns:
        saw_alive = saw[saw["n_alive"] > 0]
        plt.plot(saw_alive["step"], saw_alive["mean_rg2"], label="SAW Rg²")

    plt.xlabel("step")
    plt.ylabel("mean_rg2")
    plt.title("Radius of gyration squared")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_mean_rg2.png", dpi=300)
    plt.close()

def plot_rg2_loglog(rw_path, saw_path, out_prefix):
    rw = pd.read_csv(rw_path)
    saw = pd.read_csv(saw_path)

    plt.figure(figsize=(7, 5))

    rw = rw[(rw["step"] > 0) & (rw["mean_rg2"] > 0)]
    saw = saw[(saw["step"] > 0) & (saw["mean_rg2"] > 0) & (saw["n_alive"] > 0)]

    plt.loglog(rw["step"], rw["mean_rg2"], label="RW Rg²")
    plt.loglog(saw["step"], saw["mean_rg2"], label="SAW Rg²")

    plt.xlabel("step")
    plt.ylabel("mean_rg2")
    plt.title("Radius of gyration squared log-log")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_mean_rg2_loglog.png", dpi=300)
    plt.close()

def plot_diagnostics(csv_path, output_prefix):
    df = pd.read_csv(csv_path)

    fig, ax1 = plt.subplots(figsize=(8,5))

    ax1.plot(
        df["step"],
        df["mean_r2"],
        label="mean_r2"
    )

    ax1.plot(
        df["step"],
        df["max_r2"],
        label="max_r2"
    )

    ax1.set_xlabel("step")
    ax1.set_ylabel("R²")

    ax2 = ax1.twinx()

    ax2.plot(
        df["step"],
        df["n_alive"],
        "--",
        label="n_alive"
    )

    ax2.set_ylabel("alive walkers")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()

    ax1.legend(
        lines1 + lines2,
        labels1 + labels2,
        loc="best"
    )

    plt.tight_layout()

    plt.savefig(
        f"{output_prefix}_diagnostics.png",
        dpi=300
    )

    plt.close()

def plot_cv(csv_path, output_prefix):
    df = pd.read_csv(csv_path)

    plt.figure(figsize=(7,5))

    plt.plot(
        df["step"],
        df["cv_r2"]
    )

    plt.xlabel("step")
    plt.ylabel("cv_r2")

    plt.title("Coefficient of variation")

    plt.grid(True)

    plt.tight_layout()

    plt.savefig(
        f"{output_prefix}_cv_r2.png",
        dpi=300
    )

    plt.close()

def plot_alive(csv_path, output_prefix):
    df = pd.read_csv(csv_path)

    plt.figure(figsize=(7,5))

    plt.semilogy(
        df["step"],
        df["n_alive"]
    )

    plt.xlabel("step")
    plt.ylabel("n_alive")

    plt.grid(True)

    plt.tight_layout()

    plt.savefig(
        f"{output_prefix}_alive.png",
        dpi=300
    )

    plt.close()

def plot_survival_probability(csv_path, output_prefix):
    df = pd.read_csv(csv_path)

    survival = 1.0 - df["trapped_rate"]

    plt.figure()

    plt.plot(
        df["step"],
        survival
    )

    plt.xlabel("step")
    plt.ylabel("P_survival")

    plt.title("Survival probability")

    plt.grid(True)
    plt.tight_layout()

    plt.savefig(
        f"{output_prefix}_survival_probability.png",
        dpi=300
    )

    plt.close()

def plot_survival_probability_loglog(csv_path, output_prefix):
    df = pd.read_csv(csv_path)

    survival = 1.0 - df["trapped_rate"]

    mask = (
        (df["step"] > 0)
        &
        (survival > 0)
    )

    plt.figure()

    plt.loglog(
        df["step"][mask],
        survival[mask]
    )

    plt.xlabel("step")
    plt.ylabel("P_survival")

    plt.title("Survival probability log-log")

    plt.grid(True)
    plt.tight_layout()

    plt.savefig(
        f"{output_prefix}_survival_probability_loglog.png",
        dpi=300
    )

    plt.close()

def plot_single_walk_metrics(saw_path, out_prefix):
    saw = pd.read_csv(saw_path)

    alive = saw[saw["n_alive"] > 0]

    # mean_r2: alive / all
    plt.figure(figsize=(7, 5))
    plt.plot(alive["step"], alive["mean_r2"], label="alive avg")

    if "mean_r2_all" in saw.columns:
        plt.plot(
            saw["step"],
            saw["mean_r2_all"],
            "--",
            label="all avg"
        )

    plt.xlabel("step")
    plt.ylabel("mean_r2")
    plt.title("Target walk MSD")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_single_mean_r2.png", dpi=300)
    plt.close()

    # log-log
    alive_log = alive[
        (alive["step"] > 0) &
        (alive["mean_r2"] > 0)
    ]

    plt.figure(figsize=(7, 5))
    plt.loglog(
        alive_log["step"],
        alive_log["mean_r2"],
        label="alive avg"
    )

    if "mean_r2_all" in saw.columns:
        all_log = saw[
            (saw["step"] > 0) &
            (saw["mean_r2_all"] > 0)
        ]
        plt.loglog(
            all_log["step"],
            all_log["mean_r2_all"],
            "--",
            label="all avg"
        )

    plt.xlabel("step")
    plt.ylabel("mean_r2")
    plt.title("Target walk MSD log-log")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_single_mean_r2_loglog.png", dpi=300)
    plt.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rw", required=True)
    parser.add_argument("--saw", required=True)
    parser.add_argument("--rw-traj")
    parser.add_argument("--saw-traj")
    parser.add_argument("--dim", type=int, required=True)
    parser.add_argument("--out-prefix", required=True)
    args = parser.parse_args()

    plot_summary(args.rw, args.saw, args.out_prefix)
    plot_summary_allavg(args.rw, args.saw, args.out_prefix)
    plot_single_walk_metrics(args.saw, args.out_prefix)
    plot_local_exponent(args.saw, args.out_prefix, window=5)
    plot_local_exponent_logx(args.saw, args.out_prefix, window=5)
    plot_rg2(args.rw, args.saw, args.out_prefix)
    plot_rg2_loglog(args.rw, args.saw, args.out_prefix)
    plot_diagnostics(args.saw, args.out_prefix)
    plot_cv(args.saw, args.out_prefix)
    plot_alive(args.saw, args.out_prefix)
    plot_survival_probability(args.saw, args.out_prefix)
    plot_survival_probability_loglog(args.saw, args.out_prefix)

    if args.rw_traj:
        plot_traj(args.rw_traj, f"{args.out_prefix}_rw_traj.png", args.dim)

    if args.saw_traj:
        plot_traj(args.saw_traj, f"{args.out_prefix}_saw_traj.png", args.dim)


if __name__ == "__main__":
    main()