#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "io.h"

int io_save_summary_csv_single(const char *filename,
                               const Lattice *lat,
                               const ClusterSet *cs,
                               double p)
{
    FILE *fp = fopen(filename, "w");
    if (!fp)
        return 0;

    fprintf(fp, "p,n_sites,n_occupied,n_clusters,largest,second\n");

    int largest = (cs->n_clusters > 0) ? cs->clusters[0].size : 0;
    int second = (cs->n_clusters > 1) ? cs->clusters[1].size : 0;

    fprintf(fp, "%f,%d,%d,%d,%d,%d\n",
            p,
            lat->n_sites,
            lat->n_occupied,
            cs->n_clusters,
            largest,
            second);

    fclose(fp);
    return 1;
}

int io_append_summary_csv_mean(const char *filename,
                               double p,
                               int dim,
                               int L,
                               int n_sites,
                               int n_trials,
                               double mean_occupied,
                               double mean_clusters,
                               double mean_largest,
                               double mean_second,
                               double std_occupied,
                               double std_clusters,
                               double std_largest,
                               double std_second)
{
    FILE *check = fopen(filename, "r");
    int need_header = (check == NULL);

    if (check != NULL)
    {
        fclose(check);
    }

    FILE *fp = fopen(filename, "a");
    if (!fp)
        return 0;

    if (need_header)
    {
        fprintf(fp,
                "p,dim,L,n_sites,n_trials,"
                "mean_occupied,mean_clusters,mean_largest,mean_second,"
                "std_occupied,std_clusters,std_largest,std_second\n");
    }

    fprintf(fp,
            "%f,%d,%d,%d,%d,%f,%f,%f,%f,%f,%f,%f,%f\n",
            p,
            dim,
            L,
            n_sites,
            n_trials,
            mean_occupied,
            mean_clusters,
            mean_largest,
            mean_second,
            std_occupied,
            std_clusters,
            std_largest,
            std_second);

    fclose(fp);
    return 1;
}

int io_save_cluster_sizes_csv(const char *filename, const ClusterSet *cs)
{
    FILE *fp = fopen(filename, "w");
    if (!fp)
        return 0;

    fprintf(fp, "cluster_rank,cluster_id,size\n");

    for (int i = 0; i < cs->n_clusters; i++)
    {
        fprintf(fp, "%d,%d,%d\n",
                i + 1,
                cs->clusters[i].id,
                cs->clusters[i].size);
    }

    fclose(fp);
    return 1;
}

int io_save_top_clusters_coords_csv(const char *filename,
                                    const Lattice *lat,
                                    const ClusterSet *cs,
                                    int top_k)
{
    FILE *fp = fopen(filename, "w");
    if (!fp)
        return 0;

    if (lat->dim == 2)
    {
        fprintf(fp, "site_index,x,y,cluster_rank\n");
    }
    else
    {
        fprintf(fp, "site_index,x,y,z,cluster_rank\n");
    }

    for (int k = 0; k < top_k && k < cs->n_clusters; k++)
    {
        Cluster *cluster = &cs->clusters[k];

        for (int j = 0; j < cluster->size; j++)
        {
            int site_index = cluster->sites[j];

            int coord[3] = {0, 0, 0};
            lattice_index_to_coord(site_index, coord, lat->dim, lat->L);

            if (lat->dim == 2)
            {
                fprintf(fp, "%d,%d,%d,%d\n",
                        site_index,
                        coord[0],
                        coord[1],
                        k + 1);
            }
            else
            {
                fprintf(fp, "%d,%d,%d,%d,%d\n",
                        site_index,
                        coord[0],
                        coord[1],
                        coord[2],
                        k + 1);
            }
        }
    }

    fclose(fp);
    return 1;
}

int io_save_selected_clusters_coords_csv(const char *filename,
                                         const Lattice *lat,
                                         const ClusterSet *cs,
                                         const char *view_mode)
{
    int top_k = 1;

    if (strcmp(view_mode, "top2") == 0)
        top_k = 2;
    else if (strcmp(view_mode, "top3") == 0)
        top_k = 3;

    return io_save_top_clusters_coords_csv(filename, lat, cs, top_k);
}