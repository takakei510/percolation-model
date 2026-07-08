#include <ctype.h>
#include <math.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "config.h"

static void trim_newline(char *str) {
    str[strcspn(str, "\r\n")] = '\0';
}

static void trim_whitespace(char *str) {
    char *start = str;
    while (*start && isspace((unsigned char)*start)) {
        start++;
    }

    char *end = start + strlen(start);
    while (end > start && isspace((unsigned char)*(end - 1))) {
        end--;
    }

    size_t len = end - start;
    memmove(str, start, len);
    str[len] = '\0';
}

static void free_msd_distribution_steps(Config *cfg)
{
    free(cfg->msd_distribution_step_values);
    cfg->msd_distribution_step_values = NULL;
    cfg->msd_distribution_step_count = 0;
}

static void free_lifetime_checkpoint_trials(Config *cfg)
{
    free(cfg->lifetime_checkpoint_trial_values);
    cfg->lifetime_checkpoint_trial_values = NULL;
    cfg->lifetime_checkpoint_trial_count = 0;
}

static int compare_ints(const void *a, const void *b)
{
    int lhs = *(const int *)a;
    int rhs = *(const int *)b;
    if (lhs < rhs) return -1;
    if (lhs > rhs) return 1;
    return 0;
}

static int append_step(int **steps, int *count, int *capacity, int value)
{
    if (value <= 0) {
        return 1;
    }

    if (*count == *capacity) {
        int new_capacity = (*capacity == 0) ? 8 : (*capacity * 2);
        int *resized = realloc(*steps, (size_t)new_capacity * sizeof(int));
        if (!resized) {
            return 0;
        }
        *steps = resized;
        *capacity = new_capacity;
    }

    (*steps)[(*count)++] = value;
    return 1;
}

static int parse_step_token(const char *token, int n_steps, int **steps, int *count, int *capacity)
{
    const char *colon = strchr(token, ':');
    if (colon) {
        char start_buf[64];
        char end_buf[64];
        size_t start_len = (size_t)(colon - token);
        size_t end_len = strlen(colon + 1);

        if (start_len == 0 || end_len == 0 || start_len >= sizeof(start_buf) || end_len >= sizeof(end_buf)) {
            return 0;
        }

        memcpy(start_buf, token, start_len);
        start_buf[start_len] = '\0';
        memcpy(end_buf, colon + 1, end_len);
        end_buf[end_len] = '\0';

        char *endptr = NULL;
        long start = strtol(start_buf, &endptr, 10);
        if (endptr == start_buf || *endptr != '\0') {
            return 0;
        }

        endptr = NULL;
        long end = strtol(end_buf, &endptr, 10);
        if (endptr == end_buf || *endptr != '\0') {
            return 0;
        }

        if (start > end) {
            return 1;
        }

        for (long step = start; step <= end; step++) {
            if (step > n_steps) {
                break;
            }
            if (!append_step(steps, count, capacity, (int)step)) {
                return 0;
            }
        }
        return 1;
    }

    char *endptr = NULL;
    long value = strtol(token, &endptr, 10);
    if (endptr == token || *endptr != '\0') {
        return 0;
    }
    if (value > INT_MAX) {
        return 0;
    }
    if (value > n_steps) {
        return 1;
    }

    return append_step(steps, count, capacity, (int)value);
}

