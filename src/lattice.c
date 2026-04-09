#include <stdio.h>
#include <stdlib.h>
#include "lattice.h"

static int int_pow(int base, int exp) {
    int result = 1;
    for (int i = 0; i < exp; i++) {
        result *= base;
    }
    return result;
}

Lattice *lattice_create(int dim, int L) {
    if (dim < 1 || L < 1) {
        return NULL;
    }

    Lattice *lat = malloc(sizeof(Lattice));
    if (lat == NULL) {
        return NULL;
    }

    lat->dim = dim;
    lat->L = L;
    lat->n_sites = int_pow(L, dim);
    lat->occupied = calloc(lat->n_sites, sizeof(int));

    if (lat->occupied == NULL) {
        free(lat);
        return NULL;
    }

    return lat;
}

void lattice_free(Lattice *lat) {
    if (lat == NULL) {
        return;
    }
    free(lat->occupied);
    free(lat);
}

int lattice_coord_to_index(const int *coord, int dim, int L) {
    int index = 0;
    for (int d = 0; d < dim; d++) {
        index = index * L + coord[d];
    }
    return index;
}

void lattice_index_to_coord(int index, int *coord, int dim, int L) {
    for (int d = dim - 1; d >= 0; d--) {
        coord[d] = index % L;
        index /= L;
    }
}

int lattice_get_neighbors(const Lattice *lat, int index, int *neighbors) {
    int coord[3] = {0, 0, 0};
    int temp[3] = {0, 0, 0};
    int count = 0;

    lattice_index_to_coord(index, coord, lat->dim, lat->L);

    for (int d = 0; d < lat->dim; d++) {
        for (int k = 0; k < lat->dim; k++) {
            temp[k] = coord[k];
        }

        if (coord[d] > 0) {
            temp[d] = coord[d] - 1;
            neighbors[count++] = lattice_coord_to_index(temp, lat->dim, lat->L);
            temp[d] = coord[d];
        }

        if (coord[d] < lat->L - 1) {
            temp[d] = coord[d] + 1;
            neighbors[count++] = lattice_coord_to_index(temp, lat->dim, lat->L);
            temp[d] = coord[d];
        }
    }

    return count;
}