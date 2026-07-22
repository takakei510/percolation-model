#include <errno.h>
#include <float.h>
#include <math.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>

#include "coordinate_hash_set.h"
#include "config.h"
#include "perm.h"
#include "random_walk.h"

typedef struct {
    unsigned long long state;
} PermRng;

typedef struct {
    unsigned long long *sample_count;
    double *sum_weight;
    double *sum_weight_r2;
    double *sum_weight_squared;
    double *max_weight;
    unsigned long long completed_tours;
    size_t size;
} PermStats;

typedef struct {
    int step;
    int x;
    int y;
    int z;
    long double weight;
    PermRng rng;
    WalkPos *path;
    size_t path_len;
    size_t path_cap;
    CoordinateHashSet visited;
} PermBranch;

typedef struct {
    long double mantissa;
    int exponent;
    int is_zero;
} ScaledPositive;

typedef struct {
    PermBranch **items;
    size_t size;
    size_t capacity;
    size_t max_size_observed;
} PermBranchStack;

typedef struct {
    unsigned long long clone_count;
    long double clone_time;
    unsigned long long copied_path_elements;
    unsigned long long copied_hash_capacity;
} PermCloneStats;

typedef struct {
    int tour;
    int max_reached_step;
    unsigned long long generated_branches;
    unsigned long long pruned_count;
    unsigned long long enriched_count;
    unsigned long long max_stack_size;
    unsigned long long tour_total_nodes;
    unsigned long long tour_clone_count;
    long double clone_time;
    unsigned long long copied_path_elements;
    unsigned long long copied_hash_capacity;
} PermTourDiagnostics;

typedef struct {
    unsigned long long sample_count;
    unsigned long long nonzero_tours;
    ScaledPositive branch_weight_sum;
    ScaledPositive branch_weight_r2_sum;
    ScaledPositive branch_weight_squared_sum;
    ScaledPositive tour_weight_sum;
    ScaledPositive tour_weight_r2_sum;
    ScaledPositive tour_weight_squared_sum;
    long double max_weight;
    long double lower_threshold;
    long double upper_threshold;
    int threshold_enabled;
} StepStats;

typedef struct {
    int enabled;
    size_t tour_count;
    size_t step_count;
    long double *tour_weight_sum;
    long double *tour_weight_r2_sum;
    long double *tour_weight_squared_sum;
} TourBuffer;

static uint64_t perm_splitmix64(uint64_t value)
{
    value += 0x9e3779b97f4a7c15ULL;
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}

static unsigned long long perm_rng_next(PermRng *rng)
{
    rng->state = perm_splitmix64(rng->state);
    return rng->state;
}

static unsigned long long perm_rng_bounded(PermRng *rng, unsigned long long bound)
{
    if (bound == 0ULL) {
        return 0ULL;
    }

    unsigned long long threshold = (unsigned long long)(-bound) % bound;
    for (;;) {
        unsigned long long value = perm_rng_next(rng);
        if (value >= threshold) {
            return value % bound;
        }
    }
}

static double now_seconds(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

static int ensure_parent_dir(const char *path)
{
    char buffer[512];

    if (strlen(path) >= sizeof(buffer)) {
        return 0;
    }

    strcpy(buffer, path);
    char *slash = strrchr(buffer, '/');
    if (!slash) {
        return 1;
    }
    *slash = '\0';

    for (char *p = buffer + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0';
            if (mkdir(buffer, 0777) != 0 && errno != EEXIST) {
                return 0;
            }
            *p = '/';
        }
    }

    if (mkdir(buffer, 0777) != 0 && errno != EEXIST) {
        return 0;
    }

    return 1;
}

static void build_sibling_path(char *dst, size_t dst_size, const char *src, const char *filename)
{
    strncpy(dst, src, dst_size - 1);
    dst[dst_size - 1] = '\0';

    char *slash = strrchr(dst, '/');
    if (slash) {
        strcpy(slash + 1, filename);
    } else {
        strncpy(dst, filename, dst_size - 1);
        dst[dst_size - 1] = '\0';
    }
}

static void write_json_string(FILE *fp, const char *value)
{
    fputc('"', fp);
    for (const unsigned char *p = (const unsigned char *)value; p && *p; p++) {
        if (*p == '"' || *p == '\\') {
            fputc('\\', fp);
            fputc(*p, fp);
        } else if (*p == '\n') {
            fputs("\\n", fp);
        } else if (*p == '\r') {
            fputs("\\r", fp);
        } else if (*p == '\t') {
            fputs("\\t", fp);
        } else {
            fputc(*p, fp);
        }
    }
    fputc('"', fp);
}

static void scaled_positive_init(ScaledPositive *value)
{
    value->mantissa = 0.0L;
    value->exponent = 0;
    value->is_zero = 1;
}

static void scaled_positive_add(ScaledPositive *value, long double addend)
{
    if (!(addend > 0.0L) || !isfinite(addend)) {
        return;
    }

    int exponent = 0;
    long double mantissa = frexpl(addend, &exponent);

    if (value->is_zero) {
        value->mantissa = mantissa;
        value->exponent = exponent;
        value->is_zero = 0;
        return;
    }

    if (value->exponent < exponent) {
        long double scaled = ldexpl(value->mantissa, value->exponent - exponent);
        value->mantissa = mantissa + scaled;
        value->exponent = exponent;
    } else {
        long double scaled = ldexpl(mantissa, exponent - value->exponent);
        value->mantissa += scaled;
    }

    if (value->mantissa == 0.0L) {
        value->is_zero = 1;
        value->exponent = 0;
        return;
    }

    int renorm_exponent = 0;
    value->mantissa = frexpl(value->mantissa, &renorm_exponent);
    value->exponent += renorm_exponent;
    value->is_zero = 0;
}

