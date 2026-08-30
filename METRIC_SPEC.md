# DetourBench metric specification

**Frozen version:** `detourbench-v3`  
**Frozen on:** 2026-08-21

This file is the normative definition used by generation, per-episode
scoring, and aggregate analysis. The implementation is `metrics.py`.
Changes require a new metric version and a full regeneration of paper
tables. The 216-run hard-matrix tables remain attainment-v2 numbers;
v3 adds Progress and NDR without changing the attainment formula.

The previous headline, `attainment-v2-success-weighted-oracle`, is unchanged
as the efficiency formula. v3 adds Progress and NDR, which need a remaining
oracle bound at episode termination.

## Interaction model

Actions are globally addressable. After a node has been visited, every
outgoing identifier it revealed remains usable for the rest of the episode.
The exact lower-bound and remaining-bound solvers expand

```text
actions(visited) = union(OutEdges(v) for v in visited)
```

They do **not** expand only `OutEdges(current_node)`. A positional walk-back
to a previously visited hub is never required to reuse one of its edges.
State is `(visited, inventory)`. Reopening an already-visited resource is
still a charged duplicate.

## Resource units

A billable document or policy resource is an independently addressable
graph node. The recommended default is **section-level retrieval**: a node
corresponds to a real heading, table row, or other independently
addressable source range, not necessarily an entire physical webpage.

- Reopening the same section is a duplicate.
- Different real sections may be billed separately.
- Graphs must not split a source below its real heading or row solely to
  inflate step count.
- An instance may record `meta.resource_unit` (`section-level` or
  `page-level`). This choice does not change the metric formulas.

## Lower bounds

- **Oracle lower bound (`L_o`)**: the exact shortest successful execution in
  the grader's complete graph, computed by BFS over `(visited, inventory)`
  under the global-addressability rule above.
  It is mechanically verifiable and is the efficiency normalizer.
- **Remaining lower bound (`R_T`)**: the exact shortest remaining execution
  from the episode's terminal `(visited, inventory)` state to the target.
  Computed once per episode. If the target has already been visited, `R_T = 0`.
- **Informed lower bound (`L_i`)**: a conservative task-author declaration of
  the interactions an agent needs before it can make an informed decision.
  It protects the step budget from requiring foreknowledge. It is not used
  as the efficiency numerator.

The step budget for difficulty multiplier `m` is:

```text
ceil(max(L_o, L_i) * m)
```

The current multipliers are easy `8.0`, medium `3.0`, and hard `1.5`.

## Charged steps

`C` / `C_charged` is the number of environment accesses in the episode
(`steps_total`). One access costs one step, including invalid and duplicate
accesses.

## Outcome: Success

`success(e)` is 1 if and only if the episode visited the target. Preserve the
full failure taxonomy (`budget_exhausted`, `gave_up`, `terminal_failure`,
…). Infrastructure failures (`api_error_abort`, `harness_exception`) are not
episodes and must be rerun.

## Efficiency: Attainment

```text
A(e) = success(e) * L_o(e) / C(e)
```

- A failed valid episode receives `0`.
- An optimal successful episode receives `1`.
- A successful episode below `L_o` is invalid data and aborts analysis.
- Aggregate attainment is the arithmetic mean over all valid episodes.

## Progress

```text
P(e) = 1 - R_T(e) / L_o(e)
```

- At the start, `R_T = L_o` and `P = 0`.
- On success, `R_T = 0` and `P = 1`.
- Failed episodes keep a nonzero progress score when they reduced remaining
  work. This replaces the v2 milestone-fraction diagnostic.

## Detour: NDR

```text
NDR(e) = (C(e) + R_T(e) - L_o(e)) / L_o(e)
```

- An optimal success has `C = L_o`, `R_T = 0`, and `NDR = 0`.
- A successful detour of `k` extra steps has `NDR = k / L_o`.
- A failure charges both extra steps already taken and remaining work.
- `C + R_T < L_o` is invalid data and aborts analysis.

## Diagnostics

- **Invalid**: accesses that did not succeed (`valid` is false).
- **Duplicate**: successful accesses of an already-known node.
- **RSR**: `(invalid + duplicate) / C`, successful episodes only; null on
  failure.
- **Outcome**: preserve the full failure taxonomy; never collapse gateway or
  harness failures into model failure.

## Interpretation boundary

Oracle-normalized efficiency counts all discovery interactions above the
omniscient shortest execution as overhead. It does not by itself separate
necessary exploration from planning error. Progress and NDR score failed
trajectories without giving them a nonzero attainment. The Local-vs-Full
visibility experiment remains the planned causal comparison for discovery
versus planning.
