#!/usr/bin/env python3
"""Audit saved runs before any DetourBench analysis or paper table."""

import argparse
import collections
import glob
import json
import os
import sys

from metrics import INFRASTRUCTURE_OUTCOMES


REQUIRED_RUN_FIELDS = {
    "success", "outcome", "steps_total", "steps_invalid",
    "steps_duplicate", "trajectory",
}


def audit(runs_dir, instances_dir):
    instances = {}
    for path in glob.glob(os.path.join(instances_dir, "*", "oracle.json")):
        with open(path) as f:
            oracle = json.load(f)
        instances[(oracle["theme"], oracle["topology"])] = oracle

    report = {
        "runs_dir": runs_dir,
        "instances_dir": instances_dir,
        "total_files": 0,
        "valid_model_episodes": 0,
        "infrastructure_errors": [],
        "invalid_json": [],
        "schema_errors": [],
        "metric_inconsistencies": [],
        "counts_by_model": {},
        "counts_by_outcome": {},
    }
    by_model = collections.Counter()
    by_outcome = collections.Counter()

    for path in sorted(glob.glob(os.path.join(runs_dir, "*", "*", "*.json"))):
        report["total_files"] += 1
        parts = path.replace("\\", "/").split("/")
        topology, theme = parts[-3], parts[-2]
        try:
            with open(path) as f:
                run = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            report["invalid_json"].append({"path": path, "error": str(exc)})
            continue

        model = run.get("model") or parts[-1].rsplit("_r", 1)[0]
        outcome = run.get("outcome")
        by_model[model] += 1
        by_outcome[str(outcome)] += 1

        missing = sorted(REQUIRED_RUN_FIELDS - set(run))
        if missing:
            report["schema_errors"].append({"path": path, "missing": missing})
            continue
        if outcome in INFRASTRUCTURE_OUTCOMES:
            report["infrastructure_errors"].append({
                "path": path, "model": model, "outcome": outcome,
            })
            continue

        oracle = instances.get((theme, topology))
        if oracle is None:
            report["schema_errors"].append({
                "path": path,
                "missing_instance": f"{theme}__{topology}",
            })
            continue
        steps = run.get("steps_total")
        lb = oracle["lower_bound_steps"]
        if run.get("success") and (
                not isinstance(steps, int) or isinstance(steps, bool)
                or steps < lb):
            report["metric_inconsistencies"].append({
                "path": path, "success": True, "steps_total": steps,
                "oracle_lower_bound": lb,
            })
            continue
        report["valid_model_episodes"] += 1

    report["counts_by_model"] = dict(sorted(by_model.items()))
    report["counts_by_outcome"] = dict(sorted(by_outcome.items()))
    report["clean"] = not any(report[key] for key in (
        "infrastructure_errors", "invalid_json", "schema_errors",
        "metric_inconsistencies"))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="out/hard_runs")
    ap.add_argument("--instances", default="out/hard_instances")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    report = audit(args.runs, args.instances)
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.out:
        with open(args.out, "w") as f:
            f.write(rendered + "\n")
    if not report["clean"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
