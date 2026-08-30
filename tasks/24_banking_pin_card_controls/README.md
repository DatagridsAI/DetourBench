# 24 — banking_pin_card_controls

Classification: internal integrated development challenge. All customer/account/card facts are synthetic; the workflow is a DetourBench-authored overlay. Upstream redistribution is prohibited.

- Task revision: `banking-taubench-adaptation-v3`
- Nodes: 25
- Exact lower bound: 14
- Hard budget: 21
- Primary mechanism: Breadth
- Supporting mechanisms: Depth, Currency, Disposition
- Oracle witness: replayed successfully
- Semantic necessity audit: passed

## Packaged pilots

- claude-opus-5: success, 18/14 steps, NDR 0.286, RSR 0.056.
- qwen3.6-plus: success, 18/14 steps, NDR 0.286, RSR 0.000.
- Both runs use `closed-benchmark-v2` on the same v3 graph and are strictly protocol-comparable; the sample size is one per model.
- Older v1/v2 outputs are listed only as exclusions in `pilot_trajectories.json`.
- Frozen episodes: `pilots/claude-opus-5.json` and `pilots/qwen3.6-plus.json`.
