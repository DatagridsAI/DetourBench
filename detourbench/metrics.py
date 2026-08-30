"""Versioned metric definitions shared by generation, scoring, and analysis.

Frozen 2026-08-21 as detourbench-v3. METRIC_SPEC.md is normative. A formula
change needs a new METRIC_VERSION and regenerated paper tables.
"""

import math

METRIC_VERSION = "detourbench-v3"
METRIC_VERSION_V2 = "attainment-v2-success-weighted-oracle"
INFRASTRUCTURE_OUTCOMES = frozenset({"api_error_abort",
                                     "harness_exception"})

# Outcomes that enter an absorbing wrong state. The target is
# unreachable from these, so residual work, progress and NDR have no
# finite value. The search state used elsewhere is (visited,
# inventory) and carries no outcome term, so it will happily return a
# distance here; that distance is a property of a relaxed graph in
# which the commitment never happened, and must not be reported.
ABSORBING_OUTCOMES = frozenset({"terminal_failure"})


class InfrastructureOutcomeError(ValueError):
    """Raised when a non-episode is submitted for metric scoring."""


def episode_metrics(*, success, outcome, charged_steps,
                    remaining_lower_bound, oracle_lower_bound,
                    invalid_steps=0, duplicate_steps=0):
    """Compute the complete frozen-v3 payload for one valid episode.

    This is the normative episode-level entry point. Infrastructure outcomes
    are not episodes under METRIC_SPEC.md and are rejected so they cannot
    silently enter aggregate denominators. RSR remains conditional on
    success.
    """
    if not isinstance(success, bool):
        raise ValueError("success must be a boolean")
    if not isinstance(outcome, str) or not outcome:
        raise ValueError("outcome must be a nonempty string")
    if outcome in INFRASTRUCTURE_OUTCOMES:
        raise InfrastructureOutcomeError(
            f"{outcome} is an infrastructure outcome, not a valid episode")
    if success != (outcome == "success"):
        raise ValueError(
            f"success={success} is inconsistent with outcome={outcome!r}")

    charged = _nonnegative_int(charged_steps, "charged steps")
    if remaining_lower_bound is None and outcome in ABSORBING_OUTCOMES:
        # score_episode reports no residual after an absorbing commitment.
        # Carry a placeholder through the arithmetic below; every field it
        # feeds is overwritten with None before this function returns.
        remaining = 0
    else:
        remaining = _nonnegative_int(
            remaining_lower_bound, "remaining lower bound")
    lower = _positive_int(oracle_lower_bound, "oracle lower bound")
    invalid = _nonnegative_int(invalid_steps, "invalid steps")
    duplicate = _nonnegative_int(duplicate_steps, "duplicate steps")
    if invalid + duplicate > charged:
        raise ValueError(
            "invalid plus duplicate steps cannot exceed charged steps")
    if success and remaining != 0:
        raise ValueError(
            "a successful episode must have zero remaining lower bound")
    if not success and remaining == 0 and outcome not in ABSORBING_OUTCOMES:
        raise ValueError(
            "a failed episode cannot have zero remaining lower bound")

    result = {
        "success": success,
        "outcome": outcome,
        "steps_total": charged,
        "charged_steps": charged,
        "steps_invalid": invalid,
        "steps_duplicate": duplicate,
        "lower_bound_steps": lower,
        "remaining_lower_bound": remaining,
        "metric_version": METRIC_VERSION,
        "attainment": attainment_score(success, charged, lower),
        "progress": progress_score(remaining, lower),
        "ndr": ndr_score(charged, remaining, lower),
    }
    if success:
        result["rsr"] = (invalid + duplicate) / charged
        result["excess_over_lower_bound"] = charged - lower
    else:
        result["rsr"] = None
        result["excess_over_lower_bound"] = None
    if outcome in ABSORBING_OUTCOMES:
        # Whatever the caller passed for remaining came from a search that
        # cannot see the commitment. Discard it rather than report a
        # distance to a goal the episode can no longer reach.
        result["remaining_lower_bound"] = None
        result["progress"] = None
        result["ndr"] = None
        result["residual_undefined_reason"] = (
            "absorbing wrong commitment: the target is unreachable from "
            "the terminal state, so residual work has no finite value")
    return result


def attainment_score(success, steps_total, oracle_lower_bound):
    """Success-weighted oracle efficiency for one episode.

    Failed episodes score zero. A successful episode shorter than the
    proven lower bound is invalid data and is rejected instead of clipped.
    """
    if not success:
        return 0.0
    charged = _positive_int(steps_total, "charged steps")
    lower = _positive_int(oracle_lower_bound, "oracle lower bound")
    if charged < lower:
        raise ValueError(
            f"successful episode used {charged} steps, below proven "
            f"lower bound {lower}")
    return lower / charged


def progress_score(remaining_lower_bound, oracle_lower_bound):
    """Fraction of remaining oracle work already done: 1 - R_T / L_o."""
    remaining = _nonnegative_int(remaining_lower_bound, "remaining lower bound")
    lower = _positive_int(oracle_lower_bound, "oracle lower bound")
    if remaining == 0:
        return 1.0
    return 1.0 - remaining / lower


def ndr_score(charged_steps, remaining_lower_bound, oracle_lower_bound):
    """Normalized detour ratio: (C + R_T - L_o) / L_o."""
    charged = _nonnegative_int(charged_steps, "charged steps")
    remaining = _nonnegative_int(remaining_lower_bound, "remaining lower bound")
    lower = _positive_int(oracle_lower_bound, "oracle lower bound")
    excess = charged + remaining - lower
    if excess < 0:
        raise ValueError(
            f"C + R_T = {charged} + {remaining} is below proven "
            f"lower bound {lower}")
    return excess / lower


def compute_step_budget(oracle_lower_bound, informed_lower_bound, multiplier):
    """Compute a difficulty budget without requiring agent foreknowledge."""
    values = (oracle_lower_bound, informed_lower_bound)
    if any(not isinstance(v, int) or isinstance(v, bool) or v <= 0
           for v in values):
        raise ValueError("lower bounds must be positive integers")
    if not isinstance(multiplier, (int, float)) \
            or isinstance(multiplier, bool) or multiplier <= 0:
        raise ValueError("difficulty multiplier must be positive")
    return math.ceil(max(values) * multiplier)


def _positive_int(value, label):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _nonnegative_int(value, label):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return value
