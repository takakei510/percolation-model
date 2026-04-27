# Percolation Model

Cで実装したサイトパーコレーションシミュレーションです。  
2次元・3次元格子上でクラスタ構造を解析し、sweep実行や可視化まで行えます。

## 実装済み機能

- 2D / 3D サイトパーコレーション
- 連結成分（クラスタ）の抽出
- 最大連結成分・第2連結成分の解析
- configファイルによる実行管理
- single / sweep / size_sweep 実行
- n_trials による平均化
- 標準偏差の計算
- CSV 出力
- Python による可視化
- クラスタ構造のアニメーション表示（2D / 3D）


---

## ディレクトリ構成

```text
project/
├── src/          # Cソースコード
├── include/      # ヘッダファイル
├── configs/      # 実行設定ファイル
├── scripts/      # Python可視化スクリプト
├── data/         # 出力CSV（Git管理外）
├── build/        # 実行ファイル
├── Makefile
└── README.md
```

## 必要環境
C
- gcc
- make
Python
- Python 3
- pandas
- matplotlib
- numpy

## Pythonライブラリ

必要なライブラリは requirements.txt に記載されている。

インストール：

```bash
pip install -r requirements.txt
```
主なライブラリ：
- numpy
- pandas
- matplotlib
- pillow（アニメーション保存用）

## C のビルド方法z
make
```
実行ファイルは build/main に作られます。

## 実行方法
single 実行
```
./build/main configs/config_single.txt
```
sweep 実行
```
./build/main configs/config_sweep.txt
```
size_sweep 実行
```
./build/main configs/config_size_sweep_2d.txt
./build/main configs/config_size_sweep_3d.txt
```
## config説明 
ファイル例
configs/config_single.txt
```
mode=single
dim=3
L=100
p=0.31
n_trials=1
save_cluster_sizes=0
save_top_coords=0
```
configs/config_sweep.txt
```
mode=sweep
dim=3
L=100
p_start=0.10
p_end=0.80
dp=0.01
n_trials=10
save_cluster_sizes=0
save_top_coords=0
```
configs/config_size_sweep.txt
```
mode=size_sweep
dim=2
p=0.5927
L_start=16
L_max=512
L_multiplier=2
n_trials=5
cluster_view_mode=top2
```
各パラメータ
- mode
  - single : 1つの p で実行
  - sweep : p を範囲で掃引
  - size_sweep : L掃引
- dim
  - 格子の次元（2 または 3）
- L
  - 格子サイズ
  - 総サイト数は L^dim
- L_start: size_sweep の開始サイズ
- L_max: size_sweep の最大サイズ
- L_multiplier: L の増加倍率
- p
  - 占有確率
- p_start, p_end, dp
  - sweep モードでの p の開始・終了・刻み幅
- n_trials
  - 各 p に対する試行回数
  - 平均値・標準偏差の計算に使用
- cluster_view_mode
  - クラスタ可視化の表示モード
    - largest_only  : 最大クラスタのみ
    - second_only   : 第2クラスタのみ
    - top2          : 最大・第2クラスタ
- save_cluster_sizes
  - クラスタサイズ一覧を保存するか
- save_top_coords
  - 上位クラスタの座標を保存するか

## 出力ファイル

### summary.csv(single / sweep)

```
data/summary.csv
```
single の場合:
```
p,dim,L,n_sites,n_occupied,n_clusters,largest_size,second_size
```
sweep の場合:
```
p,dim,L,n_sites,n_trials,mean_occupied,mean_clusters,mean_largest,mean_second,std_occupied,std_clusters,std_largest,std_second
```
size_sweep の場合:
```
data/2d/time_vs_L.csv
data/3d/time_vs_L.csv
```
time_vs_L.csv は計算時間およびクラスタサイズのスケーリング解析に使用される。

内容：
```
L,n_sites,n_trials,time_sec,mean_largest,mean_second,std_largest,std_second
```
クラスタ構造
```
data/2d/size_sweep_clusters/
data/3d/size_sweep_clusters/
```
CSV形式：

- 2D
```
site_index,x,y,cluster_rank
```
- 3D
```
site_index,x,y,z,cluster_rank
```
---
#### 各項目
- `site_index` : サイトのインデックス
- `x, y, z` : 格子状の座標
- `cluster`: 
  - 1 : 最大クラスタ
  - 2 : 第2クラスタ
#### 備考
- データは「最大クラスタ→第2クラスタ」の順に書き込まれる
- 可視化スクリプト(plot_cluster.py)で使用される
(可視化については次のPython 可視化のCluster Visualizationを参照)
## Python 可視化

### 仮想環境を使う場合:
```
source venv/bin/activate
```
ライブラリインストール:
```
pip install -r requirements.txt
```
### プロット実行:
```
scripts/
├── plot.py
├── plot.cluster.py
├── plot_time_vs_L.py
├── plot_cluster_scaling.py
├── animate_clusters_vs_L.py
```
基本プロット：

```bash
python scripts/plot.py
```
L依存の計算時間：
```bash
python scripts/plot_time_vs_L.py
```
クラスタサイズ解析：
```bash
python scripts/plot_cluster_scaling.py
```
### グラフで見ている量
- 最大連結成分
- 第2連結成分
- 正規化した最大連結成分 largest / n_sites
- 正規化した第2連結成分 second / n_sites
- 標準偏差（エラーバー）

第2連結成分は臨界点近傍でピークを持つため、臨界点の推定に有効です。

## Cluster Visualization
最大クラスタ・第2クラスタの構造を2D/3Dで可視化できます。
### 表示モード
configファイルに`cluster_view_mode=`で以下を指定可能:
- `largest_only`: 最大クラスタのみ表示
- `second_only` : 第2クラスタのみ表示
- `top2` : 最大クラスタと第2クラスタを同時表示
例：
cluster_view_mode=top2
### クラスタ可視化との関係
`cluster_coords.csv`は以下の可視化スクリプトで使用される
```bash
python scripts/plot_cluster.py
```
#### 実行結果
- cluster_rankに応じて色分け表示される
- 最大クラスタ(青),第2クラスタ(赤)として描画される

## size_sweep（L依存解析）
### 計算時間プロット
```bash
python scripts/plot_time_vs_L.py
```
### クラスタサイズ解析
```bash
python scripts/plot_cluster_scaling.py
```
---
### クラスタアニメーション
#### 実行
```
bash scripts/run_anim.sh configs/config_size_sweep_2d.txt
bash scripts/run_anim.sh configs/config_size_sweep_3d.txt
```
#### 出力
```
data/2d/animations/clusters.gif
data/3d/animations/clusters.gif
```
### 物理的知見
- 系サイズ増加により最大クラスタが支配的になる
- 第2クラスタの相対サイズは減少する
- 有限サイズ効果を可視化できる

## 現在の到達点
- 臨界点近傍の挙動を再現
- 第2クラスタの挙動を確認
- スケーリング則の検証
- 可視化・アニメーションまで実装

## 今後の展望
- 臨界点の精密推定
- 有限サイズスケーリング解析
- p sweepによるピーク解析
- 3Dでの詳細検証
- bond percolation への拡張

## 注意
data/ は生成物のため Git 管理しません。
---

## 最短実行手順
### C 実行
```
make clean
make
./build/main configs/config_sweep.txt
```
### Python 可視化
```
source venv/bin/activate
python scripts/plot.py
```
#### animateの場合
```
bash scripts/run_anim.sh configs/config_size_sweep_2d.txt
```