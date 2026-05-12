#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#include <math.h>

#include "lattice.h"
#include "union_find.h"
#include "simulation.h"

typedef struct
{
    int index;
    double r;
} RandomSite;

static int compare_random_site(const void *a, const void *b)
{
    const RandomSite *ra = (const RandomSite *)a;
    const RandomSite *rb = (const RandomSite *)b;

    if (ra->r < rb->r)
        return -1;
    if (ra->r > rb->r)
        return 1;
    return 0;
}

static int run_p_incremental_sweep_bfs(const Config *cfg)
{
    int dim = cfg->dim;
    int L = cfg->L;

    double p_start = cfg->p_start;
    double p_end = cfg->p_end;
    double dp = cfg->dp;

    int n_trials = cfg->n_trials;

    if (dp <= 0.0)
    {
        fprintf(stderr, "Invalid dp\n");
        return 0;
    }

    create_output_dirs(dim);

    int n_sites = compute_n_sites(dim, L);

    char output_filename[256];

    if (cfg->output[0] != '\0')
    {
        snprintf(output_filename, sizeof(output_filename), "%s", cfg->output);
    }
    else
    {
        const char *dim_dir = (dim == 2) ? "data/2d" : "data/3d";

        snprintf(output_filename,
                sizeof(output_filename),
                "%s/p_sweep_time/%s.csv",
                dim_dir,
                cfg->cluster_method);
    }

    FILE *fp = fopen(output_filename, "w");

    if (fp == NULL)
    {
        perror(output_filename);
        return 0;
    }

    fprintf(fp,
            "p,dim,L,n_sites,n_trials,method,"
            "step_time,total_time,"
            "mean_largest,mean_second,"
            "std_largest,std_second\n");

    double total_time = 0.0;

    for (double p = p_start;
         p <= p_end + 1e-12;
         p += dp)
    {
        clock_t t0 = clock();

        SweepStats stats =
            compute_sweep_stats_for_p_bfs_fast(
                dim,
                L,
                p,
                n_trials);

        clock_t t1 = clock();

        double step_time =
            (double)(t1 - t0) / CLOCKS_PER_SEC;

        total_time += step_time;

        fprintf(fp,
                "%.6f,%d,%d,%d,%d,%s,"
                "%.6f,%.6f,"
                "%.6f,%.6f,"
                "%.6f,%.6f\n",
                p,
                dim,
                L,
                n_sites,
                n_trials,
                "bfs",
                step_time,
                total_time,
                stats.mean_largest,
                stats.mean_second,
                stats.std_largest,
                stats.std_second);

        printf("p=%.6f step=%.6f total=%.6f\n",
               p,
               step_time,
               total_time);
    }

    fclose(fp);

    return 1;
}

