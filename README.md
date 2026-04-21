# Percolation Model

Cで実装したサイトパーコレーションシミュレーションです。  
2次元・3次元格子上でクラスタ構造を解析し、sweep実行や可視化まで行えます。

## 実装済み機能

- 2D / 3D サイトパーコレーション
- 連結成分（クラスタ）の抽出
- 最大連結成分・第2連結成分の解析
- configファイルによる single / sweep 実行
- n_trials による平均化
- 標準偏差の計算
- CSV 出力
- Python による可視化

---

## ディレクトリ構成

```text
project/
├── src/          # Cソースコード
├── include/      # ヘッダファイル
├── configs/      # 実行設定ファイル
├── scripts/      # Python可視化スクリプト
├── data/         # 出力CSV
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
## C のビルド方法
```
make clean
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
各パラメータ
- mode
  - single : 1つの p で実行
  - sweep : p を範囲で掃引
- dim
  - 格子の次元（2 または 3）
- L
  - 格子サイズ
  - 総サイト数は L^dim
- p
  - single モードでの占有確率
- p_start, p_end, dp
  - sweep モードでの p の開始・終了・刻み幅
- n_trials
  - 各 p に対する試行回数
  - 平均値・標準偏差の計算に使用
- save_cluster_sizes
  - クラスタサイズ一覧を保存するか
- save_top_coords
  - 上位クラスタの座標を保存するか

## 出力ファイル
### data/summary.csv

- single の場合:
```
p,dim,L,n_sites,n_occupied,n_clusters,largest_size,second_size
```
- sweep + n_trials の場合:
```
p,dim,L,n_sites,n_trials,mean_occupied,mean_clusters,mean_largest,mean_second,std_occupied,std_clusters,std_largest,std_second
```

### data/cluster_coords.csv
クラスタ構造の可視化用データ
singleモード実行時に、指定したクラスタの座標を出力します。
#### フォーマット
2Dの場合:
`site_index,x,y,cluster_rank`
3Dの場合:
`site_index,x,y,z,cluster_rank`
#### 各項目
- `site_index` : サイトのインデックス
- `x, y, z` : 格子状の座標
- `clurster`: 
  - 1 : 最大クラスタ
  - 2 : 第2クラスタ
#### 備考
- データは「最大クラスタ→第2クラスタ」の順に書き込まれる
- 可視化スクリプト(plot_cluster.py)で使用される
(可視化については次のPython 可視化のCluster Visulizationを参照)
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
python scripts/plot.py
```
### グラフで見ている量
- 最大連結成分
- 第2連結成分
- 正規化した最大連結成分 largest / n_sites
- 正規化した第2連結成分 second / n_sites
- 標準偏差（エラーバー）

第2連結成分は臨界点近傍でピークを持つため、臨界点の推定に有効です。

## Cluster Visulization (04_21追加)
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
```
python scripts/plot_clusters.py
```
#### 実行結果
- cluster_rankに応じて色分け表示される
- 最大クラスタ(青),第2クラスタ(赤)として描画される
---

## 現在の到達点
- 3D サイトパーコレーションで臨界点付近の挙動を再現
- 第2連結成分のピークから臨界点を確認
- 平均化と標準偏差付きの可視化まで実装

## 今後の展望
- 臨界点近傍での高分解能 sweep
- n_trials 増加による精度向上
- エラーバー付き解析の強化
- 有限サイズスケーリング
- bond percolation への拡張

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
