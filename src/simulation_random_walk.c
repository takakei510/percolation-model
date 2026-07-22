#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#include "config.h"
#include "random_walk.h"

static double now_seconds(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

typedef struct {
    unsigned long long count;
    double mean;
    double m2;
    double min;
    double max;
} RunningStats;

typedef struct {
    double r2;
    int source_trial;
    int lifetime;
} ReservoirSample;

typedef struct {
    unsigned long long seen_count;
    size_t stored_count;
    size_t capacity;
    ReservoirSample *samples;
} ReservoirStep;

typedef struct {
    unsigned long long state;
} SamplingRng;

static void running_stats_init(RunningStats *stats)
{
    stats->count = 0ULL;
    stats->mean = 0.0;
    stats->m2 = 0.0;
    stats->min = INFINITY;
    stats->max = -INFINITY;
}

static void running_stats_update(RunningStats *stats, double value)
{
    stats->count++;
    double delta = value - stats->mean;
    stats->mean += delta / (double)stats->count;
    double delta2 = value - stats->mean;
    stats->m2 += delta * delta2;
    if (value < stats->min) {
        stats->min = value;
    }
    if (value > stats->max) {
        stats->max = value;
    }
}

static double running_stats_variance(const RunningStats *stats)
{
    if (!stats || stats->count < 2ULL) {
        return NAN;
    }
    return stats->m2 / (double)(stats->count - 1ULL);
}

static double running_stats_stddev(const RunningStats *stats)
{
    double variance = running_stats_variance(stats);
    return isnan(variance) ? NAN : sqrt(variance);
}

static unsigned long long sampling_rng_next(SamplingRng *rng)
{
    unsigned long long x = rng->state + 0x9e3779b97f4a7c15ULL;
    rng->state = x;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
    return x ^ (x >> 31);
}

static unsigned long long sampling_rng_bounded(SamplingRng *rng, unsigned long long bound)
{
    if (bound == 0ULL) {
        return 0ULL;
    }

    unsigned long long threshold = (unsigned long long)(-bound) % bound;
    for (;;) {
        unsigned long long value = sampling_rng_next(rng);
        if (value >= threshold) {
            return value % bound;
        }
    }
}

static int parse_sampling_seed(const Config *cfg, unsigned long long *out_seed)
{
    if (cfg->sampling_seed_provided) {
        char *endptr = NULL;
        unsigned long long value = strtoull(cfg->sampling_seed_str, &endptr, 10);
        if (endptr == cfg->sampling_seed_str || *endptr != '\0') {
            return 0;
        }
        *out_seed = value;
        return 1;
    }

    *out_seed = ((unsigned long long)cfg->resolved_seed << 1) ^ 0xd1b54a32d192ed03ULL;
    return 1;
}

static void reservoir_step_init(ReservoirStep *step, size_t capacity)
{
    step->seen_count = 0ULL;
    step->stored_count = 0;
    step->capacity = capacity;
    step->samples = capacity > 0 ? calloc(capacity, sizeof(ReservoirSample)) : NULL;
}

static void reservoir_step_destroy(ReservoirStep *step)
{
    if (!step) {
        return;
    }
    free(step->samples);
    step->samples = NULL;
    step->capacity = 0;
    step->seen_count = 0ULL;
    step->stored_count = 0;
}

static void reservoir_step_update(ReservoirStep *step, SamplingRng *rng, double r2, int source_trial, int lifetime)
{
    if (!step) {
        return;
    }

    step->seen_count++;

    if (step->stored_count < step->capacity) {
        step->samples[step->stored_count].r2 = r2;
        step->samples[step->stored_count].source_trial = source_trial;
        step->samples[step->stored_count].lifetime = lifetime;
        step->stored_count++;
        return;
    }

    unsigned long long j = sampling_rng_bounded(rng, step->seen_count);
    if (j < step->capacity) {
        step->samples[j].r2 = r2;
        step->samples[j].source_trial = source_trial;
        step->samples[j].lifetime = lifetime;
    }
}

static void build_sibling_path(char *dst, size_t dst_size, const char *src, const char *filename)
{
    strncpy(dst, src, dst_size - 1);
    dst[dst_size - 1] = '\0';

    char *slash = strrchr(dst, '/');
    if (slash) {
        strcpy(slash + 1, filename);
    } else {
        strncpy(dst, filename, dst_size - 1);
        dst[dst_size - 1] = '\0';
    }
}

static int ensure_parent_dir(const char *path)
{
    char buffer[512];

    if (strlen(path) >= sizeof(buffer)) {
        return 0;
    }

    strcpy(buffer, path);
    char *slash = strrchr(buffer, '/');
    if (!slash) {
        return 1;
    }
    *slash = '\0';

    for (char *p = buffer + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0';
            if (mkdir(buffer, 0777) != 0 && errno != EEXIST) {
                return 0;
            }
            *p = '/';
        }
    }

    if (mkdir(buffer, 0777) != 0 && errno != EEXIST) {
        return 0;
    }

    return 1;
}

