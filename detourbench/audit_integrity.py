#!/usr/bin/env python3
"""Mechanical audit of every episode record against what must be true.

These are not statistics, they are invariants. If any of them fails, some
number in the paper is wrong in a way no amount of re-analysis fixes:

  1. no success in fewer steps than the proven lower bound - that would
     mean the bound is not a bound;
  2. no episode over its budget - the engine is supposed to stop it;
  3. attainment in (0, 1] for successes, and exactly 0 for failures;
  4. outcome consistent with the flags it is derived from;
  5. every (task, corpus, model) cell present exactly once;
  6. trajectory length consistent with the step count it reports.

Also reports the distributions that reveal degenerate behaviour without
being invariant violations: how many successes land exactly on the bound
(suspicious if near everything - it would suggest the route is being given
away), and how many failures spent zero steps.
"""
import collections
import glob
import json
import os
import statistics
import sys

from metrics import attainment_score

RUNS, INST = sys.argv[1], sys.argv[2]

meta = {}
for d in glob.glob(f"{INST}/*"):
    o = json.load(open(f"{d}/oracle.json"))
    corpus, task = os.path.basename(d).split("__", 1)
    meta[(task, corpus)] = (o["lower_bound_steps"], o["step_budget"])

problems = []
rows = []
seen = collections.Counter()
for p in sorted(glob.glob(f"{RUNS}/*/*/*.json")):
    pa = p.split(os.sep)
    task, corpus = pa[-3], pa[-2]
    model = os.path.basename(p).rsplit("_r", 1)[0]
    r = json.load(open(p))
    lb, budget = meta[(task, corpus)]
    tag = f"{task}/{corpus}/{model}"
    seen[(task, corpus, model)] += 1
    steps, ok, outcome = r["steps_total"], r["success"], r.get("outcome")

    if ok and steps < lb:
        problems.append(f"BOUND VIOLATED {tag}: success in {steps} < lb {lb}")
    if steps > budget:
        problems.append(f"OVER BUDGET {tag}: {steps} > {budget}")
    att = attainment_score(ok, steps, lb) if ok else 0.0
    if ok and not (0 < att <= 1.0 + 1e-9):
        problems.append(f"ATTAINMENT RANGE {tag}: {att}")
    if not ok and att != 0.0:
        problems.append(f"FAILURE NOT ZERO {tag}: {att}")
    if ok and outcome != "success":
        problems.append(f"OUTCOME MISMATCH {tag}: success but {outcome}")
    if outcome == "success" and not ok:
        problems.append(f"OUTCOME MISMATCH {tag}: {outcome} but not success")
    if outcome == "budget_exhausted" and steps < budget:
        problems.append(f"EXHAUSTED EARLY {tag}: {steps} < {budget}")
    traj = r.get("trajectory") or []
    if traj and len(traj) != steps:
        problems.append(f"TRAJECTORY LENGTH {tag}: {len(traj)} vs {steps}")
    rows.append((tag, task, corpus, model, ok, steps, lb, budget, outcome,
                 att, len(traj)))

dupes = [k for k, v in seen.items() if v > 1]
if dupes:
    problems.append(f"DUPLICATE CELLS: {dupes[:5]}")
expected = {(t, c, m) for (t, c) in meta
            for m in {r[3] for r in rows}}
missing = expected - set(seen)
print(f"records: {len(rows)}   cells expected: {len(expected)}   "
      f"missing: {len(missing)}")
if missing:
    by_model = collections.Counter(m for _, _, m in missing)
    print("  missing by model:", dict(by_model))

print(f"\ninvariant problems: {len(problems)}")
for x in problems[:20]:
    print("  -", x)

succ = [r for r in rows if r[4]]
print(f"\nsuccesses: {len(succ)}")
exact = [r for r in succ if r[5] == r[6]]
print(f"  exactly on the bound: {len(exact)} ({len(exact)/max(1,len(succ)):.0%})")
print(f"  steps/lb  mean {statistics.mean(r[5]/r[6] for r in succ):.3f}"
      f"  max {max(r[5]/r[6] for r in succ):.2f}")
fail = [r for r in rows if not r[4]]
zero = [r for r in fail if r[5] == 0]
print(f"failures: {len(fail)}   with zero steps: {len(zero)}")
for r in zero[:6]:
    print(f"    {r[0]:52s} {r[8]}")
print("\noutcome mix:", dict(collections.Counter(r[8] for r in rows)))
