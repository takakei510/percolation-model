## Plan: Add lifetime distribution analysis script

TL;DR: Create `scripts/analysis/fit_lifetime_distribution.py` to read `final_steps.csv`, compute discrete lifetime distribution P(T), fit a geometric distribution, save histogram and semi-log plots, and export CSV summaries with mean lifetime and fit parameter p.

**Steps**
1. Create `scripts/analysis/fit_lifetime_distribution.py`.
2. Use `argparse` with required options `--input` and `--out-prefix`, plus optional `--max-step`.
3. Read input CSV with `pandas.read_csv()` and require a `final_step` column.
4. Build a discrete histogram of final_step values using integer bin counts; compute probability P(T) = count / total.
5. If `--max-step` is provided, treat `final_step == max_step` as right-censored and report `censored_count` and `censored_fraction`.
6. Compute mean lifetime from the sample mean of `final_step` values.
7. Fit a geometric distribution parameter `p` using the MLE formula for support starting at the observed minimum: `p = 1.0 / (mean - support_start + 1)`.
8. Save a histogram plot to `{out_prefix}_lifetime_hist.png`.
9. Save a semi-log plot to `{out_prefix}_lifetime_semilog.png` with both observed P(T) and fitted geometric PMF.
10. Save histogram data and fitted PMF to `{out_prefix}_lifetime_distribution.csv`.
11. Save summary stats `mean_lifetime`, `p`, `censored_count`, `censored_fraction`, and a warning note about fitting including censored samples to `{out_prefix}_lifetime_fit_summary.csv`.

**Relevant files**
- `/home/takak/project/scripts/analysis/fit_survival.py` — CLI style and plotting patterns
- `/home/takak/project/scripts/analysis/fit_diffusion_exponent.py` — summary CSV output pattern
- `/home/takak/project/scripts/visualization/plot_final_step.py` — `final_step` input handling and histogram style

**Verification**
1. Run the script with a sample `final_steps.csv` and `--out-prefix` to confirm output files are created.
2. Confirm CSV files contain expected columns: `final_step`, `count`, `probability`, `geometric_fit` and summary file contains `mean_lifetime`, `p`.
3. Confirm plots are saved at the expected names and use linear histogram / semi-log axis.

**Decisions**
- Use the observed minimum `final_step` value as the geometric distribution support start to support both 0-based and 1-based data.
- Produce two CSV outputs: one for distribution data and one for scalar fit summary.
- No changes to other scripts are required.

## Research considerations
- Check censored samples
- Verify geometric assumption
- Export reproducible CSV outputs