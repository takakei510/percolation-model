#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "lattice.h"
#include "percolation.h"
#include "cluster.h"
#include "io.h"

int main(void) {
    int dim = 2;       // 2 or 3
    int L = 20;        // lattice size
    double p = 0.60;   // occupation probability

    int save_cluster_sizes = 0;
    int save_top_coords = 1;

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
    printf("n_occupied = %d\n", percolation_count_occupied(lat));
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