#!/usr/bin/env python3
"""Score a completed DetourBench episode.

RSR is only meaningful conditional on success — a model that gives up
immediately has Steps_total near 0 and would score a misleadingly great RSR
otherwise. We report Success Rate and RSR as two separate, jointly-required
numbers; RSR is left null for failed episodes rather than defaulting to 0.

Metric v3 adds Progress and NDR, both of which need the remaining oracle
bound R_T at the episode's terminal state. That search runs once per
episode; it is not a per-step trace.
"""
import json

from env import GraphEnv
from generate import remaining_lower_bound
from metrics import ABSORBING_OUTCOMES
from metrics import episode_metrics


def terminal_search_state(env):
    """(visited, inventory) for the remaining-bound search."""
    visited = set(env.node_visit_count)
    inventory = set(env.inventory)
    start_grant = (env.meta.get("token_grants") or {}).get(env.meta["start"])
    if start_grant:
        inventory.update([start_grant] if isinstance(start_grant, str)
                         else start_grant)
    return visited, inventory


def remaining_from_env(env):
    visited, inventory = terminal_search_state(env)
    return remaining_lower_bound(env.graph, env.meta, visited, inventory)


def residual_for_outcome(env, outcome):
    """Residual work implied by the terminal outcome.

    The search behind remaining_from_env ranges over (visited, inventory)
    and carries no outcome term, so it cannot see that an episode has
    already ended. Two cases where it therefore disagrees with the
    environment:

    A success reached through the determination tool never enters the
    target node, so the search reports a positive distance for an episode
    that is already finished. A success reached by traversing the filing
    edge does enter it and searches to zero -- the same outcome scoring
    two different ways depending on which route the model took.

    An absorbing wrong commitment has no route to the target at all, but
    the search finds one anyway through the nodes read beforehand, in a
    relaxed graph where the commitment never happened.

    After a terminal outcome the answer follows from the outcome itself.
    Only an episode still active needs the search.
    """
    if env.success or outcome == "success":
        return 0
    if outcome in ABSORBING_OUTCOMES:
        return None
    return remaining_from_env(env)


def score_episode(env, oracle, outcome=None):
    total = env.steps_used
    invalid = sum(1 for e in env.trajectory if not e.get("valid", False))
    duplicate = sum(1 for e in env.trajectory
                     if e.get("valid") and e.get("already_known"))
    return _metric_payload(
        success=env.success,
        outcome=outcome or ("success" if env.success else "unknown"),
        charged=total,
        remaining=residual_for_outcome(
            env, outcome or ("success" if env.success else "unknown")),
        lower=oracle["lower_bound_steps"],
        invalid=invalid,
        duplicate=duplicate,
        oracle=oracle,
    )


def load_and_score(instance_dir, trajectory_path):
    with open(f"{instance_dir}/oracle.json") as f:
        oracle = json.load(f)
    with open(trajectory_path) as f:
        run = json.load(f)
    outcome = run.get(
        "outcome", "success" if run["success"] else "unknown")
    env = GraphEnv(instance_dir, step_budget=10 ** 9)
    for row in run.get("trajectory") or []:
        ident = row.get("identifier")
        if not ident or ident == "<determination>":
            continue
        env.access(ident)
        if env.success:
            break
    result = score_episode(env, oracle, outcome=outcome)
    result["gave_up_recoverable"] = run.get("gave_up_recoverable")
    return result


def _metric_payload(success, outcome, charged, remaining, lower, invalid,
                    duplicate, oracle):
    result = episode_metrics(
        success=success,
        outcome=outcome,
        charged_steps=charged,
        remaining_lower_bound=remaining,
        oracle_lower_bound=lower,
        invalid_steps=invalid,
        duplicate_steps=duplicate,
    )
    result["informed_lower_bound"] = oracle.get(
        "informed_lower_bound", lower)
    result["step_budget"] = oracle.get("step_budget")
    return result
