#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "config.h"

static void trim_newline(char *str) {
    str[strcspn(str, "\r\n")] = '\0';
}

int config_load(const char *filename, Config *cfg) {
    FILE *fp = fopen(filename, "r");
    if (fp == NULL) {
        fprintf(stderr, "Failed to open config file: %s\n", filename);
        return 0;
    }

    char line[256];

    while (fgets(line, sizeof(line), fp)) {
        trim_newline(line);

        char key[128], value[128];
        if (sscanf(line, "%127[^=]=%127s", key, value) != 2) {
            continue;
        }

        if (strcmp(key, "mode") == 0) {
            strncpy(cfg->mode, value, sizeof(cfg->mode) - 1);
            cfg->mode[sizeof(cfg->mode) - 1] = '\0';
        } else if (strcmp(key, "dim") == 0) {
            cfg->dim = atoi(value);
        } else if (strcmp(key, "L") == 0) {
            cfg->L = atoi(value);
        } else if (strcmp(key, "p") == 0) {
            cfg->p = atof(value);
        } else if (strcmp(key, "p_start") == 0) {
            cfg->p_start = atof(value);
        } else if (strcmp(key, "p_end") == 0) {
            cfg->p_end = atof(value);
        } else if (strcmp(key, "dp") == 0) {
            cfg->dp = atof(value);
        } else if (strcmp(key, "save_cluster_sizes") == 0) {
            cfg->save_cluster_sizes = atoi(value);
        } else if (strcmp(key, "save_top_coords") == 0) {
            cfg->save_top_coords = atoi(value);
        }
    }

    fclose(fp);
    return 1;
}