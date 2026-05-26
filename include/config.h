#ifndef CONFIG_H
#define CONFIG_H

typedef struct {
    char mode[32];

    int dim;
    int L;
    char cluster_method[32];
    
    double p;

    double p_start;
    double p_end;
    double dp;

    int n_trials;
    
    int L_start;
    int L_max;
    double L_multiplier;

    int save_cluster_sizes;
    int save_top_coords;

    char cluster_view_mode[32];
    char output[256];

    //random_walk
    char walk_type[16];      // rw / saw
    int n_steps;
    char start[32];          // center
    char boundary[32];       // free / periodic
    int save_trajectory;
    int save_trajectory_trials;
    char trajectory_output[256];
    
} Config;

int config_load(const char *filename, Config *cfg);

#endif