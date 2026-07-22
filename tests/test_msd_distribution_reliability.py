import math
import os
import subprocess
import sys
import tempfile
import unittest

import pandas as pd
import numpy as np


SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "analysis"))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from msd_reliability_common import attach_reliability_metrics, compute_summary_by_step, validate_sample_frame


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUILD_MAIN = os.path.join(PROJECT_ROOT, "build", "main")


def _run_config(config_text, workdir, name):
    config_path = os.path.join(workdir, f"{name}.cfg")
    with open(config_path, "w", encoding="utf-8") as handle:
        handle.write(config_text)

    subprocess.run(
        [BUILD_MAIN, config_path],
        cwd=PROJECT_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _read_csv(path):
    return pd.read_csv(path)


class MsdReliabilitySummaryTest(unittest.TestCase):
    def test_summary_statistics(self):
        frame = pd.DataFrame(
            {
                "trial": [0, 1, 2, 3, 4],
                "step": [10, 10, 10, 10, 10],
                "r2": [1, 2, 3, 4, 10],
                "lifetime": [20, 20, 20, 20, 20],
                "alive": [1, 1, 1, 1, 1],
                "trapped": [0, 0, 1, 0, 1],
                "boundary_dead": [0, 0, 0, 0, 0],
                "contact_dead": [0, 0, 1, 0, 0],
            }
        )

        summary = compute_summary_by_step(frame, n_trials=10, fit_min_alive=3, fit_min_survival_probability=0.1, fit_max_relative_standard_error=1.0)
        row = summary.iloc[0]

        self.assertEqual(int(row["step"]), 10)
        self.assertEqual(int(row["n_alive"]), 5)
        self.assertAlmostEqual(row["survival_probability"], 0.5)
        self.assertAlmostEqual(row["mean_r2"], 4.0)
        self.assertAlmostEqual(row["median_r2"], 3.0)
        self.assertAlmostEqual(row["variance_r2"], 12.5)
        self.assertAlmostEqual(row["std_r2"], math.sqrt(12.5))
        self.assertAlmostEqual(row["standard_error_r2"], math.sqrt(12.5) / math.sqrt(5.0))
        self.assertAlmostEqual(row["relative_standard_error_r2"], (math.sqrt(12.5) / math.sqrt(5.0)) / 4.0)
        self.assertAlmostEqual(row["q10_r2"], 1.4)
        self.assertAlmostEqual(row["q25_r2"], 2.0)
        self.assertAlmostEqual(row["q75_r2"], 4.0)
        self.assertAlmostEqual(row["q90_r2"], 7.6)
        self.assertAlmostEqual(row["q95_r2"], 8.8)
        self.assertAlmostEqual(row["q99_r2"], 9.76)
        self.assertAlmostEqual(row["max_r2"], 10.0)
        self.assertAlmostEqual(row["coefficient_of_variation"], math.sqrt(12.5) / 4.0)
        self.assertAlmostEqual(row["mean_median_ratio"], 4.0 / 3.0)
        self.assertEqual(int(row["fit_eligible"]), 1)

    def test_single_point_and_zero_mean(self):
        frame = pd.DataFrame(
            {
                "trial": [0],
                "step": [7],
                "r2": [0.0],
                "lifetime": [7],
                "alive": [1],
                "trapped": [0],
                "boundary_dead": [0],
                "contact_dead": [0],
            }
        )

        summary = compute_summary_by_step(frame, n_trials=4, fit_min_alive=1, fit_min_survival_probability=0.0, fit_max_relative_standard_error=1.0)
        row = summary.iloc[0]

        self.assertEqual(int(row["n_alive"]), 1)
        self.assertTrue(math.isnan(row["std_r2"]))
        self.assertTrue(math.isnan(row["variance_r2"]))
        self.assertTrue(math.isnan(row["standard_error_r2"]))
        self.assertTrue(math.isnan(row["relative_standard_error_r2"]))
        self.assertTrue(math.isnan(row["coefficient_of_variation"]))
        self.assertTrue(math.isnan(row["mean_median_ratio"]))
        self.assertEqual(int(row["fit_eligible"]), 0)

    def test_validation_rejects_duplicate_trial_step(self):
        frame = pd.DataFrame(
            {
                "trial": [0, 0],
                "step": [1, 1],
                "r2": [1.0, 2.0],
                "lifetime": [1, 1],
                "alive": [1, 1],
                "trapped": [0, 0],
                "boundary_dead": [0, 0],
                "contact_dead": [0, 0],
            }
        )

        with self.assertRaises(ValueError):
            validate_sample_frame(frame, "dummy.csv")

    def test_reliability_metrics_merge(self):
        fit_frame = pd.DataFrame({"step": [10, 20, 30], "value": [1.0, 2.0, 3.0]})
        reliability = pd.DataFrame(
            {
                "step": [10, 20, 30],
                "n_alive": [5, 4, 3],
                "relative_standard_error_r2": [0.1, 0.2, 0.3],
                "fit_eligible": [1, 1, 0],
            }
        )

        merged = attach_reliability_metrics(fit_frame, reliability)
        self.assertEqual(int(merged["fit_n_alive_min"].iloc[0]), 3)
        self.assertEqual(int(merged["fit_n_alive_median"].iloc[0]), 4)
        self.assertAlmostEqual(merged["fit_max_relative_standard_error"].iloc[0], 0.3)
        self.assertEqual(int(merged["fit_all_points_eligible"].iloc[0]), 0)
        self.assertEqual(int(merged["fit_reliability_point_count"].iloc[0]), 3)

    def test_dense_and_hash_outputs_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dense_dir = os.path.join(tmpdir, "dense")
            hash_dir = os.path.join(tmpdir, "hash")
            os.makedirs(dense_dir)
            os.makedirs(hash_dir)

            dense_cfg = f"""mode=random_walk
walk_type=saw
dim=2
spatial_backend=dense
boundary=free
L=64
n_steps=20
n_trials=5
seed=12345
save_trajectory=0
save_msd_distribution=1
msd_sample_mode=exact
msd_distribution_steps=5,10,15,20
output={dense_dir}/saw.csv
"""

            hash_cfg = f"""mode=random_walk
walk_type=saw
dim=2
spatial_backend=hash
boundary=infinite
n_steps=20
n_trials=5
seed=12345
save_trajectory=0
save_msd_distribution=1
msd_sample_mode=exact
msd_distribution_steps=5,10,15,20
output={hash_dir}/saw.csv
"""

            _run_config(dense_cfg, dense_dir, "dense")
            _run_config(hash_cfg, hash_dir, "hash")

            self.assertTrue(_read_csv(os.path.join(dense_dir, "final_steps.csv")).equals(_read_csv(os.path.join(hash_dir, "final_steps.csv"))))
            self.assertTrue(_read_csv(os.path.join(dense_dir, "saw.csv")).equals(_read_csv(os.path.join(hash_dir, "saw.csv"))))
            self.assertTrue(_read_csv(os.path.join(dense_dir, "msd_samples.csv")).equals(_read_csv(os.path.join(hash_dir, "msd_samples.csv"))))

    def test_hash_infinite_handles_negative_coordinates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = f"""mode=random_walk
walk_type=saw
dim=2
spatial_backend=hash
boundary=infinite
n_steps=30
n_trials=1
seed=12345
save_trajectory=1
save_trajectory_trials=1
trajectory_output={tmpdir}/trajectory.csv
save_msd_distribution=1
msd_sample_mode=none
msd_distribution_steps=5,10,15,20,25,30
output={tmpdir}/saw.csv
"""
            _run_config(cfg, tmpdir, "hash_negative")
            trajectory = _read_csv(os.path.join(tmpdir, "trajectory.csv"))
            self.assertTrue(((trajectory[["x", "y", "z"]] < 0).any(axis=1)).any())

    def test_streaming_summary_matches_exact_recompute(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = f"""mode=random_walk
walk_type=saw
dim=2
spatial_backend=hash
boundary=infinite
n_steps=20
n_trials=20
seed=12345
save_trajectory=0
save_msd_distribution=1
msd_sample_mode=exact
msd_distribution_steps=5,10,15,20
output={tmpdir}/saw.csv
"""
            _run_config(cfg, tmpdir, "exact_summary")

            samples = _read_csv(os.path.join(tmpdir, "msd_samples.csv"))
            summary = _read_csv(os.path.join(tmpdir, "msd_streaming_summary.csv"))
            recomputed = compute_summary_by_step(
                validate_sample_frame(samples, os.path.join(tmpdir, "msd_samples.csv")),
                n_trials=20,
                fit_min_alive=1,
                fit_min_survival_probability=0.0,
                fit_max_relative_standard_error=math.inf,
            )

            merged = summary.merge(recomputed, on="step", suffixes=("_stream", "_recomputed"))
            self.assertGreater(len(merged), 0)
            for column in ["n_alive", "mean_r2", "variance_r2", "std_r2", "standard_error_r2", "relative_standard_error_r2", "min_r2", "max_r2"]:
                self.assertTrue(np.allclose(merged[f"{column}_stream"], merged[f"{column}_recomputed"], equal_nan=True))

    def test_reservoir_is_reproducible_and_walk_invariant(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exact_dir = os.path.join(tmpdir, "exact")
            reservoir_dir = os.path.join(tmpdir, "reservoir")
            reservoir_dir_2 = os.path.join(tmpdir, "reservoir_2")
            os.makedirs(exact_dir)
            os.makedirs(reservoir_dir)
            os.makedirs(reservoir_dir_2)

            exact_cfg = f"""mode=random_walk
walk_type=saw
dim=2
spatial_backend=hash
boundary=infinite
n_steps=20
n_trials=10
seed=12345
save_trajectory=0
save_msd_distribution=1
msd_sample_mode=exact
msd_distribution_steps=5,10,15,20
output={exact_dir}/saw.csv
"""

            reservoir_cfg = f"""mode=random_walk
walk_type=saw
dim=2
spatial_backend=hash
boundary=infinite
n_steps=20
n_trials=10
seed=12345
save_trajectory=0
save_msd_distribution=1
msd_sample_mode=reservoir
msd_reservoir_size=5
sampling_seed=987654321
msd_distribution_steps=5,10,15,20
output={reservoir_dir}/saw.csv
"""

            reservoir_cfg_2 = f"""mode=random_walk
walk_type=saw
dim=2
spatial_backend=hash
boundary=infinite
n_steps=20
n_trials=10
seed=12345
save_trajectory=0
save_msd_distribution=1
msd_sample_mode=reservoir
msd_reservoir_size=5
sampling_seed=987654321
msd_distribution_steps=5,10,15,20
output={reservoir_dir_2}/saw.csv
"""

            _run_config(exact_cfg, exact_dir, "exact_walk")
            _run_config(reservoir_cfg, reservoir_dir, "reservoir_walk")
            _run_config(reservoir_cfg_2, reservoir_dir_2, "reservoir_walk_2")

            self.assertTrue(_read_csv(os.path.join(exact_dir, "final_steps.csv")).equals(_read_csv(os.path.join(reservoir_dir, "final_steps.csv"))))
            self.assertTrue(_read_csv(os.path.join(exact_dir, "saw.csv")).equals(_read_csv(os.path.join(reservoir_dir, "saw.csv"))))
            self.assertTrue(_read_csv(os.path.join(reservoir_dir, "msd_reservoir_samples.csv")).equals(_read_csv(os.path.join(reservoir_dir_2, "msd_reservoir_samples.csv"))))


if __name__ == "__main__":
    unittest.main()