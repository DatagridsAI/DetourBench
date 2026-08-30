#!/usr/bin/env python3
"""Are 39 instances really 39, or 13 corpora counted three times?

The paired test treats each (task, corpus) pair as an instance. Three of
them share a corpus, and a corpus is a whole citation graph - if a model
that does well on title 12's conflict_case does well on title 12's other
two for reasons belonging to title 12 rather than to the model, then the
effective sample is closer to 13 and every p-value is optimistic.

Two ways at it, both conservative:

  1. Aggregate to corpus level - average a model's three tasks within a
     corpus and pair on the 13 corpora. Any pair that stays significant
     under this cannot be an artefact of counting a corpus three times.
  2. Measure the correlation directly: how much of the variance in scores
     is between corpora rather than within them.

If (1) keeps the significant pairs significant, the 39-instance analysis
stands as reported. If it does not, the honest number is 13 and the
conclusions need restating.
"""
import collections
import glob
import json
import os
import random
import statistics
import sys

from metrics import attainment_score

RUNS, INST = sys.argv[1], sys.argv[2]

bounds = {}
for d in glob.glob(f"{INST}/*"):
    o = json.load(open(f"{d}/oracle.json"))
    c, t = os.path.basename(d).split("__", 1)
    bounds[(t, c)] = o["lower_bound_steps"]

cell = {}
for p in glob.glob(f"{RUNS}/*/*/*.json"):
    pa = p.split(os.sep)
    task, corpus = pa[-3], pa[-2]
    model = os.path.basename(p).rsplit("_r", 1)[0]
    r = json.load(open(p))
    if r.get("outcome") == "api_error_abort":
        continue
    lb = bounds[(task, corpus)]
    cell[(model, task, corpus)] = (
        attainment_score(r["success"], r["steps_total"], lb)
        if r["success"] else 0.0)

models = sorted({m for m, _, _ in cell})
tasks = sorted({t for _, t, _ in cell})
corpora = sorted({c for _, _, c in cell})


def perm(d, iters=20000):
    if len(d) < 2:
        return float("nan"), float("nan")
    obs = statistics.mean(d)
    rng = random.Random(0)
    hits = sum(1 for _ in range(iters)
               if abs(statistics.mean(x if rng.random() < .5 else -x
                                      for x in d)) >= abs(obs))
    return obs, (hits + 1) / (iters + 1)


print("pair-level: instance pairing (n=39) vs corpus pairing (n=13)\n")
print(f"{'A':24s}{'B':24s}{'inst p':>9s}{'corpus p':>10s}{'gap':>7s}")
flips = 0
for i, a in enumerate(models):
    for b in models[i + 1:]:
        di = [cell[(a, t, c)] - cell[(b, t, c)]
              for t in tasks for c in corpora
              if (a, t, c) in cell and (b, t, c) in cell]
        dc = []
        for c in corpora:
            xs = [cell[(a, t, c)] for t in tasks if (a, t, c) in cell]
            ys = [cell[(b, t, c)] for t in tasks if (b, t, c) in cell]
            if len(xs) == len(tasks) and len(ys) == len(tasks):
                dc.append(statistics.mean(xs) - statistics.mean(ys))
        gi, pi = perm(di)
        gc, pc = perm(dc)
        mark = ""
        if (pi < .05) != (pc < .05):
            mark = "  <- verdict changes"
            flips += 1
        print(f"{a[:23]:24s}{b[:23]:24s}{pi:9.4f}{pc:10.4f}{gi:7.2f}{mark}")

print(f"\npairs whose verdict changes under corpus pairing: {flips}")

# variance between corpora vs within
print("\nvariance decomposition of per-cell attainment")
for m in models:
    vals = {(t, c): cell[(m, t, c)] for t in tasks for c in corpora
            if (m, t, c) in cell}
    if len(vals) < 6:
        continue
    by_corpus = collections.defaultdict(list)
    for (t, c), v in vals.items():
        by_corpus[c].append(v)
    means = [statistics.mean(v) for v in by_corpus.values() if v]
    within = [statistics.pvariance(v) for v in by_corpus.values()
              if len(v) > 1]
    print(f"  {m:24s} between-corpus var {statistics.pvariance(means):.3f}"
          f"   mean within-corpus var {statistics.mean(within):.3f}")
