# Percolation & Random Walk Simulation

本リポジトリは C 言語で実装したサイトパーコレーションとランダムウォーク／自己回避ウォーク（SAW）のシミュレーション、および Python による解析・可視化をまとめた研究用コードベースです。

## 主な特徴

- 2D / 3D サイトパーコレーション
- BFS / Union-Find によるクラスタ抽出
- 最大クラスタ・第2クラスタの解析
- sweep / size_sweep / p_incremental_sweep / random_walk 実行
- CSV 出力による結果保存
- Python でのプロットとフィッティング
- 生存確率解析や寿命分布解析
- Mean Square Displacement (MSD) 分析
- 生存条件付き MSD サンプル分布の信頼性評価
- 無限格子 hash backend による kinetic SAW
- Rosenbluth weight による 2D SAW 推定
- PERM (Pruned-Enriched Rosenbluth Method) による 2D SAW 推定

## ディレクトリ構成

```text
project/
├── build/                 # コンパイル済みバイナリ
├── configs/               # 実行設定ファイル
│   ├── bfs/
│   ├── union_find/
│   └── random_walk/
├── data/                  # 出力データ（Git 管理外）
├── include/               # ヘッダファイル
├── scripts/
│   ├── analysis/          # 分析・フィッティング用 Python スクリプト
│   ├── visualization/     # 可視化用 Python スクリプト
│   ├── run_analysis.sh    # 分析ワークフロー用ラッパー
│   ├── run_plot.sh        # 可視化ワークフロー用ラッパー
│   └── test_all.sh        # テスト実行用スクリプト
├── src/                   # C ソースコード
├── Makefile
└── README.md
```

## 必要環境

- gcc
- make
- Python 3
- numpy
- pandas
- matplotlib
- pillow

Python の依存は `requirements.txt` にまとめています。

```bash
pip install -r requirements.txt
```

## クイックスタート

### 1. ビルド

```bash
make clean && make
```

### 2. 単一実行でテスト

```bash
# 2D パーコレーション（単一 p 値）
./build/main configs/bfs/single/2d_largest.txt

# 2D ランダムウォーク
./build/main configs/random_walk/2d/rw.txt
```

### 3. 結果を確認

```bash
# 出力データの確認
ls data/

# 可視化
python scripts/visualization/plot_cluster.py data/.../summary.csv
```

## ビルド手順

```bash
make
```

ビルド後、実行バイナリは `build/main` に生成されます。

## シミュレーション実行

C 実装のシミュレーションは設定ファイルを指定して実行します。

```bash
./build/main <config-file>
```

例:

```bash
./build/main configs/bfs/single/2d_largest.txt
./build/main configs/bfs/sweep/2d/L512.txt
./build/main configs/bfs/size_sweep/2d.txt
./build/main configs/random_walk/2d/rw.txt
```

### 代表的なモード

- `mode=single` : 単一の p で実行
- `mode=sweep` : p の掃引実行
- `mode=size_sweep` : L の掃引実行
- `mode=p_incremental_sweep` : p を段階的に増加させる掃引
- `mode=random_walk` : ランダムウォーク / SAW 実行

## config パラメータ概要

- `mode` : 実行モード
- `dim` : 2 または 3
- `L` : 格子サイズ
- `p` : 占有確率
- `p_start`, `p_end`, `dp` : `sweep` モードの p 範囲
- `L_start`, `L_max`, `L_multiplier` : `size_sweep` の L 掃引設定
- `n_trials` : 試行回数
- `cluster_view_mode` : `largest_only`, `second_only`, `top2`
- `save_cluster_sizes` : クラスタサイズ保存フラグ
- `save_top_coords` : 上位クラスタ座標保存フラグ
- `save_msd_distribution` : MSD 分布保存フラグ（random_walk モード）
- `msd_distribution_steps` : 保存する step のリストまたは範囲（例: `10,30,50,100,200:800`）

### random_walk 固有パラメータ

- `walk_type` : `rw` または `saw`
- `walk_algorithm` : `kinetic`, `rosenbluth`, `perm`。省略時は `kinetic`
- `n_steps` : ステップ数
- `n_tours` : Rosenbluth / PERM の tour 数。`n_trials` とは別項目
- `spatial_backend` : `dense` または `hash`。未指定時は `dense`
- `boundary` : `free`, `periodic`, `infinite`
- `hash_max_load_factor` : hash backend の上限 load factor
- `perm_c_minus` : pruning 用係数。閾値は `perm_c_minus * z_estimate[n]`
- `perm_c_plus` : enrichment 用係数。閾値は `perm_c_plus * z_estimate[n]`
- `perm_min_tours_for_threshold` : 過去の completed tour がこの数未満なら pruning/enrichment を無効化
- `perm_threshold_scheme` : 現在は `basic` のみ対応。将来の threshold 戦略切替用

