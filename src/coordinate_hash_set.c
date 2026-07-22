#include "coordinate_hash_set.h"

#include <limits.h>
#include <stdlib.h>
#include <string.h>

static uint64_t splitmix64(uint64_t value)
{
    value += 0x9e3779b97f4a7c15ULL;
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}

static size_t next_power_of_two(size_t value)
{
    if (value <= 1) {
        return 1;
    }

    value--;
    for (size_t shift = 1; shift < sizeof(size_t) * CHAR_BIT; shift <<= 1) {
        value |= value >> shift;
    }
    return value + 1;
}

static uint64_t hash_coordinates(int dim, int x, int y, int z)
{
    uint64_t key = 0x243f6a8885a308d3ULL;
    key ^= splitmix64((uint64_t)(uint32_t)x ^ 0x9e3779b9u);
    key = splitmix64(key);
    key ^= splitmix64(((uint64_t)(uint32_t)y << 1) ^ 0xbf58476du);
    key = splitmix64(key);
    key ^= splitmix64(((uint64_t)(uint32_t)z << 2) ^ 0x94d049bbu);
    key ^= splitmix64((uint64_t)(unsigned int)dim * 0x632be59bd9b4e019ULL);
    return splitmix64(key);
}

static int coordinates_match(const CoordinateHashSet *set, size_t index, int x, int y, int z)
{
    return set->stamps[index] == set->generation &&
           set->x_keys[index] == x &&
           set->y_keys[index] == y &&
           set->z_keys[index] == z;
}

int coordinate_hash_set_init(CoordinateHashSet *set, int dim, size_t max_items, double max_load_factor)
{
    if (!set || (dim != 2 && dim != 3) || max_items == 0 || !(max_load_factor > 0.0) || max_load_factor >= 1.0) {
        return 0;
    }

    size_t required = (size_t)((double)max_items / max_load_factor + 0.999999999999);
    if (required < 8) {
        required = 8;
    }

    size_t capacity = next_power_of_two(required);
    if (capacity == 0) {
        return 0;
    }

    set->x_keys = calloc(capacity, sizeof(int32_t));
    set->y_keys = calloc(capacity, sizeof(int32_t));
    set->z_keys = calloc(capacity, sizeof(int32_t));
    set->stamps = calloc(capacity, sizeof(uint32_t));
    if (!set->x_keys || !set->y_keys || !set->z_keys || !set->stamps) {
        free(set->x_keys);
        free(set->y_keys);
        free(set->z_keys);
        free(set->stamps);
        memset(set, 0, sizeof(*set));
        return 0;
    }

    set->capacity = capacity;
    set->size = 0;
    set->max_items = max_items;
    set->max_load_factor = max_load_factor;
    set->generation = 1;
    set->dim = dim;
    return 1;
}

int coordinate_hash_set_contains(const CoordinateHashSet *set, int x, int y, int z)
{
    if (!set || !set->stamps || set->capacity == 0) {
        return 0;
    }

    uint64_t hash = hash_coordinates(set->dim, x, y, z);
    size_t mask = set->capacity - 1;
    size_t index = (size_t)hash & mask;

    for (size_t probe = 0; probe < set->capacity; probe++) {
        if (set->stamps[index] != set->generation) {
            return 0;
        }
        if (coordinates_match(set, index, x, y, z)) {
            return 1;
        }
        index = (index + 1) & mask;
    }

    return 0;
}

int coordinate_hash_set_insert(CoordinateHashSet *set, int x, int y, int z)
{
    if (!set || !set->stamps || set->capacity == 0) {
        return -1;
    }

    if (set->size >= set->max_items) {
        return -1;
    }

    uint64_t hash = hash_coordinates(set->dim, x, y, z);
    size_t mask = set->capacity - 1;
    size_t index = (size_t)hash & mask;

    for (size_t probe = 0; probe < set->capacity; probe++) {
        if (set->stamps[index] != set->generation) {
            set->x_keys[index] = (int32_t)x;
            set->y_keys[index] = (int32_t)y;
            set->z_keys[index] = (int32_t)z;
            set->stamps[index] = set->generation;
            set->size++;
            return 1;
        }
        if (coordinates_match(set, index, x, y, z)) {
            return 0;
        }
        index = (index + 1) & mask;
    }

    return -1;
}

void coordinate_hash_set_clear(CoordinateHashSet *set)
{
    if (!set || !set->stamps || set->capacity == 0) {
        return;
    }

    if (set->generation == UINT32_MAX) {
        memset(set->stamps, 0, set->capacity * sizeof(uint32_t));
        set->generation = 1;
    } else {
        set->generation++;
    }

    set->size = 0;
}

void coordinate_hash_set_destroy(CoordinateHashSet *set)
{
    if (!set) {
        return;
    }

    free(set->x_keys);
    free(set->y_keys);
    free(set->z_keys);
    free(set->stamps);
    memset(set, 0, sizeof(*set));
}