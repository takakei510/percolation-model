#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <sys/stat.h>
#include <sys/types.h>

#include "simulation.h"
#include "lattice.h"
#include "percolation.h"
#include "cluster.h"
#include "io.h"
#include "union_find.h"

int compute_n_sites(int dim, int L)
{
    int n_sites = 1;
    for (int i = 0; i < dim; i++)
    {
        n_sites *= L;
    }
    return n_sites;
}

void create_output_dirs(int dim)
{
    mkdir("data", 0777);

    if (dim == 2)
    {
        mkdir("data/2d", 0777);
        mkdir("data/2d/sweep", 0777);
        mkdir("data/2d/time_vs_L", 0777);
        mkdir("data/2d/size_sweep_clusters", 0777);
        mkdir("data/2d/size_sweep_cluster_sizes", 0777);
    }
    else if (dim == 3)
    {
        mkdir("data/3d", 0777);
        mkdir("data/3d/sweep", 0777);
        mkdir("data/3d/time_vs_L", 0777);
        mkdir("data/3d/size_sweep_clusters", 0777);
        mkdir("data/3d/size_sweep_cluster_sizes", 0777);
    }
}

static int run_one_simulation(int dim, int L, double p,
                              Lattice **out_lat,
                              ClusterSet **out_cs)
{
    Lattice *lat = lattice_create(dim, L);
    if (lat == NULL)
    {
        fprintf(stderr, "Failed to create lattice.\n");
        return 0;
    }

    percolation_generate_site(lat, p);

    ClusterSet *cs = cluster_find_all(lat);
    if (cs == NULL)
    {
        fprintf(stderr, "Failed to find clusters.\n");
        lattice_free(lat);
        return 0;
    }

    cluster_sort_by_size(cs);

    *out_lat = lat;
    *out_cs = cs;

    return 1;
}

static void print_single_result(const Config *cfg,
                                const Lattice *lat,
                                const ClusterSet *cs)
{
    printf("mode = single\n");
    printf("dim = %d\n", cfg->dim);
    printf("L = %d\n", cfg->L);
    printf("p = %.3f\n", cfg->p);
    printf("n_sites = %d\n", lat->n_sites);
    printf("n_occupied = %d\n", lat->n_occupied);
    printf("n_clusters = %d\n", cs->n_clusters);
    printf("cluster_view_mode = %s\n", cfg->cluster_view_mode);

    if (cs->n_clusters > 0)
    {
        printf("largest cluster size = %d\n", cs->clusters[0].size);
    }

    if (cs->n_clusters > 1)
    {
        printf("second cluster size = %d\n", cs->clusters[1].size);
    }
}

static int save_single_outputs(const Config *cfg,
                               const Lattice *lat,
                               const ClusterSet *cs)
{
    int ok = 1;

    if (!io_save_summary_csv_single("data/summary.csv", lat, cs, cfg->p))
    {
        fprintf(stderr, "Failed to write summary CSV\n");
        ok = 0;
    }

    if (cfg->save_top_coords)
    {
        if (!io_save_selected_clusters_coords_csv("data/cluster_coords.csv",
                                                  lat,
                                                  cs,
                                                  cfg->cluster_view_mode))
        {
            fprintf(stderr,
                    "Failed to save cluster_coords.csv (mode=%s)\n",
                    cfg->cluster_view_mode);
            ok = 0;
        }
    }
    if (cfg->save_cluster_sizes)
    {
        if (!io_save_cluster_sizes_csv("data/cluster_sizes.csv", cs))
        {
            fprintf(stderr, "Failed to save cluster_sizes.csv\n");
            ok = 0;
        }
    }

    return ok;
}

