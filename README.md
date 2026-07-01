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

### random_walk 固有パラメータ

- `walk_type` : `rw` または `saw`
- `n_steps` : ステップ数
- `boundary` : 境界条件（例: `free`）
- `save_trajectory` : 軌跡保存の有無
- `save_trajectory_trials` : 軌跡保存試行数
- `output` : 結果 CSV の出力先
- `trajectory_output` : 軌跡 CSV の出力先

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
- `data/.../rw_traj.csv`, `data/.../saw_traj.csv` : 軌跡データ
- `data/.../final_steps.csv` : 最終ステップ / 寿命データ
- `data/.../summary.csv` : single / sweep の集計結果
- `data/.../time_vs_L.csv` : size_sweep の L 依存結果

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

Random walk シミュレーション時に `save_msd_distribution=1` を config で設定すると、各試行の Mean Square Displacement (MSD) 分布が `msd_distribution.csv` に保存されます。

```text
# config example
mode=random_walk
walk_type=rw
dim=2
n_steps=1000
n_trials=100
save_msd_distribution=1
```

出力ファイル構造:
```text
step,msd_trial_1,msd_trial_2,...,msd_trial_n
0,0.0,0.0,...,0.0
1,1.23,0.85,...,1.45
...
```

分析スクリプトで詳細統計を抽出:

```bash
python scripts/analysis/analyze_msd_distribution.py 2d saw data/2d/random_walk/msd_distribution.csv
```

出力:
- MSD 時間発展の中央値、四分位数
- 拡散指数の推定値
- 異常拡散の判定

### 実行ラッパー

- `bash scripts/run_analysis.sh <mode> <dim> <case>` : 分析ワークフロー
- `bash scripts/run_plot.sh <mode> ...` : 可視化ワークフロー

#### `scripts/run_analysis.sh` のモード例

- `fit_rw` : RW / SAW の拡散指数フィット
- `fit_survival` : 生存確率の指数フィット
- `fit_lifetime` : 寿命分布のフィット

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
