#ifndef UNION_FIND_H
#define UNION_FIND_H

typedef struct
{
    int n;

    int *parent;
    int *size;
    int *active;

    int n_clusters;
    int *size_count;

} UnionFind;

void uf_init(UnionFind *uf, int n);

void uf_free(UnionFind *uf);

int uf_find(UnionFind *uf, int x);

void uf_union(UnionFind *uf, int a, int b);

void uf_activate(UnionFind *uf, int x);

void uf_get_largest_second(const UnionFind *uf, int *largest, int *second);

#endif