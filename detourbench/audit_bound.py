#!/usr/bin/env python3
"""Is the lower bound actually minimal?

"Provably exact" is the load-bearing claim: attainment divides by this
number, so a bound that is too high inflates every score and one that is
too low would have shown up as an impossible success. The BFS that computes
it prunes first - dropping nodes that reach neither the target, nor a
credential, nor anything named by requires_visited - on the argument that
visiting such a node spends a step and reveals nothing usable. The argument
is sound but it has never been checked against the unpruned search.

So: recompute every bound with pruning disabled and compare. Any instance
where the unpruned search finds something shorter means the pruning is
dropping a node an optimal walk needs, and every attainment score computed
against that instance is wrong.

Independently, replay the recorded oracle path through a live environment
and confirm it both succeeds and takes exactly that many steps - a bound
nothing achieves is not a bound either.
"""
import glob
import json
import os
import sys

import generate
from env import GraphEnv

INST = sys.argv[1]

src = open(generate.__file__, encoding="utf-8").read()
if "reaches = set(keep_targets)" not in src:
    raise SystemExit("pruning block not in the expected form")

# Rebuild compute_lower_bound with the pruning neutralised: keep every node.
patched = src.replace(
    "    edges = {u: [e for e in es if e[\"to\"] in reaches]",
    "    reaches = set(edges) | {e['to'] for es in edges.values() for e in es}\n"
    "    edges = {u: [e for e in es if e[\"to\"] in reaches]", 1)
ns = {"__file__": generate.__file__, "__name__": "generate_unpruned"}
exec(compile(patched, "generate_unpruned", "exec"), ns)
unpruned = ns["compute_lower_bound"]

worse = []
unreachable = []
instance_dirs = [d for d in sorted(glob.glob(f"{INST}/*"))
                 if os.path.isdir(d)
                 and os.path.isfile(os.path.join(d, "graph_full.json"))
                 and os.path.isfile(os.path.join(d, "oracle.json"))]
for d in instance_dirs:
    name = os.path.basename(d)
    full = json.load(open(f"{d}/graph_full.json"))
    o = json.load(open(f"{d}/oracle.json"))
    g, meta = full["graph"], full["meta"]
    lb = o["lower_bound_steps"]

    try:
        lb2, _ = unpruned(g, meta)
    except Exception as exc:
        worse.append(f"{name}: unpruned search failed - {exc}")
        continue
    if lb2 != lb:
        worse.append(f"{name}: pruned {lb} vs unpruned {lb2}")

    # and the recorded path must actually achieve it
    env = GraphEnv(d, seed=0, step_budget=lb + 5)
    by = {e["edge_id"]: e for es in g["edges"].values() for e in es}
    for eid in o["oracle_edge_path"]:
        if env.done:
            break
        env.access(by[eid]["desc"])
    if not env.success or env.steps_used != lb:
        unreachable.append(f"{name}: oracle path -> success={env.success} "
                           f"steps={env.steps_used} lb={lb}")

n = len(instance_dirs)
print(f"instances: {n}")
print(f"bounds that change without pruning: {len(worse)}")
for x in worse[:10]:
    print("  -", x)
print(f"oracle paths that do not achieve the bound: {len(unreachable)}")
for x in unreachable[:10]:
    print("  -", x)
if not worse and not unreachable:
    print("\nthe bound is unchanged by pruning and is achieved exactly on "
          "every instance: minimal and attained.")
