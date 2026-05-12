#include <stdio.h>
#include <string.h>

#include "simulation_runner.h"
#include "simulation.h"

int run_simulation(const Config *cfg)
{
    if (strcmp(cfg->mode, "single") == 0)
    {
        return run_single_simulation(cfg);
    }
    else if (strcmp(cfg->mode, "sweep") == 0)
    {
        return run_sweep_simulation(cfg);
    }
    else if (strcmp(cfg->mode, "size_sweep") == 0)
    {
        return run_size_sweep_simulation(cfg);
    }
    else if (strcmp(cfg->mode, "p_incremental_sweep") == 0)
    {
        return run_p_incremental_sweep_simulation(cfg);
    }

    fprintf(stderr, "Unknown mode: %s\n", cfg->mode);

    return 0;
}