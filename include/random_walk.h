#ifndef RANDOM_WALK_H
#define RANDOM_WALK_H

#include <stdio.h>
#include <stddef.h>

#include "coordinate_hash_set.h"

typedef struct {
    int x, y, z;
} WalkPos;

typedef enum {
    SPATIAL_BACKEND_DENSE = 0,
    SPATIAL_BACKEND_HASH = 1
} SpatialBackend;

typedef struct {
    SpatialBackend backend;
    int dim;
    int L;
    unsigned char *dense_visited;
    int *dense_touched;
    size_t dense_touched_cap;
    size_t *dense_touched_count;
    CoordinateHashSet *hash_visited;
} VisitedState;

typedef struct {
    int final_step;
    int trapped;
    int contact_dead;
    int boundary_dead;
} WalkResult;

typedef struct {
    double time_initialize;
    double time_walk;
    double time_statistics;
    double time_reset;
} WalkTiming;

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
    int save_traj,
    unsigned char *visited,
    int *touched,
    size_t touched_cap,
    size_t *touched_count,
    FILE *msd_fp,
    const int *msd_steps,
    int msd_step_count,
    double *msd_r2_values,
    WalkTiming *timing,
    VisitedState *visited_state
);

int visited_state_init_dense(
    VisitedState *state,
    int dim,
    int L,
    unsigned char *dense_visited,
    int *dense_touched,
    size_t dense_touched_cap,
    size_t *dense_touched_count
);

int visited_state_init_hash(
    VisitedState *state,
    int dim,
    CoordinateHashSet *hash_visited
);

void visited_state_reset(VisitedState *state);

#endif