#!/usr/bin/env python3
"""The paired signpost result on forty distinct problems.

Three things other benchmarks' methodology asked for, none of which this
suite reported before:

pass^k (tau-bench) - all k attempts succeed rather than at least one.
pass@1 hides the variation this task produces most: a model that queries
four times in five reads as a 92% model under pass@1 and as something
else under pass^3.

The mid-range band (item response theory) - items whose pass rate sits
between 30% and 70% carry the most information about ability; items
everyone passes or everyone fails carry almost none. Reported per item so
the suite can say which of its forty problems are actually discriminating
rather than asserting that all of them are.

Aborts are dropped, never scored as failures, and any cell with too few
usable episodes is refused rather than reported. Both rules exist because
this project has already published a false result by breaking them.
"""
import glob, json, os, statistics as st
from collections import defaultdict

MIN_EPISODES = 12



def _view_node(instance_dir):
    """The point-in-time view node for one instance.

    Identified from the edge that offers it rather than by name, so a
    renamed node does not silently turn every episode into a non-query.
    """
    g = json.load(open(instance_dir + "/graph_full.json"))
    for _src, lst in g["graph"]["edges"].items():
        items = lst if isinstance(lst, list) else lst.values()
        for e in items:
            desc = str(e.get("desc") or "")
            if "/sections/in-force" in desc or "as_of=" in desc:
                return e.get("to")
    raise ValueError("no point-in-time view edge in %s" % instance_dir)


def load(root, suite):
    cells = defaultdict(list)
    for f in sorted(glob.glob("%s/*/*/*.json" % root)):
        inst = f.split(os.sep)[-2]
        model = os.path.basename(f).rsplit("_r", 1)[0]
        d = glob.glob("%s/%s__*" % (suite, inst))
        if not d:
            continue
        m = json.load(open(d[0] + "/graph_full.json"))["meta"]
        r = json.load(open(f))
        oc = r.get("outcome") or ""
        if not oc or "abort" in oc or "error" in oc:
            continue
        txt = json.dumps(r.get("trajectory") or [], ensure_ascii=False)
        view = _view_node(d[0])
        entered = any(st.get("to") == view
                      for st in (r.get("trajectory") or [])
                      if isinstance(st, dict))
        cells[(model, inst)].append({
            "ok": oc == "success",
            # Entering the view node, not a substring of a URL: the filing
            # endpoint also spells "latest-in-force", so a substring test
            # counts every submission as a consultation.
            "shortcut": entered,
            "waste": sum(1 for s in m["out_of_scope"] if ("sec_" + s) in txt),
            "att": r.get("attainment") or 0.0,
        })
    return cells


A = load("out/m40_hint", "out/suite40_hint")
B = load("out/m40_nohint", "out/suite40_nohint")


def summ(cells, model):
    cs = [v for (m, _), v in cells.items() if m == model and v]
    eps = [e for c in cs for e in c]
    if not eps:
        return None
    return {
        "n": len(eps), "items": len(cs),
        "q": 100 * sum(e["shortcut"] for e in eps) / len(eps),
        "p1": 100 * sum(e["ok"] for e in eps) / len(eps),
        "pk": 100 * sum(1 for c in cs if all(e["ok"] for e in c)) / len(cs),
        "w": st.mean(e["waste"] for e in eps),
        "att": st.mean(e["att"] for e in eps),
    }


models = sorted({m for m, _ in A})
print("%-18s %-32s | %s" % ("", "指路（种子写明）", "对照（不写）"))
print("%-18s %5s %5s %6s %5s %5s | %5s %5s %6s %5s %5s"
      % ("模型", "查询", "pass@1", "pass^3", "浪费", "attain",
         "查询", "pass@1", "pass^3", "浪费", "attain"))
for model in models:
    a, b = summ(A, model), summ(B, model)
    if not a or not b:
        continue
    if min(a["n"], b["n"]) < MIN_EPISODES:
        print("%-18s 可用 episode 太少（%d / %d），不报"
              % (model, a["n"], b["n"]))
        continue
    print("%-18s %4.0f%% %5.0f%% %5.0f%% %5.1f %5.3f | %4.0f%% %5.0f%% %5.0f%% %5.1f %5.3f"
          % (model, a["q"], a["p1"], a["pk"], a["w"], a["att"],
             b["q"], b["p1"], b["pk"], b["w"], b["att"]))

# paired within item and model
print("\n配对（同题同模型，只差一句话）:")
dq, dok, dw = [], [], []
for key, ca in A.items():
    cb = B.get(key)
    if not (ca and cb):
        continue
    dq.append(sum(e["shortcut"] for e in ca) / len(ca)
              - sum(e["shortcut"] for e in cb) / len(cb))
    dok.append(sum(e["ok"] for e in ca) / len(ca)
               - sum(e["ok"] for e in cb) / len(cb))
    dw.append(st.mean(e["waste"] for e in cb) - st.mean(e["waste"] for e in ca))
if dq:
    print("  配对 %d 对 | 查询率 -%.0f pt | 成功率 -%.0f pt | 无关条文多读 +%.1f 条"
          % (len(dq), 100 * st.mean(dq), 100 * st.mean(dok), st.mean(dw)))
    print("  查询率下降的配对 %d/%d，无变化 %d，上升 %d"
          % (sum(1 for d in dq if d > 0), len(dq),
             sum(1 for d in dq if d == 0), sum(1 for d in dq if d < 0)))

# which items discriminate (IRT mid-range band)
print("\n条目难度分布（pass@1 汇总所有模型，指路臂）:")
bands = {"全过 (>70%)": 0, "中段 30-70%": 0, "全挂 (<30%)": 0}
for inst in sorted({i for _, i in A}):
    eps = [e for (m, i), c in A.items() if i == inst for e in c]
    if not eps:
        continue
    p = sum(e["ok"] for e in eps) / len(eps)
    bands["全过 (>70%)" if p > .7 else
          ("全挂 (<30%)" if p < .3 else "中段 30-70%")] += 1
for k, v in bands.items():
    print("  %-14s %2d 题" % (k, v))
print("  —— 中段是区分度最高的一段；全过/全挂的条目几乎不携带能力信息")
