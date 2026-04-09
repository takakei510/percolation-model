#include <stdlib.h>
#include <time.h>
#include "percolation.h"

void percolation_seed(unsigned int seed) {
    srand(seed);
}

void percolation_generate_site(Lattice *lat, double p) {
    lat->n_occupied = 0;

    for (int i = 0; i < lat->n_sites; i++) {
        double r = (double)rand() / (double)RAND_MAX;
        lat->occupied[i] = (r < p) ? 1 : 0;

        if (lat->occupied[i]) {
            lat->n_occupied++;
        }
    }
}

int percolation_count_occupied(const Lattice *lat) {
    return lat->n_occupied;
}