#ifndef RANDOM_WALK_H
#define RANDOM_WALK_H

#include <stdio.h>

typedef struct {
    int x, y, z;
} WalkPos;

typedef struct {
    int final_step;
    int trapped;
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
    int *n_alive,
    FILE *traj_fp,
    int save_traj
);

#endif