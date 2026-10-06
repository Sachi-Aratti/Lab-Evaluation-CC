#!/usr/bin/env python3
"""Create the four lab graphs from results/workload_results.csv.
Usage: python3 scripts/make_graphs.py [results_dir]   (needs pandas + matplotlib)"""
import sys, os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

d = sys.argv[1] if len(sys.argv) > 1 else "results"
df = pd.read_csv(os.path.join(d, "workload_results.csv"))
x = df["Concurrent Requests"]
svc = [c.replace(" CPU (%)", "") for c in df.columns if c.endswith(" CPU (%)")]


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(d, name), dpi=150)
    plt.close(fig)


fig, ax = plt.subplots(figsize=(7, 4.5))
ax.plot(x, df["Response Time (ms)"], marker="o", label="Average")
if "p95 (ms)" in df:
    ax.plot(x, df["p95 (ms)"], marker="s", linestyle="--", label="95th percentile")
ax.set(xlabel="Concurrent Requests", ylabel="Response Time (ms)", title="Concurrent Requests vs Average Response Time", xticks=list(x))
ax.grid(alpha=.3); ax.legend()
save(fig, "response_time.png")

fig, ax = plt.subplots(figsize=(7, 4.5))
ax.plot(x, df["Throughput (req/s)"], marker="o", color="tab:green")
ax.set(xlabel="Concurrent Requests", ylabel="Throughput (req/s)", title="Concurrent Requests vs Throughput", xticks=list(x))
ax.grid(alpha=.3)
save(fig, "throughput.png")

fig, ax = plt.subplots(figsize=(7, 4.5))
for s in svc:
    ax.plot(x, df[f"{s} CPU (%)"], marker="o", label=f"{s} Service")
ax.set(xlabel="Concurrent Requests", ylabel="CPU Utilization (% of one core)", title="Concurrent Requests vs CPU Utilization", xticks=list(x))
ax.grid(alpha=.3); ax.legend()
save(fig, "cpu_utilization.png")

fig, ax = plt.subplots(figsize=(7, 4.5))
for s in svc:
    ax.plot(x, df[f"{s} Memory (MiB)"], marker="o", label=f"{s} Service")
ax.set(xlabel="Concurrent Requests", ylabel="Memory Usage (MiB)", title="Concurrent Requests vs Memory Utilization", xticks=list(x))
ax.grid(alpha=.3); ax.legend()
save(fig, "memory_utilization.png")
print("Graphs written to", d)
