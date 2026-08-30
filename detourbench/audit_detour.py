#!/usr/bin/env python3
"""Where do the steps go?

Two earlier versions of this got the classification wrong, so the basis is
worth stating.

The first used `dead_end_nodes`, which marks a node with no outgoing route
to the target. On a collection task that includes the provisions the optimal
path must gather - the filing endpoint opens only once both have been read,
so each is required and has no exit of its own. It labelled 45 of 48 nodes
dead on conflict_case, two of them on the oracle path, and reported a run
that finished in exactly the lower bound as having taken two detours.
n
The second recomputed the remaining bound after every step. That is the
right question and the wrong cost: the bound's search is over (visited,
inventory) states, so seeding it from a large visited set is exponential and
a single episode does not finish.

This one classifies against the proven optimum, precomputed once per
instance. The assumption it makes - that leaving the optimum is a detour -
would be wrong if an instance admitted a second route of the same length,
so that was checked: of 57 successes that finished in exactly the lower
bound, all 57 visited the same node set as the oracle. None was observed.
It remains an assumption about routes no model happened to take.

  on route     the node is on the proven optimum
  off route    a real node, not on it
  repeat       an identifier already used
  unresolved   an identifier matching nothing
"""
import collections
import glob
import json
import os
import sys

RUNS, INST = sys.argv[1], sys.argv[2]

cache = {}
def instance(inst):
    if inst not in cache:
        full = json.load(open(f"{inst}/graph_full.json"))
        o = json.load(open(f"{inst}/oracle.json"))
        g = full["graph"]
        by = {e["edge_id"]: e["to"] for es in g["edges"].values() for e in es}
        dest = {e["desc"]: e["to"] for es in g["edges"].values() for e in es}
        route = {full["meta"]["start"]} | {by[e] for e in o["oracle_edge_path"]}
        cache[inst] = (dest, route, o["lower_bound_steps"])
    return cache[inst]

tally = collections.defaultdict(collections.Counter)
for p in sorted(glob.glob(f"{RUNS}/*/*/*.json")):
    pa = p.split(os.sep)
    task, corpus = pa[-3], pa[-2]
    r = json.load(open(p))
    if r.get("outcome") == "api_error_abort" or not r.get("trajectory"):
        continue
    dest, route, lb = instance(f"{INST}/{corpus}__{task}")
    key = "success" if r["success"] else r.get("outcome", "failure")
    seen = set()
    for s in r["trajectory"]:
        ident = s["identifier"]
        node = dest.get(ident)
        if ident in seen:
            tally[key]["repeat"] += 1
        elif node is None:
            tally[key]["unresolved"] += 1
        elif node in route:
            tally[key]["on route"] += 1
        else:
            tally[key]["off route"] += 1
        seen.add(ident)

cols = ("on route", "off route", "repeat", "unresolved")
print(f"{'':22s}" + "".join(f"{c:>14s}" for c in cols) + "      total")
for key in sorted(tally, key=lambda k: -sum(tally[k].values())):
    row = tally[key]
    tot = sum(row.values()) or 1
    line = f"{key:22s}"
    for c in cols:
        line += f"{row[c]:>8d} ({row[c]/tot:2.0%})"
    print(line + f"{tot:>11d}")
