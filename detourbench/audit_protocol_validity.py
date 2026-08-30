#!/usr/bin/env python3
"""Does the seed produce a different problem, and can a null agent score?

The position check turned up five values repeated eight times each, which
is what it looks like when the seed changes nothing. Worth knowing before
any claim resting on instance counts: five instances run five times is
five problems, not twenty-five.
"""
import glob, json, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate import build_graph                                # noqa: E402

TOPOS = ["t12_latest", "t14_latest", "t19_latest", "t29_latest",
         "t47_latest"]

print("=== seed 是否改变实例 ===")
for topo in TOPOS:
    sigs = set()
    for seed in range(8):
        g, m = build_graph(random.Random(seed), "finance_pipeline", topo)
        sigs.add((m["governs"], tuple(m["candidates"]), m["matter_year"]))
    print("  %-12s 8 个 seed -> %d 个不同问题" % (topo, len(sigs)))

print("\n=== 提交边是否要求凭证（空 agent 能否直接过）===")
for topo in TOPOS:
    g, m = build_graph(random.Random(0), "finance_pipeline", topo)
    edges = g["edges"]
    flat = []
    if isinstance(edges, dict):
        for v in edges.values():
            flat.extend(v if isinstance(v, list) else [v])
    else:
        flat = list(edges)
    to_target = [e for e in flat
                 if isinstance(e, dict) and e.get("to") == m["target"]]
    if not to_target:
        print("  %-12s !! 找不到通向 target 的边" % topo)
        continue
    reqs = [len(e.get("requires") or []) for e in to_target]
    print("  %-12s 通向 target 的边 %d 条, 各自要求凭证 %s | 相关条文 %d 条"
          % (topo, len(to_target), reqs, len(m["in_scope"])))
