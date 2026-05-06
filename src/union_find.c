#include <stdlib.h>

#include "union_find.h"

void uf_init(UnionFind *uf, int n)
{
    uf->n = n;

    uf->n_clusters = 0;
    uf->size_count = calloc(n + 1, sizeof(int));

    uf->parent = malloc(sizeof(int) * n);
    uf->size = malloc(sizeof(int) * n);
    uf->active = malloc(sizeof(int) * n);

    for (int i = 0; i < n; i++)
    {
        uf->parent[i] = i;
        uf->size[i] = 1;
        uf->active[i] = 0;
    }
}

void uf_free(UnionFind *uf)
{
    free(uf->parent);
    free(uf->size);
    free(uf->active);
    free(uf->size_count);
}

int uf_find(UnionFind *uf, int x)
{
    if (uf->parent[x] != x)
    {
        uf->parent[x] = uf_find(uf, uf->parent[x]);
    }

    return uf->parent[x];
}

void uf_union(UnionFind *uf, int a, int b)
{
    if (!uf->active[a] || !uf->active[b])
    {
        return;
    }

    int root_a = uf_find(uf, a);
    int root_b = uf_find(uf, b);

    if (root_a == root_b)
    {
        return;
    }

    if (uf->size[root_a] < uf->size[root_b])
    {
        int tmp = root_a;
        root_a = root_b;
        root_b = tmp;
    }

    int size_a = uf->size[root_a];
    int size_b = uf->size[root_b];
    int merged_size = size_a + size_b;

    uf->size_count[size_a]--;
    uf->size_count[size_b]--;

    uf->parent[root_b] = root_a;
    uf->size[root_a] = merged_size;
    uf->size[root_b] = 0;

    uf->size_count[merged_size]++;
    uf->n_clusters--;
}

void uf_activate(UnionFind *uf, int x)
{
    if (uf->active[x])
    {
        return;
    }

    uf->active[x] = 1;
    uf->parent[x] = x;
    uf->size[x] = 1;

    uf->n_clusters++;
    uf->size_count[1]++;
}

void uf_get_largest_second(const UnionFind *uf, int *largest, int *second)
{
    *largest = 0;
    *second = 0;

    for (int s = uf->n; s >= 1; s--)
    {
        int count = uf->size_count[s];

        if (count <= 0)
        {
            continue;
        }

        if (*largest == 0)
        {
            *largest = s;

            if (count >= 2)
            {
                *second = s;
                return;
            }
        }
        else
        {
            *second = s;
            return;
        }
    }
}