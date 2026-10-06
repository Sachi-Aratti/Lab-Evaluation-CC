#!/usr/bin/env python3
"""
Workload generator + resource monitor for the Lost & Found microservices.

For every concurrency level it:
  1. runs ApacheBench (ab) for a fixed duration against one endpoint,
  2. streams `docker stats` for the chosen containers *while the load runs*,
  3. repeats the run several times and averages the repetitions.

Output (in --outdir):
  workload_results.csv     one row per concurrency level (averages of the runs)
  raw/ab_c<N>_run<K>.txt   untouched ab output
  raw/stats_c<N>_run<K>.csv  every docker-stats sample taken during that run

Example (original PHP stack):
  python3 scripts/run_benchmark.py --url http://localhost:8082/ \
      --containers lostfound-item:Item lostfound-handover:Handover lostfound-user:User \
      --outdir results

Requires: ApacheBench (apache2-utils / Apache's ab.exe), Docker.
"""
import argparse
import csv
import os
import re
import statistics
import subprocess
import threading
import time

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
UNITS = {"B": 1 / 1048576, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "kB": 1 / 1048.576, "MB": 0.953674, "GB": 976.5625}


def to_mib(text):
    m = re.match(r"([\d.]+)\s*([A-Za-z]+)", text.strip())
    return float(m.group(1)) * UNITS[m.group(2)] if m else 0.0


class StatsSampler:
    """Streams `docker stats` and stores timestamped samples."""

    def __init__(self, names):
        self.samples = []  # (t, container, cpu%, mem_mib, mem%)
        self.proc = subprocess.Popen(
            ["docker", "stats", "--format", "{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}}", *names],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        for raw in self.proc.stdout:
            line = ANSI.sub("", raw).strip()
            parts = line.split(",")
            if len(parts) != 4 or not parts[1].endswith("%"):
                continue
            try:
                self.samples.append((time.time(), parts[0], float(parts[1].rstrip("%")),
                                     to_mib(parts[2].split("/")[0]), float(parts[3].rstrip("%"))))
            except ValueError:
                pass

    def stop(self):
        self.proc.terminate()
        self.proc.wait()


def parse_ab(text):
    def num(pattern):
        m = re.search(pattern, text)
        return float(m.group(1)) if m else 0.0
    return {
        "complete": int(num(r"Complete requests:\s+(\d+)")),
        "failed": int(num(r"Failed requests:\s+(\d+)")),
        "non2xx": int(num(r"Non-2xx responses:\s+(\d+)")),
        "rps": num(r"Requests per second:\s+([\d.]+)"),
        "mean_ms": num(r"Time per request:\s+([\d.]+) \[ms\] \(mean\)\s*\n"),
        "p50_ms": num(r"\n\s+50%\s+(\d+)"),
        "p95_ms": num(r"\n\s+95%\s+(\d+)"),
        "max_ms": num(r"\n\s+100%\s+(\d+)"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--containers", nargs="+", required=True, help="container:Label ...")
    ap.add_argument("--outdir", default="results")
    ap.add_argument("--levels", type=int, nargs="+", default=[1, 2, 4, 8, 16])
    ap.add_argument("--duration", type=int, default=15, help="seconds per run")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--warmup", type=int, default=5)
    ap.add_argument("--ab", default="ab")
    a = ap.parse_args()

    cont = [c.split(":") for c in a.containers]
    names = [c[0] for c in cont]
    os.makedirs(os.path.join(a.outdir, "raw"), exist_ok=True)

    def run_ab(c, seconds):
        out = subprocess.run([a.ab, "-q", "-t", str(seconds), "-n", "100000000", "-c", str(c), a.url],
                             capture_output=True, text=True).stdout
        return out

    print(f"Warm-up ({a.warmup}s, c=4) ...")
    run_ab(4, a.warmup)
    time.sleep(3)

    rows = []
    for c in a.levels:
        runs = []
        for k in range(1, a.reps + 1):
            sampler = StatsSampler(names)
            time.sleep(2)                      # let the stats stream settle
            t0 = time.time()
            out = run_ab(c, a.duration)
            t1 = time.time()
            sampler.stop()
            open(os.path.join(a.outdir, "raw", f"ab_c{c}_run{k}.txt"), "w").write(out)
            ab = parse_ab(out)

            # keep only samples taken during the load (skip first second of ramp-up)
            win = [s for s in sampler.samples if t0 + 1 <= s[0] <= t1]
            with open(os.path.join(a.outdir, "raw", f"stats_c{c}_run{k}.csv"), "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["unix_time", "container", "cpu_percent", "mem_mib", "mem_percent"])
                w.writerows(win)
            per = {}
            for name in names:
                ss = [s for s in win if s[1] == name]
                per[name] = {
                    "cpu": statistics.mean(s[2] for s in ss) if ss else 0.0,
                    "cpu_max": max((s[2] for s in ss), default=0.0),
                    "mem": statistics.mean(s[3] for s in ss) if ss else 0.0,
                    "mem_pct": statistics.mean(s[4] for s in ss) if ss else 0.0,
                    "n": len(ss),
                }
            runs.append((ab, per))
            print(f"c={c:<2} run{k}: {ab['rps']:8.2f} req/s  mean {ab['mean_ms']:8.3f} ms  "
                  f"p95 {ab['p95_ms']:5.0f} ms  failed {ab['failed']}  non2xx {ab['non2xx']}  "
                  + "  ".join(f"{cont[i][1]} {per[n]['cpu']:.1f}%/{per[n]['mem']:.1f}MiB" for i, n in enumerate(names)))
            time.sleep(3)

        m = lambda key: statistics.mean(r[0][key] for r in runs)
        row = {
            "Concurrent Requests": c,
            "Response Time (ms)": round(m("mean_ms"), 3),
            "Throughput (req/s)": round(m("rps"), 2),
            "Failed Requests": sum(r[0]["failed"] + r[0]["non2xx"] for r in runs),
        }
        for (name, label) in cont:
            row[f"{label} CPU (%)"] = round(statistics.mean(r[1][name]["cpu"] for r in runs), 2)
            row[f"{label} Memory (MiB)"] = round(statistics.mean(r[1][name]["mem"] for r in runs), 2)
        row.update({
            "Total Requests Completed": sum(r[0]["complete"] for r in runs),
            "p50 (ms)": round(m("p50_ms"), 1),
            "p95 (ms)": round(m("p95_ms"), 1),
            "Max (ms)": round(max(r[0]["max_ms"] for r in runs), 1),
            "Throughput StdDev (req/s)": round(statistics.pstdev(r[0]["rps"] for r in runs), 2),
        })
        for (name, label) in cont:
            row[f"{label} CPU Peak (%)"] = round(max(r[1][name]["cpu_max"] for r in runs), 2)
            row[f"{label} Memory (%)"] = round(statistics.mean(r[1][name]["mem_pct"] for r in runs), 3)
        rows.append(row)

    with open(os.path.join(a.outdir, "workload_results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nSaved {os.path.join(a.outdir, 'workload_results.csv')}")


if __name__ == "__main__":
    main()
