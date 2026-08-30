#!/usr/bin/env python3
"""How much choice did the agent actually face at each step?

Forty-seven percent of successes land exactly on the lower bound, which has
two very different explanations. Either the tasks reward knowing where to
look and a model that knows goes straight there - the claim being made - or
the route is a corridor and the model is reading instructions rather than
navigating. A step count cannot tell those apart.

Branching can. Replaying each trajectory through the environment gives, at
every step, the set of identifiers the agent had been shown and not yet
used. That is the size of the decision it actually faced. A corridor shows
one or two; a real search shows many.

Reported alongside: how many of the available options at each step were
dead ends, since choosing among options that all lead somewhere is a
different task from choosing among options where most lead nowhere.
"""
import collections
import glob
import json
import os
import statistics
import sys

from env import GraphEnv

RUNS, INST = sys.argv[1], sys.argv[2]

# how many nodes can never reach the target, per instance
dead = {}
for d in glob.glob(f"{INST}/*"):
    full = json.load(open(f"{d}/graph_full.json"))
    dead[os.path.basename(d)] = set(full["meta"].get("dead_end_nodes", []))

rows = []
for p in sorted(glob.glob(f"{RUNS}/*/*/*.json")):
    pa = p.split(os.sep)
    task, corpus = pa[-3], pa[-2]
    model = os.path.basename(p).rsplit("_r", 1)[0]
    r = json.load(open(p))
    if r.get("outcome") == "api_error_abort" or not r.get("trajectory"):
        continue
    inst = f"{INST}/{corpus}__{task}"
    o = json.load(open(f"{inst}/oracle.json"))
    env = GraphEnv(inst, seed=0, step_budget=999)
    used = set()
    choices = []
    for s in r["trajectory"]:
        known = {x["identifier"] for x in env.look()["known_resources"]}
        options = known - used
        choices.append(len(options))
        ident = s["identifier"]
        used.add(ident)
        try:
            env.access(ident)
        except Exception:
            break
        if env.done:
            break
    if choices:
        rows.append((task, corpus, model, r["success"], choices,
                     o["lower_bound_steps"]))

print(f"episodes replayed: {len(rows)}\n")

def summarise(label, sel):
    sub = [r for r in rows if sel(r)]
    if not sub:
        print(f"{label:34s} (none)")
        return
    first = [r[4][0] for r in sub]
    allc = [c for r in sub for c in r[4]]
    print(f"{label:34s} n={len(sub):3d}  options at step 1: "
          f"median {statistics.median(first):4.0f}  max {max(first):3d}   "
          f"across all steps: median {statistics.median(allc):4.0f}  "
          f"mean {statistics.mean(allc):5.1f}")

summarise("all episodes", lambda r: True)
summarise("successes", lambda r: r[3])
summarise("successes exactly on bound", lambda r: r[3] and len(r[4]) == r[5])
summarise("failures", lambda r: not r[3])
for t in sorted({r[0] for r in rows}):
    summarise(f"  task {t}", lambda r, t=t: r[0] == t)

print("\ndead ends as a share of the graph")
for name, ds in sorted(dead.items())[:6]:
    full = json.load(open(f"{INST}/{name}/graph_full.json"))
    n = len(full["graph"]["nodes"])
    print(f"  {name:34s} {len(ds):3d} / {n:3d} nodes ({len(ds)/n:.0%})")
