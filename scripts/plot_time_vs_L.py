import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

df = pd.read_csv("data/time_vs_L.csv")

logL = np.log(df["L"])
logT = np.log(df["time_sec"])

coef = np.polyfit(logL, logT, 1)
print("slope =", coef[0])
plt.loglog(df["L"], df["time_sec"], marker="o", label="Measured")
plt.xlabel("L")
plt.ylabel("Time (sec)")
plt.title("Scaling behavior")
plt.grid(True, which="both")
plt.legend()

plt.show()