SweepStats compute_sweep_stats_for_p(int dim, int L, double p, int n_trials)
{
    SweepStats stats = {0};

    double sum_occupied = 0.0;
    double sum_clusters = 0.0;
    double sum_largest = 0.0;
    double sum_second = 0.0;

    double sum_occupied_sq = 0.0;
    double sum_clusters_sq = 0.0;
    double sum_largest_sq = 0.0;
    double sum_second_sq = 0.0;

    for (int trial = 0; trial < n_trials; trial++)
    {
        Lattice *lat = NULL;
        ClusterSet *cs = NULL;

        if (!run_one_simulation(dim, L, p, &lat, &cs))
        {
            return stats;
        }

        int largest = (cs->n_clusters > 0) ? cs->clusters[0].size : 0;
        int second = (cs->n_clusters > 1) ? cs->clusters[1].size : 0;

        sum_occupied += lat->n_occupied;
        sum_clusters += cs->n_clusters;
        sum_largest += largest;
        sum_second += second;

        sum_occupied_sq += (double)lat->n_occupied * lat->n_occupied;
        sum_clusters_sq += (double)cs->n_clusters * cs->n_clusters;
        sum_largest_sq += (double)largest * largest;
        sum_second_sq += (double)second * second;

        cluster_free_all(cs);
        lattice_free(lat);
    }

    stats.mean_occupied = sum_occupied / n_trials;
    stats.mean_clusters = sum_clusters / n_trials;
    stats.mean_largest = sum_largest / n_trials;
    stats.mean_second = sum_second / n_trials;

    double var_occupied = (sum_occupied_sq / n_trials) -
                          (stats.mean_occupied * stats.mean_occupied);
    double var_clusters = (sum_clusters_sq / n_trials) -
                          (stats.mean_clusters * stats.mean_clusters);
    double var_largest = (sum_largest_sq / n_trials) -
                         (stats.mean_largest * stats.mean_largest);
    double var_second = (sum_second_sq / n_trials) -
                        (stats.mean_second * stats.mean_second);

    if (var_occupied < 0.0)
        var_occupied = 0.0;
    if (var_clusters < 0.0)
        var_clusters = 0.0;
    if (var_largest < 0.0)
        var_largest = 0.0;
    if (var_second < 0.0)
        var_second = 0.0;

    stats.std_occupied = sqrt(var_occupied);
    stats.std_clusters = sqrt(var_clusters);
    stats.std_largest = sqrt(var_largest);
    stats.std_second = sqrt(var_second);

    return stats;
}

static SweepStats compute_sweep_stats_for_p_union_find(int dim, int L, double p, int n_trials)
{
    SweepStats stats = {0};

    double sum_occupied = 0.0;
    double sum_clusters = 0.0;
    double sum_largest = 0.0;
    double sum_second = 0.0;

    double sum_occupied_sq = 0.0;
    double sum_clusters_sq = 0.0;
    double sum_largest_sq = 0.0;
    double sum_second_sq = 0.0;

    for (int trial = 0; trial < n_trials; trial++)
    {
        Lattice *lat = lattice_create(dim, L);
        if (lat == NULL)
        {
            fprintf(stderr, "Failed to create lattice.\n");
            return stats;
        }

        UnionFind uf;
        uf_init(&uf, lat->n_sites);

        lat->n_occupied = 0;

        int neighbors[6];

        for (int i = 0; i < lat->n_sites; i++)
        {
            double r = (double)rand() / RAND_MAX;

            if (r >= p)
            {
                lat->occupied[i] = 0;
                continue;
            }

            lat->occupied[i] = 1;
            lat->n_occupied++;

            uf_activate(&uf, i);

            int n_neighbors = lattice_get_neighbors(lat, i, neighbors);

            for (int k = 0; k < n_neighbors; k++)
            {
                int j = neighbors[k];

                /*
                  j < i の近傍だけを見る。
                  こうすると、すでに処理済みの占有サイトだけをunionできる。
                */
                if (j < i && uf.active[j])
                {
                    uf_union(&uf, i, j);
                }
            }
        }

        int largest = 0;
        int second = 0;

        uf_get_largest_second(&uf, &largest, &second);

        int n_clusters = uf.n_clusters;
                sum_occupied += lat->n_occupied;
                sum_clusters += n_clusters;
                sum_largest += largest;
                sum_second += second;

                sum_occupied_sq += (double)lat->n_occupied * lat->n_occupied;
                sum_clusters_sq += (double)n_clusters * n_clusters;
                sum_largest_sq += (double)largest * largest;
                sum_second_sq += (double)second * second;

                uf_free(&uf);
                lattice_free(lat);
    }

    stats.mean_occupied = sum_occupied / n_trials;
    stats.mean_clusters = sum_clusters / n_trials;
    stats.mean_largest = sum_largest / n_trials;
    stats.mean_second = sum_second / n_trials;

    double var_occupied = (sum_occupied_sq / n_trials) - stats.mean_occupied * stats.mean_occupied;
    double var_clusters = (sum_clusters_sq / n_trials) - stats.mean_clusters * stats.mean_clusters;
    double var_largest = (sum_largest_sq / n_trials) - stats.mean_largest * stats.mean_largest;
    double var_second = (sum_second_sq / n_trials) - stats.mean_second * stats.mean_second;

    if (var_occupied < 0.0) var_occupied = 0.0;
    if (var_clusters < 0.0) var_clusters = 0.0;
    if (var_largest < 0.0) var_largest = 0.0;
    if (var_second < 0.0) var_second = 0.0;

    stats.std_occupied = sqrt(var_occupied);
    stats.std_clusters = sqrt(var_clusters);
    stats.std_largest = sqrt(var_largest);
    stats.std_second = sqrt(var_second);

    return stats;
}

