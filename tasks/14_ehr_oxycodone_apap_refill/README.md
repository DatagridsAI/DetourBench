# 14 — EHR oxycodone/APAP controlled refill

冻结日期：2026-08-21。指标：`detourbench-v3`。

这是当前正式冻结的第三道 EHR 实例。来源是
`out/ehr_tasks/task4_ehr_oxycodone_apap_refill`。原目录没有移动。

不要从 `ehr_topologies.py` / `generate_ehr_suite.py` 重新生成覆盖本目录。
`generate_ehr_suite.py` 会跳过已冻结的 Task 2 / Task 3 / Task 4。

## 实例

| 项 | 值 |
|---|---|
| 节点 | 39 |
| 预言 / 知情下界 | 11 / 11 |
| Hard 预算 | 17（\(\lceil 11 \times 1.5 \rceil\)） |
| 长路 | 13（gap 2） |
| 终点动作 | 暂停配药，转入 `pending-controlled-medication-review` |
| Oracle | intake → patient → meds → fibro → snapshot → pdmp → agreement → policy_folder → policy_2026 → hold → target |
| 图哈希 | `sha256:fb7d20eaf22f0dd46023acb4d4dc95f56cc37a08ea2003e752a2053a7bbe80e8` |

核心机制：强制 linked indication + 三类监测的 **2-of-3**（`cii_history` / `clinic_monitoring` / `apap_existing_orders`）。短路用 overlay PDMP + 协议；长路用 in-chart CII 连续性证明 + Synthea medication-review-due。2025 年活跃医嘱与排队 MedicationRequest 是同一资源。提交门是一条 `requires_any_n=2` 的 hold URL。

## 冻结轨迹（每模型 5 次）

\(L_o=11\)。Attainment \(A=1_{\mathrm{success}}\cdot L_o/C\)，Progress \(P=1-R_T/L_o\)，NDR \(=(C+R_T-L_o)/L_o\)。

| 模型 | 重复 | 结果 | \(C\) | \(R_T\) | \(A\) | \(P\) | NDR |
|---|---:|---|---:|---:|---:|---:|---:|
| Claude Opus 5 | 1 | 成功 | 15 | 0 | 0.733 | 1.000 | 0.364 |
| Claude Opus 5 | 2 | 成功 | 12 | 0 | 0.917 | 1.000 | 0.091 |
| Claude Opus 5 | 3 | 成功 | 15 | 0 | 0.733 | 1.000 | 0.364 |
| Claude Opus 5 | 4 | 成功 | 13 | 0 | 0.846 | 1.000 | 0.182 |
| Claude Opus 5 | 5 | 成功 | 16 | 0 | 0.688 | 1.000 | 0.455 |
| DeepSeek V4 Pro | 1 | 预算耗尽 | 17 | 1 | 0 | 0.909 | 0.636 |
| DeepSeek V4 Pro | 2 | 预算耗尽 | 17 | 1 | 0 | 0.909 | 0.636 |
| DeepSeek V4 Pro | 3 | 预算耗尽 | 17 | 1 | 0 | 0.909 | 0.636 |
| DeepSeek V4 Pro | 4 | 预算耗尽 | 17 | 1 | 0 | 0.909 | 0.636 |
| DeepSeek V4 Pro | 5 | 预算耗尽 | 17 | 1 | 0 | 0.909 | 0.636 |

| 模型 | 成功 | 均值 \(C\) | 均值 \(A\) | 均值 \(P\) | 均值 NDR | 均值 \(R_T\) |
|---|---:|---:|---:|---:|---:|---:|
| Claude Opus 5 | 5/5 | 14.2 | 0.783 | 1.000 | 0.291 | 0.0 |
| DeepSeek V4 Pro | 0/5 | 17.0 | 0 | 0.909 | 0.636 | 1.0 |

轨迹副本：`pilots/{claude-opus-5,deepseek-v4-pro}-r{1–5}.json`。
汇总：[`pilot_trajectories.json`](pilot_trajectories.json)。

原始 5×2 目录（未移动）：

- `../out/ehr_pilot_opus5_task4_5x_20260821/run{1–5}/`
- `../out/ehr_pilot_deepseekv4pro_task4_5x_20260821/run{1–5}/`