static long double scaled_positive_value(const ScaledPositive *value)
{
    if (!value || value->is_zero) {
        return 0.0L;
    }
    return ldexpl(value->mantissa, value->exponent);
}

static long double scaled_positive_log_value(const ScaledPositive *value)
{
    if (!value || value->is_zero) {
        return -INFINITY;
    }
    return logl(value->mantissa) + (long double)value->exponent * logl(2.0L);
}

static void perm_branch_stack_init(PermBranchStack *stack)
{
    stack->items = NULL;
    stack->size = 0;
    stack->capacity = 0;
    stack->max_size_observed = 0;
}

static int perm_branch_stack_push(PermBranchStack *stack, PermBranch *branch)
{
    if (stack->size == stack->capacity) {
        size_t new_capacity = (stack->capacity == 0) ? 16 : (stack->capacity * 2);
        PermBranch **resized = realloc(stack->items, new_capacity * sizeof(*resized));
        if (!resized) {
            return 0;
        }
        stack->items = resized;
        stack->capacity = new_capacity;
    }

    stack->items[stack->size++] = branch;
    if (stack->size > stack->max_size_observed) {
        stack->max_size_observed = stack->size;
    }
    return 1;
}

static PermBranch *perm_branch_stack_pop(PermBranchStack *stack)
{
    if (stack->size == 0) {
        return NULL;
    }
    return stack->items[--stack->size];
}

static void perm_branch_stack_destroy(PermBranchStack *stack)
{
    free(stack->items);
    stack->items = NULL;
    stack->size = 0;
    stack->capacity = 0;
}

static int tour_buffer_init(TourBuffer *buffer, size_t tour_count, size_t step_count)
{
    memset(buffer, 0, sizeof(*buffer));
    if (tour_count == 0 || step_count == 0) {
        return 1;
    }

    size_t cells = tour_count * step_count;
    const size_t jackknife_cell_limit = 20000000ULL;
    if (cells > jackknife_cell_limit) {
        buffer->enabled = 0;
        return 1;
    }

    buffer->tour_weight_sum = calloc(cells, sizeof(long double));
    buffer->tour_weight_r2_sum = calloc(cells, sizeof(long double));
    buffer->tour_weight_squared_sum = calloc(cells, sizeof(long double));
    if (!buffer->tour_weight_sum || !buffer->tour_weight_r2_sum || !buffer->tour_weight_squared_sum) {
        free(buffer->tour_weight_sum);
        free(buffer->tour_weight_r2_sum);
        free(buffer->tour_weight_squared_sum);
        memset(buffer, 0, sizeof(*buffer));
        return 0;
    }

    buffer->enabled = 1;
    buffer->tour_count = tour_count;
    buffer->step_count = step_count;
    return 1;
}

static void tour_buffer_destroy(TourBuffer *buffer)
{
    free(buffer->tour_weight_sum);
    free(buffer->tour_weight_r2_sum);
    free(buffer->tour_weight_squared_sum);
    memset(buffer, 0, sizeof(*buffer));
}

static inline size_t tour_buffer_index(const TourBuffer *buffer, size_t tour_index, size_t step_index)
{
    return tour_index * buffer->step_count + step_index;
}

static int clone_coordinate_hash_set(CoordinateHashSet *dst, const CoordinateHashSet *src)
{
    memset(dst, 0, sizeof(*dst));

    if (!src || src->capacity == 0) {
        return 0;
    }

    dst->x_keys = malloc(src->capacity * sizeof(int32_t));
    dst->y_keys = malloc(src->capacity * sizeof(int32_t));
    dst->z_keys = malloc(src->capacity * sizeof(int32_t));
    dst->stamps = malloc(src->capacity * sizeof(uint32_t));
    if (!dst->x_keys || !dst->y_keys || !dst->z_keys || !dst->stamps) {
        free(dst->x_keys);
        free(dst->y_keys);
        free(dst->z_keys);
        free(dst->stamps);
        memset(dst, 0, sizeof(*dst));
        return 0;
    }

    memcpy(dst->x_keys, src->x_keys, src->capacity * sizeof(int32_t));
    memcpy(dst->y_keys, src->y_keys, src->capacity * sizeof(int32_t));
    memcpy(dst->z_keys, src->z_keys, src->capacity * sizeof(int32_t));
    memcpy(dst->stamps, src->stamps, src->capacity * sizeof(uint32_t));
    dst->capacity = src->capacity;
    dst->size = src->size;
    dst->max_items = src->max_items;
    dst->max_load_factor = src->max_load_factor;
    dst->generation = src->generation;
    dst->dim = src->dim;
    return 1;
}

static void destroy_branch(PermBranch *branch)
{
    if (!branch) {
        return;
    }

    free(branch->path);
    coordinate_hash_set_destroy(&branch->visited);
    free(branch);
}

static PermBranch *create_root_branch(const Config *cfg, unsigned long long tour_seed)
{
    PermBranch *branch = calloc(1, sizeof(*branch));
    if (!branch) {
        return NULL;
    }

    branch->path_cap = (size_t)cfg->n_steps + 1;
    branch->path = calloc(branch->path_cap, sizeof(WalkPos));
    if (!branch->path) {
        destroy_branch(branch);
        return NULL;
    }

    if (!coordinate_hash_set_init(&branch->visited, 2, (size_t)cfg->n_steps + 1, cfg->hash_max_load_factor)) {
        destroy_branch(branch);
        return NULL;
    }

    branch->step = 0;
    branch->x = 0;
    branch->y = 0;
    branch->z = 0;
    branch->weight = 1.0L;
    branch->rng.state = perm_splitmix64(tour_seed);
    branch->path_len = 1;
    branch->path[0].x = 0;
    branch->path[0].y = 0;
    branch->path[0].z = 0;
    if (coordinate_hash_set_insert(&branch->visited, 0, 0, 0) < 0) {
        destroy_branch(branch);
        return NULL;
    }

    return branch;
}

