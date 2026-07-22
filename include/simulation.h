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

int run_p_incremental_sweep_simulation(const Config *cfg);


/* 共通関数 */
int compute_n_sites(int dim, int L);

void create_output_dirs(int dim);

SweepStats compute_sweep_stats_for_p(int dim, int L, double p, int n_trials);
SweepStats compute_sweep_stats_for_p_bfs_fast(int dim, int L, double p, int n_trials);

//random_walk
int run_random_walk_simulation(const Config *cfg);
int run_rosenbluth_simulation(const Config *cfg);
int run_perm_simulation(const Config *cfg);

#endif