`partition sum` 推定値は tour 数で正規化した平均重みです。
- `msd_sample_mode` : `exact`, `reservoir`, `none`
- `msd_reservoir_size` : reservoir の最大保持数
- `sampling_seed` : reservoir 用の独立 seed
- `save_trajectory` : 軌跡保存の有無
- `save_trajectory_trials` : 軌跡保存試行数
- `output` : 結果 CSV の出力先
- `trajectory_output` : 軌跡 CSV の出力先
- `seed` / `seed_offset` : 乱数 seed とオフセット

### 無限格子 kinetic SAW

`spatial_backend=hash` かつ `boundary=infinite` のとき、`L` は不要です。これは equilibrium SAW ではなく、未訪問最近接点を一様に選んで進む kinetic SAW のままです。trapping、選択バイアス、生存条件付き分布は残ります。

`dense + free` と `dense + periodic` は従来どおり、`hash + infinite` は新規対応です。`dense + infinite` と `hash + free/periodic` はエラーになります。

### Rosenbluth / PERM

この実装では 2D / `hash` / `infinite` / `saw` のみ対応します。`walk_algorithm=rosenbluth` は Rosenbluth 重み付けのみ、`walk_algorithm=perm` は pruning と enrichment を追加した PERM を実行します。`walk_algorithm` を省略した場合は従来どおり `kinetic` です。

各 step で未訪問近傍数を $m_n$ とすると、Rosenbluth 重みは

$$
W_n = W_{n-1} m_n, \qquad W_0 = 1
$$

です。集計量は step ごとに `sum_weight`, `sum_weight_r2`, `sum_weight_squared`, `sample_count` を保持し、重み付き平均は

$$
\langle R_n^2 \rangle_w = \frac{\sum W_n R_n^2}{\sum W_n}
$$

partition sum 推定値は tour 数で正規化した

$$
Z_n \approx \frac{\sum W_n}{\text{completed tours}}
$$

です。`effective_sample_size` は

$$
\mathrm{ESS}_n = \frac{(\sum W_n)^2}{\sum W_n^2}
$$

で計算しますが、branch 間には相関があるため、独立サンプル数そのものではありません。

PERM では、`weight < lower_threshold[n]` の branch を確率 $1/2$ で削除し、生存した場合は weight を 2 倍します。期待重みは保存されます。`weight > upper_threshold[n]` の branch は 2 分割し、各 branch の weight を 1/2 にして独立に継続します。閾値は completed tour から得た `z_estimate[n]` に基づき、`completed_tours < perm_min_tours_for_threshold` の間は pruning/enrichment を行いません。

## 代表的な config 例

### `configs/bfs/single/2d_largest.txt`

```text
mode=single
p=0.59
dim=2
L=100
n_trials=1
save_cluster_sizes=1
save_top_coords=1
cluster_view_mode=largest_only
```

### `configs/bfs/sweep/2d/L512.txt`

```text
mode=sweep
dim=2
L=512
n_trials=10
p_start=0.10
p_end=0.80
dp=0.001
save_cluster_sizes=0
save_top_coords=0
```

### `configs/bfs/size_sweep/2d.txt`

```text
mode=size_sweep
p=0.5927
L_start=16
L_max=2048
L_multiplier=2
n_trials=5
cluster_view_mode=top2
save_cluster_sizes=0
save_top_coords=0
```

## 出力データ

- `data/.../rw.csv`, `data/.../saw.csv` : RW / SAW 統計データ
- `data/.../rosenbluth/rosenbluth.csv` : Rosenbluth の重み付き統計
- `data/.../perm/perm.csv` : PERM の重み付き統計
- `data/.../perm/perm_tours.csv` : tour 診断データ
- `data/.../msd_samples.csv` : 生存条件付き MSD サンプルの生データ
- `data/.../msd_distribution.csv` : `msd_samples.csv` の互換エイリアス
- `data/.../msd_reservoir_samples.csv` : reservoir sample の生データ
- `data/.../msd_streaming_summary.csv` : 生存 walk 全体から正確に計算した streaming summary
- `data/.../rw_traj.csv`, `data/.../saw_traj.csv` : 軌跡データ
- `data/.../final_steps.csv` : 最終ステップ / 寿命データ
- `data/.../summary.csv` : single / sweep の集計結果
- `data/.../time_vs_L.csv` : size_sweep の L 依存結果