static PermBranch *clone_branch(const PermBranch *src, unsigned long long branch_salt, PermCloneStats *clone_stats)
{
    PermBranch *branch = calloc(1, sizeof(*branch));
    if (!branch) {
        return NULL;
    }

    branch->path_cap = src->path_cap;
    branch->path_len = src->path_len;
    branch->path = malloc(branch->path_cap * sizeof(WalkPos));
    if (!branch->path) {
        destroy_branch(branch);
        return NULL;
    }
    memcpy(branch->path, src->path, branch->path_len * sizeof(WalkPos));

    if (!clone_coordinate_hash_set(&branch->visited, &src->visited)) {
        destroy_branch(branch);
        return NULL;
    }

    branch->step = src->step;
    branch->x = src->x;
    branch->y = src->y;
    branch->z = src->z;
    branch->weight = src->weight;
    branch->rng.state = perm_splitmix64(src->rng.state ^ branch_salt);

    if (clone_stats) {
        clone_stats->clone_count++;
        clone_stats->copied_path_elements += (unsigned long long)branch->path_len;
        clone_stats->copied_hash_capacity += (unsigned long long)branch->visited.capacity;
    }

    return branch;
}

static int branch_append_position(PermBranch *branch, int x, int y, int z)
{
    if (branch->path_len >= branch->path_cap) {
        return 0;
    }

    branch->path[branch->path_len].x = x;
    branch->path[branch->path_len].y = y;
    branch->path[branch->path_len].z = z;
    branch->path_len++;
    return 1;
}

static int write_metadata(
    const Config *cfg,
    const char *output_path,
    const char *tours_path,
    const char *metadata_path
)
{
    FILE *fp = fopen(metadata_path, "w");
    if (!fp) {
        return 0;
    }

    fprintf(fp, "{\n");
    fprintf(fp, "  \"walk_algorithm\": ");
    write_json_string(fp, cfg->walk_algorithm);
    fprintf(fp, ",\n");
    fprintf(fp, "  \"walk_type\": ");
    write_json_string(fp, cfg->walk_type);
    fprintf(fp, ",\n");
    fprintf(fp, "  \"dim\": %d,\n", cfg->dim);
    fprintf(fp, "  \"boundary\": ");
    write_json_string(fp, cfg->boundary);
    fprintf(fp, ",\n");
    fprintf(fp, "  \"spatial_backend\": ");
    write_json_string(fp, cfg->spatial_backend);
    fprintf(fp, ",\n");
    fprintf(fp, "  \"n_steps\": %d,\n", cfg->n_steps);
    fprintf(fp, "  \"n_tours\": %d,\n", cfg->n_tours);
    fprintf(fp, "  \"seed\": ");
    if (cfg->seed_provided) {
        write_json_string(fp, cfg->seed_str);
    } else {
        fputs("null", fp);
    }
    fprintf(fp, ",\n");
    fprintf(fp, "  \"actual_seed\": %u,\n", cfg->resolved_seed_set ? cfg->resolved_seed : 0u);
    fprintf(fp, "  \"perm_c_minus\": %.17g,\n", cfg->perm_c_minus);
    fprintf(fp, "  \"perm_c_plus\": %.17g,\n", cfg->perm_c_plus);
    fprintf(fp, "  \"perm_min_tours_for_threshold\": %d,\n", cfg->perm_min_tours_for_threshold);
    fprintf(fp, "  \"output_file\": ");
    write_json_string(fp, output_path);
    fprintf(fp, ",\n");
    fprintf(fp, "  \"tour_diagnostics_file\": ");
    write_json_string(fp, tours_path);
    fprintf(fp, "\n}\n");

    if (fclose(fp) != 0) {
        return 0;
    }

    return 1;
}

static int validate_perm_config(const Config *cfg)
{
    if (cfg->dim != 2) {
        fprintf(stderr, "PERM only supports dim=2\n");
        return 0;
    }

    if (strcmp(cfg->walk_type, "saw") != 0) {
        fprintf(stderr, "PERM only supports walk_type=saw\n");
        return 0;
    }

    if (strcmp(cfg->spatial_backend, "hash") != 0) {
        fprintf(stderr, "PERM only supports spatial_backend=hash\n");
        return 0;
    }

    if (strcmp(cfg->boundary, "infinite") != 0) {
        fprintf(stderr, "PERM only supports boundary=infinite\n");
        return 0;
    }

    if (cfg->n_steps < 0) {
        fprintf(stderr, "n_steps must be >= 0\n");
        return 0;
    }

    if (cfg->n_tours <= 0) {
        fprintf(stderr, "n_tours must be > 0\n");
        return 0;
    }

    return 1;
}

static void record_step_contribution(
    StepStats *steps,
    size_t step_index,
    long double weight,
    long double r2,
    long double *local_tour_weight_sum,
    long double *local_tour_weight_r2_sum,
    long double *local_tour_weight_squared_sum
)
{
    StepStats *step_stats = &steps[step_index];
    step_stats->sample_count++;
    scaled_positive_add(&step_stats->branch_weight_sum, weight);
    scaled_positive_add(&step_stats->branch_weight_r2_sum, weight * r2);
    scaled_positive_add(&step_stats->branch_weight_squared_sum, weight * weight);
    if (weight > step_stats->max_weight) {
        step_stats->max_weight = weight;
    }

    local_tour_weight_sum[step_index] += weight;
    local_tour_weight_r2_sum[step_index] += weight * r2;
    local_tour_weight_squared_sum[step_index] += weight * weight;
}

