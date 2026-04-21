#include <stdio.h>
#include <string.h>
#include <time.h>
#include "config.h"
#include "percolation.h"
#include "simulation.h"

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <config_file>\n", argv[0]);
        return 1;
    }

    Config cfg = {0};

    if (!config_load(argv[1], &cfg)) {
        return 1;
    }

    percolation_seed((unsigned int)time(NULL));

    if (strcmp(cfg.mode, "single") == 0) {
        return run_single_simulation(&cfg) ? 0 : 1;
    } else if (strcmp(cfg.mode, "sweep") == 0) {
        return run_sweep_simulation(&cfg) ? 0 : 1;
    } else {
        fprintf(stderr, "Unknown mode: %s\n", cfg.mode);
        fprintf(stderr, "Use mode=single or mode=sweep in config file.\n");
        return 1;
    }
}