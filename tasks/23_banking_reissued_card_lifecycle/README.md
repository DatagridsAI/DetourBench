# 23 — banking_reissued_card_lifecycle

Classification: internal integrated development challenge. All customer/account/card facts are synthetic; the workflow is a DetourBench-authored overlay. Upstream redistribution is prohibited.

- Task revision: `banking-taubench-adaptation-v3`
- Nodes: 28
- Exact lower bound: 17
- Hard budget: 26
- Primary mechanism: Depth
- Supporting mechanisms: Breadth, Currency, Disposition
- Oracle witness: replayed successfully
- Semantic necessity audit: passed

## Packaged pilots

- claude-opus-5: success, 24/17 steps, NDR 0.412, RSR 0.042.
- qwen3.6-plus: success, 24/17 steps, NDR 0.412, RSR 0.083.
- Both runs use `closed-benchmark-v2` on the same v3 graph and are strictly protocol-comparable; the sample size is one per model.
- Older v1/v2 outputs are listed only as exclusions in `pilot_trajectories.json`.
- Frozen episodes: `pilots/claude-opus-5.json` and `pilots/qwen3.6-plus.json`.
