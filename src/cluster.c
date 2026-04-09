#include <stdlib.h>
#include <string.h>
#include "cluster.h"

static int compare_cluster_size_desc(const void *a, const void *b) {
    const Cluster *ca = (const Cluster *)a;
    const Cluster *cb = (const Cluster *)b;

    if (cb->size > ca->size) return 1;
    if (cb->size < ca->size) return -1;
    return 0;
}

ClusterSet *cluster_find_all(const Lattice *lat) {
    int *visited = calloc(lat->n_sites, sizeof(int));
    int *queue = malloc(lat->n_sites * sizeof(int));
    Cluster *clusters = malloc(lat->n_sites * sizeof(Cluster));

    if (visited == NULL || queue == NULL || clusters == NULL) {
        free(visited);
        free(queue);
        free(clusters);
        return NULL;
    }

    int cluster_count = 0;
    int neighbors[6];

    for (int start = 0; start < lat->n_sites; start++) {
        if (!lat->occupied[start] || visited[start]) {
            continue;
        }

        int front = 0;
        int back = 0;
        queue[back++] = start;
        visited[start] = 1;

        int *sites = malloc(lat->n_sites * sizeof(int));
        if (sites == NULL) {
            for (int i = 0; i < cluster_count; i++) {
                free(clusters[i].sites);
            }
            free(visited);
            free(queue);
            free(clusters);
            return NULL;
        }

        int size = 0;

        while (front < back) {
            int current = queue[front++];
            sites[size++] = current;

            int n_nb = lattice_get_neighbors(lat, current, neighbors);
            for (int k = 0; k < n_nb; k++) {
                int nb = neighbors[k];
                if (lat->occupied[nb] && !visited[nb]) {
                    visited[nb] = 1;
                    queue[back++] = nb;
                }
            }
        }

        clusters[cluster_count].id = cluster_count;
        clusters[cluster_count].size = size;
        clusters[cluster_count].sites = malloc(size * sizeof(int));

        if (clusters[cluster_count].sites == NULL) {
            free(sites);
            for (int i = 0; i < cluster_count; i++) {
                free(clusters[i].sites);
            }
            free(visited);
            free(queue);
            free(clusters);
            return NULL;
        }

        memcpy(clusters[cluster_count].sites, sites, size * sizeof(int));
        free(sites);
        cluster_count++;
    }

    free(visited);
    free(queue);

    ClusterSet *cs = malloc(sizeof(ClusterSet));
    if (cs == NULL) {
        for (int i = 0; i < cluster_count; i++) {
            free(clusters[i].sites);
        }
        free(clusters);
        return NULL;
    }

    cs->n_clusters = cluster_count;

    if (cluster_count == 0) {
        free(clusters);
        cs->clusters = NULL;
        return cs;
    }

    Cluster *tmp = realloc(clusters, cluster_count * sizeof(Cluster));
    if (tmp == NULL) {
        for (int i = 0; i < cluster_count; i++) {
            free(clusters[i].sites);
        }
        free(clusters);
        free(cs);
        return NULL;
    }

    cs->clusters = tmp;
    return cs;
}

void cluster_sort_by_size(ClusterSet *cs) {
    if (cs == NULL || cs->n_clusters <= 1) {
        return;
    }

    qsort(cs->clusters, cs->n_clusters, sizeof(Cluster), compare_cluster_size_desc);
}

void cluster_free_all(ClusterSet *cs) {
    if (cs == NULL) {
        return;
    }
    for (int i = 0; i < cs->n_clusters; i++) {
        free(cs->clusters[i].sites);
    }
    free(cs->clusters);
    free(cs);
}