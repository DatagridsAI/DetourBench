# 28 — synthea_gum_disease_onset

Encounter contents and dates are synthetic Synthea output. The audit packet, policy versions, terminology crosswalk, search behavior, indexes, and filing actions are DetourBench-authored. No real patient record or clinical advice is involved.

- Task revision: `synthea-onset-v5`
- Nodes / edges / reachable: 53 / 54 / 53
- Exact lower bound: 16
- Hard budget: 24
- Primary mechanism: Depth
- Supporting mechanisms: Currency, Breadth, Disposition
- Oracle witness: replayed successfully
- Semantic necessity audit: passed
- Pilot status: pending on this revision

## Decision

The current policy requires both crosswalk-confirmed codes. Across all four unordered hits, the earliest Conditions recorded entry is Gingivitis on 2012-12-23.

## Design note

The public initial state contains only the first case endpoint and no answer
identifier. Every packaged node is reachable. The verifier checks the exact
bound, canonical witness, replay, reachability, evidence gates, provenance,
mechanism routing, and initial-state leakage before freezing.