static int parse_msd_distribution_steps(const char *value, int n_steps, int **steps_out, int *count_out)
{
    *steps_out = NULL;
    *count_out = 0;

    if (value == NULL || value[0] == '\0') {
        return 1;
    }

    char buffer[256];
    strncpy(buffer, value, sizeof(buffer) - 1);
    buffer[sizeof(buffer) - 1] = '\0';

    int *steps = NULL;
    int count = 0;
    int capacity = 0;

    char *token = strtok(buffer, ",");
    while (token) {
        trim_whitespace(token);
        if (*token == '\0') {
            free(steps);
            return 0;
        }

        if (!parse_step_token(token, n_steps, &steps, &count, &capacity)) {
            free(steps);
            return 0;
        }
        token = strtok(NULL, ",");
    }

    if (count == 0) {
        free(steps);
        *steps_out = NULL;
        *count_out = 0;
        return 1;
    }

    qsort(steps, (size_t)count, sizeof(int), compare_ints);

    int unique_count = 1;
    for (int i = 1; i < count; i++) {
        if (steps[i] != steps[unique_count - 1]) {
            steps[unique_count++] = steps[i];
        }
    }

    int *shrunk = realloc(steps, (size_t)unique_count * sizeof(int));
    if (shrunk) {
        steps = shrunk;
    }

    *steps_out = steps;
    *count_out = unique_count;
    return 1;
}

static int parse_lifetime_checkpoint_token(const char *token, int **steps, int *count, int *capacity)
{
    const char *first_colon = strchr(token, ':');
    if (first_colon == NULL) {
        char *endptr = NULL;
        double value = strtod(token, &endptr);
        if (endptr == token || *endptr != '\0' || value <= 0.0) {
            return 0;
        }

        long long step = (long long)(value + 0.5);
        if (step <= 0 || step > INT_MAX) {
            return 1;
        }

        return append_step(steps, count, capacity, (int)step);
    }

    const char *second_colon = strchr(first_colon + 1, ':');
    if (second_colon == NULL) {
        return 0;
    }

    char start_buf[64];
    char end_buf[64];
    char mode_buf[64];

    size_t start_len = (size_t)(first_colon - token);
    size_t end_len = (size_t)(second_colon - (first_colon + 1));
    size_t mode_len = strlen(second_colon + 1);

    if (start_len == 0 || end_len == 0 || mode_len == 0 ||
        start_len >= sizeof(start_buf) || end_len >= sizeof(end_buf) || mode_len >= sizeof(mode_buf)) {
        return 0;
    }

    memcpy(start_buf, token, start_len);
    start_buf[start_len] = '\0';
    memcpy(end_buf, first_colon + 1, end_len);
    end_buf[end_len] = '\0';
    memcpy(mode_buf, second_colon + 1, mode_len);
    mode_buf[mode_len] = '\0';

    if (strcmp(mode_buf, "log10") != 0) {
        return 0;
    }

    char *endptr = NULL;
    double start = strtod(start_buf, &endptr);
    if (endptr == start_buf || *endptr != '\0' || start <= 0.0) {
        return 0;
    }

    endptr = NULL;
    double end = strtod(end_buf, &endptr);
    if (endptr == end_buf || *endptr != '\0' || end <= 0.0) {
        return 0;
    }

    int start_exp = (int)ceil(log10(start));
    int end_exp = (int)floor(log10(end));
    if (start_exp > end_exp) {
        return 1;
    }

    for (int exp = start_exp; exp <= end_exp; exp++) {
        double v = pow(10.0, (double)exp);
        long long step = (long long)(v + 0.5);
        if (step <= 0 || step > INT_MAX) {
            continue;
        }
        if (!append_step(steps, count, capacity, (int)step)) {
            return 0;
        }
    }

    return 1;
}

static int parse_lifetime_checkpoint_trials(const char *value, int **steps_out, int *count_out)
{
    *steps_out = NULL;
    *count_out = 0;

    if (value == NULL || value[0] == '\0') {
        return 1;
    }

    char buffer[256];
    strncpy(buffer, value, sizeof(buffer) - 1);
    buffer[sizeof(buffer) - 1] = '\0';

    int *steps = NULL;
    int count = 0;
    int capacity = 0;

    char *token = strtok(buffer, ",");
    while (token) {
        trim_whitespace(token);
        if (*token == '\0') {
            free(steps);
            return 0;
        }
        if (!parse_lifetime_checkpoint_token(token, &steps, &count, &capacity)) {
            free(steps);
            return 0;
        }
        token = strtok(NULL, ",");
    }

    if (count == 0) {
        free(steps);
        *steps_out = NULL;
        *count_out = 0;
        return 1;
    }

    qsort(steps, (size_t)count, sizeof(int), compare_ints);

    int unique_count = 1;
    for (int i = 1; i < count; i++) {
        if (steps[i] != steps[unique_count - 1]) {
            steps[unique_count++] = steps[i];
        }
    }

    int *shrunk = realloc(steps, (size_t)unique_count * sizeof(int));
    if (shrunk) {
        steps = shrunk;
    }

    *steps_out = steps;
    *count_out = unique_count;
    return 1;
}

