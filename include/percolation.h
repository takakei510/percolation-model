#ifndef PERCOLATION_H
#define PERCOLATION_H

#include "lattice.h"

void percolation_seed(unsigned int seed);
void percolation_generate_site(Lattice *lat, double p);
int percolation_count_occupied(const Lattice *lat);

#endif