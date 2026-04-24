#ifndef SIMULATION_H
#define SIMULATION_H

#include "config.h"

typedef struct {
    double mean_occupied;
    double mean_clusters;
    double mean_largest;
    double mean_second;

    double std_occupied;
    double std_clusters;
    double std_largest;
    double std_second;
} SweepStats;

int run_single_simulation(const Config *cfg);
int run_sweep_simulation(const Config *cfg);

int run_size_sweep_simulation(const Config *cfg);

#endif