`perm.csv` の列:

```text
step,weighted_mean_r2,weighted_mean_r2_standard_error,partition_sum_estimate,partition_sum_standard_error,log_partition_sum,partition_sum_mantissa,partition_sum_exponent,sample_count,nonzero_tours,completed_tours,branch_weight_ess,tour_weight_ess,mean_weight,max_weight,lower_threshold,upper_threshold,threshold_enabled
```

`perm_tours.csv` の列:

```text
tour,max_reached_step,generated_branches,pruned_count,enriched_count,max_stack_size,tour_total_nodes,tour_clone_count,clone_count,clone_time,copied_path_elements,copied_hash_capacity
```

`simulation_metadata.json` には `walk_algorithm`, `walk_type`, `dim`, `boundary`, `spatial_backend`, `n_steps`, `n_tours`, `seed`, `actual_seed`, `perm_c_minus`, `perm_c_plus`, `perm_min_tours_for_threshold` を含めます。

`walk_algorithm=perm` の出力先は kinetic SAW と分離してください。たとえば `data/2d/random_walk/saw/kinetic/`, `data/2d/random_walk/saw/rosenbluth/`, `data/2d/random_walk/saw/perm/` のように分けます。

### 既知の制約

- 現時点で対応するのは 2D / `hash` / `infinite` / `saw` のみです
- SAT, 接触相互作用 $\omega$, 3D, FlatPERM, bootstrap, weighted least squares, MPI / OpenMP は未実装です
- Prellberg 論文ベースの拡張は今後の課題です

### クラスタ構造データ

- `data/2d/size_sweep_clusters/`
- `data/3d/size_sweep_clusters/`

2D の形式:

```text
site_index,x,y,cluster_rank
```

3D の形式:

```text
site_index,x,y,z,cluster_rank
```

`cluster_rank` は 1 が最大クラスタ、2 が第2クラスタを示します。

## 分析・可視化スクリプト

### 分析 (`scripts/analysis`)

- `fit_diffusion_exponent.py` : RW / SAW の MSD を対数フィットして拡散指数を推定
- `fit_survival.py` : 生存確率を指数関数フィット
- `fit_lifetime_distribution.py` : `final_steps.csv` から寿命分布を解析し、幾何分布をフィット

`fit_lifetime_distribution.py` は `--max-step` を指定すると、最大ステップで打ち切られた試行を右側打ち切り（right-censoring）として扱います。

- `analyze_msd_distribution.py` : MSD 分布の詳細分析（中央値、四分位数、パーセンタイル）
- `analyze_msd_distribution_reliability.py` : exact / reservoir / streaming summary を統合して MSD 分布、分散、標準誤差、分位点、fit 適格性を解析

### 可視化 (`scripts/visualization`)

- `plot_random_walk.py`
- `plot_final_step.py`
- `plot_cluster.py`
- `plot_cluster_distribution.py`
- `plot_cluster_scaling.py`
- `plot_mean_cluster_size.py`
- `plot_p_sweep_time.py`
- `plot_time_vs_L.py`
- `animate_clusters_vs_L.py`

## ワークフロー実行（高度な使い方）

### シミュレーション → 分析 → 可視化

シミュレーションから可視化まで一連のワークフローは、ラッパースクリプトで実行できます。

```bash
# 全テストを実行
bash scripts/test_all.sh

# 分析ワークフロー
bash scripts/run_analysis.sh analyze_msd_distribution 2d saw data/2d/animations/msd_distribution.csv

# 可視化ワークフロー
bash scripts/run_plot.sh plot_random_walk data/2d/random_walk/rw.csv
```

## 高度な機能

### MSD 分布分析

Random walk シミュレーション時に `save_msd_distribution=1` を config で設定すると、指定 step に到達した生存 walk の MSD サンプルまたは要約が出力されます。

- `msd_sample_mode=exact` は全サンプルを `msd_samples.csv` に保存します
- `msd_sample_mode=reservoir` は固定容量の `msd_reservoir_samples.csv` を保存します
- `msd_sample_mode=none` は分布サンプルを保存せず、`msd_streaming_summary.csv` だけを出力します

互換性のため、sample file に対して `msd_distribution.csv` のエイリアスも作成されます。

`msd_streaming_summary.csv` の `mean_r2`, `std_r2`, `variance_r2`, `standard_error_r2`, `relative_standard_error_r2`, `n_alive` は全生存 walk から正確に計算されます。reservoir は分位点推定と分布形状の確認に使います。

