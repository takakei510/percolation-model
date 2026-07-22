#ifndef COORDINATE_HASH_SET_H
#define COORDINATE_HASH_SET_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    int32_t *x_keys;
    int32_t *y_keys;
    int32_t *z_keys;
    uint32_t *stamps;
    size_t capacity;
    size_t size;
    size_t max_items;
    double max_load_factor;
    uint32_t generation;
    int dim;
} CoordinateHashSet;

int coordinate_hash_set_init(CoordinateHashSet *set, int dim, size_t max_items, double max_load_factor);
int coordinate_hash_set_contains(const CoordinateHashSet *set, int x, int y, int z);
int coordinate_hash_set_insert(CoordinateHashSet *set, int x, int y, int z);
void coordinate_hash_set_clear(CoordinateHashSet *set);
void coordinate_hash_set_destroy(CoordinateHashSet *set);

#endif