static int perm_threshold_for_step(
    const Config *cfg,
    const StepStats *steps,
    unsigned long long completed_tours_snapshot,
    size_t step_index,
    long double *lower_threshold,
    long double *upper_threshold
)
{
    if (strcmp(cfg->perm_threshold_scheme, "basic") != 0) {
        return 0;
    }

    if (completed_tours_snapshot < (unsigned long long)cfg->perm_min_tours_for_threshold) {
        return 0;
    }

    if (steps[step_index].nonzero_tours < (unsigned long long)cfg->perm_min_tours_for_threshold) {
        return 0;
    }

    long double total_tour_weight = scaled_positive_value(&steps[step_index].tour_weight_sum);
    if (!(total_tour_weight > 0.0L) || !isfinite(total_tour_weight)) {
        return 0;
    }

    long double z_estimate = total_tour_weight / (long double)completed_tours_snapshot;
    if (!(z_estimate > 0.0L) || !isfinite(z_estimate)) {
        return 0;
    }

    *lower_threshold = (long double)cfg->perm_c_minus * z_estimate;
    *upper_threshold = (long double)cfg->perm_c_plus * z_estimate;

    if (!isfinite(*lower_threshold) || !isfinite(*upper_threshold) || !(*lower_threshold > 0.0L) || !(*upper_threshold > *lower_threshold)) {
        return 0;
    }

    return 1;
}

static long double compute_partition_sum_standard_error(
    const StepStats *step_stats,
    unsigned long long completed_tours
)
{
    if (completed_tours < 2ULL) {
        return NAN;
    }

    long double total = scaled_positive_value(&step_stats->tour_weight_sum);
    long double total_squared = scaled_positive_value(&step_stats->tour_weight_squared_sum);
    if (!(total >= 0.0L) || !isfinite(total) || !isfinite(total_squared)) {
        return NAN;
    }

    long double n = (long double)completed_tours;
    long double mean = total / n;
    long double variance = (total_squared - n * mean * mean) / (n - 1.0L);
    if (!(variance >= 0.0L) || !isfinite(variance)) {
        if (variance < 0.0L && fabsl(variance) < 1e-18L * fabsl(total_squared)) {
            variance = 0.0L;
        } else {
            return NAN;
        }
    }

    return sqrtl(variance / n);
}

static long double compute_weighted_mean_r2_standard_error(const TourBuffer *buffer, size_t step_index, long double total_weight, long double total_weight_r2)
{
    if (!buffer || !buffer->enabled || buffer->tour_count < 2 || !(total_weight > 0.0L) || !isfinite(total_weight) || !isfinite(total_weight_r2)) {
        return NAN;
    }

    long double mean = 0.0L;
    long double m2 = 0.0L;
    unsigned long long valid_count = 0ULL;

    for (size_t tour = 0; tour < buffer->tour_count; tour++) {
        size_t index = tour_buffer_index(buffer, tour, step_index);
        long double x = buffer->tour_weight_sum[index];
        long double y = buffer->tour_weight_r2_sum[index];
        long double denom = total_weight - x;
        if (!(denom > 0.0L) || !isfinite(denom)) {
            continue;
        }

        long double theta = (total_weight_r2 - y) / denom;
        if (!isfinite(theta)) {
            continue;
        }

        valid_count++;
        long double delta = theta - mean;
        mean += delta / (long double)valid_count;
        long double delta2 = theta - mean;
        m2 += delta * delta2;
    }

    if (valid_count < 2ULL || !(m2 >= 0.0L) || !isfinite(m2)) {
        return NAN;
    }

    return sqrtl(((long double)valid_count - 1.0L) / (long double)valid_count * m2);
}


static int write_convergence_snapshot(
    FILE *fp,
    const Config *cfg,
    const StepStats *steps,
    const TourBuffer *buffer,
    size_t step_count,
    unsigned long long completed_tours
)
{
    if (!fp || completed_tours == 0ULL) {
        return 1;
    }

    TourBuffer prefix_buffer = *buffer;
    if (prefix_buffer.enabled) {
        prefix_buffer.tour_count = (size_t)completed_tours;
    }

    for (size_t step = 0; step < step_count; step++) {
        long double branch_sum = scaled_positive_value(&steps[step].branch_weight_sum);
        long double branch_sum_r2 = scaled_positive_value(&steps[step].branch_weight_r2_sum);
        long double branch_sum_sq = scaled_positive_value(&steps[step].branch_weight_squared_sum);
        long double tour_sum = scaled_positive_value(&steps[step].tour_weight_sum);
        long double tour_sum_r2 = scaled_positive_value(&steps[step].tour_weight_r2_sum);
        long double tour_sum_sq = scaled_positive_value(&steps[step].tour_weight_squared_sum);

        long double weighted_mean_r2 = (branch_sum > 0.0L) ? (branch_sum_r2 / branch_sum) : NAN;
        long double weighted_mean_r2_standard_error =
            compute_weighted_mean_r2_standard_error(&prefix_buffer, step, tour_sum, tour_sum_r2);
        long double partition_sum_estimate = tour_sum / (long double)completed_tours;
        long double partition_sum_standard_error =
            compute_partition_sum_standard_error(&steps[step], completed_tours);
        long double branch_weight_ess =
            (branch_sum_sq > 0.0L) ? (branch_sum * branch_sum / branch_sum_sq) : NAN;
        long double tour_weight_ess =
            (tour_sum_sq > 0.0L) ? (tour_sum * tour_sum / tour_sum_sq) : NAN;
        long double mean_weight =
            (steps[step].sample_count > 0ULL) ?
            (branch_sum / (long double)steps[step].sample_count) : NAN;

        long double lower_threshold = NAN;
        long double upper_threshold = NAN;
        int threshold_enabled = perm_threshold_for_step(
            cfg,
            steps,
            completed_tours,
            step,
            &lower_threshold,
            &upper_threshold
        );
        if (!threshold_enabled) {
            lower_threshold = NAN;
            upper_threshold = NAN;
        }

        fprintf(
            fp,
            "%llu,%zu,%.17Lg,%.17Lg,%.17Lg,%.17Lg,%llu,%llu,%.17Lg,%.17Lg,%.17Lg,%.17Lg,%.17Lg,%.17Lg,%d\n",
            completed_tours,
            step,
            weighted_mean_r2,
            weighted_mean_r2_standard_error,
            partition_sum_estimate,
            partition_sum_standard_error,
            steps[step].sample_count,
            steps[step].nonzero_tours,
            branch_weight_ess,
            tour_weight_ess,
            mean_weight,
            steps[step].max_weight,
            lower_threshold,
            upper_threshold,
            threshold_enabled
        );
    }

    return fflush(fp) == 0;
}

