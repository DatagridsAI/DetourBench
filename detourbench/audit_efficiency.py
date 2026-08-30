#!/usr/bin/env python3
"""Do models differ in efficiency on instances they both solve?

Efficiency conditional on a model's own successes is selection-biased: a
weak model succeeds only where the task was easy for it, and looks
efficient there. Comparing two models on the instances *both* solved
removes that - same instances, same bounds, only the walk differs.

If the paired-on-common-successes comparison shows no reliable differences,
then the efficiency signal this benchmark is named for does not exist in
the current data, and attainment is a pass/fail score with extra decimals.
If it does show differences, the signal is real and the headline metric is
simply drowning it in the success term.
"""
import collections
import glob
import itertools
import json
import os
import random
import statistics
import sys

RUNS, INST = sys.argv[1], sys.argv[2]

bounds = {}
for d in glob.glob(f"{INST}/*"):
    o = json.load(open(f"{d}/oracle.json"))
    c, t = os.path.basename(d).split("__", 1)
    bounds[(t, c)] = o["lower_bound_steps"]

steps = {}
for p in glob.glob(f"{RUNS}/*/*/*.json"):
    pa = p.split(os.sep)
    task, corpus = pa[-3], pa[-2]
    model = os.path.basename(p).rsplit("_r", 1)[0]
    r = json.load(open(p))
    if r.get("outcome") == "api_error_abort" or not r["success"]:
        continue
    steps[(model, task, corpus)] = r["steps_total"] / bounds[(task, corpus)]

models = sorted({m for m, _, _ in steps})


def perm(d, iters=20000):
    obs = statistics.mean(d)
    rng = random.Random(0)
    hits = sum(1 for _ in range(iters)
               if abs(statistics.mean(x if rng.random() < .5 else -x
                                      for x in d)) >= abs(obs))
    return obs, (hits + 1) / (iters + 1)


print("steps/lb compared only on instances both models solved\n")
print(f"{'A':24s}{'B':24s}{'n':>4s}{'A':>7s}{'B':>7s}{'diff':>8s}{'p':>9s}")
any_sig = 0
for a, b in itertools.combinations(models, 2):
    common = [(t, c) for (m, t, c) in steps if m == a
              and (b, t, c) in steps]
    if len(common) < 5:
        continue
    da = [steps[(a, t, c)] for t, c in common]
    db = [steps[(b, t, c)] for t, c in common]
    diff = [x - y for x, y in zip(da, db)]
    obs, p = perm(diff)
    star = " *" if p < .05 else ""
    any_sig += p < .05
    print(f"{a[:23]:24s}{b[:23]:24s}{len(common):4d}"
          f"{statistics.mean(da):7.2f}{statistics.mean(db):7.2f}"
          f"{obs:+8.2f}{p:9.4f}{star}")

print(f"\npairs differing in efficiency on shared successes: {any_sig}")

print("\nsteps/lb distribution over all successful episodes")
allv = sorted(steps.values())
print(f"  n={len(allv)}  min {allv[0]:.2f}  median "
      f"{statistics.median(allv):.2f}  p90 {allv[int(.9*len(allv))]:.2f}  "
      f"max {allv[-1]:.2f}")
print(f"  exactly optimal: {sum(1 for v in allv if v == 1.0)} "
      f"({sum(1 for v in allv if v == 1.0)/len(allv):.0%})")
print(f"  within 1.25x:    {sum(1 for v in allv if v <= 1.25)} "
      f"({sum(1 for v in allv if v <= 1.25)/len(allv):.0%})")
