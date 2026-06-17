#ifndef RANDOM_WALK_H
#define RANDOM_WALK_H

#include <stdio.h>

typedef struct {
    int x, y, z;
} WalkPos;

typedef struct {
    int final_step;
    int trapped;
    int contact_dead;
    int boundary_dead;
} WalkResult;

WalkResult run_one_walk(
    int dim,
    int L,
    int n_steps,
    const char *walk_type,
    const char *boundary,
    int trial,
    double *sum_r2,
    double *sum_r,
    double *sum_r2_sq,
    double *sum_r_sq,
    double *sum_rg2,
    double *sum_rg2_sq,
    double *min_r2,
    double *max_r2,
    double *sum_r2_all,
    double *sum_rg2_all,
    int *n_alive,
    FILE *traj_fp,
    int save_traj
);

#endif