static int save_size_sweep_cluster_coords(const Config *cfg,
                                          const char *dim_dir,
                                          int L)
{
    char cluster_filename[256];

    snprintf(cluster_filename,
             sizeof(cluster_filename),
             "%s/size_sweep_clusters/cluster_coords_L_%d.csv",
             dim_dir,
             L);

    Lattice *lat = NULL;
    ClusterSet *cs = NULL;

    if (!run_one_simulation(cfg->dim, L, cfg->p, &lat, &cs))
    {
        return 0;
    }

    int ok = io_save_selected_clusters_coords_csv(cluster_filename,
                                                  lat,
                                                  cs,
                                                  cfg->cluster_view_mode);

    if (!ok)
    {
        fprintf(stderr,
                "Failed to save cluster coords for L=%d, mode=%s\n",
                L,
                cfg->cluster_view_mode);
    }

    cluster_free_all(cs);
    lattice_free(lat);

    return ok;
}

static int save_size_sweep_cluster_sizes(const Config *cfg,
                                         const char *dim_dir,
                                         int L)
{
    char filename[256];

    snprintf(filename,
             sizeof(filename),
             "%s/size_sweep_cluster_sizes/cluster_sizes_L_%d.csv",
             dim_dir,
             L);

    Lattice *lat = NULL;
    ClusterSet *cs = NULL;

    if (!run_one_simulation(cfg->dim, L, cfg->p, &lat, &cs))
    {
        return 0;
    }

    int ok = io_save_cluster_sizes_csv(filename, cs);

    if (!ok)
    {
        fprintf(stderr, "Failed to save cluster sizes for L=%d\n", L);
    }

    cluster_free_all(cs);
    lattice_free(lat);

    return ok;
}

int run_single_simulation(const Config *cfg)
{
    Lattice *lat = NULL;
    ClusterSet *cs = NULL;

    if (!run_one_simulation(cfg->dim, cfg->L, cfg->p, &lat, &cs))
    {
        return 0;
    }

    print_single_result(cfg, lat, cs);

    int ok = save_single_outputs(cfg, lat, cs);

    cluster_free_all(cs);
    lattice_free(lat);

    return ok;
}

int run_sweep_simulation(const Config *cfg)
{
    int dim = cfg->dim;
    int L = cfg->L;

    create_output_dirs(dim);

    double p_start = cfg->p_start;
    double p_end = cfg->p_end;
    double dp = cfg->dp;
    int n_trials = cfg->n_trials;

    if (dp <= 0.0)
    {
        fprintf(stderr, "Invalid dp. It must be > 0.\n");
        return 0;
    }

    if (n_trials <= 0)
    {
        fprintf(stderr, "Invalid n_trials. It must be > 0.\n");
        return 0;
    }

    int n_sites = compute_n_sites(dim, L);

    create_output_dirs(dim);

    const char *dim_dir = (dim == 2) ? "data/2d" : "data/3d";

    char summary_filename[256];
    if (cfg->output[0] != '\0'){
        snprintf(summary_filename, sizeof(summary_filename), "%s", cfg->output);
    }else{
        snprintf(summary_filename, sizeof(summary_filename), "%s/summary.csv", dim_dir);
    }

    remove(summary_filename);

    printf("mode = sweep\n");
    printf("dim = %d\n", dim);
    printf("L = %d\n", L);
    printf("p_start = %.3f\n", p_start);
    printf("p_end = %.3f\n", p_end);
    printf("dp = %.3f\n", dp);
    printf("n_trials = %d\n", n_trials);

    for (double p = p_start; p <= p_end + 1e-12; p += dp)
    {
        SweepStats stats = compute_sweep_stats_for_p(dim, L, p, n_trials);

        printf("p = %.3f, mean_L1 = %.2f, mean_L2 = %.2f, std_L1 = %.2f, std_L2 = %.2f\n",
               p,
               stats.mean_largest,
               stats.mean_second,
               stats.std_largest,
               stats.std_second);

        if(!io_append_summary_csv_mean(summary_filename,
                                    p, dim, L, n_sites, n_trials,
                                    stats.mean_occupied,
                                    stats.mean_clusters,
                                    stats.mean_largest,
                                    stats.mean_second,
                                    stats.std_occupied,
                                    stats.std_clusters,
                                    stats.std_largest,
                                    stats.std_second))
        {
            fprintf(stderr, "Failed to append summary CSV at p = %.6f\n", p);
            return 0;
        }
    }

    return 1;
}

