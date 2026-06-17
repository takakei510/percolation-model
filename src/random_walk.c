#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

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
)
{
    WalkResult result;

    result.final_step = 0;
    result.trapped = 0;
    result.contact_dead = 0;
    result.boundary_dead = 0;

    int x0 = L / 2;
    int y0 = L / 2;
    int z0 = (dim == 3) ? L / 2 : 0;

    int x = x0;
    int y = y0;
    int z = z0;

    int n_sites = (dim == 3) ? L * L * L : L * L;
    unsigned char *visited = NULL;

    int use_visited =
        (strcmp(walk_type, "saw") == 0) ||
        (strcmp(walk_type, "death_on_contact") == 0);

    if (use_visited) {
        visited = (unsigned char *)calloc(n_sites, sizeof(unsigned char));
        if (!visited) {
            fprintf(stderr, "Failed to allocate visited array\n");
            result.trapped = 1;
            return result;
        }
        visited[index_3d(x, y, z, L)] = 1;
    }

    double sx = 0.0;
    double sy = 0.0;
    double sz = 0.0;
    double sr2 = 0.0;

    for (int step = 0; step <= n_steps; step++) {
        int dx0 = x - x0;
        int dy0 = y - y0;
        int dz0 = z - z0;

        double r2 = (double)(dx0 * dx0 + dy0 * dy0 + dz0 * dz0);
        double r = sqrt(r2);

        /* Radius of gyration up to this step */
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

        if (step == n_steps) {
            result.final_step = step;
            break;
        }

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

            if (strcmp(boundary, "periodic") == 0) {
                apply_periodic(&nx, &ny, &nz, dim, L);
            } else {
                if (!inside(nx, ny, nz, dim, L)) {
                    continue;
                }
            }

            if (strcmp(walk_type, "saw") == 0) {
                int idx = index_3d(nx, ny, nz, L);
                if (visited[idx]) {
                    continue;
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

            break;
        }

        int choice = rand() % n_candidates;

        int nx = candidates[choice][0];
        int ny = candidates[choice][1];
        int nz = candidates[choice][2];

        if (strcmp(walk_type, "death_on_contact") == 0) {
            if (strcmp(boundary, "periodic") == 0) {
                apply_periodic(&nx, &ny, &nz, dim, L);
            } else {
                if (!inside(nx, ny, nz, dim, L)) {
                    result.trapped = 1;
                    result.boundary_dead = 1;
                    result.final_step = step;
                    break;
                }
            }

            int idx = index_3d(nx, ny, nz, L);
            if (visited[idx]) {
                result.trapped = 1;
                result.contact_dead = 1;
                result.final_step = step;
                break;
            }
        }

        x = nx;
        y = ny;
        z = nz;

        if (use_visited) {
            visited[index_3d(x, y, z, L)] = 1;
        }

        result.final_step = step + 1;
    }

    free(visited);
    return result;
}