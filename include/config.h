#ifndef CONFIG_H
#define CONFIG_H

typedef struct {
    char mode[32];
    int dim;
    int L;
    int n_trials;

    double p;

    double p_start;
    double p_end;
    double dp;

    int save_cluster_sizes;
    int save_top_coords;
} Config;

int config_load(const char *filename, Config *cfg);

#endif