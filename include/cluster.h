#ifndef CLUSTER_H
#define CLUSTER_H

#include "lattice.h"

typedef struct {
    int id;
    int size;
    int *sites;
} Cluster;

typedef struct {
    int n_clusters;
    Cluster *clusters;
} ClusterSet;

ClusterSet *cluster_find_all(const Lattice *lat);
void cluster_sort_by_size(ClusterSet *cs);
void cluster_free_all(ClusterSet *cs);

#endif