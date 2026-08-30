#!/usr/bin/env python3
"""Was the shortcut's result available before the reads it should have
filtered?

Ordering is by turn, not by step: calls issued in the same turn are
committed before any of their results are seen, so a query batched
alongside the reads it was meant to filter cannot have informed them.

Per episode the query is classified as:
  informed  - strictly earlier turn than every wasted read
  batched   - same turn as at least one wasted read
  late      - only after every wasted read
  none      - never issued
  clean     - no wasted read occurred at all

`clean` is kept separate from `informed`. Folding them together is how
this analysis first reported a false 94% informed: the breadth meta key
was wrong, the waste set came back empty, every episode had zero wasted
reads, and all of them landed in `informed`.
"""
import glob, json, os
from collections import Counter

RUNS = [("Breadth", "out/turn_breadth", "out/breadth40_hint", "dormant"),
        ("Sufficiency", "out/turn_sufficiency", "out/sufficiency_hint",
         "dormant_conditions")]

for cat, root, suite, waste_key in RUNS:
    files = sorted(glob.glob("%s/*/*/*.json" % root))
    if not files:
        print("%s: 还没跑完\n" % cat)
        continue
    cls, by_outcome, empty_waste = Counter(), {}, 0
    for f in files:
        inst = f.split(os.sep)[-2]
        gp = "%s/%s__hint/graph_full.json" % (suite, inst)
        if not os.path.exists(gp):
            continue
        m = json.load(open(gp))["meta"]
        r = json.load(open(f))
        oc = r.get("outcome") or ""
        if not oc or "abort" in oc or "error" in oc:
            continue
        raw = m.get(waste_key)
        if not raw:
            empty_waste += 1
            continue
        waste = {w if str(w).startswith("sec_") else "sec_" + str(w)
                 for w in raw}
        tr = r.get("trajectory") or []
        qturn = next((s.get("turn") for s in tr
                      if "in-force" in str(s.get("identifier", ""))), None)
        wturns = [s.get("turn") for s in tr if s.get("to") in waste]
        if not wturns:
            k = "clean"
        elif qturn is None:
            k = "none"
        elif qturn < min(wturns):
            k = "informed"
        elif qturn <= max(wturns):
            k = "batched"
        else:
            k = "late"
        cls[k] += 1
        by_outcome.setdefault(oc == "success", Counter())[k] += 1

    n = sum(cls.values())
    if empty_waste:
        print("  !! %d 个实例的 %r 为空，已跳过（不计入）" % (empty_waste, waste_key))
    if not n:
        print("%s: 没有可用 episode\n" % cat)
        continue
    print("=== %s (n=%d) ===" % (cat, n))
    for k in ("clean", "informed", "batched", "late", "none"):
        if cls[k]:
            print("  %-9s %3d (%2.0f%%)" % (k, cls[k], 100 * cls[k] / n))
    for ok in (True, False):
        c = by_outcome.get(ok)
        if c:
            print("  %s (n=%d): %s"
                  % ("成功" if ok else "失败", sum(c.values()), dict(c)))
    print()
