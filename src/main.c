#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "lattice.h"
#include "percolation.h"
#include "cluster.h"
#include "io.h"
#include "config.h"

static int run_single(const Config *cfg) {
    int dim = cfg->dim;
    int L = cfg->L;
    double p = cfg->p;

    int save_cluster_sizes = cfg->save_cluster_sizes;
    int save_top_coords = cfg->save_top_coords;

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

    if (save_cluster_sizes) {
        if (!io_save_cluster_sizes_csv("data/cluster_sizes.csv", cs)) {
            fprintf(stderr, "Failed to save cluster_sizes.csv\n");
        }
    }

    if (save_top_coords) {
        if (!io_save_top_clusters_coords_csv("data/top_clusters_coords.csv", lat, cs, 2)) {
            fprintf(stderr, "Failed to save top_clusters_coords.csv\n");
        }
    }

    cluster_free_all(cs);
    lattice_free(lat);
    return 1;
}

static int run_sweep(const Config *cfg) {
    int dim = cfg->dim;
    int L = cfg->L;
    int n_trials = cfg->n_trials;
    double p_start = cfg->p_start;
    double p_end = cfg->p_end;
    double dp = cfg->dp;

    int save_cluster_sizes = cfg->save_cluster_sizes;
    int save_top_coords = cfg->save_top_coords;

    int n_sites = 1;
    for (int i = 0; i < dim; i++) {
        n_sites *= L;
    }
    
    if (dp <= 0.0) {
        fprintf(stderr, "Invalid dp. It must be > 0.\n");
        return 0;
    }


    remove("data/summary.csv");

    printf("mode = sweep\n");
    printf("dim = %d\n", dim);
    printf("L = %d\n", L);
    printf("p_start = %.3f\n", p_start);
    printf("p_end = %.3f\n", p_end);
    printf("dp = %.3f\n", dp);

    for (double p = p_start; p <= p_end + 1e-12; p += dp) {

        double sum_largest = 0.0;
        double sum_second = 0.0;
        double sum_occupied = 0.0;
        double sum_clusters = 0.0;

        for (int trial = 0; trial < n_trials; trial++) {

            Lattice *lat = lattice_create(dim, L);
            percolation_generate_site(lat, p);

            ClusterSet *cs = cluster_find_all(lat);
            cluster_sort_by_size(cs);

            int largest = (cs->n_clusters > 0) ? cs->clusters[0].size : 0;
            int second  = (cs->n_clusters > 1) ? cs->clusters[1].size : 0;

            sum_largest += largest;
            sum_second  += second;
            sum_occupied += lat->n_occupied;
            sum_clusters += cs->n_clusters;

            cluster_free_all(cs);
            lattice_free(lat);
        }

        double mean_largest = sum_largest / n_trials;
        double mean_second  = sum_second / n_trials;
        double mean_occupied = sum_occupied / n_trials;
        double mean_clusters = sum_clusters / n_trials;

        printf("p=%.3f, mean_L1=%.2f, mean_L2=%.2f\n",
            p, mean_largest, mean_second);

        io_append_summary_csv_mean(
            "data/summary.csv",
            p, dim, L, n_sites, n_trials,
            mean_occupied, mean_clusters,
            mean_largest, mean_second
        );
    }

    return 1;
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <config_file>\n", argv[0]);
        return 1;
    }

    Config cfg = {0};

    if (!config_load(argv[1], &cfg)) {
        return 1;
    }

    percolation_seed((unsigned int)time(NULL));

    if (strcmp(cfg.mode, "single") == 0) {
        if (!run_single(&cfg)) {
            return 1;
        }
    } else if (strcmp(cfg.mode, "sweep") == 0) {
        if (!run_sweep(&cfg)) {
            return 1;
        }
    } else {
        fprintf(stderr, "Unknown mode: %s\n", cfg.mode);
        fprintf(stderr, "Use mode=single or mode=sweep in config file.\n");
        return 1;
    }

    return 0;
}