#ifndef CONFIG_H
#define CONFIG_H

typedef struct {
    int dim;
    int L;
    double p;
    int save_cluster_sizes;
    int save_top_coords;
} Config;

int config_load(const char *filename, Config *cfg);

#endif