static int run_weighted_saw(const Config *cfg, int use_perm)
{
    if (!validate_perm_config(cfg)) {
        return 0;
    }

    size_t step_count = (size_t)cfg->n_steps + 1U;
    StepStats *steps = calloc(step_count, sizeof(*steps));
    if (!steps) {
        fprintf(stderr, "Failed to allocate PERM statistics\n");
        return 0;
    }

    for (size_t step = 0; step < step_count; step++) {
        scaled_positive_init(&steps[step].branch_weight_sum);
        scaled_positive_init(&steps[step].branch_weight_r2_sum);
        scaled_positive_init(&steps[step].branch_weight_squared_sum);
        scaled_positive_init(&steps[step].tour_weight_sum);
        scaled_positive_init(&steps[step].tour_weight_r2_sum);
        scaled_positive_init(&steps[step].tour_weight_squared_sum);
        steps[step].sample_count = 0ULL;
        steps[step].nonzero_tours = 0ULL;
        steps[step].max_weight = 0.0L;
        steps[step].lower_threshold = NAN;
        steps[step].upper_threshold = NAN;
        steps[step].threshold_enabled = 0;
    }

    TourBuffer buffer;
    if (!tour_buffer_init(&buffer, (size_t)cfg->n_tours, step_count)) {
        fprintf(stderr, "Failed to allocate tour buffers\n");
        free(steps);
        return 0;
    }

    char main_path[512];
    char tours_path[512];
    char metadata_path[512];
    char convergence_path[512];
    build_sibling_path(main_path, sizeof(main_path), cfg->output, use_perm ? "perm.csv" : "rosenbluth.csv");
    build_sibling_path(tours_path, sizeof(tours_path), cfg->output, "perm_tours.csv");
    build_sibling_path(metadata_path, sizeof(metadata_path), cfg->output, "simulation_metadata.json");
    build_sibling_path(convergence_path, sizeof(convergence_path), cfg->output, "weighted_convergence.csv");

    if (!ensure_parent_dir(main_path) || !ensure_parent_dir(metadata_path) || (use_perm && !ensure_parent_dir(tours_path))) {
        fprintf(stderr, "Failed to create PERM output directories\n");
        tour_buffer_destroy(&buffer);
        free(steps);
        return 0;
    }

    FILE *main_fp = fopen(main_path, "w");
    if (!main_fp) {
        fprintf(stderr, "Failed to open output file: %s\n", main_path);
        tour_buffer_destroy(&buffer);
        free(steps);
        return 0;
    }

    FILE *convergence_fp = NULL;
    if (strcmp(cfg->tour_checkpoint_mode, "log10") == 0) {
        convergence_fp = fopen(convergence_path, "w");
        if (!convergence_fp) {
            fprintf(stderr, "Failed to open convergence file: %s\n", convergence_path);
            fclose(main_fp);
            tour_buffer_destroy(&buffer);
            free(steps);
            return 0;
        }
        fprintf(convergence_fp, "checkpoint_tours,step,weighted_mean_r2,weighted_mean_r2_standard_error,partition_sum_estimate,partition_sum_standard_error,sample_count,nonzero_tours,branch_weight_ess,tour_weight_ess,mean_weight,max_weight,lower_threshold,upper_threshold,threshold_enabled\n");
    }

    FILE *tours_fp = NULL;
    if (use_perm) {
        tours_fp = fopen(tours_path, "w");
        if (!tours_fp) {
            fprintf(stderr, "Failed to open tour diagnostics file: %s\n", tours_path);
            if (convergence_fp) fclose(convergence_fp);
            fclose(main_fp);
            tour_buffer_destroy(&buffer);
            free(steps);
            return 0;
        }
        fprintf(tours_fp, "tour,max_reached_step,generated_branches,pruned_count,enriched_count,max_stack_size,tour_total_nodes,tour_clone_count,clone_count,clone_time,copied_path_elements,copied_hash_capacity\n");
    }

    fprintf(main_fp, "step,weighted_mean_r2,weighted_mean_r2_standard_error,partition_sum_estimate,partition_sum_standard_error,log_partition_sum,partition_sum_mantissa,partition_sum_exponent,sample_count,nonzero_tours,completed_tours,branch_weight_ess,tour_weight_ess,mean_weight,max_weight,lower_threshold,upper_threshold,threshold_enabled\n");

    long double *local_tour_weight_sum = calloc(step_count, sizeof(long double));
    long double *local_tour_weight_r2_sum = calloc(step_count, sizeof(long double));
    long double *local_tour_weight_squared_sum = calloc(step_count, sizeof(long double));
    long double *threshold_lower = calloc(step_count, sizeof(long double));
    long double *threshold_upper = calloc(step_count, sizeof(long double));
    int *threshold_enabled = calloc(step_count, sizeof(int));
    if (!local_tour_weight_sum || !local_tour_weight_r2_sum || !local_tour_weight_squared_sum || !threshold_lower || !threshold_upper || !threshold_enabled) {
        fprintf(stderr, "Failed to allocate tour-local PERM buffers\n");
        free(local_tour_weight_sum);
        free(local_tour_weight_r2_sum);
        free(local_tour_weight_squared_sum);
        free(threshold_lower);
        free(threshold_upper);
        free(threshold_enabled);
        if (tours_fp) fclose(tours_fp);
        fclose(main_fp);
        tour_buffer_destroy(&buffer);
        free(steps);
        return 0;
    }

    unsigned long long next_checkpoint = (unsigned long long)cfg->tour_checkpoint_start;

    for (int tour = 0; tour < cfg->n_tours; tour++) {
        memset(local_tour_weight_sum, 0, step_count * sizeof(long double));
        memset(local_tour_weight_r2_sum, 0, step_count * sizeof(long double));
        memset(local_tour_weight_squared_sum, 0, step_count * sizeof(long double));

        unsigned long long completed_tours_snapshot = (unsigned long long)tour;
        for (size_t step = 0; step < step_count; step++) {
            long double lower = NAN;
            long double upper = NAN;
            if (use_perm && perm_threshold_for_step(cfg, steps, completed_tours_snapshot, step, &lower, &upper)) {
                threshold_enabled[step] = 1;
                threshold_lower[step] = lower;
                threshold_upper[step] = upper;
            } else {
                threshold_enabled[step] = 0;
                threshold_lower[step] = NAN;
                threshold_upper[step] = NAN;
            }
        }

        PermCloneStats clone_stats = {0};
        PermTourDiagnostics diag = {0};
        diag.tour = tour;
        diag.clone_time = 0.0L;
        diag.max_reached_step = 0;

        unsigned long long root_seed = perm_splitmix64(((unsigned long long)cfg->resolved_seed << 1) ^ (unsigned long long)(tour + 1) ^ 0x53f2d40b97a1e2c1ULL);
        PermBranch *root = create_root_branch(cfg, root_seed);
        if (!root) {
            fprintf(stderr, "Failed to create root branch\n");
            free(local_tour_weight_sum);
            free(local_tour_weight_r2_sum);
            free(local_tour_weight_squared_sum);
            free(threshold_lower);
            free(threshold_upper);
            free(threshold_enabled);
            if (tours_fp) fclose(tours_fp);
            fclose(main_fp);
            tour_buffer_destroy(&buffer);
            free(steps);
            return 0;
        }

        PermBranchStack stack;
        perm_branch_stack_init(&stack);
        if (!perm_branch_stack_push(&stack, root)) {
            destroy_branch(root);
            free(local_tour_weight_sum);
            free(local_tour_weight_r2_sum);
            free(local_tour_weight_squared_sum);
            free(threshold_lower);
            free(threshold_upper);
            free(threshold_enabled);
            if (tours_fp) fclose(tours_fp);
            fclose(main_fp);
            tour_buffer_destroy(&buffer);
            free(steps);
            return 0;
        }

        long double root_r2 = 0.0L;
        record_step_contribution(steps, 0, 1.0L, root_r2, local_tour_weight_sum, local_tour_weight_r2_sum, local_tour_weight_squared_sum);
        diag.generated_branches = 1ULL;
        diag.tour_total_nodes = 1ULL;

        while (stack.size > 0) {
            PermBranch *branch = perm_branch_stack_pop(&stack);
            if (!branch) {
                break;
            }

            diag.tour_total_nodes++;

            if (branch->step >= cfg->n_steps) {
                destroy_branch(branch);
                continue;
            }

            int dirs[4][2] = {{1,0},{-1,0},{0,1},{0,-1}};
            int candidates[4][2];
            int n_candidates = 0;
            for (int i = 0; i < 4; i++) {
                int nx = branch->x + dirs[i][0];
                int ny = branch->y + dirs[i][1];
                if (coordinate_hash_set_contains(&branch->visited, nx, ny, 0)) {
                    continue;
                }
                candidates[n_candidates][0] = nx;
                candidates[n_candidates][1] = ny;
                n_candidates++;
            }

            if (n_candidates == 0) {
                destroy_branch(branch);
                continue;
            }

            unsigned long long choice = perm_rng_bounded(&branch->rng, (unsigned long long)n_candidates);
            int nx = candidates[choice][0];
            int ny = candidates[choice][1];

            branch->x = nx;
            branch->y = ny;
            branch->step += 1;
            branch->weight *= (long double)n_candidates;
            if (!branch_append_position(branch, nx, ny, 0)) {
                fprintf(stderr, "Path capacity exceeded\n");
                destroy_branch(branch);
                goto cleanup_fail;
            }
            if (coordinate_hash_set_insert(&branch->visited, nx, ny, 0) < 0) {
                fprintf(stderr, "Failed to insert visited site\n");
                destroy_branch(branch);
                goto cleanup_fail;
            }

            size_t current_step = (size_t)branch->step;
            long double r2 = (long double)branch->x * (long double)branch->x + (long double)branch->y * (long double)branch->y;

            int thresholds_enabled_here = 0;
            long double lower_threshold = NAN;
            long double upper_threshold = NAN;
            if (use_perm && current_step < step_count) {
                thresholds_enabled_here = perm_threshold_for_step(cfg, steps, (unsigned long long)tour, current_step, &lower_threshold, &upper_threshold);
            }

            if (thresholds_enabled_here && branch->weight < lower_threshold) {
                if (perm_rng_bounded(&branch->rng, 2ULL) == 0ULL) {
                    diag.pruned_count++;
                    destroy_branch(branch);
                    continue;
                }

                /* Pruning keeps the expected weight unchanged: survival probability 1/2 and surviving weight 2W. */
                branch->weight *= 2.0L;
            }

            if (thresholds_enabled_here && branch->weight > upper_threshold) {
                long double clone_start = (long double)now_seconds();
                PermBranch *child = clone_branch(branch, perm_splitmix64(branch->rng.state ^ (unsigned long long)(tour + 1) ^ (unsigned long long)(clone_stats.clone_count + 1ULL)), &clone_stats);
                clone_stats.clone_time += (long double)now_seconds() - clone_start;
                if (!child) {
                    fprintf(stderr, "Failed to clone branch\n");
                    destroy_branch(branch);
                    goto cleanup_fail;
                }

                branch->weight *= 0.5L;
                child->weight = branch->weight;
                child->step = branch->step;
                diag.enriched_count++;
                diag.tour_clone_count = clone_stats.clone_count;
                diag.clone_time = clone_stats.clone_time;
                diag.copied_path_elements = clone_stats.copied_path_elements;
                diag.copied_hash_capacity = clone_stats.copied_hash_capacity;

                record_step_contribution(steps, current_step, branch->weight, r2, local_tour_weight_sum, local_tour_weight_r2_sum, local_tour_weight_squared_sum);
                record_step_contribution(steps, current_step, child->weight, r2, local_tour_weight_sum, local_tour_weight_r2_sum, local_tour_weight_squared_sum);

                if (!perm_branch_stack_push(&stack, branch) || !perm_branch_stack_push(&stack, child)) {
                    destroy_branch(branch);
                    destroy_branch(child);
                    goto cleanup_fail;
                }
                diag.generated_branches += 2ULL;
                if (stack.max_size_observed > diag.max_stack_size) {
                    diag.max_stack_size = (unsigned long long)stack.max_size_observed;
                }
                if (branch->step > diag.max_reached_step) {
                    diag.max_reached_step = branch->step;
                }
                continue;
            }

            record_step_contribution(steps, current_step, branch->weight, r2, local_tour_weight_sum, local_tour_weight_r2_sum, local_tour_weight_squared_sum);
            if (!perm_branch_stack_push(&stack, branch)) {
                destroy_branch(branch);
                goto cleanup_fail;
            }
            diag.generated_branches += 1ULL;
            if (stack.max_size_observed > diag.max_stack_size) {
                diag.max_stack_size = (unsigned long long)stack.max_size_observed;
            }
            if (branch->step > diag.max_reached_step) {
                diag.max_reached_step = branch->step;
            }
        }

        perm_branch_stack_destroy(&stack);

        for (size_t step = 0; step < step_count; step++) {
            long double tour_weight_sum = local_tour_weight_sum[step];
            long double tour_weight_r2_sum = local_tour_weight_r2_sum[step];
            long double tour_weight_squared_sum = local_tour_weight_sum[step] * local_tour_weight_sum[step];

            if (tour_weight_sum > 0.0L) {
                steps[step].nonzero_tours++;
            }
            scaled_positive_add(&steps[step].tour_weight_sum, tour_weight_sum);
            scaled_positive_add(&steps[step].tour_weight_r2_sum, tour_weight_r2_sum);
            scaled_positive_add(&steps[step].tour_weight_squared_sum, tour_weight_squared_sum);

            if (buffer.enabled) {
                size_t index = tour_buffer_index(&buffer, (size_t)tour, step);
                buffer.tour_weight_sum[index] = tour_weight_sum;
                buffer.tour_weight_r2_sum[index] = tour_weight_r2_sum;
                buffer.tour_weight_squared_sum[index] = tour_weight_squared_sum;
            }
        }

        unsigned long long completed_tours = (unsigned long long)tour + 1ULL;
        if (convergence_fp &&
            (completed_tours == next_checkpoint || completed_tours == (unsigned long long)cfg->n_tours)) {
            if (!write_convergence_snapshot(convergence_fp, cfg, steps, &buffer, step_count, completed_tours)) {
                fprintf(stderr, "Failed to write tour checkpoint at %llu tours\n", completed_tours);
                goto cleanup_fail;
            }
            if (completed_tours == next_checkpoint) {
                if (next_checkpoint <= ULLONG_MAX / 10ULL) {
                    next_checkpoint *= 10ULL;
                } else {
                    next_checkpoint = ULLONG_MAX;
                }
            }
        }

        if (use_perm && tours_fp) {
            fprintf(tours_fp, "%d,%d,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%.17Lg,%llu,%llu\n",
                tour,
                diag.max_reached_step,
                diag.generated_branches,
                diag.pruned_count,
                diag.enriched_count,
                diag.max_stack_size,
                diag.tour_total_nodes,
                diag.tour_clone_count,
                clone_stats.clone_count,
                clone_stats.clone_time,
                diag.copied_path_elements,
                diag.copied_hash_capacity);
        }
    }

    for (size_t step = 0; step < step_count; step++) {
        long double branch_sum = scaled_positive_value(&steps[step].branch_weight_sum);
        long double branch_sum_r2 = scaled_positive_value(&steps[step].branch_weight_r2_sum);
        long double branch_sum_sq = scaled_positive_value(&steps[step].branch_weight_squared_sum);
        long double tour_sum = scaled_positive_value(&steps[step].tour_weight_sum);
        long double tour_sum_sq = scaled_positive_value(&steps[step].tour_weight_squared_sum);

        long double weighted_mean_r2 = (branch_sum > 0.0L) ? (branch_sum_r2 / branch_sum) : NAN;
        long double partition_sum_estimate_ld = (cfg->n_tours > 0) ? (tour_sum / (long double)cfg->n_tours) : NAN;
        long double partition_sum_standard_error = compute_partition_sum_standard_error(&steps[step], (unsigned long long)cfg->n_tours);
        long double weighted_mean_r2_standard_error = compute_weighted_mean_r2_standard_error(&buffer, step, tour_sum, scaled_positive_value(&steps[step].tour_weight_r2_sum));

        long double branch_weight_ess = (branch_sum_sq > 0.0L) ? (branch_sum * branch_sum / branch_sum_sq) : NAN;
        long double tour_weight_ess = (tour_sum_sq > 0.0L) ? (tour_sum * tour_sum / tour_sum_sq) : NAN;
        long double mean_weight = (steps[step].sample_count > 0ULL) ? (branch_sum / (long double)steps[step].sample_count) : NAN;
        long double max_weight = steps[step].max_weight;

        long double log_partition_sum = scaled_positive_log_value(&steps[step].tour_weight_sum) - logl((long double)cfg->n_tours);
        long double partition_mantissa = 0.0L;
        int partition_exponent = 0;
        long double partition_value = partition_sum_estimate_ld;
        if (isfinite(partition_value) && partition_value > 0.0L) {
            partition_mantissa = frexpl(partition_value, &partition_exponent);
        }

        double partition_sum_estimate = (isfinite(partition_value) && partition_value <= (long double)DBL_MAX) ? (double)partition_value : NAN;
        long double lower_threshold = NAN;
        long double upper_threshold = NAN;
        int threshold_enabled_value = perm_threshold_for_step(cfg, steps, (unsigned long long)cfg->n_tours, step, &lower_threshold, &upper_threshold);
        if (!threshold_enabled_value) {
            lower_threshold = NAN;
            upper_threshold = NAN;
        }

        fprintf(
            main_fp,
            "%zu,%.17Lg,%.17Lg,%.17g,%.17Lg,%.17Lg,%.17Lg,%d,%llu,%llu,%d,%.17Lg,%.17Lg,%.17Lg,%.17Lg,%.17Lg,%.17Lg,%d\n",
            step,
            weighted_mean_r2,
            weighted_mean_r2_standard_error,
            partition_sum_estimate,
            partition_sum_standard_error,
            log_partition_sum,
            partition_mantissa,
            partition_exponent,
            steps[step].sample_count,
            steps[step].nonzero_tours,
            (int)cfg->n_tours,
            branch_weight_ess,
            tour_weight_ess,
            mean_weight,
            max_weight,
            lower_threshold,
            upper_threshold,
            threshold_enabled_value
        );
    }

    if (convergence_fp && fclose(convergence_fp) != 0) {
        if (tours_fp) fclose(tours_fp);
        fclose(main_fp);
        tour_buffer_destroy(&buffer);
        free(steps);
        free(local_tour_weight_sum);
        free(local_tour_weight_r2_sum);
        free(local_tour_weight_squared_sum);
        free(threshold_lower);
        free(threshold_upper);
        free(threshold_enabled);
        return 0;
    }

    if (fclose(main_fp) != 0) {
        if (tours_fp) fclose(tours_fp);
        tour_buffer_destroy(&buffer);
        free(steps);
        free(local_tour_weight_sum);
        free(local_tour_weight_r2_sum);
        free(local_tour_weight_squared_sum);
        free(threshold_lower);
        free(threshold_upper);
        free(threshold_enabled);
        return 0;
    }

    if (tours_fp && fclose(tours_fp) != 0) {
        tour_buffer_destroy(&buffer);
        free(steps);
        free(local_tour_weight_sum);
        free(local_tour_weight_r2_sum);
        free(local_tour_weight_squared_sum);
        free(threshold_lower);
        free(threshold_upper);
        free(threshold_enabled);
        return 0;
    }

    if (!write_metadata(cfg, main_path, use_perm ? tours_path : "", metadata_path)) {
        tour_buffer_destroy(&buffer);
        free(steps);
        free(local_tour_weight_sum);
        free(local_tour_weight_r2_sum);
        free(local_tour_weight_squared_sum);
        free(threshold_lower);
        free(threshold_upper);
        free(threshold_enabled);
        return 0;
    }

    tour_buffer_destroy(&buffer);
    free(steps);
    free(local_tour_weight_sum);
    free(local_tour_weight_r2_sum);
    free(local_tour_weight_squared_sum);
    free(threshold_lower);
    free(threshold_upper);
    free(threshold_enabled);
    return 1;

cleanup_fail:
    if (convergence_fp) {
        fclose(convergence_fp);
    }
    if (tours_fp) {
        fclose(tours_fp);
    }
    fclose(main_fp);
    tour_buffer_destroy(&buffer);
    free(steps);
    free(local_tour_weight_sum);
    free(local_tour_weight_r2_sum);
    free(local_tour_weight_squared_sum);
    free(threshold_lower);
    free(threshold_upper);
    free(threshold_enabled);
    return 0;
}

int run_rosenbluth_simulation(const Config *cfg)
{
    return run_weighted_saw(cfg, 0);
}

int run_perm_simulation(const Config *cfg)
{
    return run_weighted_saw(cfg, 1);
}