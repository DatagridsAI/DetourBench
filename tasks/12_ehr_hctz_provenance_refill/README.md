# 12 — EHR HCTZ provenance refill

冻结日期：2026-08-21。

这是当前正式冻结的 EHR 实例。来源是
`out/ehr_tasks/task2_ehr_hctz_provenance_refill` 在预算改为 18 之后的图；
原目录和更早的 budget-17 pilots 都没有移动。

不要从 `ehr_topologies.py` / `generate_ehr_suite.py` 重新生成覆盖本目录。
`generate_ehr_suite.py` 会跳过已冻结的 Task 2 / Task 3。
生成器仍可能产出旧的 hold / \(L^*=11\) / 预算 17 版本。

## 实例

| 项 | 值 |
|---|---|
| 节点 | 40 |
| 预言 / 知情下界 | 12 / 12 |
| Hard 预算 | 18（\(\lceil 12 \times 1.5 \rceil\)） |
| 终点动作 | 暂停配药，转入 `pending-clinical-review` |
| Oracle | intake → patient → rx → renal → creatinine → ckd → egfr → docs → ccd → policy → escalate → target |

## 冻结轨迹

| 模型 | 结果 | 步数 | Attainment | 来源 |
|---|---|---:|---:|---|
| Claude Opus 5 | 成功 | 18 | 0.667 | `../out/ehr_pilot_opus5_task2_budget18_20260821/` |
| DeepSeek V4 Pro | 预算耗尽 | 18 | 0 | `../out/ehr_pilot_deepseekv4pro_task2_budget18_20260821/` |

两条轨迹的副本：

- [`pilots/claude-opus-5.json`](pilots/claude-opus-5.json)
- [`pilots/deepseek-v4-pro.json`](pilots/deepseek-v4-pro.json)
- 汇总：[`pilot_trajectories.json`](pilot_trajectories.json)
