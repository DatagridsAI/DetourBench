#!/usr/bin/env python3
"""Does each topology measure something different, or the same thing ten
times?

Primary statistic: for each topology, rank the models by attainment, then
compute tie-aware Kendall's tau-b between every pair of topologies' scores. High tau
everywhere => the topologies are redundant and the benchmark is really one
task. Low/mixed tau => detour behaviour is multi-dimensional, and a single
efficiency number necessarily hides most of it.

Conditional efficiency is `step_ratio` = steps_total / lower_bound, not RSR.
RSR was shown to be structurally blind to route-choice waste (on
two_routes a model took 3.3x the optimal path while scoring RSR 0.20,
indistinguishable from its usual 0.17) because the long route's steps are
all valid and non-duplicate. step_ratio catches that; both are reported.

Only successful episodes contribute to step ratio and RSR. Headline attainment
is success-weighted, so every valid failure contributes zero.
"""
import argparse
import collections
import glob
import itertools
import json
import os
import random
import statistics
import sys
from math import comb, sqrt

# METRIC_SPEC.md is normative and metrics.py is its implementation. This
# file used to carry its own copy of attainment — failures priced at a
# hard-coded cost of 40 steps — which is exactly the duplication that lets
# an evaluator's semantics drift mid-experiment. It was also wrong in a way
# that mattered: 40 was the old flat budget, so under hard difficulty
# (budgets of 5-11) it valued a failure at several times the whole task and
# inflated the spread between models. Failures score zero here.
from metrics import (INFRASTRUCTURE_OUTCOMES, METRIC_VERSION,
                     attainment_score)


def kendall_tau_b(a, b):
    """Kendall's tau-b between two ``{item: score}`` mappings.

    Tau-a silently turns equal attainment values into an arbitrary ordering.
    Tau-b keeps those pairs tied and adjusts the denominator for ties on only
    one side. Pairs tied on both sides carry no ordering information.
    """
    items = [k for k in a if k in b]
    conc = disc = ties_a = ties_b = 0
    for x, y in itertools.combinations(items, 2):
        da, db = a[x] - a[y], b[x] - b[y]
        if da == 0 and db == 0:
            continue
        if da == 0:
            ties_a += 1
            continue
        if db == 0:
            ties_b += 1
            continue
        s = da * db
        if s > 0:
            conc += 1
        else:
            disc += 1
    denominator = sqrt((conc + disc + ties_a) *
                       (conc + disc + ties_b))
    return (conc - disc) / denominator if denominator else float("nan")


# Backward-compatible import name for callers that used the old helper.
kendall_tau = kendall_tau_b


def assert_attainment_bound(aggregate):
    """Enforce the episode-level invariant after aggregation.

    Because every episode has ``attainment <= success_indicator``, any cell
    with mean attainment above success rate necessarily used inconsistent
    episode sets or denominators.
    """
    attainment = aggregate.get("attainment")
    success_rate = aggregate.get("success_rate")
    if (attainment is not None and success_rate is not None
            and attainment > success_rate + 1e-12):
        raise ValueError(
            f"attainment {attainment:.6f} exceeds success rate "
            f"{success_rate:.6f}; metric denominators are inconsistent")


def percentile(values, q):
    """Linearly interpolated percentile for a non-empty numeric sequence."""
    if not values:
        raise ValueError("percentile needs at least one value")
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(ordered) - 1)
    weight = pos - lo
    return ordered[lo] * (1 - weight) + ordered[hi] * weight


def bootstrap_mean(cluster_values, rng, samples):
    """Mean and percentile CI after resampling independent clusters."""
    values = list(cluster_values)
    if not values:
        return {"estimate": None, "ci_low": None, "ci_high": None,
                "n_clusters": 0, "bootstrap_samples": samples}
    draws = []
    for _ in range(samples):
        draws.append(statistics.mean(rng.choice(values)
                                     for _ in range(len(values))))
    return {"estimate": statistics.mean(values),
            "ci_low": percentile(draws, 0.025),
            "ci_high": percentile(draws, 0.975),
            "n_clusters": len(values), "bootstrap_samples": samples}


def bootstrap_paired_difference(a, b, rng, samples):
    """Paired cluster bootstrap for mean(a - b), keyed by instance."""
    keys = sorted(set(a) & set(b))
    differences = [a[k] - b[k] for k in keys]
    result = bootstrap_mean(differences, rng, samples)
    result["n_paired_clusters"] = result.pop("n_clusters")
    return result


