#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <errno.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>

#include "config.h"
#include "random_walk.h"

static double now_seconds(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
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

int run_random_walk_simulation(const Config *cfg)
{
    WalkTiming total_timing = {0.0, 0.0, 0.0, 0.0};
    int use_visited =
        (strcmp(cfg->walk_type, "saw") == 0) ||
        (strcmp(cfg->walk_type, "death_on_contact") == 0);
    int n_sites = (cfg->dim == 3) ? cfg->L * cfg->L * cfg->L : cfg->L * cfg->L;
    unsigned char *visited = NULL;
    int *touched = NULL;
    size_t touched_count = 0;
    size_t touched_cap = 0;

    FILE *out = fopen(cfg->output, "w");
    if (!out) {
        fprintf(stderr, "Failed to open output file: %s\n", cfg->output);
        return 0;
    }

    FILE *traj = NULL;
    if (cfg->save_trajectory) {
        double traj_init_start = now_seconds();
        traj = fopen(cfg->trajectory_output, "w");
        if (!traj) {
            fprintf(stderr, "Failed to open trajectory file: %s\n", cfg->trajectory_output);
            fclose(out);
            return 0;
        }
        fprintf(traj, "trial,step,x,y,z\n");
        total_timing.time_initialize += now_seconds() - traj_init_start;
    }

    FILE *msd_fp = NULL;
    double *msd_r2_values = NULL;

    if (cfg->save_msd_distribution) {
        char msd_path[512];
        build_sibling_path(msd_path, sizeof(msd_path), cfg->output, "msd_distribution.csv");
        msd_fp = fopen(msd_path, "w");
        if (!msd_fp) {
            fprintf(stderr, "Failed to open MSD distribution file: %s\n", msd_path);
            fclose(out);
            if (traj) fclose(traj);
            return 0;
        }
        fprintf(msd_fp, "trial,step,r2,alive,trapped,boundary_dead,contact_dead\n");
        msd_r2_values = calloc((size_t)cfg->msd_distribution_step_count, sizeof(double));
        if (!msd_r2_values) {
            fprintf(stderr, "Failed to allocate MSD distribution buffer\n");
            fclose(out);
            if (traj) fclose(traj);
            fclose(msd_fp);
            return 0;
        }
    }

    char final_path[512];
    char timing_path[512];

    build_sibling_path(final_path, sizeof(final_path), cfg->output, "final_steps.csv");
    build_sibling_path(timing_path, sizeof(timing_path), cfg->output, "timing_breakdown.csv");

    FILE *final_fp = fopen(final_path, "w");
    if (!final_fp) {
        fprintf(stderr, "Failed to open final step file: %s\n", final_path);
        fclose(out);
        if (traj) fclose(traj);
        return 0;
    }

    fprintf(final_fp, "trial,final_step,trapped,contact_dead,boundary_dead\n");

    int checkpoint_index = 0;

    FILE *timing_fp = fopen(timing_path, "w");
    if (!timing_fp) {
        fprintf(stderr, "Failed to open timing file: %s\n", timing_path);
        fclose(out);
        if (traj) fclose(traj);
        fclose(final_fp);
        return 0;
    }

    fprintf(timing_fp, "L,n_trials,time_initialize,time_walk,time_statistics,time_reset,total_time\n");

    int n = cfg->n_steps + 1;

    double *sum_r2 = calloc(n, sizeof(double));
    double *sum_r = calloc(n, sizeof(double));
    double *sum_r2_sq = calloc(n, sizeof(double));
    double *sum_r_sq = calloc(n, sizeof(double));
    int *n_alive = calloc(n, sizeof(int));

    double *sum_rg2 = calloc(n, sizeof(double));
    double *sum_rg2_sq = calloc(n, sizeof(double));

    double *min_r2 = malloc(n * sizeof(double));
    double *max_r2 = malloc(n * sizeof(double));

    double *sum_r2_all = calloc(n, sizeof(double));
    double *sum_rg2_all = calloc(n, sizeof(double));

    for (int i = 0; i < n; i++) {
        min_r2[i] = INFINITY;
        max_r2[i] = 0.0;
    }

    if (!sum_r2 || !sum_r || !sum_r2_sq || !sum_r_sq || !n_alive ||
        !sum_rg2 || !sum_rg2_sq ) {
        fprintf(stderr, "Failed to allocate random walk arrays\n");
        fclose(out);
        if (traj) fclose(traj);
        fclose(final_fp);
        fclose(timing_fp);

        free(sum_r2);
        free(sum_r);
        free(sum_r2_sq);
        free(sum_r_sq);
        free(sum_rg2);
        free(sum_rg2_sq);
        free(min_r2);
        free(max_r2);
        free(n_alive);


        return 0;
    }

    if (use_visited) {
        double init_start = now_seconds();
        visited = calloc((size_t)n_sites, sizeof(unsigned char));
        touched = malloc((size_t)n_sites * sizeof(int));
        touched_cap = (size_t)n_sites;

        if (!visited || !touched) {
            fprintf(stderr, "Failed to allocate visited/touched arrays\n");
            fclose(out);
            if (traj) fclose(traj);
            fclose(final_fp);
            fclose(timing_fp);
            free(visited);
            free(touched);
            free(sum_r2);
            free(sum_r);
            free(sum_r2_sq);
            free(sum_r_sq);
            free(sum_rg2);
            free(sum_rg2_sq);
            free(min_r2);
            free(max_r2);
            free(n_alive);
            free(sum_r2_all);
            free(sum_rg2_all);
            return 0;
        }
        total_timing.time_initialize += now_seconds() - init_start;
    }

    int trapped_count = 0;

    for (int trial = 0; trial < cfg->n_trials; trial++) {
        int save_traj = 0;
        if (cfg->save_trajectory && trial < cfg->save_trajectory_trials) {
            save_traj = 1;
        }

        WalkResult res = run_one_walk(
            cfg->dim,
            cfg->L,
            cfg->n_steps,
            cfg->walk_type,
            cfg->boundary,
            trial,
            sum_r2,
            sum_r,
            sum_r2_sq,
            sum_r_sq,
            sum_rg2,
            sum_rg2_sq,
            min_r2,
            max_r2,
            sum_r2_all,
            sum_rg2_all,
            n_alive,
            traj,
            save_traj,
            visited,
            touched,
            touched_cap,
            &touched_count,
            msd_fp,
            cfg->msd_distribution_step_values,
            cfg->msd_distribution_step_count,
            msd_r2_values,
            &total_timing
        );

        fprintf(
            final_fp,
            "%d,%d,%d,%d,%d\n",
            trial,
            res.final_step,
            res.trapped,
            res.contact_dead,
            res.boundary_dead
        );

        if (res.trapped) {
            trapped_count++;
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
                    fclose(out);
                    if (traj) fclose(traj);
                    fclose(final_fp);
                    fclose(timing_fp);
                    if (msd_fp) fclose(msd_fp);
                    free(sum_r2);
                    free(sum_r);
                    free(sum_r2_sq);
                    free(sum_r_sq);
                    free(sum_rg2);
                    free(sum_rg2_sq);
                    free(min_r2);
                    free(max_r2);
                    free(n_alive);
                    free(visited);
                    free(touched);
                    free(msd_r2_values);
                    return 0;
                }

                checkpoint_index++;
            }
        }

    }

    fprintf(out, "step,mean_r2,mean_r,std_r2,std_r,n_alive,trapped_rate,mean_rg2,std_rg2,mean_r2_all,mean_rg2_all,min_r2,max_r2,se_r2,cv_r2\n");

    for (int step = 0; step <= cfg->n_steps; step++) {
        if (n_alive[step] == 0) {
            fprintf(out, "%d,0,0,0,0,0,1,0,0\n", step);
            continue;
        }

        double mean_r2 = sum_r2[step] / n_alive[step];
        double mean_r = sum_r[step] / n_alive[step];

        double var_r2 = sum_r2_sq[step] / n_alive[step] - mean_r2 * mean_r2;
        double var_r = sum_r_sq[step] / n_alive[step] - mean_r * mean_r;

        if (var_r2 < 0) var_r2 = 0;
        if (var_r < 0) var_r = 0;

        double std_r2 = sqrt(var_r2);
        double std_r = sqrt(var_r);

        double se_r2 = std_r2 / sqrt((double)n_alive[step]);

        double cv_r2 = 0.0;
        if (mean_r2 > 0.0) {
            cv_r2 = std_r2 / mean_r2;
        }

        double trapped_rate = 0.0;
        if (strcmp(cfg->walk_type, "saw") == 0) {
            trapped_rate = 1.0 - ((double)n_alive[step] / cfg->n_trials);
        }

        double mean_rg2 = sum_rg2[step] / n_alive[step];
        double var_rg2 = sum_rg2_sq[step] / n_alive[step] - mean_rg2 * mean_rg2;
        if (var_rg2 < 0) var_rg2 = 0;
        double std_rg2 = sqrt(var_rg2);
        double mean_r2_all = sum_r2_all[step] / cfg->n_trials;
        double mean_rg2_all = sum_rg2_all[step] / cfg->n_trials;

        fprintf(
            out,
            "%d,%.10f,%.10f,%.10f,%.10f,%d,%.10f,%.10f,%.10f,%.10f,%.10f,%.10f,%.10f,%.10f,%.10f\n",
            step,
            mean_r2,
            mean_r,
            std_r2,
            std_r,
            n_alive[step],
            trapped_rate,
            mean_rg2,
            std_rg2,
            mean_r2_all,
            mean_rg2_all,
            min_r2[step],
            max_r2[step],
            se_r2,
            cv_r2
        );
        
    }

    fclose(out);

    if (traj)
        fclose(traj);

    fclose(final_fp);
    if (msd_fp) {
        fclose(msd_fp);
    }

    fprintf(
        timing_fp,
        "%d,%d,%.10f,%.10f,%.10f,%.10f,%.10f\n",
        cfg->L,
        cfg->n_trials,
        total_timing.time_initialize,
        total_timing.time_walk,
        total_timing.time_statistics,
        total_timing.time_reset,
        total_timing.time_initialize + total_timing.time_walk + total_timing.time_statistics + total_timing.time_reset
    );
    fclose(timing_fp);

    free(sum_r2);
    free(sum_r);
    free(sum_r2_sq);
    free(sum_r_sq);
    free(sum_rg2);
    free(sum_rg2_sq);
    free(min_r2);
    free(max_r2);
    free(n_alive);
    free(visited);
    free(touched);
    free(msd_r2_values);
 
    printf("Random walk simulation completed.\n");
    printf("walk_type=%s dim=%d L=%d n_steps=%d n_trials=%d\n",
           cfg->walk_type, cfg->dim, cfg->L, cfg->n_steps, cfg->n_trials);

    printf("Visited initialization: %.6f s\n", total_timing.time_initialize);
    printf("Walk: %.6f s\n", total_timing.time_walk);
    printf("Statistics: %.6f s\n", total_timing.time_statistics);
    printf("Visited reset: %.6f s\n", total_timing.time_reset);
    printf("Total: %.6f s\n",
           total_timing.time_initialize + total_timing.time_walk + total_timing.time_statistics + total_timing.time_reset);

    if (strcmp(cfg->walk_type, "saw") == 0) {
        printf("trapped_count=%d trapped_rate=%.4f\n",
               trapped_count, (double)trapped_count / cfg->n_trials);
    }

    return 1;
}