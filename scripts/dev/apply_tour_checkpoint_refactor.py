#!/usr/bin/env python3
"""Apply the tour-checkpoint refactor to the current feature/perm sources.

This is intentionally a one-shot migration script. It uses guarded exact replacements
so it fails instead of silently editing an unexpected source revision.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one replacement target, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# include/config.h
config_h = ROOT / "include/config.h"
replace_once(
    config_h,
    "    int n_tours;\n    char start[32];",
    "    int n_tours;\n"
    "    char tour_checkpoint_mode[32]; // none / log10\n"
    "    int tour_checkpoint_start;\n"
    "    char start[32];",
)

# src/config.c
config_c = ROOT / "src/config.c"
replace_once(
    config_c,
    "    cfg->n_tours = 1;\n    cfg->save_trajectory = 0;",
    "    cfg->n_tours = 1;\n"
    "    strcpy(cfg->tour_checkpoint_mode, \"none\");\n"
    "    cfg->tour_checkpoint_start = 1;\n"
    "    cfg->save_trajectory = 0;",
)
replace_once(
    config_c,
    "        } else if (strcmp(key, \"n_tours\") == 0) {\n"
    "            cfg->n_tours = atoi(value);\n"
    "        } else if (strcmp(key, \"save_cluster_sizes\") == 0) {",
    "        } else if (strcmp(key, \"n_tours\") == 0) {\n"
    "            cfg->n_tours = atoi(value);\n"
    "        } else if (strcmp(key, \"tour_checkpoint_mode\") == 0) {\n"
    "            sscanf(value, \"%31s\", cfg->tour_checkpoint_mode);\n"
    "        } else if (strcmp(key, \"tour_checkpoint_start\") == 0) {\n"
    "            cfg->tour_checkpoint_start = atoi(value);\n"
    "        } else if (strcmp(key, \"save_cluster_sizes\") == 0) {",
)
replace_once(
    config_c,
    "    if (cfg->n_tours <= 0) {\n"
    "        fprintf(stderr, \"n_tours must be > 0\\n\");\n"
    "        free_lifetime_checkpoint_trials(cfg);\n"
    "        free_msd_distribution_steps(cfg);\n"
    "        return 0;\n"
    "    }\n\n"
    "    if (!(cfg->perm_c_minus > 0.0)",
    "    if (cfg->n_tours <= 0) {\n"
    "        fprintf(stderr, \"n_tours must be > 0\\n\");\n"
    "        free_lifetime_checkpoint_trials(cfg);\n"
    "        free_msd_distribution_steps(cfg);\n"
    "        return 0;\n"
    "    }\n\n"
    "    if (strcmp(cfg->tour_checkpoint_mode, \"none\") != 0 &&\n"
    "        strcmp(cfg->tour_checkpoint_mode, \"log10\") != 0) {\n"
    "        fprintf(stderr, \"Invalid tour_checkpoint_mode: %s\\n\", cfg->tour_checkpoint_mode);\n"
    "        free_lifetime_checkpoint_trials(cfg);\n"
    "        free_msd_distribution_steps(cfg);\n"
    "        return 0;\n"
    "    }\n\n"
    "    if (strcmp(cfg->tour_checkpoint_mode, \"log10\") == 0 &&\n"
    "        cfg->tour_checkpoint_start <= 0) {\n"
    "        fprintf(stderr, \"tour_checkpoint_start must be > 0 for log10 mode\\n\");\n"
    "        free_lifetime_checkpoint_trials(cfg);\n"
    "        free_msd_distribution_steps(cfg);\n"
    "        return 0;\n"
    "    }\n\n"
    "    if (!(cfg->perm_c_minus > 0.0)",
)

# src/perm.c
perm_c = ROOT / "src/perm.c"
helper = r'''
static int write_convergence_snapshot(
    FILE *fp,
    const Config *cfg,
    const StepStats *steps,
    const TourBuffer *buffer,
    size_t step_count,
    unsigned long long completed_tours
)
{
    if (!fp || completed_tours == 0ULL) {
        return 1;
    }

    TourBuffer prefix_buffer = *buffer;
    if (prefix_buffer.enabled) {
        prefix_buffer.tour_count = (size_t)completed_tours;
    }

    for (size_t step = 0; step < step_count; step++) {
        long double branch_sum = scaled_positive_value(&steps[step].branch_weight_sum);
        long double branch_sum_r2 = scaled_positive_value(&steps[step].branch_weight_r2_sum);
        long double branch_sum_sq = scaled_positive_value(&steps[step].branch_weight_squared_sum);
        long double tour_sum = scaled_positive_value(&steps[step].tour_weight_sum);
        long double tour_sum_r2 = scaled_positive_value(&steps[step].tour_weight_r2_sum);
        long double tour_sum_sq = scaled_positive_value(&steps[step].tour_weight_squared_sum);

        long double weighted_mean_r2 = (branch_sum > 0.0L) ? (branch_sum_r2 / branch_sum) : NAN;
        long double weighted_mean_r2_standard_error =
            compute_weighted_mean_r2_standard_error(&prefix_buffer, step, tour_sum, tour_sum_r2);
        long double partition_sum_estimate = tour_sum / (long double)completed_tours;
        long double partition_sum_standard_error =
            compute_partition_sum_standard_error(&steps[step], completed_tours);
        long double branch_weight_ess =
            (branch_sum_sq > 0.0L) ? (branch_sum * branch_sum / branch_sum_sq) : NAN;
        long double tour_weight_ess =
            (tour_sum_sq > 0.0L) ? (tour_sum * tour_sum / tour_sum_sq) : NAN;
        long double mean_weight =
            (steps[step].sample_count > 0ULL) ?
            (branch_sum / (long double)steps[step].sample_count) : NAN;

        long double lower_threshold = NAN;
        long double upper_threshold = NAN;
        int threshold_enabled = perm_threshold_for_step(
            cfg,
            steps,
            completed_tours,
            step,
            &lower_threshold,
            &upper_threshold
        );
        if (!threshold_enabled) {
            lower_threshold = NAN;
            upper_threshold = NAN;
        }

        fprintf(
            fp,
            "%llu,%zu,%.17Lg,%.17Lg,%.17Lg,%.17Lg,%llu,%llu,%.17Lg,%.17Lg,%.17Lg,%.17Lg,%.17Lg,%.17Lg,%d\n",
            completed_tours,
            step,
            weighted_mean_r2,
            weighted_mean_r2_standard_error,
            partition_sum_estimate,
            partition_sum_standard_error,
            steps[step].sample_count,
            steps[step].nonzero_tours,
            branch_weight_ess,
            tour_weight_ess,
            mean_weight,
            steps[step].max_weight,
            lower_threshold,
            upper_threshold,
            threshold_enabled
        );
    }

    return fflush(fp) == 0;
}

'''
replace_once(
    perm_c,
    "static int run_weighted_saw(const Config *cfg, int use_perm)\n{",
    helper + "static int run_weighted_saw(const Config *cfg, int use_perm)\n{",
)
replace_once(
    perm_c,
    "    char metadata_path[512];\n"
    "    build_sibling_path(main_path, sizeof(main_path), cfg->output, use_perm ? \"perm.csv\" : \"rosenbluth.csv\");\n"
    "    build_sibling_path(tours_path, sizeof(tours_path), cfg->output, \"perm_tours.csv\");\n"
    "    build_sibling_path(metadata_path, sizeof(metadata_path), cfg->output, \"simulation_metadata.json\");",
    "    char metadata_path[512];\n"
    "    char convergence_path[512];\n"
    "    build_sibling_path(main_path, sizeof(main_path), cfg->output, use_perm ? \"perm.csv\" : \"rosenbluth.csv\");\n"
    "    build_sibling_path(tours_path, sizeof(tours_path), cfg->output, \"perm_tours.csv\");\n"
    "    build_sibling_path(metadata_path, sizeof(metadata_path), cfg->output, \"simulation_metadata.json\");\n"
    "    build_sibling_path(convergence_path, sizeof(convergence_path), cfg->output, \"weighted_convergence.csv\");",
)
replace_once(
    perm_c,
    "    FILE *tours_fp = NULL;\n"
    "    if (use_perm) {",
    "    FILE *convergence_fp = NULL;\n"
    "    if (strcmp(cfg->tour_checkpoint_mode, \"log10\") == 0) {\n"
    "        convergence_fp = fopen(convergence_path, \"w\");\n"
    "        if (!convergence_fp) {\n"
    "            fprintf(stderr, \"Failed to open convergence file: %s\\n\", convergence_path);\n"
    "            fclose(main_fp);\n"
    "            tour_buffer_destroy(&buffer);\n"
    "            free(steps);\n"
    "            return 0;\n"
    "        }\n"
    "        fprintf(convergence_fp, \"checkpoint_tours,step,weighted_mean_r2,weighted_mean_r2_standard_error,partition_sum_estimate,partition_sum_standard_error,sample_count,nonzero_tours,branch_weight_ess,tour_weight_ess,mean_weight,max_weight,lower_threshold,upper_threshold,threshold_enabled\\n\");\n"
    "    }\n\n"
    "    FILE *tours_fp = NULL;\n"
    "    if (use_perm) {",
)
replace_once(
    perm_c,
    "            fclose(main_fp);\n"
    "            tour_buffer_destroy(&buffer);",
    "            if (convergence_fp) fclose(convergence_fp);\n"
    "            fclose(main_fp);\n"
    "            tour_buffer_destroy(&buffer);",
)
replace_once(
    perm_c,
    "    for (int tour = 0; tour < cfg->n_tours; tour++) {",
    "    unsigned long long next_checkpoint = (unsigned long long)cfg->tour_checkpoint_start;\n\n"
    "    for (int tour = 0; tour < cfg->n_tours; tour++) {",
)
replace_once(
    perm_c,
    "        if (use_perm && tours_fp) {\n"
    "            fprintf(tours_fp,",
    "        unsigned long long completed_tours = (unsigned long long)tour + 1ULL;\n"
    "        if (convergence_fp &&\n"
    "            (completed_tours == next_checkpoint || completed_tours == (unsigned long long)cfg->n_tours)) {\n"
    "            if (!write_convergence_snapshot(convergence_fp, cfg, steps, &buffer, step_count, completed_tours)) {\n"
    "                fprintf(stderr, \"Failed to write tour checkpoint at %llu tours\\n\", completed_tours);\n"
    "                goto cleanup_fail;\n"
    "            }\n"
    "            if (completed_tours == next_checkpoint) {\n"
    "                if (next_checkpoint <= ULLONG_MAX / 10ULL) {\n"
    "                    next_checkpoint *= 10ULL;\n"
    "                } else {\n"
    "                    next_checkpoint = ULLONG_MAX;\n"
    "                }\n"
    "            }\n"
    "        }\n\n"
    "        if (use_perm && tours_fp) {\n"
    "            fprintf(tours_fp,",
)
# ULLONG_MAX
replace_once(
    perm_c,
    "#include <math.h>\n#include <stdio.h>",
    "#include <math.h>\n#include <limits.h>\n#include <stdio.h>",
)
# Close convergence file on normal path before main_fp close.
replace_once(
    perm_c,
    "    if (fclose(main_fp) != 0) {",
    "    if (convergence_fp && fclose(convergence_fp) != 0) {\n"
    "        if (tours_fp) fclose(tours_fp);\n"
    "        fclose(main_fp);\n"
    "        tour_buffer_destroy(&buffer);\n"
    "        free(steps);\n"
    "        free(local_tour_weight_sum);\n"
    "        free(local_tour_weight_r2_sum);\n"
    "        free(local_tour_weight_squared_sum);\n"
    "        free(threshold_lower);\n"
    "        free(threshold_upper);\n"
    "        free(threshold_enabled);\n"
    "        return 0;\n"
    "    }\n\n"
    "    if (fclose(main_fp) != 0) {",
)
replace_once(
    perm_c,
    "cleanup_fail:\n    if (tours_fp) {",
    "cleanup_fail:\n"
    "    if (convergence_fp) {\n"
    "        fclose(convergence_fp);\n"
    "    }\n"
    "    if (tours_fp) {",
)

# Remove the obsolete malformed patch from the working tree if present; the workflow
# handles the tracked deletion separately.
print("Tour checkpoint refactor applied successfully.")
