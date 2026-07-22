#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "config.h"
#include "percolation.h"
#include "simulation_runner.h"

static int parse_seed_expression(const char *expr, int L, unsigned int *out_seed) {
    if (expr == NULL || expr[0] == '\0') {
        return 0;
    }

    const char *p = expr;
    long result = 0;
    int sign = 1;
    int used = 0;

    while (*p) {
        while (*p && isspace((unsigned char)*p)) {
            p++;
        }

        if (*p == '+') {
            sign = 1;
            p++;
            continue;
        }

        if (*p == '-') {
            sign = -1;
            p++;
            continue;
        }

        if (*p == 'L' || *p == 'l') {
            result += sign * (long)L;
            used = 1;
            p++;
            continue;
        }

        if (isdigit((unsigned char)*p)) {
            char *endptr;
            long value = strtol(p, &endptr, 10);
            if (endptr == p) {
                return 0;
            }
            result += sign * value;
            used = 1;
            p = endptr;
            continue;
        }

        return 0;
    }

    if (!used) {
        return 0;
    }

    *out_seed = (unsigned int)result;
    return 1;
}

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

    unsigned int base_seed = (unsigned int)time(NULL);
    unsigned int seed = base_seed;

    int seed_L = (cfg.L > 0) ? cfg.L : 0;

    if (cfg.seed_provided) {
        unsigned int parsed_seed;
        if (!parse_seed_expression(cfg.seed_str, seed_L, &parsed_seed)) {
            fprintf(stderr, "Invalid seed expression: %s\n", cfg.seed_str);
            return 1;
        }
        seed = parsed_seed;
    }

    if (cfg.seed_offset_provided) {
        unsigned int offset;
        if (!parse_seed_expression(cfg.seed_offset_str, seed_L, &offset)) {
            fprintf(stderr, "Invalid seed_offset expression: %s\n", cfg.seed_offset_str);
            return 1;
        }
        seed += offset;
    }

    cfg.resolved_seed = seed;
    cfg.resolved_seed_set = 1;

    percolation_seed(seed);
    printf("[RNG]\n");
    if (cfg.seed_provided) {
        printf("seed = %s\n", cfg.seed_str);
    } else {
        printf("seed = time(NULL) = %u\n", base_seed);
    }
    if (cfg.seed_offset_provided) {
        printf("seed_offset = %s\n", cfg.seed_offset_str);
    }
    printf("actual_seed = %u\n", seed);

    int ok = run_simulation(&cfg);

    return ok ? 0 : 1;
}