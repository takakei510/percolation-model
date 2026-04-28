# scripts/utils/common.py

import re
from pathlib import Path


def extract_L(path):
    match = re.search(r"L_(\d+)", str(path))
    if match is None:
        raise ValueError(f"L not found in filename: {path}")
    return int(match.group(1))


def get_sweep_dir(dim):
    return Path(f"data/{dim}d/sweep")


def get_cluster_size_dir(dim):
    return Path(f"data/{dim}d/size_sweep_cluster_sizes")


def get_cluster_coord_dir(dim):
    return Path(f"data/{dim}d/size_sweep_clusters")