この分布は無条件分布ではなく、

$$
P(r^2(t) \mid \text{walk is alive at } t)
$$

です。

```text
# config example
mode=random_walk
walk_type=rw
dim=2
n_steps=1000
n_trials=100
save_msd_distribution=1
msd_distribution_steps=10,30,50,100,200:800
```

`msd_samples.csv` の列:

```text
trial,step,r2,lifetime,alive,trapped,boundary_dead,contact_dead
```

`alive` はこの CSV では常に `1` です。`lifetime` は walk の最終到達 step です。

`msd_reservoir_samples.csv` の列:

```text
step,sample_index,r2,source_trial,lifetime
```

reservoir 由来の分位点は近似です。図と CSV では `quantile_source=reservoir` を明記します。

```bash
python scripts/analysis/analyze_msd_distribution_reliability.py \
	data/2d/random_walk/saw/L64_N50_T100_reliability/msd_samples.csv \
	--output-dir data/2d/random_walk/saw/L64_N50_T100_reliability/msd_distribution_analysis \
	--n-trials 100 \
	--fit-start 5 \
	--fit-end 50 \
	--fit-min-alive 10 \
	--fit-min-survival-probability 0.01 \
	--fit-max-relative-standard-error 0.5 \
	--histogram-steps 5,10,20,30,40,50 \
	--boxplot-steps 5,10,20,30,40,50 \
	--bins fd
```

出力例:

```text
msd_distribution_analysis/
├── msd_distribution_summary.csv
├── analysis_metadata.json
├── histograms/
└── summary/
```

`fit_eligible` は統計的な最低条件を満たす点のフラグです。物理定数ではありません。閾値は解析用パラメータであり、ハードコードしません。

`std_r2` と `standard_error_r2` は `n_alive=1` のとき `NaN` になります。`mean_r2=0` または `median_r2=0` の場合も比率系の指標は `NaN` です。

この生データ方式は小〜中規模試行で分布形状を確認するための機能です。非常に大きな `n_trials` では使用しないでください。

既存の alpha fit は引き続き通常最小二乗です。weighted fit と bootstrap は未実装です。

### 大規模試行の推奨

`n_trials=10^5` 以上では、`msd_sample_mode=reservoir` または `none` を使ってください。`n_trials=10^6` で全サンプルを CSV に落とす設計は、出力容量と後処理コストが大きすぎるため推奨しません。

`msd_streaming_summary.csv` は大規模試行の正確な要約用、reservoir は分布形状の可視化用です。

既存の checkpoint は snapshot として扱います。`final_steps.csv` の途中コピーは保存できますが、reservoir の完全再開は未実装です。

### 実行ラッパー

- `bash scripts/run_analysis.sh <mode> <dim> <case>` : 分析ワークフロー
- `bash scripts/run_plot.sh <mode> ...` : 可視化ワークフロー

#### `scripts/run_analysis.sh` のモード例

- `fit_rw` : RW / SAW の拡散指数フィット
- `fit_survival` : 生存確率の指数フィット
- `fit_lifetime` : 寿命分布のフィット

`analyze_msd_distribution_reliability.py` は `msd_samples.csv`, `msd_reservoir_samples.csv`, `msd_streaming_summary.csv` を入力にできます。reservoir 分位点は近似で、exact / streaming の mean と RSE は summary を正とします。

#### `scripts/run_plot.sh` のモード例

- `sweep`, `sweep3d`
- `cluster`
- `anim`
- `time`, `time3d`, `time_compare`, `time3d_compare`
- `p_time`, `p_time3d`
- `scaling`
- `dist`, `dist3d`
- `mean`, `mean3d`
- `random_walk`
- `final_step`

## 使用例

### 分析の実行

```bash
bash scripts/run_analysis.sh fit_rw 2d L512_N1000_T10000
bash scripts/run_analysis.sh fit_survival 2d L512_N1000_T10000
bash scripts/run_analysis.sh fit_lifetime 2d L512_N1000_T10000
```

### 可視化の実行

```bash
bash scripts/run_plot.sh random_walk 2d L512_N1000_T10000
bash scripts/run_plot.sh final_step 2d L512_N1000_T10000
bash scripts/run_plot.sh sweep
bash scripts/run_plot.sh time
bash scripts/run_plot.sh scaling
```

## 注意

- `data/` 以下は生成データのため Git 管理対象外です。
- ソース変更後は再度 `make` を実行してください。
- Python スクリプト実行時は `requirements.txt` の依存を満たしてください。
