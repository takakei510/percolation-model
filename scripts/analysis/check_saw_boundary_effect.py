import argparse
import csv
import os
import re


def parse_metadata_from_path(path):
    path = os.path.normpath(path)
    parts = path.split(os.sep)

    dim_name = None
    if "2d" in parts:
        dim_name = "2d"
    elif "3d" in parts:
        dim_name = "3d"

    dim = int(dim_name[0]) if dim_name else ""

    model = ""
    case = ""
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
        pattern = re.compile(r"^L(?P<L>\d+)_N(?P<N>\d+)_T(?P<T>\d+)(?:_(?P<model>.+))?$")
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
        "dim": dim,
        "model": model,
        "case": case,
        "L": L,
        "N": N,
        "T": T,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-csv", required=True)
    args = parser.parse_args()

    if not os.path.exists(args.input):
        raise FileNotFoundError(f"Input file not found: {args.input}")

    with open(args.input, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    required = ["trial", "final_step", "trapped", "contact_dead", "boundary_dead"]
    if not rows:
        raise ValueError(f"Input CSV {args.input} contains no rows")
    missing = [c for c in required if c not in rows[0]]
    if missing:
        raise ValueError(f"Input CSV {args.input} is missing required columns: {', '.join(missing)}")

    metadata = parse_metadata_from_path(args.input)

    diagnostics = []
    final_steps = []
    trapped_count = 0
    boundary_dead_count = 0
    contact_dead_count = 0

    for row in rows:
        try:
            final_step = int(row["final_step"])
            trapped = int(row["trapped"])
            boundary_dead = int(row["boundary_dead"])
            contact_dead = int(row["contact_dead"])
        except ValueError:
            raise ValueError(f"Input CSV {args.input} contains invalid numeric values")

        diagnostics.append({
            "trial": int(row["trial"]),
            "final_step": final_step,
            "trapped": trapped,
            "boundary_dead": boundary_dead,
            "contact_dead": contact_dead,
        })
        final_steps.append(final_step)
        trapped_count += trapped
        boundary_dead_count += boundary_dead
        contact_dead_count += contact_dead

    n = len(diagnostics)
    mean_final = sum(final_steps) / n
    max_final = max(final_steps)
    fraction_boundary = boundary_dead_count / n
    fraction_trapped = trapped_count / n

    print("Metadata:")
    print(metadata)
    print("Summary:")
    print(f"mean_final_step: {mean_final}")
    print(f"max_final_step: {max_final}")
    print(f"fraction_boundary_dead: {fraction_boundary}")
    print(f"fraction_trapped: {fraction_trapped}")

    with open(args.output_csv, "w", newline="") as out:
        writer = csv.DictWriter(
            out,
            fieldnames=["trial", "final_step", "trapped", "boundary_dead", "contact_dead"],
        )
        writer.writeheader()
        for row in diagnostics:
            writer.writerow(row)

    print(f"Saved: {args.output_csv}")


if __name__ == "__main__":
    main()