int config_load(const char *filename, Config *cfg) {
    cfg->n_trials = 1;
    strncpy(cfg->cluster_view_mode, "largest_only", sizeof(cfg->cluster_view_mode) - 1);
    cfg->cluster_view_mode[sizeof(cfg->cluster_view_mode) - 1] = '\0';
    strcpy(cfg->cluster_method, "bfs");

    cfg->seed_provided = 0;
    cfg->seed_str[0] = '\0';
    cfg->seed_offset_provided = 0;
    cfg->seed_offset_str[0] = '\0';

    //ramdom_walk
    strcpy(cfg->walk_type, "rw");
    strcpy(cfg->start, "center");
    strcpy(cfg->boundary, "free");
    cfg->n_steps = 1000;
    cfg->save_trajectory = 0;
    cfg->save_trajectory_trials = 1;
    cfg->save_msd_distribution = 0;
    cfg->save_lifetime_checkpoints = 0;
    cfg->msd_distribution_steps[0] = '\0';
    cfg->msd_distribution_step_values = NULL;
    cfg->msd_distribution_step_count = 0;
    cfg->lifetime_checkpoint_trials[0] = '\0';
    cfg->lifetime_checkpoint_trial_values = NULL;
    cfg->lifetime_checkpoint_trial_count = 0;

    FILE *fp = fopen(filename, "r");
    if (fp == NULL) {
        fprintf(stderr, "Failed to open config file: %s\n", filename);
        return 0;
    }

    char line[256];

    while (fgets(line, sizeof(line), fp)) {
        trim_newline(line);

        char key[128], value[128];
        if (sscanf(line, "%127[^=]=%127[^\"]", key, value) != 2) {
            continue;
        }

        trim_whitespace(key);
        trim_whitespace(value);

        if (strcmp(key, "mode") == 0) {
            strncpy(cfg->mode, value, sizeof(cfg->mode) - 1);
            cfg->mode[sizeof(cfg->mode) - 1] = '\0';
        } else if (strcmp(key, "dim") == 0) {
            cfg->dim = atoi(value);
        } else if (strcmp(key, "L") == 0) {
            cfg->L = atoi(value);
        } else if (strcmp(key, "seed") == 0) {
            strncpy(cfg->seed_str, value, sizeof(cfg->seed_str) - 1);
            cfg->seed_str[sizeof(cfg->seed_str) - 1] = '\0';
            cfg->seed_provided = 1;
        } else if (strcmp(key, "seed_offset") == 0) {
            strncpy(cfg->seed_offset_str, value, sizeof(cfg->seed_offset_str) - 1);
            cfg->seed_offset_str[sizeof(cfg->seed_offset_str) - 1] = '\0';
            cfg->seed_offset_provided = 1;
        } else if (strcmp(key, "cluster_method") == 0) {
            sscanf(value, "%31s", cfg->cluster_method);
        } else if (strcmp(key, "p") == 0) {
            cfg->p = atof(value);
        } else if (strcmp(key, "p_start") == 0) {
            cfg->p_start = atof(value);
        } else if (strcmp(key, "p_end") == 0) {
            cfg->p_end = atof(value);
        } else if (strcmp(key, "dp") == 0) {
            cfg->dp = atof(value);
        } else if (strcmp(key, "n_trials") == 0) {
            cfg->n_trials = atoi(value);
        } else if (strcmp(key, "save_cluster_sizes") == 0) {
            cfg->save_cluster_sizes = atoi(value);
        } else if (strcmp(key, "save_top_coords") == 0) {
            cfg->save_top_coords = atoi(value);
        } else if (strcmp(key, "cluster_view_mode") == 0) {
            strncpy(cfg->cluster_view_mode, value, sizeof(cfg->cluster_view_mode) - 1);
            cfg->cluster_view_mode[sizeof(cfg->cluster_view_mode) - 1] = '\0';
        } else if (strcmp(key, "L_start") == 0) {
            cfg->L_start = atoi(value);
        } else if (strcmp(key, "L_max") == 0) {
            cfg->L_max = atoi(value);
        } else if (strcmp(key, "L_multiplier") == 0) {
            cfg->L_multiplier = atof(value);
        } else if (strcmp(key, "output") == 0) {
            sscanf(value, "%255s", cfg->output);
        } else if (strcmp(key, "walk_type") == 0) {
            sscanf(value, "%63s", cfg->walk_type);
        } else if (strcmp(key, "n_steps") == 0) {
            cfg->n_steps = atoi(value);
        } else if (strcmp(key, "start") == 0) {
            sscanf(value, "%31s", cfg->start);
        } else if (strcmp(key, "boundary") == 0) {
            sscanf(value, "%31s", cfg->boundary);
        } else if (strcmp(key, "save_trajectory") == 0) {
            cfg->save_trajectory = atoi(value);
        } else if (strcmp(key, "save_trajectory_trials") == 0) {
            cfg->save_trajectory_trials = atoi(value);
        } else if (strcmp(key, "trajectory_output") == 0) {
            sscanf(value, "%255s", cfg->trajectory_output);
        } else if (strcmp(key, "save_msd_distribution") == 0) {
            cfg->save_msd_distribution = atoi(value);
        } else if (strcmp(key, "msd_distribution_steps") == 0) {
            sscanf(value, "%255s", cfg->msd_distribution_steps);
        } else if (strcmp(key, "save_lifetime_checkpoints") == 0) {
            cfg->save_lifetime_checkpoints = atoi(value);
        } else if (strcmp(key, "lifetime_checkpoint_trials") == 0) {
            sscanf(value, "%255s", cfg->lifetime_checkpoint_trials);
        }
    }

    fclose(fp);

    if (cfg->save_msd_distribution) {
        if (!parse_msd_distribution_steps(cfg->msd_distribution_steps, cfg->n_steps, &cfg->msd_distribution_step_values, &cfg->msd_distribution_step_count)) {
            fprintf(stderr, "Failed to parse msd_distribution_steps: %s\n", cfg->msd_distribution_steps);
            free_msd_distribution_steps(cfg);
            return 0;
        }
        if (cfg->msd_distribution_step_count == 0) {
            fprintf(stderr, "save_msd_distribution=1 requires at least one valid msd_distribution_steps entry\n");
            free_msd_distribution_steps(cfg);
            return 0;
        }
    }

    if (cfg->save_lifetime_checkpoints) {
        if (!parse_lifetime_checkpoint_trials(cfg->lifetime_checkpoint_trials, &cfg->lifetime_checkpoint_trial_values, &cfg->lifetime_checkpoint_trial_count)) {
            fprintf(stderr, "Failed to parse lifetime_checkpoint_trials: %s\n", cfg->lifetime_checkpoint_trials);
            free_lifetime_checkpoint_trials(cfg);
            free_msd_distribution_steps(cfg);
            return 0;
        }
        if (cfg->lifetime_checkpoint_trial_count == 0) {
            fprintf(stderr, "save_lifetime_checkpoints=1 requires at least one valid lifetime_checkpoint_trials entry\n");
            free_lifetime_checkpoint_trials(cfg);
            free_msd_distribution_steps(cfg);
            return 0;
        }
    }

    return 1;
}