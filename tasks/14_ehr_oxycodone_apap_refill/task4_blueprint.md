# EHR Task 4 blueprint — oxycodone/APAP controlled refill

Status: **frozen candidate / NEAR PILOT-READY.** Mechanically verified. Do not keep polishing difficulty.

Instance: `out/ehr_tasks/task4_ehr_oxycodone_apap_refill/`
Frozen copy: `initial_integrated_tasks/14_ehr_oxycodone_apap_refill/`
Corpus: `corpora_ehr/it-ehr-04-oxycodone-apap-refill.json`
Topology: `integrated_ehr_oxycodone_apap_case`

## 1. Verified Synthea facts

Patient **Micaela928 Josefina523 Rendón540**, MRN `46fcc34a-97a1-f038-9bb1-4ae87116ae61`, F, DOB 1985-06-12, Northbridge MA.

- Active MedicationRequest **RxNorm 1049625**, FHIR id `46fcc34a-97a1-f038-e42e-36415b133408`, start 2025-10-29, no stop. This **is** the queued refill resource.
- Annual 1049625 chain from 2015-09-02; CSV `DISPENSES=3`; empty `REASONCODE`.
- No other acetaminophen-containing medication. No FHIR MedicationDispense / MedicationStatement.
- Active from 2014-01-31: Fibromyalgia 203082005, chronic low back pain 278860009, chronic pain 82423001.
- Percocet orders do **not** carry a reason.
- Active medication-review-due 314529007 from 2025-10-29.
- A completed 1049625 order for 2022-10-12 through 2023-10-18 exists in Synthea and is **not** a graph node.

## 2. Overlay facts

- Queue **RXQ-4611**, date **2026-08-21**.
- Linked indication: fibromyalgia (opaque Condition URL). Overlay linkage.
- Short-route monitors: PDMP extract, controlled-medication agreement, existing-order acetaminophen check, in-pharmacy fill log.
- Long-route CII monitor: in-chart CII continuity attestation from the 2023 and 2024 completed orders plus the already-queued active MedicationRequest.
- Two dated memos: 2019-11-01–2025-12-31 vs 2026-01-01 packet rule.
- Terminal: `pending-controlled-medication-review`.

## 3. Goal

Assemble a complete evidence packet and route this refill to the appropriate queue disposition. Pause fulfillment; do not prescribe, dose-select, discontinue, or substitute.

## 4. Graph (39 nodes)

- Spine: start → intake → patient → oxycodone_rx
- Indication: fibro
- Current monitoring: snapshot → pdmp, agreement, apap, pharmacy_fill_log
- Longitudinal: history → y2023 → y2024 → cii_continuity; history → review_due
- Identity: `e_y2025` from y2024 aliases to **oxycodone_rx** at the Synthea FHIR id. There is no separate `y2025` node.
- Policy: policy_folder → memo-20191101 | memo-20260101
- Commit: **one** hold URL with token 2-of-3, then target
- Dead ends: tokenless leaves only (fill log, previews, lookalike problem-list rows, etc.)

Sibling order: `sha256(4611:identifier)` hex ascending.

`off_canonical_oracle_nodes` = nodes not on the short oracle. Long-route nodes are in that set and are still valid success.

`dead_end_nodes` = outdegree-zero nodes that grant **no** success token. Evidence leaves (`pdmp`, `agreement`, `apap`, `cii_continuity`, `review_due`, `fibro`) are not dead ends.

## 5. Mechanism

| Mechanism | Mapping |
|---|---|
| linear_gate | billed hops on both routes |
| evidence_synthesis | mandatory `pain_indication`; 2 of 3 **categories** via `requires_any` / `requires_any_n=2` |
| version_constraint | only 2026-01-01 grants `governing_policy` |
| two_routes | short: PDMP + agreement; long: `cii_continuity` + `review_due` |
| alias_maze | Percocet / RxNorm / APAP-oxycodone / 2025 FHIR id → `oxycodone_rx` |

Category tokens:

- `cii_history` ← `pdmp` **or** `cii_continuity`
- `clinic_monitoring` ← `agreement` **or** `review_due`
- `apap_existing_orders` ← `apap`

One hold URL: `scenario://ehr/pharmacy/RXQ-4611/pending-controlled-medication-review`. Spine tokens are AND; the three categories are a true 2-of-3 over inventory.

## 6–8. Solver bounds

**Short / oracle (\(L_o=11\)):**
intake → patient → meds → fibro → snapshot → pdmp → agreement → policy_folder → policy_2026 → hold → target

**Long / valid (\(C=13\), gap 2):**
intake → patient → meds → fibro → history → y2023 → y2024 → cii_continuity → review_due → policy_folder → policy_2026 → hold → target

Solver after this pass: \(L_o=11\), \(L_i=11\), budget \(\lceil 1.5 \times 11 \rceil = 17\). Long length 13. Not padded.

## 9. \(L_i=11\)

Same 11 information nodes as the short route. APAP and both long-route category members are interchangeable, so they are not on \(L_i\). The archived memo is not on \(L_i\).

## 10–13. Threshold and long route

Mandatory linked indication plus 2 of 3 categories. Same-category pair (PDMP + continuity) does not unlock hold. Fill log / LBP / generic pain do not grant a category.

The long route rebuilds two **categories** from chart history without opening the overlay PDMP or agreement. The 2025 year is the queued MedicationRequest already visited on the spine.

NDR for a successful long run: \(2/11 \approx 0.18\).

## 14. Difference from Task 2 / 3

Task 4 is sufficient subset + governing version + two semantically distinct evidence packets to one terminal. Not HCTZ provenance, not INR conflict.

## 15. Remaining honest limitations

1. Indication linkage is overlay.
2. PDMP and agreement are overlay; `cii_continuity` is overlay reconstruction of observed 2023–2024 orders plus the active queued Rx.
3. CSV `DISPENSES=3` is not a FHIR MedicationDispense.
4. Acetaminophen check uses labeling 4 g/day as eligibility only.
5. Env gained `requires_any` / `requires_any_n` so this gate is one submission, not three pair URLs. Other topologies are unchanged.

Verifier: 62/62. `test_ehr_topologies.py` + `test_metrics.py`: 26/26.
