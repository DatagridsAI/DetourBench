# 15 — EHR aspirin-allergy naproxen local review

冻结日期：2026-08-24。指标：`detourbench-v3`。分类：`Integrated development challenge`。

这是正式冻结的第四道 EHR integrated task，也是 necessity-ablation 后
EHR overlay suite 中第一道冻结题。来源实例为
`out/ehr_overlay_tasks/21_ehr_asa_nsaid_class`；原目录与原始运行没有移动。

## 实例

| 项 | 值 |
|---|---|
| 节点 | 27 |
| 预言 / 知情下界 | 12 / 12 |
| Hard 预算 | 18（`ceil(12 × 1.5)`） |
| 真实 acquisition / benchmark actions / decision depth | 7 / 3 / 4 |
| 终点动作 | `pending-allergy-review`，通知 prescriber，不停用 OA therapy |
| 图哈希 | `sha256:ff521a61f3559ef7326d70e3a8f6856d2384af97529bca35adfacc4ed6fdad90` |

核心机制：未描述反应表型的 aspirin AllergyIntolerance、本地保守审核规则、
ticket-specific exception search，以及三路 evidence merge。一般性 aspirin allergy
不被表述为 FDA 对所有患者的普遍 NSAID 禁忌；外部标签只支持更窄的
aspirin-sensitive asthma / cross-reactivity 风险语境。

## 冻结 pilot（每模型 3 次）

| 模型 | 成功 | 步数 | 均值 Attainment | 均值 Progress | 均值 NDR |
|---|---:|---|---:|---:|---:|
| Claude Opus 5 | 3/3 | 15 / 12 / 15 | 0.867 | 1.000 | 0.167 |
| DeepSeek V4 Pro | 0/3 | 18 / 18 / 18 | 0.000 | 0.667 | 0.833 |

DeepSeek 三次失败均为可解释的广度探索导致预算耗尽，终态剩余下界均为 4；
Opus 三次全部成功且包含一次 oracle-length 路径，因此没有观察到 task-level floor。

完整轨迹在 `pilots/`，聚合文件为 `pilot_trajectories.json`，冻结哈希与来源为
`freeze_manifest.json`。不得从 overlay 生成器覆盖本目录。
