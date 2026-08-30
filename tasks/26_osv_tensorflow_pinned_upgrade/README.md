# 26 — osv_tensorflow_pinned_upgrade

Classification: integrated development challenge. The task is limited to frozen OSV records with `GHSA-` identifiers; the deployment and filing policy are DetourBench-authored overlay.

- Task revision: `osv-pinned-upgrade-v3`
- Nodes / edges: 54 / 343
- Exact lower bound: 10
- Hard budget: 15
- Primary mechanism: Breadth
- Supporting mechanisms: Sufficiency, Disposition
- Oracle witness: replayed successfully
- Semantic necessity audit: passed

## Decision

The manifest identifies `tensorflow==2.2.0`. Exactly five records, distributed across three selected mixed query packets among six sibling candidates, cover that pin. Three are fixed in 2.2.1 and two in 2.4.0. Therefore K2 is insufficient, Q4 violates the distribution-preserving policy, T9 overshoots the lowest-safe rule, and M7 is the unique compliant bundle. PYSEC records are outside this task's declared scope and are not present in the graph.

## Pilot status

Revision v1 pilots are invalidated for scope integrity. Revision v2 pilots are invalidated because the index disclosed the exact five-record checklist and all 15 episodes reproduced the Oracle. Revision v3 currently has 3 active exact-graph pilot episodes. deepseek-v4-pro: 0/1 success; kimi-k3: 1/1 success; qwen3.6-plus: 0/1 success. These post-revision pilots diagnose task behavior but do not establish blind selection.
