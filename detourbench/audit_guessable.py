#!/usr/bin/env python3
"""Can the target be reached without doing the work?

The whole construction rests on an agent only being able to act on
identifiers it has been shown. If the success endpoint can be called
straight from the start - because the URL is guessable, or because the
engine resolves an identifier it has not revealed - then the lower bound
describes a route nobody has to take, the scores measure nothing, and the
random baseline being near zero would only mean random does not guess
plausible URLs, which a language model very well might.

Three attacks, from the start state:

  1. call the exact success identifier taken from the graph;
  2. call it after reading only the seed, which is what an agent has after
     one step;
  3. call plausible constructed variants of the filing endpoint - the shape
     a model would produce from the ticket text alone.

Any of them succeeding is fatal to the design, not a tuning problem.
"""
import glob
import json
import os
import re
import sys

from env import GraphEnv

INST = sys.argv[1]

def target_edge(g, meta):
    for src, es in g["edges"].items():
        for e in es:
            if e["to"] == meta["target"]:
                return src, e
    return None, None


bad = []
checked = 0
for d in sorted(glob.glob(f"{INST}/*")):
    name = os.path.basename(d)
    full = json.load(open(f"{d}/graph_full.json"))
    g, meta = full["graph"], full["meta"]
    o = json.load(open(f"{d}/oracle.json"))
    src, e = target_edge(g, meta)
    if e is None:
        bad.append(f"{name}: no edge into target")
        continue
    checked += 1
    ident = e["desc"]

    # 1. straight at the target from the start
    env = GraphEnv(d, seed=0, step_budget=o["step_budget"])
    r = env.access(ident)
    if r.get("ok"):
        bad.append(f"{name}: SUCCESS ENDPOINT REACHABLE FROM START -> {ident}")

    # 2. after one step (read the seed, which the ticket names)
    env2 = GraphEnv(d, seed=0, step_budget=o["step_budget"])
    first = [x for x in env2.look()["known_resources"]]
    if first:
        env2.access(first[0]["identifier"])
    r2 = env2.access(ident)
    if r2.get("ok") and env2.success:
        bad.append(f"{name}: SUCCESS AFTER ONE STEP via {ident}")

    # 3. constructed variants a model could write from the ticket alone
    base = re.sub(r"\?.*$", "", ident)
    variants = [base, base + "?", ident.replace("?", "/"),
                base + "/submit", base.rstrip("/") + "/"]
    for v in variants:
        if v == ident:
            continue
        env3 = GraphEnv(d, seed=0, step_budget=o["step_budget"])
        r3 = env3.access(v)
        if r3.get("ok"):
            bad.append(f"{name}: CONSTRUCTED VARIANT ACCEPTED -> {v}")

print(f"instances checked: {checked}")
print(f"problems: {len(bad)}")
for x in bad[:15]:
    print("  -", x)
if not bad:
    print("\nno instance lets the target be reached without the route: the "
          "engine refuses identifiers it has not revealed, and near-miss "
          "identifiers are not resolved.")
