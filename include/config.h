#ifndef CONFIG_H
#define CONFIG_H

typedef struct {
    char mode[32];

    int dim;
    int L;
    int L_provided;
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

    int seed_provided;
    char seed_str[128];
    int seed_offset_provided;
    char seed_offset_str[128];
    unsigned int resolved_seed;
    int resolved_seed_set;

    //random_walk
    char walk_type[64];      // rw / saw
    char walk_algorithm[32]; // kinetic / rosenbluth / perm
    int n_steps;
    int n_tours;
    char tour_checkpoint_mode[32]; // none / log10
    int tour_checkpoint_start;
    char start[32];          // center
    char boundary[32];       // free / periodic
    char spatial_backend[32]; // dense / hash
    double hash_max_load_factor;
    int save_trajectory;
    int save_trajectory_trials;
    char trajectory_output[256];
    int save_msd_distribution;
    char msd_sample_mode[32]; // exact / reservoir / none
    int msd_reservoir_size;
    int sampling_seed_provided;
    char sampling_seed_str[128];
    unsigned long long resolved_sampling_seed;
    int resolved_sampling_seed_set;
    double perm_c_minus;
    double perm_c_plus;
    int perm_min_tours_for_threshold;
    char perm_threshold_scheme[32];
    char msd_distribution_steps[256];
    int *msd_distribution_step_values;
    int msd_distribution_step_count;

    int save_lifetime_checkpoints;
    char lifetime_checkpoint_trials[256];
    int *lifetime_checkpoint_trial_values;
    int lifetime_checkpoint_trial_count;
    
} Config;

int config_load(const char *filename, Config *cfg);

#endif