def bootstrap_mean_tau(instance_scores, topologies, models, rng, samples):
    """Stratified instance bootstrap for mean pairwise topology tau-b.

    ``instance_scores[topology][instance][model]`` contains the mean over
    stochastic repeats. Instances are resampled within topology so every
    bootstrap replicate preserves the benchmark's mechanism composition.
    """
    draws = []
    usable = {}
    for topology in topologies:
        complete = [scores for scores in instance_scores.get(topology, {}).values()
                    if all(model in scores for model in models)]
        if complete:
            usable[topology] = complete
    usable_topologies = sorted(usable)
    for _ in range(samples):
        topology_model_scores = {}
        for topology in usable_topologies:
            clusters = usable[topology]
            selected = [rng.choice(clusters) for _ in range(len(clusters))]
            topology_model_scores[topology] = {
                model: statistics.mean(row[model] for row in selected)
                for model in models}
        taus = [kendall_tau_b(topology_model_scores[a],
                              topology_model_scores[b])
                for a, b in itertools.combinations(usable_topologies, 2)]
        finite = [tau for tau in taus if tau == tau]
        if finite:
            draws.append(statistics.mean(finite))
    return {"ci_low": percentile(draws, 0.025) if draws else None,
            "ci_high": percentile(draws, 0.975) if draws else None,
            "bootstrap_samples": samples,
            "n_topologies": len(usable_topologies),
            "instances_per_topology": {
                topology: len(rows) for topology, rows in usable.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="out/exp_runs")
    ap.add_argument("--instances", default="out/exp_instances")
    ap.add_argument("--out", default="out/experiment_analysis.json")
    ap.add_argument(
        "--exclude-infrastructure-errors", action="store_true",
        help="produce an explicitly incomplete diagnostic report instead of "
             "failing when gateway/harness outcomes are present")
    ap.add_argument("--bootstrap-samples", type=int, default=2000)
    ap.add_argument("--bootstrap-seed", type=int, default=0)
    args = ap.parse_args()
    if args.bootstrap_samples <= 0:
        ap.error("--bootstrap-samples must be positive")

    lb, milestones = {}, {}
    for d in glob.glob(f"{args.instances}/*"):
        name = os.path.basename(d)
        theme, topo = name.split("__")
        with open(f"{d}/oracle.json") as f:
            oracle = json.load(f)
        lb[(theme, topo)] = oracle["lower_bound_steps"]
        # Milestone set for partial credit: the nodes the oracle path must
        # pass through. Borrowed from TheAgentCompany's checkpoint grading
        # — binary success throws away the difference between a model that
        # died one step from the target and one that never left the start.
        # Unlike hand-written checkpoints, ours fall out of the provable
        # optimal path, so they need no separate authoring or review.
        with open(f"{d}/graph_full.json") as f:
            g = json.load(f)["graph"]
        by_id = {e["edge_id"]: e for ne in g["edges"].values() for e in ne}
        milestones[(theme, topo)] = [by_id[eid]["to"]
                                     for eid in oracle["oracle_edge_path"]]

    # cell[(topo, model)] -> list of per-episode records
    cell = collections.defaultdict(list)
    outcomes = collections.Counter()
    infrastructure_errors = []
    for path in glob.glob(f"{args.runs}/*/*/*.json"):
        parts = path.replace("\\", "/").split("/")
        topo, theme = parts[-3], parts[-2]
        with open(path) as f:
            r = json.load(f)
        model = r.get("model") or parts[-1].rsplit("_r", 1)[0]
        outcomes[(topo, r.get("outcome"))] += 1
        if r.get("outcome") in INFRASTRUCTURE_OUTCOMES:
            infrastructure_errors.append({
                "path": path, "model": model, "outcome": r.get("outcome")})
            continue
        ms = milestones[(theme, topo)]
        reached = {e.get("to") for e in r.get("trajectory", []) if e.get("valid")}
        # Pre-v3 diagnostic: share of oracle-path nodes visited. Frozen v3
        # Progress is 1 - R_T/L_o and lives in score.py / metrics.py.
        r["_progress"] = (sum(1 for n in ms if n in reached) / len(ms)
                          if ms else 0.0)
        r["_instance"] = theme          # repeats of one instance share this
        cell[(topo, model)].append((r, lb[(theme, topo)]))

    if infrastructure_errors and not args.exclude_infrastructure_errors:
        print(
            f"ERROR: found {len(infrastructure_errors)} infrastructure "
            "outcomes; rerun those cells before analysis. Use "
            "--exclude-infrastructure-errors only for an explicitly "
            "incomplete diagnostic report.", file=sys.stderr)
        for item in infrastructure_errors[:10]:
            print(f"  {item['outcome']}: {item['path']}", file=sys.stderr)
        if len(infrastructure_errors) > 10:
            print(f"  ... and {len(infrastructure_errors) - 10} more",
                  file=sys.stderr)
        raise SystemExit(2)
    if infrastructure_errors:
        print(f"WARNING: excluding {len(infrastructure_errors)} "
              "infrastructure outcomes; report is incomplete.",
              file=sys.stderr)

    topos = sorted({t for t, _ in cell})
    models = sorted({m for _, m in cell})

    # ---- per (topology, model) aggregates -------------------------------
    # Headline metric is `attainment` (see METRIC_SPEC.md): the mean over
    # all episodes of oracle_lower_bound / steps, with failures scoring
    # zero. Efficiency computed over successes only has a selection bias —
    # a model that abandons whatever it finds hard is then scored solely on
    # the easy half, and can outrank one that solved everything slightly
    # inefficiently — so failures have to count. Scoring them zero rather
    # than at some assumed cost keeps the metric a property of the graphs
    # instead of a property of the budget we happened to set.
    # Infrastructure outcomes are excluded rather than scored: a gateway
    # returning HTML is not the model failing the task.
    agg = {}
    for t in topos:
        for m in models:
            runs = cell.get((t, m), [])
            ok = [(r, l) for r, l in runs if r.get("success")]
            ratios = [r["steps_total"] / l for r, l in ok]
            rsrs = [(r["steps_invalid"] + r["steps_duplicate"]) / r["steps_total"]
                    for r, _ in ok if r["steps_total"]]
            attain = [attainment_score(bool(r.get("success")),
                                       r.get("steps_total") or 0, l)
                      for r, l in runs]
            prog = [r["_progress"] for r, _ in runs]
            # pass^k, after tau-bench: of n repeats of the same instance,
            # c successes -> P(all k of a random k-subset succeed). k=1 is
            # ordinary success rate; k=n is "never fails". Capability and
            # reliability are different properties and a mean hides the
            # difference between 3/3 and a lucky 1/3.
            by_inst = collections.defaultdict(list)
            for r, _ in runs:
                by_inst[r.get("_instance", "all")].append(bool(r.get("success")))
            pass_k = {}
            if by_inst:
                nrep = min(len(v) for v in by_inst.values())
                for k in range(1, nrep + 1):
                    vals = []
                    for succ in by_inst.values():
                        c, n = sum(succ[:nrep]), nrep
                        vals.append(comb(c, k) / comb(n, k) if c >= k else 0.0)
                    pass_k[k] = statistics.mean(vals)
            agg[(t, m)] = {
                "pass_k": pass_k,
                "n": len(runs), "n_success": len(ok),
                "success_rate": len(ok) / len(runs) if runs else 0.0,
                "attainment": statistics.mean(attain) if attain else None,
                "progress_mean": statistics.mean(prog) if prog else None,
                "step_ratio_mean": statistics.mean(ratios) if ratios else None,
                "step_ratio_sd": statistics.stdev(ratios) if len(ratios) > 1 else 0.0,
                "rsr_mean": statistics.mean(rsrs) if rsrs else None,
            }
            assert_attainment_bound(agg[(t, m)])

    # ---- instance-clustered uncertainty ---------------------------------
    # Repeats of one graph are first averaged into one independent cluster.
    # The same sampled instance indices are then used for a model pair, so a
    # difficult graph affects both sides of a difference equally.
    clustered_attainment = collections.defaultdict(
        lambda: collections.defaultdict(list))
    clustered_success = collections.defaultdict(
        lambda: collections.defaultdict(list))
    topology_instance_scores = collections.defaultdict(
        lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
    for (topology, model), runs in cell.items():
        for run, lower_bound in runs:
            instance_key = (topology, run["_instance"])
            episode_attainment = attainment_score(
                bool(run.get("success")), run.get("steps_total") or 0,
                lower_bound)
            clustered_attainment[model][instance_key].append(
                episode_attainment)
            clustered_success[model][instance_key].append(
                float(bool(run.get("success"))))
            topology_instance_scores[topology][run["_instance"]][model].append(
                episode_attainment)

    model_attainment_by_instance = {
        model: {key: statistics.mean(values) for key, values in rows.items()}
        for model, rows in clustered_attainment.items()}
    model_success_by_instance = {
        model: {key: statistics.mean(values) for key, values in rows.items()}
        for model, rows in clustered_success.items()}
    instance_scores = {
        topology: {
            instance: {model: statistics.mean(values)
                       for model, values in model_rows.items()}
            for instance, model_rows in instance_rows.items()}
        for topology, instance_rows in topology_instance_scores.items()}

    bootstrap_rng = random.Random(args.bootstrap_seed)
    overall_intervals = {}
    for model in models:
        overall_intervals[model] = {
            "attainment": bootstrap_mean(
                model_attainment_by_instance.get(model, {}).values(),
                bootstrap_rng, args.bootstrap_samples),
            "success_rate": bootstrap_mean(
                model_success_by_instance.get(model, {}).values(),
                bootstrap_rng, args.bootstrap_samples),
        }
    pairwise_attainment = {}
    for model_a, model_b in itertools.combinations(models, 2):
        pairwise_attainment[f"{model_a}|{model_b}"] = \
            bootstrap_paired_difference(
                model_attainment_by_instance.get(model_a, {}),
                model_attainment_by_instance.get(model_b, {}),
                bootstrap_rng, args.bootstrap_samples)

    print("=== step_ratio (steps / provable lower bound), successes only ===")
    hdr = "topology".ljust(21) + "".join(m[:13].ljust(15) for m in models)
    print(hdr)
    for t in topos:
        row = t.ljust(21)
        for m in models:
            a = agg[(t, m)]
            row += (f"{a['step_ratio_mean']:.2f}({a['n_success']}/{a['n']})"
                    .ljust(15) if a["step_ratio_mean"] is not None
                    else f"--({a['n_success']}/{a['n']})".ljust(15))
        print(row)

    print(f"\n=== attainment [{METRIC_VERSION}] = mean(oracle_lb / steps), "
          "failures score 0; 1.00 = always optimal ===")
    print("topology".ljust(21) + "".join(m[:13].ljust(15) for m in models))
    for t in topos:
        row = t.ljust(21)
        for m in models:
            a = agg[(t, m)]
            row += (f"{a['attainment']:.3f}".ljust(15)
                    if a["attainment"] is not None else "--".ljust(15))
        print(row)

    print("\n=== progress (v2 diagnostic: fraction of oracle-path "
          "milestones reached; not v3 P = 1 - R_T/L_o) ===")
    print("topology".ljust(21) + "".join(m[:13].ljust(15) for m in models))
    for t in topos:
        row = t.ljust(21)
        for m in models:
            p = agg[(t, m)]["progress_mean"]
            row += (f"{p:.2f}".ljust(15) if p is not None else "--".ljust(15))
        print(row)

    print("\n=== overall leaderboard (pooled across all topologies) ===")
    board = []
    for m in models:
        vals = [agg[(t, m)]["attainment"] for t in topos
                if agg[(t, m)]["attainment"] is not None]
        srs = [agg[(t, m)]["success_rate"] for t in topos if agg[(t, m)]["n"]]
        prg = [agg[(t, m)]["progress_mean"] for t in topos
               if agg[(t, m)]["progress_mean"] is not None]
        # pass^1 vs pass^n: capability vs reliability, pooled over topologies
        p1 = [agg[(t, m)]["pass_k"].get(1) for t in topos
              if agg[(t, m)]["pass_k"].get(1) is not None]
        kmax = max((max(agg[(t, m)]["pass_k"] or [0]) for t in topos), default=0)
        pn = [agg[(t, m)]["pass_k"].get(kmax) for t in topos
              if agg[(t, m)]["pass_k"].get(kmax) is not None]
        if vals:
            board.append((m, statistics.mean(vals), statistics.mean(srs),
                          statistics.mean(prg) if prg else 0.0,
                          statistics.mean(p1) if p1 else 0.0,
                          statistics.mean(pn) if pn else 0.0, kmax))
    board.sort(key=lambda kv: -kv[1])
    for m, at, sr, pr, p1, pn, kmax in board:
        at_ci = overall_intervals[m]["attainment"]
        sr_ci = overall_intervals[m]["success_rate"]
        print(f"  {m:26s} attainment={at:.3f}  success={sr:.2f}  "
              f"progress={pr:.2f}  pass^1={p1:.2f}  pass^{kmax}={pn:.2f}\n"
              f"    95% cluster bootstrap CI: attainment "
              f"[{at_ci['ci_low']:.3f}, {at_ci['ci_high']:.3f}], "
              f"success [{sr_ci['ci_low']:.3f}, {sr_ci['ci_high']:.3f}]")

    print("\n=== paired model differences in attainment (A - B) ===")
    pair_rows = sorted(pairwise_attainment.items(),
                       key=lambda item: -abs(item[1]["estimate"]))
    for pair, interval in pair_rows:
        model_a, model_b = pair.split("|", 1)
        print(f"  {model_a:24s} - {model_b:24s} "
              f"{interval['estimate']:+.3f} "
              f"95% CI [{interval['ci_low']:+.3f}, "
              f"{interval['ci_high']:+.3f}] "
              f"(n={interval['n_paired_clusters']})")

    # ---- rankings + pairwise Kendall tau --------------------------------
    # Ranked on attainment (the headline metric), so the discriminant test
    # is asking whether topologies disagree about the metric that would
    # actually be published, not about a diagnostic sub-score.
    ranks = {}
    topology_scores = {}
    for t in topos:
        scored = [(m, agg[(t, m)]["attainment"]) for m in models
                  if agg[(t, m)]["attainment"] is not None]
        scored.sort(key=lambda kv: -kv[1])         # higher attainment = better
        topology_scores[t] = dict(scored)
        ranks[t] = {}
        previous_score = object()
        dense_rank = -1
        for model, score in scored:
            if score != previous_score:
                dense_rank += 1
                previous_score = score
            ranks[t][model] = dense_rank

    print("\n=== model ranking per topology (best -> worst) ===")
    for t in topos:
        order = sorted(ranks[t], key=lambda m: ranks[t][m])
        groups = collections.defaultdict(list)
        for model in order:
            groups[ranks[t][model]].append(model[:18])
        rendered = " > ".join(" = ".join(groups[rank])
                              for rank in sorted(groups))
        print(f"  {t:21s} {rendered}")

    print("\n=== pairwise Kendall tau-b between topologies' model scores ===")
    taus = []
    print(" " * 21 + "".join(t[:9].ljust(11) for t in topos))
    for t1 in topos:
        row = t1.ljust(21)
        for t2 in topos:
            if t1 == t2:
                row += "  --       "
                continue
            tau = kendall_tau_b(topology_scores[t1], topology_scores[t2])
            taus.append(tau)
            row += f"{tau:+.2f}".ljust(11)
        print(row)

    finite = [t for t in taus if t == t]
    tau_interval = bootstrap_mean_tau(
        instance_scores, topos, models, bootstrap_rng,
        args.bootstrap_samples)
    if finite:
        tau_interval["estimate"] = statistics.mean(finite)
        print(f"\nmean pairwise tau-b = {statistics.mean(finite):+.3f}  "
              f"95% stratified cluster bootstrap CI "
              f"[{tau_interval['ci_low']:+.3f}, "
              f"{tau_interval['ci_high']:+.3f}]  "
              f"(1.0 = every topology ranks models identically -> redundant; "
              f"~0 = they measure different things)")
    else:
        tau_interval["estimate"] = None

    # ---- outcome mix per topology ---------------------------------------
    print("\n=== outcome mix per topology ===")
    for t in topos:
        mix = {o: n for (tt, o), n in outcomes.items() if tt == t}
        tot = sum(mix.values())
        parts = ", ".join(f"{o}={n}" for o, n in sorted(mix.items(),
                                                        key=lambda kv: -kv[1]))
        print(f"  {t:21s} n={tot:3d}  {parts}")

    with open(args.out, "w") as f:
        json.dump({
            "aggregates": {f"{t}|{m}": v for (t, m), v in agg.items()},
            "ranks": ranks,
            "topology_scores": topology_scores,
            "mean_pairwise_tau": statistics.mean(finite) if finite else None,
            "mean_pairwise_tau_interval": tau_interval,
            "overall_intervals": overall_intervals,
            "pairwise_attainment_differences": pairwise_attainment,
            "bootstrap": {"unit": "instance", "paired": True,
                          "stratified_tau_by_topology": True,
                          "samples": args.bootstrap_samples,
                          "seed": args.bootstrap_seed},
            "kendall_variant": "tau-b",
            "infrastructure_errors_excluded": len(infrastructure_errors),
            "incomplete": bool(infrastructure_errors),
        }, f, indent=1)
    print(f"\nwritten to {args.out}")


if __name__ == "__main__":
    main()
