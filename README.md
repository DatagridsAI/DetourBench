# DetourBench

Task instances, exact oracles, and the evaluation harness for DetourBench, a
benchmark that scores interactive agents against the exact minimum number of
environment accesses each task admits.

Each task is a finite, partially observable transition system with unit-cost
accesses whose resources become globally addressable once discovered.
Exhaustive breadth-first search over the reachable state space yields the
full-information minimum action count `L_o` together with a replayable witness,
and from any graph-recoverable terminal state it yields the exact residual work
`R_T`.

## Layout

    tasks/                 one directory per instance
      graph_full.json      resources, actions, prerequisites, terminal conditions
      oracle.json          L_o, the shortest successful route, the frozen budget
      task_spec.json       identifiers, topology, mechanism metadata
      initial_state.json   declared start node and seed grants
      verifier_report.json result of replaying the witness under the evaluator
      freeze_manifest.json sha256 of released frozen artifacts
    corpora/               public source records the instances are built from
    detourbench/           environment, scorer, metrics, harness, builders, audits
    paper_selection_20.json  maps each evaluated task ID to its directory and hashes
    METRIC_SPEC.md         metric definitions and aggregation rules

## Identity of an instance

Resolve tasks by the `graph_sha256` and `oracle_sha256` recorded in
`paper_selection_20.json`, not by directory name. Directory numbering reflects
build order and one directory was renumbered after evaluation; the manifest
carries both the paper's task number and the original build number.

## Model trajectories

Recorded model trajectories are not included in this repository. Every metric
in the paper is computed from the frozen graph and oracle shipped here, and the
harness reproduces the runs against any endpoint you configure.

## Credentials

The harness reads endpoint credentials from environment variables only. Do not
place keys on a command line or in a tracked file; source them from a file with
restrictive permissions that git ignores.

## Licensing of source material

Instances are derived from public records: eCFR regulations, OSV/GHSA security
advisories, Apache project issues, CBP rulings, and Synthea-generated synthetic
clinical records. Synthea output is synthetic and contains no real patient
data. Source-derived content is linked to supporting spans; authored scenario
overlays are labeled separately.
