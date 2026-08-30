#!/usr/bin/env python3
"""Where do redundant steps actually come from? Breaks the 108-episode
matrix down by which trap absorbed each wasted step, so new topologies can
be designed against observed failure behaviour rather than invented shapes.
"""
import collections
import glob
import json
import os


def node_class(node):
    if node is None:
        return "unresolved"
    if node.startswith("honeypot_"):
        return "honeypot"
    if node.startswith("loop_"):
        return "loop"
    if node == "token_room":
        return "credential"
    if node in ("gate_room", "post_gate"):
        return "realpath"
    return node


def main():
    files = sorted(glob.glob("out/runs_matrix/*/*.json"))
    per_model = collections.defaultdict(lambda: collections.defaultdict(list))
    invalid_reasons = collections.Counter()
    dup_by_class = collections.Counter()
    honeypot_depth_hist = collections.Counter()
    loop_cycles_hist = collections.Counter()
    first_move_counter = collections.Counter()
    wasted_by_trap = collections.Counter()
    total_steps = 0
    total_wasted = 0
    episodes = 0

    for path in files:
        with open(path) as f:
            run = json.load(f)
        if not run.get("success"):
            continue
        episodes += 1
        model = run["model"]
        traj = run["trajectory"]
        total_steps += len(traj)

        max_hp = -1
        loop_visits = 0
        for i, e in enumerate(traj):
            to = e.get("to")
            cls = node_class(to)
            if i == 0:
                first_move_counter[cls] += 1
            if cls == "honeypot" and to:
                depth = int(to.split("_")[1])
                max_hp = max(max_hp, depth)
            if cls == "loop":
                loop_visits += 1

            if not e.get("valid"):
                invalid_reasons[e.get("reason", "?")] += 1
                total_wasted += 1
                wasted_by_trap[f"invalid:{e.get('reason','?')}"] += 1
            elif e.get("already_known"):
                dup_by_class[cls] += 1
                total_wasted += 1
                wasted_by_trap[f"duplicate:{cls}"] += 1

        # honeypot steps are *always* pure waste: never on any path to target
        hp_steps = sum(1 for e in traj
                       if e.get("valid") and node_class(e.get("to")) == "honeypot")
        wasted_by_trap["honeypot_exploration(valid but useless)"] += hp_steps

        honeypot_depth_hist[max_hp + 1] += 1
        loop_cycles_hist[max(0, loop_visits - 1)] += 1
        per_model[model]["hp_steps"].append(hp_steps)
        per_model[model]["loop_extra"].append(max(0, loop_visits - 1))
        per_model[model]["steps"].append(len(traj))

    print(f"=== {episodes} successful episodes, {total_steps} total steps ===")
    print(f"lower bound per episode = 5, so minimum possible total = {episodes*5}")
    print(f"actual total = {total_steps}, excess = {total_steps - episodes*5}\n")

    print("--- where the excess goes (all successful episodes pooled) ---")
    for k, v in wasted_by_trap.most_common():
        print(f"  {k:48s} {v:4d}")

    print("\n--- honeypot: how many hops deep did they go? ---")
    for depth in sorted(honeypot_depth_hist):
        n = honeypot_depth_hist[depth]
        bar = "#" * n
        print(f"  {depth} hops: {n:3d} {bar}")

    print("\n--- loop: extra cycles beyond the 1 mandatory touch ---")
    for c in sorted(loop_cycles_hist):
        n = loop_cycles_hist[c]
        print(f"  {c} extra: {n:3d} {'#'*n}")

    print("\n--- first move (what do they reach for first?) ---")
    for k, v in first_move_counter.most_common():
        print(f"  {k:16s} {v:3d}")

    print("\n--- invalid-step reasons ---")
    for k, v in invalid_reasons.most_common():
        print(f"  {k:24s} {v:3d}")

    print("\n--- duplicate steps by node class ---")
    for k, v in dup_by_class.most_common():
        print(f"  {k:16s} {v:3d}")

    print("\n--- per model: mean honeypot steps / mean extra loop cycles ---")
    for m, d in sorted(per_model.items()):
        hp = sum(d["hp_steps"]) / len(d["hp_steps"])
        lp = sum(d["loop_extra"]) / len(d["loop_extra"])
        st = sum(d["steps"]) / len(d["steps"])
        print(f"  {m:26s} hp={hp:4.2f}  loop_extra={lp:4.2f}  steps={st:5.2f}")


if __name__ == "__main__":
    main()
