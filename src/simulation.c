#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "simulation.h"
#include "lattice.h"
#include "percolation.h"
#include "cluster.h"
#include "io.h"

static int compute_n_sites(int dim, int L) {
    int n_sites = 1;
    for (int i = 0; i < dim; i++) {
        n_sites *= L;
    }
    return n_sites;
}

static SweepStats compute_sweep_stats_for_p(int dim, int L, double p, int n_trials) {
    SweepStats stats = {0};

    double sum_occupied = 0.0;
    double sum_clusters = 0.0;
    double sum_largest = 0.0;
    double sum_second = 0.0;

    double sum_occupied_sq = 0.0;
    double sum_clusters_sq = 0.0;
    double sum_largest_sq = 0.0;
    double sum_second_sq = 0.0;

    for (int trial = 0; trial < n_trials; trial++) {
        Lattice *lat = lattice_create(dim, L);
        if (lat == NULL) {
            fprintf(stderr, "Failed to create lattice.\n");
            return stats;
        }

        percolation_generate_site(lat, p);

        ClusterSet *cs = cluster_find_all(lat);
        if (cs == NULL) {
            fprintf(stderr, "Failed to find clusters at p = %.6f\n", p);
            lattice_free(lat);
            return stats;
        }

        cluster_sort_by_size(cs);

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

    double var_occupied = (sum_occupied_sq / n_trials) - (stats.mean_occupied * stats.mean_occupied);
    double var_clusters = (sum_clusters_sq / n_trials) - (stats.mean_clusters * stats.mean_clusters);
    double var_largest  = (sum_largest_sq / n_trials) - (stats.mean_largest * stats.mean_largest);
    double var_second   = (sum_second_sq / n_trials) - (stats.mean_second * stats.mean_second);

    if (var_occupied < 0.0) var_occupied = 0.0;
    if (var_clusters < 0.0) var_clusters = 0.0;
    if (var_largest  < 0.0) var_largest  = 0.0;
    if (var_second   < 0.0) var_second   = 0.0;

    stats.std_occupied = sqrt(var_occupied);
    stats.std_clusters = sqrt(var_clusters);
    stats.std_largest  = sqrt(var_largest);
    stats.std_second   = sqrt(var_second);

    return stats;
}

int run_single_simulation(const Config *cfg) {
    int dim = cfg->dim;
    int L = cfg->L;
    double p = cfg->p;

    Lattice *lat = lattice_create(dim, L);
    if (lat == NULL) {
        fprintf(stderr, "Failed to create lattice.\n");
        return 0;
    }

    percolation_generate_site(lat, p);

    ClusterSet *cs = cluster_find_all(lat);
    if (cs == NULL) {
        fprintf(stderr, "Failed to find clusters.\n");
        lattice_free(lat);
        return 0;
    }

    cluster_sort_by_size(cs);

    printf("mode = single\n");
    printf("dim = %d\n", dim);
    printf("L = %d\n", L);
    printf("p = %.3f\n", p);
    printf("n_sites = %d\n", lat->n_sites);
    printf("n_occupied = %d\n", lat->n_occupied);
    printf("n_clusters = %d\n", cs->n_clusters);

    if (cs->n_clusters > 0) {
        printf("largest cluster size = %d\n", cs->clusters[0].size);
    }
    if (cs->n_clusters > 1) {
        printf("second cluster size = %d\n", cs->clusters[1].size);
    }

    if (!io_save_summary_csv_single("data/summary.csv", lat, cs, p)) {
        fprintf(stderr, "Failed to write summary CSV\n");
    }

    cluster_free_all(cs);
    lattice_free(lat);
    return 1;
}

int run_sweep_simulation(const Config *cfg) {
    int dim = cfg->dim;
    int L = cfg->L;
    double p_start = cfg->p_start;
    double p_end = cfg->p_end;
    double dp = cfg->dp;
    int n_trials = cfg->n_trials;

    if (dp <= 0.0) {
        fprintf(stderr, "Invalid dp. It must be > 0.\n");
        return 0;
    }

    if (n_trials <= 0) {
        fprintf(stderr, "Invalid n_trials. It must be > 0.\n");
        return 0;
    }

    int n_sites = compute_n_sites(dim, L);

    remove("data/summary.csv");

    printf("mode = sweep\n");
    printf("dim = %d\n", dim);
    printf("L = %d\n", L);
    printf("p_start = %.3f\n", p_start);
    printf("p_end = %.3f\n", p_end);
    printf("dp = %.3f\n", dp);
    printf("n_trials = %d\n", n_trials);

    for (double p = p_start; p <= p_end + 1e-12; p += dp) {
        SweepStats stats = compute_sweep_stats_for_p(dim, L, p, n_trials);

        printf("p = %.3f, mean_L1 = %.2f, mean_L2 = %.2f, std_L1 = %.2f, std_L2 = %.2f\n",
               p,
               stats.mean_largest,
               stats.mean_second,
               stats.std_largest,
               stats.std_second);

        if (!io_append_summary_csv_mean("data/summary.csv",
                                        p, dim, L, n_sites, n_trials,
                                        stats.mean_occupied,
                                        stats.mean_clusters,
                                        stats.mean_largest,
                                        stats.mean_second,
                                        stats.std_occupied,
                                        stats.std_clusters,
                                        stats.std_largest,
                                        stats.std_second)) {
            fprintf(stderr, "Failed to append summary CSV at p = %.6f\n", p);
            return 0;
        }
    }

    return 1;
}