static int copy_file(const char *src_path, const char *dst_path)
{
    FILE *src = fopen(src_path, "rb");
    if (!src) {
        return 0;
    }

    if (!ensure_parent_dir(dst_path)) {
        fclose(src);
        return 0;
    }

    FILE *dst = fopen(dst_path, "wb");
    if (!dst) {
        fclose(src);
        return 0;
    }

    char buffer[8192];
    size_t nread;
    while ((nread = fread(buffer, 1, sizeof(buffer), src)) > 0) {
        if (fwrite(buffer, 1, nread, dst) != nread) {
            fclose(src);
            fclose(dst);
            return 0;
        }
    }

    fclose(src);
    if (fclose(dst) != 0) {
        return 0;
    }

    return 1;
}

static void write_json_string(FILE *fp, const char *value)
{
    fputc('"', fp);
    for (const unsigned char *p = (const unsigned char *)value; p && *p; p++) {
        if (*p == '"' || *p == '\\') {
            fputc('\\', fp);
            fputc(*p, fp);
        } else if (*p == '\n') {
            fputs("\\n", fp);
        } else if (*p == '\r') {
            fputs("\\r", fp);
        } else if (*p == '\t') {
            fputs("\\t", fp);
        } else {
            fputc(*p, fp);
        }
    }
    fputc('"', fp);
}

static int write_simulation_metadata(
    const Config *cfg,
    unsigned long long resolved_sampling_seed,
    const char *sample_path,
    const char *summary_path,
    const char *metadata_path,
    const char *quantile_source,
    size_t hash_capacity
)
{
    FILE *fp = fopen(metadata_path, "w");
    if (!fp) {
        return 0;
    }

    fprintf(fp, "{\n");
    fprintf(fp, "  \"seed\": ");
    if (cfg->seed_provided) {
        write_json_string(fp, cfg->seed_str);
    } else {
        write_json_string(fp, "time(NULL)");
    }
    fprintf(fp, ",\n");
    fprintf(fp, "  \"seed_offset\": ");
    if (cfg->seed_offset_provided) {
        write_json_string(fp, cfg->seed_offset_str);
    } else {
        fputs("null", fp);
    }
    fprintf(fp, ",\n");
    fprintf(fp, "  \"actual_seed\": %u,\n", cfg->resolved_seed_set ? cfg->resolved_seed : 0u);
    fprintf(fp, "  \"sampling_seed\": ");
    if (cfg->sampling_seed_provided) {
        write_json_string(fp, cfg->sampling_seed_str);
    } else {
        fprintf(fp, "%llu", resolved_sampling_seed);
    }
    fprintf(fp, ",\n");
    fprintf(fp, "  \"dim\": %d,\n", cfg->dim);
    fprintf(fp, "  \"L\": ");
    if (cfg->L < 0) {
        fputs("null", fp);
    } else {
        fprintf(fp, "%d", cfg->L);
    }
    fprintf(fp, ",\n");
    fprintf(fp, "  \"spatial_backend\": ");
    write_json_string(fp, cfg->spatial_backend);
    fprintf(fp, ",\n");
    fprintf(fp, "  \"boundary\": ");
    write_json_string(fp, cfg->boundary);
    fprintf(fp, ",\n");
    fprintf(fp, "  \"hash_capacity\": %zu,\n", hash_capacity);
    fprintf(fp, "  \"hash_max_load_factor\": %.6f,\n", cfg->hash_max_load_factor);
    fprintf(fp, "  \"n_steps\": %d,\n", cfg->n_steps);
    fprintf(fp, "  \"n_trials\": %d,\n", cfg->n_trials);
    fprintf(fp, "  \"walk_type\": ");
    write_json_string(fp, cfg->walk_type);
    fprintf(fp, ",\n");
    fprintf(fp, "  \"msd_sample_mode\": ");
    write_json_string(fp, cfg->msd_sample_mode);
    fprintf(fp, ",\n");
    fprintf(fp, "  \"msd_reservoir_size\": %d,\n", cfg->msd_reservoir_size);
    fprintf(fp, "  \"msd_distribution_steps\": ");
    write_json_string(fp, cfg->msd_distribution_steps);
    fprintf(fp, ",\n");
    fprintf(fp, "  \"quantile_source\": ");
    write_json_string(fp, quantile_source);
    fprintf(fp, ",\n");
    fprintf(fp, "  \"output_file\": ");
    write_json_string(fp, sample_path ? sample_path : "");
    fprintf(fp, ",\n");
    fprintf(fp, "  \"msd_streaming_summary_file\": ");
    if (summary_path) {
        write_json_string(fp, summary_path);
    } else {
        fputs("null", fp);
    }
    fprintf(fp, "\n}\n");

    if (fclose(fp) != 0) {
        return 0;
    }

    return 1;
}

