import math
import os
import subprocess
import tempfile
import unittest

import numpy as np
import pandas as pd


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUILD_MAIN = os.path.join(PROJECT_ROOT, "build", "main")

DIRS_2D = ((1, 0), (-1, 0), (0, 1), (0, -1))


def run_config(config_text, workdir, name):
    config_path = os.path.join(workdir, f"{name}.cfg")
    with open(config_path, "w", encoding="utf-8") as handle:
        handle.write(config_text)

    return subprocess.run(
        [BUILD_MAIN, config_path],
        cwd=PROJECT_ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def read_csv(path):
    return pd.read_csv(path)


def exact_saw_stats(max_n):
    counts = [0] * (max_n + 1)
    sum_r2 = [0.0] * (max_n + 1)
    visited = {(0, 0)}

    def dfs(step, x, y):
        counts[step] += 1
        sum_r2[step] += float(x * x + y * y)
        if step == max_n:
            return

        for dx, dy in DIRS_2D:
            nx = x + dx
            ny = y + dy
            if (nx, ny) in visited:
                continue
            visited.add((nx, ny))
            dfs(step + 1, nx, ny)
            visited.remove((nx, ny))

    dfs(0, 0, 0)
    mean_r2 = [sum_r2[n] / counts[n] if counts[n] else float("nan") for n in range(max_n + 1)]
    return counts, mean_r2


def assert_finite_numeric_frame(testcase, frame, columns):
    for column in columns:
        testcase.assertTrue(np.isfinite(pd.to_numeric(frame[column], errors="coerce")).all(), column)


class PermWalkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exact_counts, cls.exact_mean_r2 = exact_saw_stats(12)

    def test_exact_enumeration_sanity(self):
        self.assertEqual(self.exact_counts[1], 4)
        self.assertEqual(self.exact_counts[2], 12)
        self.assertAlmostEqual(self.exact_mean_r2[1], 1.0)

    def test_config_default_falls_back_to_kinetic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_cfg = f"""mode=random_walk
walk_type=saw
dim=2
spatial_backend=hash
boundary=infinite
n_steps=8
n_trials=5
seed=12345
output={tmpdir}/default/saw.csv
"""
            kinetic_cfg = f"""mode=random_walk
walk_type=saw
walk_algorithm=kinetic
dim=2
spatial_backend=hash
boundary=infinite
n_steps=8
n_trials=5
seed=12345
output={tmpdir}/kinetic/saw.csv
"""

            default_result = run_config(base_cfg, tmpdir, "default")
            kinetic_result = run_config(kinetic_cfg, tmpdir, "kinetic")

            self.assertEqual(default_result.returncode, 0, default_result.stderr)
            self.assertEqual(kinetic_result.returncode, 0, kinetic_result.stderr)
            self.assertTrue(read_csv(f"{tmpdir}/default/saw.csv").equals(read_csv(f"{tmpdir}/kinetic/saw.csv")))

    def test_invalid_walk_algorithm_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = f"""mode=random_walk
walk_type=saw
walk_algorithm=bogus
dim=2
spatial_backend=hash
boundary=infinite
n_steps=4
n_trials=1
seed=12345
output={tmpdir}/out/saw.csv
"""
            result = run_config(cfg, tmpdir, "invalid")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid walk_algorithm", result.stderr)

    def test_perm_rejects_unsupported_settings(self):
        cases = [
            ("dim=3", "PERM only supports dim=2"),
            ("spatial_backend=dense", "boundary=infinite is only supported with spatial_backend=hash"),
            ("boundary=free", "spatial_backend=hash currently requires boundary=infinite"),
            ("walk_type=rw", "PERM only supports walk_type=saw"),
        ]

        for replacement, expected in cases:
            with self.subTest(replacement=replacement):
                with tempfile.TemporaryDirectory() as tmpdir:
                    cfg = f"""mode=random_walk
walk_type=saw
walk_algorithm=perm
dim=2
spatial_backend=hash
boundary=infinite
n_steps=4
n_tours=4
seed=12345
output={tmpdir}/perm/perm.csv
"""
                    cfg = cfg.replace("dim=2", replacement) if replacement.startswith("dim=") else cfg
                    cfg = cfg.replace("spatial_backend=hash", replacement) if replacement.startswith("spatial_backend=") else cfg
                    cfg = cfg.replace("boundary=infinite", replacement) if replacement.startswith("boundary=") else cfg
                    cfg = cfg.replace("walk_type=saw", replacement) if replacement.startswith("walk_type=") else cfg
                    result = run_config(cfg, tmpdir, "perm_invalid")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(expected, result.stderr)

    def test_rosenbluth_is_reproducible_and_csv_is_finite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_1 = f"""mode=random_walk
walk_type=saw
walk_algorithm=rosenbluth
dim=2
spatial_backend=hash
boundary=infinite
n_steps=12
n_tours=2000
seed=12345
output={tmpdir}/rosenbluth_1/rosenbluth.csv
"""
            cfg_2 = f"""mode=random_walk
walk_type=saw
walk_algorithm=rosenbluth
dim=2
spatial_backend=hash
boundary=infinite
n_steps=12
n_tours=2000
seed=12345
output={tmpdir}/rosenbluth_2/rosenbluth.csv
"""
            first = run_config(cfg_1, tmpdir, "rosenbluth_1")
            second = run_config(cfg_2, tmpdir, "rosenbluth_2")

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)

            frame_1 = read_csv(f"{tmpdir}/rosenbluth_1/rosenbluth.csv")
            frame_2 = read_csv(f"{tmpdir}/rosenbluth_2/rosenbluth.csv")
            self.assertEqual(
                list(frame_1.columns),
                [
                    "step",
                    "weighted_mean_r2",
                    "weighted_mean_r2_standard_error",
                    "partition_sum_estimate",
                    "partition_sum_standard_error",
                    "log_partition_sum",
                    "partition_sum_mantissa",
                    "partition_sum_exponent",
                    "sample_count",
                    "nonzero_tours",
                    "completed_tours",
                    "branch_weight_ess",
                    "tour_weight_ess",
                    "mean_weight",
                    "max_weight",
                    "lower_threshold",
                    "upper_threshold",
                    "threshold_enabled",
                ],
            )
            assert_finite_numeric_frame(
                self,
                frame_1,
                [
                    "step",
                    "weighted_mean_r2",
                    "weighted_mean_r2_standard_error",
                    "partition_sum_estimate",
                    "partition_sum_standard_error",
                    "log_partition_sum",
                    "partition_sum_mantissa",
                    "partition_sum_exponent",
                    "sample_count",
                    "nonzero_tours",
                    "completed_tours",
                    "branch_weight_ess",
                    "tour_weight_ess",
                    "mean_weight",
                    "max_weight",
                    "lower_threshold",
                    "upper_threshold",
                    "threshold_enabled",
                ],
            )
            self.assertTrue(frame_1.equals(frame_2))

            exact_counts = np.asarray(self.exact_counts[:13], dtype=float)
            exact_mean_r2 = np.asarray(self.exact_mean_r2[:13], dtype=float)
            observed = frame_1.sort_values("step")
            self.assertTrue(np.allclose(observed["partition_sum_estimate"].to_numpy(), exact_counts, rtol=0.20, atol=0.25))
            self.assertTrue(np.allclose(observed["weighted_mean_r2"].to_numpy(), exact_mean_r2, rtol=0.20, atol=0.25, equal_nan=True))

    def test_perm_is_reproducible_and_generates_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_1 = f"""mode=random_walk
walk_type=saw
walk_algorithm=perm
dim=2
spatial_backend=hash
boundary=infinite
n_steps=12
n_tours=2000
seed=12345
perm_c_minus=0.2
perm_c_plus=2.0
perm_min_tours_for_threshold=50
output={tmpdir}/perm_1/perm.csv
"""
            cfg_2 = f"""mode=random_walk
walk_type=saw
walk_algorithm=perm
dim=2
spatial_backend=hash
boundary=infinite
n_steps=12
n_tours=2000
seed=12345
perm_c_minus=0.2
perm_c_plus=2.0
perm_min_tours_for_threshold=50
output={tmpdir}/perm_2/perm.csv
"""
            first = run_config(cfg_1, tmpdir, "perm_1")
            second = run_config(cfg_2, tmpdir, "perm_2")

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)

            frame_1 = read_csv(f"{tmpdir}/perm_1/perm.csv")
            frame_2 = read_csv(f"{tmpdir}/perm_2/perm.csv")
            tours = read_csv(f"{tmpdir}/perm_1/perm_tours.csv")
            self.assertEqual(
                list(frame_1.columns),
                [
                    "step",
                    "weighted_mean_r2",
                    "weighted_mean_r2_standard_error",
                    "partition_sum_estimate",
                    "partition_sum_standard_error",
                    "log_partition_sum",
                    "partition_sum_mantissa",
                    "partition_sum_exponent",
                    "sample_count",
                    "nonzero_tours",
                    "completed_tours",
                    "branch_weight_ess",
                    "tour_weight_ess",
                    "mean_weight",
                    "max_weight",
                    "lower_threshold",
                    "upper_threshold",
                    "threshold_enabled",
                ],
            )
            self.assertEqual(
                list(tours.columns),
                [
                    "tour",
                    "max_reached_step",
                    "generated_branches",
                    "pruned_count",
                    "enriched_count",
                    "max_stack_size",
                    "tour_total_nodes",
                    "tour_clone_count",
                    "clone_count",
                    "clone_time",
                    "copied_path_elements",
                    "copied_hash_capacity",
                ],
            )
            assert_finite_numeric_frame(
                self,
                frame_1,
                [
                    "step",
                    "weighted_mean_r2",
                    "weighted_mean_r2_standard_error",
                    "partition_sum_estimate",
                    "partition_sum_standard_error",
                    "log_partition_sum",
                    "partition_sum_mantissa",
                    "partition_sum_exponent",
                    "sample_count",
                    "nonzero_tours",
                    "completed_tours",
                    "branch_weight_ess",
                    "tour_weight_ess",
                    "mean_weight",
                    "max_weight",
                    "lower_threshold",
                    "upper_threshold",
                    "threshold_enabled",
                ],
            )
            assert_finite_numeric_frame(
                self,
                tours,
                [
                    "tour",
                    "max_reached_step",
                    "generated_branches",
                    "pruned_count",
                    "enriched_count",
                    "max_stack_size",
                    "tour_total_nodes",
                    "tour_clone_count",
                    "clone_count",
                    "clone_time",
                    "copied_path_elements",
                    "copied_hash_capacity",
                ],
            )
            self.assertTrue(frame_1.equals(frame_2))

            exact_counts = np.asarray(self.exact_counts[:13], dtype=float)
            exact_mean_r2 = np.asarray(self.exact_mean_r2[:13], dtype=float)
            observed = frame_1.sort_values("step")
            self.assertTrue(np.allclose(observed["partition_sum_estimate"].to_numpy(), exact_counts, rtol=0.25, atol=0.35))
            self.assertTrue(np.allclose(observed["weighted_mean_r2"].to_numpy(), exact_mean_r2, rtol=0.25, atol=0.35, equal_nan=True))

    def test_perm_small_toy_triggers_branching(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = f"""mode=random_walk
walk_type=saw
walk_algorithm=perm
dim=2
spatial_backend=hash
boundary=infinite
n_steps=1
n_tours=40
seed=12345
perm_c_minus=0.01
perm_c_plus=0.10
perm_min_tours_for_threshold=1
output={tmpdir}/toy/perm.csv
"""
            result = run_config(cfg, tmpdir, "perm_toy")
            self.assertEqual(result.returncode, 0, result.stderr)
            tours = read_csv(f"{tmpdir}/toy/perm_tours.csv")
            frame = read_csv(f"{tmpdir}/toy/perm.csv")
            self.assertGreater(int(tours["tour_clone_count"].sum()), 0)
            self.assertGreaterEqual(int(tours["max_stack_size"].max()), 2)
            self.assertTrue(np.isfinite(frame["partition_sum_estimate"]).all())
            self.assertAlmostEqual(float(frame["partition_sum_estimate"].iloc[-1]), 4.0, delta=1.0)
            self.assertAlmostEqual(float(frame["weighted_mean_r2"].iloc[-1]), 1.0, delta=1.0)

    def test_perm_pruning_preserves_expected_weight(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = f"""mode=random_walk
walk_type=saw
walk_algorithm=perm
dim=2
spatial_backend=hash
boundary=infinite
n_steps=1
n_tours=5000
seed=12345
perm_c_minus=10.0
perm_c_plus=20.0
perm_min_tours_for_threshold=0
output={tmpdir}/prune/perm.csv
"""
            result = run_config(cfg, tmpdir, "perm_prune")
            self.assertEqual(result.returncode, 0, result.stderr)
            frame = read_csv(f"{tmpdir}/prune/perm.csv")
            tours = read_csv(f"{tmpdir}/prune/perm_tours.csv")
            self.assertGreater(int(tours["pruned_count"].sum()), 0)
            self.assertAlmostEqual(float(frame["partition_sum_estimate"].iloc[-1]), 4.0, delta=0.5)
            self.assertAlmostEqual(float(frame["weighted_mean_r2"].iloc[-1]), 1.0, delta=0.5)

    def test_perm_multiple_seeds_track_exact_small_n(self):
        seeds = [111, 222, 333]
        estimates_z = []
        estimates_r2 = []

        with tempfile.TemporaryDirectory() as tmpdir:
            for seed in seeds:
                cfg = f"""mode=random_walk
walk_type=saw
walk_algorithm=perm
dim=2
spatial_backend=hash
boundary=infinite
n_steps=12
n_tours=2000
seed={seed}
perm_c_minus=0.2
perm_c_plus=2.0
perm_min_tours_for_threshold=50
output={tmpdir}/seed_{seed}/perm.csv
"""
                result = run_config(cfg, tmpdir, f"perm_seed_{seed}")
                self.assertEqual(result.returncode, 0, result.stderr)
                frame = read_csv(f"{tmpdir}/seed_{seed}/perm.csv")
                estimates_z.append(float(frame["partition_sum_estimate"].iloc[-1]))
                estimates_r2.append(float(frame["weighted_mean_r2"].iloc[-1]))

        exact_z = float(self.exact_counts[12])
        exact_r2 = float(self.exact_mean_r2[12])
        self.assertTrue(all(np.isfinite(estimates_z)))
        self.assertTrue(all(np.isfinite(estimates_r2)))
        self.assertAlmostEqual(float(np.mean(estimates_z)), exact_z, delta=exact_z * 0.25)
        self.assertAlmostEqual(float(np.mean(estimates_r2)), exact_r2, delta=exact_r2 * 0.25)


if __name__ == "__main__":
    unittest.main()