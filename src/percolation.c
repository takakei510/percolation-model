#include <stdlib.h>
#include <time.h>
#include "percolation.h"

void percolation_seed(unsigned int seed) {
    srand(seed);
}

void percolation_generate_site(Lattice *lat, double p) {
    for (int i = 0; i < lat->n_sites; i++) {
        double r = (double)rand() / (double)RAND_MAX;
        lat->occupied[i] = (r < p) ? 1 : 0;
    }
}

int percolation_count_occupied(const Lattice *lat) {
    int count = 0;
    for (int i = 0; i < lat->n_sites; i++) {
        if (lat->occupied[i]) {
            count++;
        }
    }
    return count;
}