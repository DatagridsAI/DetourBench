# 13 — EHR warfarin same-specimen INR conflict

冻结日期：2026-08-21。指标：`detourbench-v3`。

这是当前正式冻结的第二道 EHR 实例。来源是
`out/ehr_tasks/task3_ehr_warfarin_inr_conflict`；原目录和更早的 n=1 pilots
都没有移动。

不要从 `ehr_topologies.py` / `generate_ehr_suite.py` 重新生成覆盖本目录。
`generate_ehr_suite.py` 会跳过已冻结的 Task 2 / Task 3。

## 实例

| 项 | 值 |
|---|---|
| 节点 | 41 |
| 预言 / 知情下界 | 11 / 11 |
| Hard 预算 | 17（\(\lceil 11 \times 1.5 \rceil\)） |
| 终点动作 | 暂停配药，转入 `pending-anticoag-review` |
| Oracle | intake → patient → warfarin_rx → clinic INR → ED INR → AF → documents → precedence → policy → escalate → target |
| 图哈希 | `sha256:c571e4d96c2a96aa5f629801d60d7096cb174198f752d3ecd2178e0d9c97c196` |

核心机制：同一标本、同一 accession 的两份已签发实验室 INR 不一致（clinic 4.8 vs hospital interface 1.4）；AF 作为 dual_key 选择抗凝门诊审核路线，而不是通用临床审核。

## 冻结轨迹（每模型 5 次）

\(L_o=11\)。Attainment \(A=1_{\mathrm{success}}\cdot L_o/C\)，Progress \(P=1-R_T/L_o\)，NDR \(=(C+R_T-L_o)/L_o\)。

| 模型 | 重复 | 结果 | \(C\) | \(R_T\) | \(A\) | \(P\) | NDR |
|---|---:|---|---:|---:|---:|---:|---:|
| Claude Opus 5 | 1 | 成功 | 13 | 0 | 0.846 | 1.000 | 0.182 |
| Claude Opus 5 | 2 | 成功 | 11 | 0 | 1.000 | 1.000 | 0.000 |
| Claude Opus 5 | 3 | 成功 | 13 | 0 | 0.846 | 1.000 | 0.182 |
| Claude Opus 5 | 4 | 成功 | 13 | 0 | 0.846 | 1.000 | 0.182 |
| Claude Opus 5 | 5 | 成功 | 15 | 0 | 0.733 | 1.000 | 0.364 |
| DeepSeek V4 Pro | 1 | 预算耗尽 | 17 | 4 | 0 | 0.636 | 0.909 |
| DeepSeek V4 Pro | 2 | 预算耗尽 | 17 | 3 | 0 | 0.727 | 0.818 |
| DeepSeek V4 Pro | 3 | 预算耗尽 | 17 | 4 | 0 | 0.636 | 0.909 |
| DeepSeek V4 Pro | 4 | 预算耗尽 | 17 | 3 | 0 | 0.727 | 0.818 |
| DeepSeek V4 Pro | 5 | 预算耗尽 | 17 | 3 | 0 | 0.727 | 0.818 |

| 模型 | 成功 | 均值 \(C\) | 均值 \(A\) | 均值 \(P\) | 均值 NDR | 均值 \(R_T\) |
|---|---:|---:|---:|---:|---:|---:|
| Claude Opus 5 | 5/5 | 13.0 | 0.854 | 1.000 | 0.182 | 0.0 |
| DeepSeek V4 Pro | 0/5 | 17.0 | 0 | 0.691 | 0.855 | 3.4 |

轨迹副本：`pilots/{claude-opus-5,deepseek-v4-pro}-r{1–5}.json`。
汇总：[`pilot_trajectories.json`](pilot_trajectories.json)。

原始 5×2 目录（未移动）：

- `../out/ehr_pilot_opus5_task3_5x_20260821/run{1–5}/`
- `../out/ehr_pilot_deepseekv4pro_task3_5x_20260821/run{1–5}/`
