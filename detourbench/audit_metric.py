#!/usr/bin/env python3
"""Is attainment measuring efficiency, or is it success rate in disguise?

The suite is named for detour behaviour and scored with
attainment = oracle_lb / steps, failures counted zero. If that number is
almost perfectly predicted by success rate alone, then the efficiency
framing is decoration: we would be running a pass/fail benchmark and
reporting it with extra decimals, and the "measured against a provable
optimum" claim would be doing no work.

Three ways of asking:

  1. correlation between per-model success rate and per-model attainment;
  2. conditional efficiency - among successes only, how much do models
     differ in steps/lb? If they are all at 1.1, efficiency does not vary
     and only success does;
  3. what the ranking would be on efficiency alone, and whether it matches
     the attainment ranking.

The top model on this suite takes the most steps per success (kimi-k3 at
1.24), which is the shape that prompts the question.
"""
import collections
import glob
import json
import os
import statistics
import sys

from metrics import attainment_score

RUNS, INST = sys.argv[1], sys.argv[2]

bounds = {}
for d in glob.glob(f"{INST}/*"):
    o = json.load(open(f"{d}/oracle.json"))
    c, t = os.path.basename(d).split("__", 1)
    bounds[(t, c)] = o["lower_bound_steps"]

by = collections.defaultdict(list)
for p in glob.glob(f"{RUNS}/*/*/*.json"):
    pa = p.split(os.sep)
    task, corpus = pa[-3], pa[-2]
    model = os.path.basename(p).rsplit("_r", 1)[0]
    r = json.load(open(p))
    if r.get("outcome") == "api_error_abort":
        continue
    lb = bounds[(task, corpus)]
    by[model].append((r["success"], r["steps_total"], lb))


def pearson(xs, ys):
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = (sum((a - mx) ** 2 for a in xs) *
           sum((b - my) ** 2 for b in ys)) ** .5
    return num / den if den else float("nan")


rows = []
for m, eps in by.items():
    succ = [e for e in eps if e[0]]
    rows.append((
        m,
        len(succ) / len(eps),
        statistics.mean(attainment_score(*e) if e[0] else 0.0 for e in eps),
        statistics.mean(e[1] / e[2] for e in succ) if succ else float("nan"),
        statistics.mean(e[2] / e[1] for e in succ) if succ else float("nan"),
    ))
rows.sort(key=lambda r: -r[2])

print(f"{'model':26s}{'success':>9s}{'attain':>8s}{'steps/lb':>10s}"
      f"{'eff|success':>13s}")
for m, s, a, r, e in rows:
    print(f"{m:26s}{s:9.2f}{a:8.3f}{r:10.2f}{e:13.3f}")

print(f"\ncorrelation success rate vs attainment across models: "
      f"{pearson([r[1] for r in rows], [r[2] for r in rows]):+.4f}")
print(f"correlation efficiency-given-success vs attainment:    "
      f"{pearson([r[4] for r in rows], [r[2] for r in rows]):+.4f}")

eff_rank = [m for m, _, _, _, _ in sorted(rows, key=lambda r: -r[4])]
att_rank = [m for m, _, _, _, _ in rows]
print(f"\nranking by attainment          {' > '.join(x[:12] for x in att_rank)}")
print(f"ranking by efficiency alone    {' > '.join(x[:12] for x in eff_rank)}")

print("\nspread of each component across models")
print(f"  success rate            {min(r[1] for r in rows):.2f} - "
      f"{max(r[1] for r in rows):.2f}   (ratio "
      f"{max(r[1] for r in rows)/max(1e-9,min(r[1] for r in rows)):.1f}x)")
eff = [r[4] for r in rows]
print(f"  efficiency | success    {min(eff):.2f} - {max(eff):.2f}   (ratio "
      f"{max(eff)/min(eff):.1f}x)")
