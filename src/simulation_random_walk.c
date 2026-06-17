#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "config.h"
#include "random_walk.h"

int run_random_walk_simulation(const Config *cfg)
{
    FILE *out = fopen(cfg->output, "w");
    if (!out) {
        fprintf(stderr, "Failed to open output file: %s\n", cfg->output);
        return 0;
    }

    FILE *traj = NULL;
    if (cfg->save_trajectory) {
        traj = fopen(cfg->trajectory_output, "w");
        if (!traj) {
            fprintf(stderr, "Failed to open trajectory file: %s\n", cfg->trajectory_output);
            fclose(out);
            return 0;
        }
        fprintf(traj, "trial,step,x,y,z\n");
    }

    char final_path[512];

    strncpy(final_path, cfg->output, sizeof(final_path) - 1);
    final_path[sizeof(final_path) - 1] = '\0';

    char *slash = strrchr(final_path, '/');

    if (slash) {
        strcpy(slash + 1, "final_steps.csv");
    } else {
        strcpy(final_path, "final_steps.csv");
    }

    FILE *final_fp = fopen(final_path, "w");
    if (!final_fp) {
        fprintf(stderr, "Failed to open final step file: %s\n", final_path);
        fclose(out);
        if (traj) fclose(traj);
        return 0;
    }

    fprintf(final_fp, "trial,final_step,trapped,contact_dead,boundary_dead\n");

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
            save_traj
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

    free(sum_r2);
    free(sum_r);
    free(sum_r2_sq);
    free(sum_r_sq);
    free(sum_rg2);
    free(sum_rg2_sq);
    free(min_r2);
    free(max_r2);
    free(n_alive);
 
    printf("Random walk simulation completed.\n");
    printf("walk_type=%s dim=%d L=%d n_steps=%d n_trials=%d\n",
           cfg->walk_type, cfg->dim, cfg->L, cfg->n_steps, cfg->n_trials);

    if (strcmp(cfg->walk_type, "saw") == 0) {
        printf("trapped_count=%d trapped_rate=%.4f\n",
               trapped_count, (double)trapped_count / cfg->n_trials);
    }

    return 1;
}