int run_size_sweep_simulation(const Config *cfg)
{
    int dim = cfg->dim;
    double p = cfg->p;
    int n_trials = cfg->n_trials;

    int L = cfg->L_start;
    int L_max = cfg->L_max;
    double mult = cfg->L_multiplier;

    if (dim != 2 && dim != 3)
    {
        fprintf(stderr, "dim must be 2 or 3.\n");
        return 0;
    }

    if (L <= 0 || L_max <= 0 || L > L_max)
    {
        fprintf(stderr, "Invalid L_start or L_max.\n");
        return 0;
    }

    if (mult <= 1.0)
    {
        fprintf(stderr, "L_multiplier must be > 1.0.\n");
        return 0;
    }

    if (n_trials <= 0)
    {
        fprintf(stderr, "n_trials must be > 0.\n");
        return 0;
    }

    create_output_dirs(dim);

    const char *dim_dir = (dim == 2) ? "data/2d" : "data/3d";

    char time_filename[256];
    if (cfg->output[0] != '\0'){
        snprintf(time_filename, sizeof(time_filename), "%s", cfg->output);
    }else{
        snprintf(time_filename,
                sizeof(time_filename),
                "%s/time_vs_L/%s.csv",
                dim_dir,
                cfg->cluster_method);
    }
                
    FILE *fp = fopen(time_filename, "w");
    if (fp == NULL)
    {
        fprintf(stderr, "Failed to open %s\n", time_filename);
        return 0;
    }

    fprintf(fp,
            "L,n_sites,n_trials,save_top_coords,time_sec,mean_largest,mean_second,std_largest,std_second\n");

    printf("mode = size_sweep\n");
    printf("dim = %d\n", dim);
    printf("p = %.6f\n", p);
    printf("L_start = %d\n", L);
    printf("L_max = %d\n", L_max);
    printf("L_multiplier = %.3f\n", mult);
    printf("n_trials = %d\n", n_trials);
    printf("save_top_coords = %d\n", cfg->save_top_coords);

    while (L <= L_max)
    {
        int n_sites = compute_n_sites(dim, L);

        clock_t t0 = clock();
        SweepStats stats;

        if (strcmp(cfg->cluster_method, "union_find") == 0)
        {
            stats = compute_sweep_stats_for_p_union_find(dim, L, p, n_trials);
        }
        else
        {
            stats = compute_sweep_stats_for_p(dim, L, p, n_trials);
        }

        clock_t t1 = clock();

        double elapsed = (double)(t1 - t0) / CLOCKS_PER_SEC;

        fprintf(fp,
                "%d,%d,%d,%d,%.6f,%.6f,%.6f,%.6f,%.6f\n",
                L,
                n_sites,
                n_trials,
                cfg->save_top_coords,
                elapsed,
                stats.mean_largest,
                stats.mean_second,
                stats.std_largest,
                stats.std_second);

        if (cfg->save_cluster_sizes)
        {
            if (!save_size_sweep_cluster_sizes(cfg, dim_dir, L))
            {
                fclose(fp);
                return 0;
            }
        }
        if (cfg->save_top_coords)
        {
            if (!save_size_sweep_cluster_coords(cfg, dim_dir, L))
            {
                fclose(fp);
                return 0;
            }
        }

        printf("L=%d done (time=%.6f sec)\n", L, elapsed);

        int next_L = (int)(L * mult);
        if (next_L <= L)
        {
            next_L = L + 1;
        }

        L = next_L;
    }

    fclose(fp);
    return 1;
}