#include <stdio.h>
#include <stdlib.h>
#include "io.h"
#include "percolation.h"

int io_save_summary_csv_single(const char *filename,
                               const Lattice *lat,
                               const ClusterSet *cs,
                               double p) {
    FILE *fp = fopen(filename, "w");
    if (fp == NULL) {
        return 0;
    }

    int occupied = percolation_count_occupied(lat);
    int largest = (cs->n_clusters > 0) ? cs->clusters[0].size : 0;
    int second = (cs->n_clusters > 1) ? cs->clusters[1].size : 0;

    fprintf(fp, "p,dim,L,n_sites,n_occupied,n_clusters,largest_size,second_size\n");
    fprintf(fp, "%.6f,%d,%d,%d,%d,%d,%d,%d\n",
            p, lat->dim, lat->L, lat->n_sites, occupied, cs->n_clusters, largest, second);

    fclose(fp);
    return 1;
}

int io_append_summary_csv_mean(const char *filename,
                               double p,
                               int dim,
                               int L,
                               int n_sites,
                               int n_trials,
                               double mean_occupied,
                               double mean_clusters,
                               double mean_largest,
                               double mean_second) {
    FILE *check = fopen(filename, "r");
    int file_exists = (check != NULL);
    if (check != NULL) {
        fclose(check);
    }

    FILE *fp = fopen(filename, "a");
    if (fp == NULL) {
        return 0;
    }

    if (!file_exists) {
        fprintf(fp, "p,dim,L,n_sites,n_trials,mean_occupied,mean_clusters,mean_largest,mean_second\n");
    }

    fprintf(fp, "%.6f,%d,%d,%d,%d,%.6f,%.6f,%.6f,%.6f\n",
            p, dim, L, n_sites, n_trials,
            mean_occupied, mean_clusters, mean_largest, mean_second);

    fclose(fp);
    return 1;
}

int io_save_cluster_sizes_csv(const char *filename, const ClusterSet *cs) {
    FILE *fp = fopen(filename, "w");
    if (fp == NULL) {
        return 0;
    }

    fprintf(fp, "cluster_rank,cluster_id,size\n");
    for (int i = 0; i < cs->n_clusters; i++) {
        fprintf(fp, "%d,%d,%d\n", i + 1, cs->clusters[i].id, cs->clusters[i].size);
    }

    fclose(fp);
    return 1;
}

int io_save_top_clusters_coords_csv(const char *filename, const Lattice *lat, const ClusterSet *cs, int top_k) {
    FILE *fp = fopen(filename, "w");
    if (fp == NULL) {
        return 0;
    }

    if (lat->dim == 2) {
        fprintf(fp, "cluster_rank,site_index,x,y\n");
    } else if (lat->dim == 3) {
        fprintf(fp, "cluster_rank,site_index,x,y,z\n");
    } else {
        fprintf(fp, "cluster_rank,site_index\n");
    }

    int coord[3] = {0, 0, 0};
    int limit = (top_k < cs->n_clusters) ? top_k : cs->n_clusters;

    for (int i = 0; i < limit; i++) {
        for (int j = 0; j < cs->clusters[i].size; j++) {
            int site = cs->clusters[i].sites[j];
            lattice_index_to_coord(site, coord, lat->dim, lat->L);

            if (lat->dim == 2) {
                fprintf(fp, "%d,%d,%d,%d\n", i + 1, site, coord[0], coord[1]);
            } else if (lat->dim == 3) {
                fprintf(fp, "%d,%d,%d,%d,%d\n", i + 1, site, coord[0], coord[1], coord[2]);
            } else {
                fprintf(fp, "%d,%d\n", i + 1, site);
            }
        }
    }

    fclose(fp);
    return 1;
}