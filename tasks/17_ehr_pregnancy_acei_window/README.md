# 17 — EHR pregnancy-window ACEI review

冻结日期：2026-08-25。指标：`detourbench-v3`。分类：`Integrated model-contrast challenge`。

来源实例为 `out/ehr_overlay_tasks/23_ehr_pregnancy_acei_window`。核心机制：four-source transaction-window merge plus a ticket-scoped ACEI exception search。

## 实例

| 项 | 值 |
|---|---|
| 节点 | 31 |
| 预言 / 知情下界 | 12 / 12 |
| Hard 预算 | 18（`ceil(12 × 1.5)`） |
| 图哈希 | `sha256:aaf99efa99a0acc016e34e2e9df9643dfe9d62cc2219e94928080522117ab6f1` |

## 冻结 pilot（每模型 1 次）

| 模型 | 结果 | 步数 | Attainment | Progress | NDR |
|---|---|---:|---:|---:|---:|
| Claude Opus 5 | success | 12 | 1.000 | 1.000 | 0.000 |
| DeepSeek V4 Pro | success | 14 | 0.857 | 1.000 | 0.167 |

两条 pilot 仅用于冻结时的机制与轨迹检查。题目是在观察模型行为后调成的
model-contrast challenge，不能把这两条样本单独当作无偏的总体模型排名证据。

完整轨迹在 `pilots/`，聚合文件为 `pilot_trajectories.json`，冻结哈希与来源为
`freeze_manifest.json`。不得从 overlay 生成器覆盖本目录。
