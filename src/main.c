#include <stdio.h>
#include <time.h>

#include "config.h"
#include "percolation.h"
#include "simulation_runner.h"

int main(int argc, char *argv[])
{
    if (argc < 2)
    {
        fprintf(stderr, "Usage: %s <config_file>\n", argv[0]);
        return 1;
    }

    Config cfg = {0};

    if (!config_load(argv[1], &cfg))
    {
        return 1;
    }

    percolation_seed((unsigned int)time(NULL));

    int ok = run_simulation(&cfg);

    return ok ? 0 : 1;
}