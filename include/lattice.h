#ifndef LATTICE_H
#define LATTICE_H

typedef struct {
    int dim;
    int L;
    int n_sites;
    int n_occupied;
    int *occupied;
} Lattice;

Lattice *lattice_create(int dim, int L);
void lattice_free(Lattice *lat);

int lattice_coord_to_index(const int *coord, int dim, int L);
void lattice_index_to_coord(int index, int *coord, int dim, int L);

int lattice_get_neighbors(const Lattice *lat, int index, int *neighbors);

#endif