static int create_legacy_msd_alias(const char *sample_path, const char *legacy_path)
{
    unlink(legacy_path);

    if (link(sample_path, legacy_path) == 0) {
        return 1;
    }

    if (symlink(sample_path, legacy_path) == 0) {
        return 1;
    }

    fprintf(stderr, "Warning: failed to create legacy MSD alias: %s -> %s\n", legacy_path, sample_path);
    return 1;
}

static int save_lifetime_checkpoint(const char *final_path, int checkpoint_trial)
{
    char checkpoint_base[512];
    char checkpoint_path[512];

    if (strlen(final_path) >= sizeof(checkpoint_base)) {
        return 0;
    }

    strcpy(checkpoint_base, final_path);
    char *slash = strrchr(checkpoint_base, '/');
    if (!slash) {
        return 0;
    }
    *slash = '\0';

    if (snprintf(checkpoint_path, sizeof(checkpoint_path), "%s/checkpoints/T%d/final_steps.csv", checkpoint_base, checkpoint_trial) >= (int)sizeof(checkpoint_path)) {
        return 0;
    }

    return copy_file(final_path, checkpoint_path);
}

static void write_exact_sample_row(FILE *fp, int trial, int step, double r2, int lifetime, int trapped, int boundary_dead, int contact_dead)
{
    fprintf(fp, "%d,%d,%.10f,%d,%d,%d,%d,%d\n", trial, step, r2, lifetime, 1, trapped, boundary_dead, contact_dead);
}