static int run_p_incremental_sweep_union_find(const Config *cfg)
{
    int dim = cfg->dim;
    int L = cfg->L;
    double p_start = cfg->p_start;
    double p_end = cfg->p_end;
    double dp = cfg->dp;
    int n_trials = cfg->n_trials;

    if (dp <= 0.0)
    {
        fprintf(stderr, "Invalid dp\n");
        return 0;
    }

    if (n_trials <= 0)
    {
        fprintf(stderr, "Invalid n_trials\n");
        return 0;
    }

    create_output_dirs(dim);

    int n_sites = compute_n_sites(dim, L);

    char output_filename[256];

    if (cfg->output[0] != '\0')
    {
        snprintf(output_filename, sizeof(output_filename), "%s", cfg->output);
    }
    else
    {
        const char *dim_dir = (dim == 2) ? "data/2d" : "data/3d";

        snprintf(output_filename,
                sizeof(output_filename),
                "%s/p_sweep_time/%s.csv",
                dim_dir,
                cfg->cluster_method);
    }

    FILE *fp = fopen(output_filename, "w");

    if (fp == NULL)
    {
        perror(output_filename);
        return 0;
    }

    fprintf(fp,
            "p,dim,L,n_sites,n_trials,method,"
            "step_time,total_time,"
            "mean_largest,mean_second,"
            "std_largest,std_second\n");

    printf("mode = p_incremental_sweep\n");
    printf("method = union_find\n");
    printf("dim = %d\n", dim);
    printf("L = %d\n", L);
    printf("p_start = %.6f\n", p_start);
    printf("p_end = %.6f\n", p_end);
    printf("dp = %.6f\n", dp);
    printf("n_trials = %d\n", n_trials);
    printf("output = %s\n", output_filename);

    int n_steps = (int)((p_end - p_start) / dp + 0.5) + 1;

    double *sum_largest = calloc(n_steps, sizeof(double));
    double *sum_second = calloc(n_steps, sizeof(double));
    double *sum_largest_sq = calloc(n_steps, sizeof(double));
    double *sum_second_sq = calloc(n_steps, sizeof(double));
    double *sum_step_time = calloc(n_steps, sizeof(double));
    double *sum_total_time = calloc(n_steps, sizeof(double));

    if (!sum_largest || !sum_second || !sum_largest_sq || !sum_second_sq ||
        !sum_step_time || !sum_total_time)
    {
        fprintf(stderr, "Failed to allocate arrays.\n");
        fclose(fp);
        free(sum_largest);
        free(sum_second);
        free(sum_largest_sq);
        free(sum_second_sq);
        free(sum_step_time);
        free(sum_total_time);
        return 0;
    }

    for (int trial = 0; trial < n_trials; trial++)
    {
        Lattice *lat = lattice_create(dim, L);
        if (lat == NULL)
        {
            fprintf(stderr, "Failed to create lattice.\n");
            fclose(fp);
            return 0;
        }

        UnionFind uf;
        uf_init(&uf, n_sites);

        RandomSite *sites = malloc(sizeof(RandomSite) * n_sites);
        if (sites == NULL)
        {
            fprintf(stderr, "Failed to allocate random sites.\n");
            uf_free(&uf);
            lattice_free(lat);
            fclose(fp);
            return 0;
        }

        for (int i = 0; i < n_sites; i++)
        {
            sites[i].index = i;
            sites[i].r = (double)rand() / RAND_MAX;
            lat->occupied[i] = 0;
        }

        qsort(sites, n_sites, sizeof(RandomSite), compare_random_site);

        int next_site = 0;
        double total_time = 0.0;

        for (int step = 0; step < n_steps; step++)
        {
            double p = p_start + step * dp;

            clock_t t0 = clock();

            while (next_site < n_sites && sites[next_site].r < p)
            {
                int i = sites[next_site].index;

                lat->occupied[i] = 1;
                lat->n_occupied++;

                uf_activate(&uf, i);

                int neighbors[6];
                int n_neighbors = lattice_get_neighbors(lat, i, neighbors);

                for (int k = 0; k < n_neighbors; k++)
                {
                    int j = neighbors[k];

                    if (lat->occupied[j])
                    {
                        uf_union(&uf, i, j);
                    }
                }

                next_site++;
            }

            int largest = 0;
            int second = 0;

            uf_get_largest_second(&uf, &largest, &second);

            clock_t t1 = clock();

            double step_time = (double)(t1 - t0) / CLOCKS_PER_SEC;
            total_time += step_time;

            sum_step_time[step] += step_time;
            sum_total_time[step] += total_time;

            sum_largest[step] += largest;
            sum_second[step] += second;
            sum_largest_sq[step] += (double)largest * largest;
            sum_second_sq[step] += (double)second * second;
        }

        free(sites);
        uf_free(&uf);
        lattice_free(lat);
    }

    for (int step = 0; step < n_steps; step++)
    {
        double p = p_start + step * dp;

        double mean_largest = sum_largest[step] / n_trials;
        double mean_second = sum_second[step] / n_trials;

        double var_largest =
            (sum_largest_sq[step] / n_trials) - mean_largest * mean_largest;
        double var_second =
            (sum_second_sq[step] / n_trials) - mean_second * mean_second;

        if (var_largest < 0.0)
            var_largest = 0.0;
        if (var_second < 0.0)
            var_second = 0.0;

        double std_largest = sqrt(var_largest);
        double std_second = sqrt(var_second);

        double mean_step_time = sum_step_time[step] / n_trials;
        double mean_total_time = sum_total_time[step] / n_trials;

        fprintf(fp,
                "%.6f,%d,%d,%d,%d,%s,"
                "%.6f,%.6f,"
                "%.6f,%.6f,"
                "%.6f,%.6f\n",
                p,
                dim,
                L,
                n_sites,
                n_trials,
                "union_find",
                mean_step_time,
                mean_total_time,
                mean_largest,
                mean_second,
                std_largest,
                std_second);

        printf("p=%.6f step=%.6f total=%.6f\n",
               p,
               mean_step_time,
               mean_total_time);
    }

    fclose(fp);

    free(sum_largest);
    free(sum_second);
    free(sum_largest_sq);
    free(sum_second_sq);
    free(sum_step_time);
    free(sum_total_time);

    return 1;
}

int run_p_incremental_sweep_simulation(const Config *cfg)
{
    if (strcmp(cfg->cluster_method,
               "union_find") == 0)
    {
        return run_p_incremental_sweep_union_find(cfg);
    }

    return run_p_incremental_sweep_bfs(cfg);
}