#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "random_walk.h"

static int index_3d(int x, int y, int z, int L)
{
    return x + L * (y + L * z);
}

static int inside(int x, int y, int z, int dim, int L)
{
    if (x < 0 || x >= L) return 0;
    if (y < 0 || y >= L) return 0;
    if (dim == 3 && (z < 0 || z >= L)) return 0;
    return 1;
}

static void apply_periodic(int *x, int *y, int *z, int dim, int L)
{
    if (*x < 0) *x = L - 1;
    if (*x >= L) *x = 0;

    if (*y < 0) *y = L - 1;
    if (*y >= L) *y = 0;

    if (dim == 3) {
        if (*z < 0) *z = L - 1;
        if (*z >= L) *z = 0;
    }
}

static double now_seconds(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

int visited_state_init_dense(
    VisitedState *state,
    int dim,
    int L,
    unsigned char *dense_visited,
    int *dense_touched,
    size_t dense_touched_cap,
    size_t *dense_touched_count
)
{
    if (!state) {
        return 0;
    }

    state->backend = SPATIAL_BACKEND_DENSE;
    state->dim = dim;
    state->L = L;
    state->dense_visited = dense_visited;
    state->dense_touched = dense_touched;
    state->dense_touched_cap = dense_touched_cap;
    state->dense_touched_count = dense_touched_count;
    state->hash_visited = NULL;
    return 1;
}

int visited_state_init_hash(
    VisitedState *state,
    int dim,
    CoordinateHashSet *hash_visited
)
{
    if (!state || !hash_visited) {
        return 0;
    }

    state->backend = SPATIAL_BACKEND_HASH;
    state->dim = dim;
    state->L = 0;
    state->dense_visited = NULL;
    state->dense_touched = NULL;
    state->dense_touched_cap = 0;
    state->dense_touched_count = NULL;
    state->hash_visited = hash_visited;
    return 1;
}

static int visited_state_contains(const VisitedState *state, int x, int y, int z)
{
    if (!state) {
        return 0;
    }

    if (state->backend == SPATIAL_BACKEND_HASH) {
        return coordinate_hash_set_contains(state->hash_visited, x, y, z);
    }

    if (!state->dense_visited) {
        return 0;
    }

    return state->dense_visited[index_3d(x, y, z, state->L)] != 0;
}

static int visited_state_insert(VisitedState *state, int x, int y, int z)
{
    if (!state) {
        return 0;
    }

    if (state->backend == SPATIAL_BACKEND_HASH) {
        return coordinate_hash_set_insert(state->hash_visited, x, y, z) >= 0;
    }

    if (!state->dense_visited || !state->dense_touched || !state->dense_touched_count) {
        return 0;
    }

    int idx = index_3d(x, y, z, state->L);
    if (!state->dense_visited[idx]) {
        state->dense_visited[idx] = 1;
        if (*state->dense_touched_count >= state->dense_touched_cap) {
            fprintf(stderr, "Touched list capacity exceeded\n");
            exit(1);
        }
        state->dense_touched[(*state->dense_touched_count)++] = idx;
    }

    return 1;
}

void visited_state_reset(VisitedState *state)
{
    if (!state) {
        return;
    }

    if (state->backend == SPATIAL_BACKEND_HASH) {
        coordinate_hash_set_clear(state->hash_visited);
        return;
    }

    if (!state->dense_visited || !state->dense_touched || !state->dense_touched_count) {
        return;
    }

    for (size_t i = 0; i < *state->dense_touched_count; i++) {
        state->dense_visited[state->dense_touched[i]] = 0;
    }
    *state->dense_touched_count = 0;
}

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
)
{
    WalkResult result = {0, 0, 0, 0};

    int infinite_boundary = strcmp(boundary, "infinite") == 0;
    int x0 = infinite_boundary ? 0 : (L / 2);
    int y0 = infinite_boundary ? 0 : (L / 2);
    int z0 = (dim == 3) ? (infinite_boundary ? 0 : (L / 2)) : 0;

    int x = x0;
    int y = y0;
    int z = z0;

    int use_visited =
        (strcmp(walk_type, "saw") == 0) ||
        (strcmp(walk_type, "death_on_contact") == 0);

    if (use_visited) {
        *touched_count = 0;
        if (visited_state) {
            if (!visited_state_insert(visited_state, x, y, z)) {
                fprintf(stderr, "Failed to initialize visited state\n");
                exit(1);
            }
        } else if (visited) {
            int start_idx = index_3d(x, y, z, L);
            if (!visited[start_idx]) {
                visited[start_idx] = 1;
                if (*touched_count >= touched_cap) {
                    fprintf(stderr, "Touched list capacity exceeded\n");
                    exit(1);
                }
                touched[(*touched_count)++] = start_idx;
            }
        }
    }

    double sx = 0.0;
    double sy = 0.0;
    double sz = 0.0;
    double sr2 = 0.0;
    int msd_step_index = 0;

    for (int step = 0; step <= n_steps; step++) {
        double stats_start = now_seconds();
        int dx0 = x - x0;
        int dy0 = y - y0;
        int dz0 = z - z0;

        double r2 = (double)(dx0 * dx0 + dy0 * dy0 + dz0 * dz0);
        double r = sqrt(r2);

        sx += dx0;
        sy += dy0;
        sz += dz0;
        sr2 += r2;

        int n_points = step + 1;

        double mx = sx / n_points;
        double my = sy / n_points;
        double mz = sz / n_points;

        double mean_pos2 = sr2 / n_points;

        double rg2 = mean_pos2 - (mx * mx + my * my + mz * mz);
        if (rg2 < 0) rg2 = 0.0;

        sum_r2[step] += r2;
        sum_r[step] += r;
        sum_r2_sq[step] += r2 * r2;
        sum_r_sq[step] += r * r;
        sum_rg2[step] += rg2;
        sum_rg2_sq[step] += rg2 * rg2;
        sum_r2_all[step] += r2;
        sum_rg2_all[step] += rg2;
        n_alive[step] += 1;

        if (r2 < min_r2[step]) {
            min_r2[step] = r2;
        }
        if (r2 > max_r2[step]) {
            max_r2[step] = r2;
        }

        if (save_traj && traj_fp) {
            fprintf(traj_fp, "%d,%d,%d,%d,%d\n", trial, step, x, y, z);
        }

        while (msd_steps && msd_r2_values && msd_step_index < msd_step_count && step == msd_steps[msd_step_index]) {
            msd_r2_values[msd_step_index] = r2;
            msd_step_index++;
        }

        if (timing) {
            timing->time_statistics += now_seconds() - stats_start;
        }

        if (step == n_steps) {
            result.final_step = step;
            break;
        }

        double walk_start = now_seconds();

        int dirs[6][3] = {
            { 1, 0, 0}, {-1, 0, 0},
            { 0, 1, 0}, { 0,-1, 0},
            { 0, 0, 1}, { 0, 0,-1}
        };

        int max_dirs = (dim == 3) ? 6 : 4;
        int candidates[6][3];
        int n_candidates = 0;

        for (int d = 0; d < max_dirs; d++) {
            int nx = x + dirs[d][0];
            int ny = y + dirs[d][1];
            int nz = z + dirs[d][2];

            if (strcmp(walk_type, "death_on_contact") == 0) {
                candidates[n_candidates][0] = nx;
                candidates[n_candidates][1] = ny;
                candidates[n_candidates][2] = nz;
                n_candidates++;
                continue;
            }

            if (!infinite_boundary) {
                if (strcmp(boundary, "periodic") == 0) {
                    apply_periodic(&nx, &ny, &nz, dim, L);
                } else {
                    if (!inside(nx, ny, nz, dim, L)) {
                        continue;
                    }
                }
            }

            if (strcmp(walk_type, "saw") == 0) {
                if (visited_state) {
                    if (visited_state_contains(visited_state, nx, ny, nz)) {
                        continue;
                    }
                } else if (visited) {
                    int idx = index_3d(nx, ny, nz, L);
                    if (visited[idx]) {
                        continue;
                    }
                }
            }

            candidates[n_candidates][0] = nx;
            candidates[n_candidates][1] = ny;
            candidates[n_candidates][2] = nz;
            n_candidates++;
        }

        if (n_candidates == 0) {
            result.trapped = 1;
            result.final_step = step;

            for (int t = step + 1; t <= n_steps; t++) {
                sum_r2_all[t] += r2;
                sum_rg2_all[t] += rg2;
            }

            if (timing) {
                timing->time_walk += now_seconds() - walk_start;
            }

            break;
        }

        int choice = rand() % n_candidates;

        int nx = candidates[choice][0];
        int ny = candidates[choice][1];
        int nz = candidates[choice][2];

        if (strcmp(walk_type, "death_on_contact") == 0) {
            if (!infinite_boundary) {
                if (strcmp(boundary, "periodic") == 0) {
                    apply_periodic(&nx, &ny, &nz, dim, L);
                } else {
                    if (!inside(nx, ny, nz, dim, L)) {
                        result.trapped = 1;
                        result.boundary_dead = 1;
                        result.final_step = step;

                        if (timing) {
                            timing->time_walk += now_seconds() - walk_start;
                        }

                        break;
                    }
                }
            }

            if (visited_state) {
                if (visited_state_contains(visited_state, nx, ny, nz)) {
                    result.trapped = 1;
                    result.contact_dead = 1;
                    result.final_step = step;

                    if (timing) {
                        timing->time_walk += now_seconds() - walk_start;
                    }

                    break;
                }
            } else if (visited) {
                int idx = index_3d(nx, ny, nz, L);
                if (visited[idx]) {
                    result.trapped = 1;
                    result.contact_dead = 1;
                    result.final_step = step;

                    if (timing) {
                        timing->time_walk += now_seconds() - walk_start;
                    }

                    break;
                }
            }
        }

        x = nx;
        y = ny;
        z = nz;

        if (use_visited) {
            if (visited_state) {
                if (!visited_state_insert(visited_state, x, y, z)) {
                    fprintf(stderr, "Failed to insert visited state\n");
                    exit(1);
                }
            } else if (visited) {
                int idx = index_3d(x, y, z, L);
                if (!visited[idx]) {
                    visited[idx] = 1;
                    if (*touched_count >= touched_cap) {
                        fprintf(stderr, "Touched list capacity exceeded\n");
                        exit(1);
                    }
                    touched[(*touched_count)++] = idx;
                }
            }
        }

        result.final_step = step + 1;

        if (timing) {
            timing->time_walk += now_seconds() - walk_start;
        }
    }

    double reset_start = now_seconds();
    if (use_visited) {
        if (visited_state) {
            visited_state_reset(visited_state);
        } else if (visited) {
            for (size_t i = 0; i < *touched_count; i++) {
                visited[touched[i]] = 0;
            }
            *touched_count = 0;
        }
    }
    if (timing) {
        timing->time_reset += now_seconds() - reset_start;
    }

    if (msd_fp && msd_steps && msd_r2_values) {
        for (int i = 0; i < msd_step_count; i++) {
            if (msd_steps[i] > result.final_step) {
                break;
            }
            fprintf(
                msd_fp,
                "%d,%d,%.10f,%d,%d,%d,%d,%d\n",
                trial,
                msd_steps[i],
                msd_r2_values[i],
                result.final_step,
                1,
                result.trapped,
                result.boundary_dead,
                result.contact_dead
            );
        }
    }

    return result;
}