int run_random_walk_simulation(const Config *cfg)
{
    WalkTiming total_timing = {0.0, 0.0, 0.0, 0.0};
    int use_visited = (strcmp(cfg->walk_type, "saw") == 0) || (strcmp(cfg->walk_type, "death_on_contact") == 0);
    int use_summary = cfg->save_msd_distribution;
    int use_exact_samples = strcmp(cfg->msd_sample_mode, "exact") == 0;
    int use_reservoir_samples = strcmp(cfg->msd_sample_mode, "reservoir") == 0;
    int step_limit = cfg->msd_distribution_step_count;

    unsigned long long resolved_sampling_seed = 0ULL;
    SamplingRng sampling_rng = {0ULL};
    if (use_summary && !parse_sampling_seed(cfg, &resolved_sampling_seed)) {
        fprintf(stderr, "Failed to resolve sampling_seed\n");
        return 0;
    }
    sampling_rng.state = resolved_sampling_seed;

    unsigned char *visited = NULL;
    int *touched = NULL;
    size_t touched_count = 0;
    size_t touched_cap = 0;
    CoordinateHashSet hash_visited = {0};
    VisitedState visited_state = {0};

    int step_count = cfg->msd_distribution_step_count;
    double *msd_r2_values = NULL;
    RunningStats *streaming_stats = NULL;
    ReservoirStep *reservoir_steps = NULL;

    double *sum_r2_legacy = NULL;
    double *sum_r_legacy = NULL;
    double *sum_r2_sq_legacy = NULL;
    double *sum_r_sq_legacy = NULL;
    double *sum_rg2_legacy = NULL;
    double *sum_rg2_sq_legacy = NULL;
    double *sum_r2_all_legacy = NULL;
    double *sum_rg2_all_legacy = NULL;
    int *n_alive_legacy = NULL;
    double *min_r2 = NULL;
    double *max_r2 = NULL;

    FILE *out = NULL;
    FILE *traj = NULL;
    FILE *final_fp = NULL;
    FILE *timing_fp = NULL;
    FILE *sample_fp = NULL;
    FILE *summary_fp = NULL;

    char sample_path[512] = "";
    char sample_legacy_path[512] = "";
    char summary_path[512];
    char metadata_path[512];
    char final_path[512];
    char timing_path[512];
    char quantile_source[32];

    if (step_count <= 0 && use_summary) {
        fprintf(stderr, "save_msd_distribution=1 requires at least one step\n");
        return 0;
    }

    if (!ensure_parent_dir(cfg->output)) {
        fprintf(stderr, "Failed to create output directory for: %s\n", cfg->output);
        return 0;
    }

    out = fopen(cfg->output, "w");
    if (!out) {
        fprintf(stderr, "Failed to open output file: %s\n", cfg->output);
        return 0;
    }

    if (cfg->save_trajectory) {
        double traj_start = now_seconds();
        traj = fopen(cfg->trajectory_output, "w");
        if (!traj) {
            fprintf(stderr, "Failed to open trajectory file: %s\n", cfg->trajectory_output);
            fclose(out);
            return 0;
        }
        fprintf(traj, "trial,step,x,y,z\n");
        total_timing.time_initialize += now_seconds() - traj_start;
    }

    build_sibling_path(final_path, sizeof(final_path), cfg->output, "final_steps.csv");
    build_sibling_path(timing_path, sizeof(timing_path), cfg->output, "timing_breakdown.csv");
    build_sibling_path(summary_path, sizeof(summary_path), cfg->output, "msd_streaming_summary.csv");
    build_sibling_path(metadata_path, sizeof(metadata_path), cfg->output, "simulation_metadata.json");

    final_fp = fopen(final_path, "w");
    if (!final_fp) {
        fprintf(stderr, "Failed to open final step file: %s\n", final_path);
        goto cleanup_fail;
    }
    fprintf(final_fp, "trial,final_step,trapped,contact_dead,boundary_dead\n");

    timing_fp = fopen(timing_path, "w");
    if (!timing_fp) {
        fprintf(stderr, "Failed to open timing file: %s\n", timing_path);
        goto cleanup_fail;
    }
    fprintf(timing_fp, "spatial_backend,hash_capacity,hash_load_factor_limit,msd_sample_mode,reservoir_size,L,n_trials,time_initialize,time_walk,time_statistics,time_reset,total_time\n");

    if (use_summary) {
        msd_r2_values = calloc((size_t)step_limit, sizeof(double));
        streaming_stats = calloc((size_t)step_limit, sizeof(RunningStats));
        if (!msd_r2_values || !streaming_stats) {
            fprintf(stderr, "Failed to allocate MSD streaming state\n");
            goto cleanup_fail;
        }
        for (int i = 0; i < step_limit; i++) {
            running_stats_init(&streaming_stats[i]);
        }

        if (use_reservoir_samples) {
            reservoir_steps = calloc((size_t)step_limit, sizeof(ReservoirStep));
            if (!reservoir_steps) {
                fprintf(stderr, "Failed to allocate reservoir state\n");
                goto cleanup_fail;
            }
            for (int i = 0; i < step_limit; i++) {
                reservoir_step_init(&reservoir_steps[i], (size_t)cfg->msd_reservoir_size);
                if (cfg->msd_reservoir_size > 0 && !reservoir_steps[i].samples) {
                    fprintf(stderr, "Failed to allocate reservoir samples\n");
                    goto cleanup_fail;
                }
            }
        }
    }

    if (use_exact_samples || use_reservoir_samples) {
        build_sibling_path(sample_path, sizeof(sample_path), cfg->output, use_exact_samples ? "msd_samples.csv" : "msd_reservoir_samples.csv");
        sample_fp = fopen(sample_path, "w");
        if (!sample_fp) {
            fprintf(stderr, "Failed to open MSD sample file: %s\n", sample_path);
            goto cleanup_fail;
        }
        if (use_exact_samples) {
            fprintf(sample_fp, "trial,step,r2,lifetime,alive,trapped,boundary_dead,contact_dead\n");
        } else {
            fprintf(sample_fp, "step,sample_index,r2,source_trial,lifetime\n");
        }
    }

    if (use_visited) {
        double init_start = now_seconds();
        if (strcmp(cfg->spatial_backend, "hash") == 0) {
            size_t max_items = (size_t)cfg->n_steps + 1;
            if (!coordinate_hash_set_init(&hash_visited, cfg->dim, max_items, cfg->hash_max_load_factor) ||
                !visited_state_init_hash(&visited_state, cfg->dim, &hash_visited)) {
                fprintf(stderr, "Failed to initialize hash visited state\n");
                goto cleanup_fail;
            }
        } else {
            int n_sites = (cfg->dim == 3) ? cfg->L * cfg->L * cfg->L : cfg->L * cfg->L;
            visited = calloc((size_t)n_sites, sizeof(unsigned char));
            touched = malloc((size_t)n_sites * sizeof(int));
            touched_cap = (size_t)n_sites;
            if (!visited || !touched || !visited_state_init_dense(&visited_state, cfg->dim, cfg->L, visited, touched, touched_cap, &touched_count)) {
                fprintf(stderr, "Failed to initialize dense visited state\n");
                goto cleanup_fail;
            }
        }
        total_timing.time_initialize += now_seconds() - init_start;
    }

    sum_r2_legacy = calloc((size_t)(cfg->n_steps + 1), sizeof(double));
    sum_r_legacy = calloc((size_t)(cfg->n_steps + 1), sizeof(double));
    sum_r2_sq_legacy = calloc((size_t)(cfg->n_steps + 1), sizeof(double));
    sum_r_sq_legacy = calloc((size_t)(cfg->n_steps + 1), sizeof(double));
    sum_rg2_legacy = calloc((size_t)(cfg->n_steps + 1), sizeof(double));
    sum_rg2_sq_legacy = calloc((size_t)(cfg->n_steps + 1), sizeof(double));
    sum_r2_all_legacy = calloc((size_t)(cfg->n_steps + 1), sizeof(double));
    sum_rg2_all_legacy = calloc((size_t)(cfg->n_steps + 1), sizeof(double));
    n_alive_legacy = calloc((size_t)(cfg->n_steps + 1), sizeof(int));
    min_r2 = malloc((size_t)(cfg->n_steps + 1) * sizeof(double));
    max_r2 = malloc((size_t)(cfg->n_steps + 1) * sizeof(double));
    if (!sum_r2_legacy || !sum_r_legacy || !sum_r2_sq_legacy || !sum_r_sq_legacy || !sum_rg2_legacy || !sum_rg2_sq_legacy || !sum_r2_all_legacy || !sum_rg2_all_legacy || !n_alive_legacy || !min_r2 || !max_r2) {
        fprintf(stderr, "Failed to allocate legacy accumulators\n");
        goto cleanup_fail;
    }
    for (int i = 0; i <= cfg->n_steps; i++) {
        min_r2[i] = INFINITY;
        max_r2[i] = 0.0;
    }

    int trapped_count = 0;
    int checkpoint_index = 0;

    for (int trial = 0; trial < cfg->n_trials; trial++) {
        int save_traj = cfg->save_trajectory && trial < cfg->save_trajectory_trials;

        WalkResult res = run_one_walk(
            cfg->dim,
            cfg->L,
            cfg->n_steps,
            cfg->walk_type,
            cfg->boundary,
            trial,
            sum_r2_legacy,
            sum_r_legacy,
            sum_r2_sq_legacy,
            sum_r_sq_legacy,
            sum_rg2_legacy,
            sum_rg2_sq_legacy,
            min_r2,
            max_r2,
            sum_r2_all_legacy,
            sum_rg2_all_legacy,
            n_alive_legacy,
            traj,
            save_traj,
            visited,
            touched,
            touched_cap,
            &touched_count,
            NULL,
            cfg->msd_distribution_step_values,
            cfg->msd_distribution_step_count,
            msd_r2_values,
            &total_timing,
            use_visited ? &visited_state : NULL
        );

        fprintf(final_fp, "%d,%d,%d,%d,%d\n", trial, res.final_step, res.trapped, res.contact_dead, res.boundary_dead);
        if (res.trapped) {
            trapped_count++;
        }

        if (use_summary) {
            for (int step_index = 0; step_index < step_limit; step_index++) {
                int step_value = cfg->msd_distribution_step_values[step_index];
                if (step_value > res.final_step) {
                    break;
                }

                double r2 = msd_r2_values[step_index];
                running_stats_update(&streaming_stats[step_index], r2);

                if (use_exact_samples && sample_fp) {
                    write_exact_sample_row(sample_fp, trial, step_value, r2, res.final_step, res.trapped, res.boundary_dead, res.contact_dead);
                }

                if (use_reservoir_samples) {
                    reservoir_step_update(&reservoir_steps[step_index], &sampling_rng, r2, trial, res.final_step);
                }
            }
        }

        if (cfg->save_lifetime_checkpoints) {
            while (checkpoint_index < cfg->lifetime_checkpoint_trial_count) {
                int checkpoint_trial = cfg->lifetime_checkpoint_trial_values[checkpoint_index];
                if (checkpoint_trial > cfg->n_trials) {
                    checkpoint_index++;
                    continue;
                }
                if (trial + 1 != checkpoint_trial) {
                    break;
                }

                if (fflush(final_fp) != 0 || !save_lifetime_checkpoint(final_path, checkpoint_trial)) {
                    fprintf(stderr, "Failed to save lifetime checkpoint for T%d\n", checkpoint_trial);
                    goto cleanup_fail;
                }
                checkpoint_index++;
            }
        }
    }

    if (use_reservoir_samples && sample_fp) {
        for (int step_index = 0; step_index < step_limit; step_index++) {
            ReservoirStep *step = &reservoir_steps[step_index];
            int step_value = cfg->msd_distribution_step_values[step_index];
            for (size_t sample_index = 0; sample_index < step->stored_count; sample_index++) {
                fprintf(sample_fp, "%d,%zu,%.10f,%d,%d\n", step_value, sample_index, step->samples[sample_index].r2, step->samples[sample_index].source_trial, step->samples[sample_index].lifetime);
            }
        }
    }

    fprintf(out, "step,mean_r2,mean_r,std_r2,std_r,n_alive,trapped_rate,mean_rg2,std_rg2,mean_r2_all,mean_rg2_all,min_r2,max_r2,se_r2,cv_r2\n");
    for (int step = 0; step <= cfg->n_steps; step++) {
        if (n_alive_legacy[step] == 0) {
            fprintf(out, "%d,0,0,0,0,0,1,0,0\n", step);
            continue;
        }

        double mean_r2 = sum_r2_legacy[step] / n_alive_legacy[step];
        double mean_r = sum_r_legacy[step] / n_alive_legacy[step];
        double var_r2 = sum_r2_sq_legacy[step] / n_alive_legacy[step] - mean_r2 * mean_r2;
        double var_r = sum_r_sq_legacy[step] / n_alive_legacy[step] - mean_r * mean_r;
        if (var_r2 < 0) var_r2 = 0;
        if (var_r < 0) var_r = 0;
        double std_r2 = sqrt(var_r2);
        double std_r = sqrt(var_r);
        double se_r2 = std_r2 / sqrt((double)n_alive_legacy[step]);
        double cv_r2 = (mean_r2 > 0.0) ? std_r2 / mean_r2 : 0.0;
        double trapped_rate = (strcmp(cfg->walk_type, "saw") == 0) ? 1.0 - ((double)n_alive_legacy[step] / cfg->n_trials) : 0.0;
        double mean_rg2 = sum_rg2_legacy[step] / n_alive_legacy[step];
        double var_rg2 = sum_rg2_sq_legacy[step] / n_alive_legacy[step] - mean_rg2 * mean_rg2;
        if (var_rg2 < 0) var_rg2 = 0;
        double std_rg2 = sqrt(var_rg2);
        double mean_r2_all = sum_r2_all_legacy[step] / cfg->n_trials;
        double mean_rg2_all = sum_rg2_all_legacy[step] / cfg->n_trials;

        fprintf(out, "%d,%.10f,%.10f,%.10f,%.10f,%d,%.10f,%.10f,%.10f,%.10f,%.10f,%.10f,%.10f,%.10f,%.10f\n",
            step, mean_r2, mean_r, std_r2, std_r, n_alive_legacy[step], trapped_rate, mean_rg2, std_rg2, mean_r2_all, mean_rg2_all, min_r2[step], max_r2[step], se_r2, cv_r2);
    }

    summary_fp = fopen(summary_path, "w");
    if (!summary_fp) {
        fprintf(stderr, "Failed to open streaming summary file: %s\n", summary_path);
        goto cleanup_fail;
    }
    fprintf(summary_fp, "step,n_alive,survival_probability,mean_r2,std_r2,variance_r2,standard_error_r2,relative_standard_error_r2,min_r2,max_r2,coefficient_of_variation,sample_mode,reservoir_size,reservoir_stored_count\n");
    for (int step_index = 0; step_index < step_limit; step_index++) {
        RunningStats *stats = &streaming_stats[step_index];
        double variance_r2 = running_stats_variance(stats);
        double std_r2 = running_stats_stddev(stats);
        double se_r2 = (stats->count > 0ULL && isfinite(std_r2)) ? std_r2 / sqrt((double)stats->count) : NAN;
        double rse_r2 = (isfinite(se_r2) && stats->mean > 0.0) ? se_r2 / stats->mean : NAN;
        double cv_r2 = (isfinite(std_r2) && stats->mean > 0.0) ? std_r2 / stats->mean : NAN;
        size_t stored_count = use_reservoir_samples ? reservoir_steps[step_index].stored_count : 0;
        fprintf(summary_fp, "%d,%llu,%.10f,%.10f,%.10f,%.10f,%.10f,%.10f,%.10f,%.10f,%.10f,%s,%d,%zu\n",
            cfg->msd_distribution_step_values[step_index],
            stats->count,
            (double)stats->count / (double)cfg->n_trials,
            stats->mean,
            std_r2,
            variance_r2,
            se_r2,
            rse_r2,
            stats->min,
            stats->max,
            cv_r2,
            cfg->msd_sample_mode,
            cfg->msd_reservoir_size,
            stored_count);
    }

    fprintf(timing_fp, "%s,%zu,%.6f,%s,%d,%d,%d,%.10f,%.10f,%.10f,%.10f,%.10f\n",
        cfg->spatial_backend,
        hash_visited.capacity,
        cfg->hash_max_load_factor,
        cfg->msd_sample_mode,
        cfg->msd_reservoir_size,
        cfg->L,
        cfg->n_trials,
        total_timing.time_initialize,
        total_timing.time_walk,
        total_timing.time_statistics,
        total_timing.time_reset,
        total_timing.time_initialize + total_timing.time_walk + total_timing.time_statistics + total_timing.time_reset);

    if (sample_fp) {
        fclose(sample_fp);
        sample_fp = NULL;
    }
    if (summary_fp) {
        fclose(summary_fp);
        summary_fp = NULL;
    }

    if (use_exact_samples || use_reservoir_samples) {
        build_sibling_path(sample_legacy_path, sizeof(sample_legacy_path), cfg->output, "msd_distribution.csv");
        create_legacy_msd_alias(sample_path, sample_legacy_path);
    }

    strncpy(quantile_source, use_exact_samples ? "exact" : (use_reservoir_samples ? "reservoir" : "none"), sizeof(quantile_source) - 1);
    quantile_source[sizeof(quantile_source) - 1] = '\0';
    if (!write_simulation_metadata(cfg, resolved_sampling_seed, (use_exact_samples || use_reservoir_samples) ? sample_path : NULL, summary_path, metadata_path, quantile_source, hash_visited.capacity)) {
        fprintf(stderr, "Warning: failed to write simulation metadata: %s\n", metadata_path);
    }

    fclose(timing_fp);
    fclose(final_fp);
    fclose(out);
    if (traj) fclose(traj);

    if (reservoir_steps) {
        for (int i = 0; i < step_limit; i++) {
            reservoir_step_destroy(&reservoir_steps[i]);
        }
    }
    free(reservoir_steps);
    free(streaming_stats);
    free(msd_r2_values);
    free(sum_r2_legacy);
    free(sum_r_legacy);
    free(sum_r2_sq_legacy);
    free(sum_r_sq_legacy);
    free(sum_rg2_legacy);
    free(sum_rg2_sq_legacy);
    free(sum_r2_all_legacy);
    free(sum_rg2_all_legacy);
    free(n_alive_legacy);
    free(min_r2);
    free(max_r2);
    free(visited);
    free(touched);
    coordinate_hash_set_destroy(&hash_visited);

    printf("Random walk simulation completed.\n");
    printf("walk_type=%s dim=%d L=%d n_steps=%d n_trials=%d\n", cfg->walk_type, cfg->dim, cfg->L, cfg->n_steps, cfg->n_trials);
    printf("Spatial backend: %s boundary=%s sample_mode=%s\n", cfg->spatial_backend, cfg->boundary, cfg->msd_sample_mode);
    printf("Visited initialization: %.6f s\n", total_timing.time_initialize);
    printf("Walk: %.6f s\n", total_timing.time_walk);
    printf("Statistics: %.6f s\n", total_timing.time_statistics);
    printf("Visited reset: %.6f s\n", total_timing.time_reset);
    printf("Total: %.6f s\n", total_timing.time_initialize + total_timing.time_walk + total_timing.time_statistics + total_timing.time_reset);
    if (strcmp(cfg->walk_type, "saw") == 0) {
        printf("trapped_count=%d trapped_rate=%.4f\n", trapped_count, (double)trapped_count / cfg->n_trials);
    }

    return 1;

cleanup_fail:
    if (sample_fp) fclose(sample_fp);
    if (summary_fp) fclose(summary_fp);
    if (timing_fp) fclose(timing_fp);
    if (final_fp) fclose(final_fp);
    if (out) fclose(out);
    if (traj) fclose(traj);
    if (reservoir_steps) {
        for (int i = 0; i < step_limit; i++) {
            reservoir_step_destroy(&reservoir_steps[i]);
        }
    }
    free(reservoir_steps);
    free(streaming_stats);
    free(msd_r2_values);
    free(sum_r2_legacy);
    free(sum_r_legacy);
    free(sum_r2_sq_legacy);
    free(sum_r_sq_legacy);
    free(sum_rg2_legacy);
    free(sum_rg2_sq_legacy);
    free(sum_r2_all_legacy);
    free(sum_rg2_all_legacy);
    free(n_alive_legacy);
    free(min_r2);
    free(max_r2);
    free(visited);
    free(touched);
    coordinate_hash_set_destroy(&hash_visited);
    return 0;
}