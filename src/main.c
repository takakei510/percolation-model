#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "lattice.h"
#include "percolation.h"
#include "cluster.h"
#include "io.h"
#include "config.h"

int main(int argc, char *argv[]) {

    if (argc < 2) {
        fprintf(stderr, "Usage: %s config.txt\n", argv[0]);
        return 1;
    }

    Config cfg = {0};

    if (!config_load(argv[1], &cfg)) {
        return 1;
    }

    int dim = cfg.dim;
    int L = cfg.L;
    double p = cfg.p;

    int save_cluster_sizes = cfg.save_cluster_sizes;
    int save_top_coords = cfg.save_top_coords;

    Lattice *lat = lattice_create(dim, L);
    if (lat == NULL) {
        fprintf(stderr, "Failed to create lattice.\n");
        return 1;
    }

    percolation_seed((unsigned int)time(NULL));
    percolation_generate_site(lat, p);

    ClusterSet *cs = cluster_find_all(lat);
    if (cs == NULL) {
        fprintf(stderr, "Failed to find clusters.\n");
        lattice_free(lat);
        return 1;
    }

    cluster_sort_by_size(cs);

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

    if (!io_save_summary_csv("data/summary.csv", lat, cs, p)) {
        fprintf(stderr, "Failed to save summary.csv\n");
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

    return 0;
}