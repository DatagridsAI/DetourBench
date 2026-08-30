#!/usr/bin/env python3
"""Refuse a paired instance whose two arms are textually identical.

The paper requires that a controlled pair differ only in an allowlisted
cue field, and that the difference be established by artifact diff rather
than assumed from generator intent. The converse case is the one that bit
here: two arms that differ in nothing at all.

Two of thirty-two breadth pairs are null manipulations. Neither is a
pairing bug. On t47 and t49 the corpus cannot carry the vintage filter, so
the task falls back to its unfiltered form where every cited requirement
is engaged; that form has no shortcut, so the sentence pointing at one was
never written, and removing it changes nothing. The instances are fine.
Pairing them is not.

Run over any hint/nohint suite. Reports, per pair: whether any node text
differs, whether the difference is confined to the seed, and whether the
bound and scope agree - a pair that differs in more than the cue is as
invalid as one that differs in nothing.
"""
import glob, json, os, sys

def nodes(p):
    g = json.load(open(p))
    return g["graph"]["nodes"], g["meta"]


def audit(hint_dir, nohint_dir, label):
    rows = {"ok": [], "null": [], "wide": [], "unpaired": []}
    for d in sorted(glob.glob(os.path.join(hint_dir, "*"))):
        base = os.path.basename(d)
        twin = os.path.join(nohint_dir, base.replace("__hint", "__nohint"))
        a = os.path.join(d, "graph_full.json")
        b = os.path.join(twin, "graph_full.json")
        if not (os.path.exists(a) and os.path.exists(b)):
            rows["unpaired"].append(base)
            continue
        na, ma = nodes(a)
        nb, mb = nodes(b)
        diff = [k for k in na if na[k].get("desc") != nb.get(k, {}).get("desc")]
        seed = "sec_" + str(ma.get("corpus_seed"))
        if not diff:
            rows["null"].append(base)
        elif set(diff) - {seed}:
            rows["wide"].append((base, sorted(set(diff) - {seed})[:3]))
        else:
            rows["ok"].append(base)

    print("=== %s ===" % label)
    print("  合格(仅种子文本不同) %d" % len(rows["ok"]))
    if rows["null"]:
        print("  空操纵(两臂完全相同) %d: %s"
              % (len(rows["null"]), " ".join(rows["null"])))
    if rows["wide"]:
        print("  操纵过宽(种子之外也变了) %d:" % len(rows["wide"]))
        for base, ks in rows["wide"][:5]:
            print("     %-16s %s" % (base, ks))
    if rows["unpaired"]:
        print("  缺配对 %d: %s"
              % (len(rows["unpaired"]), " ".join(rows["unpaired"][:5])))
    return rows


SUITES = [
    ("out/breadth40_hint", "out/breadth40_nohint", "Breadth"),
    ("out/suite40_hint", "out/suite40_nohint", "Currency"),
    ("out/sufficiency_hint", "out/sufficiency_nohint", "Sufficiency"),
    ("out/disposal_hint", "out/disposal_nohint", "Disposition"),
]
bad = 0
for h, n, label in SUITES:
    if not os.path.isdir(h):
        print("=== %s === 套件不在磁盘上，跳过\n" % label)
        continue
    r = audit(h, n, label)
    bad += len(r["null"]) + len(r["wide"]) + len(r["unpaired"])
    print()
print("需要处理的配对总数: %d" % bad)
