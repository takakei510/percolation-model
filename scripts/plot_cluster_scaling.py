import pandas as pd
import matplotlib.pyplot as plt

# 読み込み
df = pd.read_csv("data/2d/time_vs_L.csv")

# 正規化
df["largest_norm"] = df["mean_largest"] / df["n_sites"]
df["second_norm"] = df["mean_second"] / df["n_sites"]

# -------------------------
# ① 絶対値プロット
# -------------------------
plt.figure()

plt.plot(df["L"], df["mean_largest"], marker="o", label="Largest")
plt.plot(df["L"], df["mean_second"], marker="o", label="Second")

plt.xlabel("L")
plt.ylabel("Cluster size")
plt.title("Cluster size vs L")
plt.legend()
plt.grid(True)

plt.show()


# -------------------------
# ② 正規化プロット（重要）
# -------------------------
plt.figure()

plt.plot(df["L"], df["largest_norm"], marker="o", label="Largest / N")
plt.plot(df["L"], df["second_norm"], marker="o", label="Second / N")

plt.xlabel("L")
plt.ylabel("Normalized cluster size")
plt.title("Normalized cluster size vs L")
plt.legend()
plt.grid(True)

plt.show()