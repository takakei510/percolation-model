#ifndef IO_H
#define IO_H

#include "lattice.h"
#include "cluster.h"

int io_save_summary_csv_single(const char *filename,
                               const Lattice *lat,
                               const ClusterSet *cs,
                               double p);

int io_append_summary_csv_mean(const char *filename,
                               double p,
                               int dim,
                               int L,
                               int n_sites,
                               int n_trials,
                               double mean_occupied,
                               double mean_clusters,
                               double mean_largest,
                               double mean_second);

int io_save_cluster_sizes_csv(const char *filename, const ClusterSet *cs);
int io_save_top_clusters_coords_csv(const char *filename, const Lattice *lat, const ClusterSet *cs, int top_k);

#endif