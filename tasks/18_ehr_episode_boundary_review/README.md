# 18 — EHR episode-boundary post-acute medication review

冻结日期：2026-08-25。指标：`detourbench-v3`。分类：`Integrated model-contrast challenge`。

来源实例为 `out/ehr_overlay_tasks/24_ehr_episode_boundary_review`。核心机制：episode-boundary merge plus ticket-scoped acute-analgesic exception search and discharge-summary collapse bait。

Patient：Tiana543 Fay398（Synthea csv_1k）。Snapshot：2014-09-01。

## 实例

| 项 | 值 |
|---|---|
| 节点 | 26 |
| 预言 / 知情下界 | 12 / 12 |
| Hard 预算 | 18 |
| 图哈希 | `sha256:837f99143baae4b63a22c2dc00ea652b31261e03eaa515e8ef59aa7185b34d3e` |

## 冻结 pilot（每模型 1 次）

| 模型 | 结果 | 步数 | Attainment | Progress | NDR |
|---|---|---:|---:|---:|---:|
| Claude Opus 5 | budget_exhausted | 18 | 0.000 | 0.917 | 0.583 |
| DeepSeek V4 Pro | budget_exhausted | 18 | 0.000 | 0.750 | 0.750 |

完整轨迹在 `pilots/`，聚合文件为 `pilot_trajectories.json`。
