# 29 — terminal_freight_dispatch_shift

Frozen DetourBench projection of the Freight Dispatch Shift V1 runtime. This
is a one-shot 09:00 dispatch-plan review over a Belgium/Luxembourg freight
snapshot. The graph is a DetourBench navigation overlay around a
source-runtime-validated dispatch decision; it does not claim that mapped
facilities or benchmark policies are commercial operating agreements.

## Identity

- Task ID: `29`
- Revision: `terminal-freight-dispatch-v1`
- Classification: `integrated_task_independently_piloted`
- Primary mechanism: `Disposition`
- Supporting mechanisms: `Currency`, `Breadth`, `Depth`
- Projection cutoff: `09:00`
- Publication status: internal development only, pending OSM derivative-license and ADR primary-page review

## Frozen graph and oracle

- Nodes / directed edges: 35 / 45
- Dead-end nodes: 2
- Exact and informed lower bound: 20
- Hard budget: 30
- Difficulty / metric: `hard` / `detourbench-v3`
- State semantics: `graph-env.expanding-search.v1`
- Oracle witness: replayed successfully in 20 steps

The only successful terminal action is `commit-plan-a`. Plan B is rejected by
the source runtime for missing mandatory continuous-driving breaks; Plan C is
rejected for controlled ADR vehicle/driver eligibility. Premature review and
either wrong commit are terminal graph outcomes.

## Packaged evidence

- `graph_full.json`: graph, mechanism regions, action gates and node provenance.
- `oracle.json`: lower bound, oracle path, budget and solver/state versions.
- `task_spec.json`: objective, actions, mechanisms and publication boundary.
- `source_corpus.json`: source hashes, the selected 09:00 snapshot, candidate plans and source-runtime validation.
- `initial_state.json`: local start state and action budget.
- `verifier_report.json`: replay, discrimination, semantic-necessity and provenance checks.
- `necessity_audit.json`: the ten evidence nodes required by the review gate.
- `freeze_manifest.json`: frozen identifiers, counts, versions and hashes.
- `pilot_trajectories.json` and `pilots/`: admitted pilot episodes and graph-hash checks.

Lanes are frozen OSM-derived fields; dispatch records, fleet and controlled
policies are benchmark data. Graph links, candidate labels, counterfactual
plans and terminal actions are DetourBench-authored overlays. The ADR and
driving/rest rules are deliberately controlled subsets, not legal advice or a
full compliance engine.

## Pilot record

Five admitted episodes are recorded on this revision:

| model | episodes | successes | recorded outcome |
|---|---:|---:|---|
| Claude Opus 5 | 1 | 1 | success |
| Qwen 3.6 Plus | 2 | 0 | gave_up |
| GPT-5.6 | 2 | 2 | success |

These are development and independent-holdout evidence, not a stable model
ranking. See `pilot_trajectories.json` for admission, hash and metric details.

## Format and release checks

`FORMAT_ALIGNMENT.md` compares this package with the remote first-ten-task
set. The frozen verifier reports `ok: true`; the manifest hashes the graph,
oracle, verifier, corpus, necessity audit, task spec and initial state. Before
public release, repeat source-data license, ADR primary-page and manifest-hash
review.
