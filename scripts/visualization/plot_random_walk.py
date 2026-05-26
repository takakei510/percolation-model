import argparse
import pandas as pd
import matplotlib.pyplot as plt

def plot_summary(rw_path, saw_path, out_prefix):
    rw = pd.read_csv(rw_path)
    saw = pd.read_csv(saw_path)

    # step vs mean_r2
    plt.figure()
    plt.plot(rw["step"], rw["mean_r2"], label="RW")
    plt.plot(saw["step"], saw["mean_r2"], label="SAW")
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
    plt.loglog(saw2["step"], saw2["mean_r2"], label="SAW")
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

    if args.rw_traj:
        plot_traj(args.rw_traj, f"{args.out_prefix}_rw_traj.png", args.dim)

    if args.saw_traj:
        plot_traj(args.saw_traj, f"{args.out_prefix}_saw_traj.png", args.dim)


if __name__ == "__main__":
    main()