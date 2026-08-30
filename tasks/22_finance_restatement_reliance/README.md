# 22 — finance_restatement_reliance

Classification: Integrated development challenge. SEC EDGAR filing metadata and
the quoted passages are observed; the credit policy, review packet, trustee
fact and write actions are authored benchmark overlays.

- Frozen corpus: `corpora_edgar_ppsi.json`
- Task revision: `finance-edgar-v1`
- Evidence cluster: `edgar-ppsi-2024-restatement`
- Nodes: 56 · Edges: 95 · edges/nodes 1.70
- Exact lower bound: 12 · Hard budget: 18 · bound/nodes 0.214
- Identifiers available per step along the oracle, median: 50.5
- Primary mechanism: Disposition
- Supporting mechanisms: Currency, Depth, Breadth
- Oracle witness: replayed successfully in 12 steps
- Semantic necessity audit: passed
- Pilots: 8 episodes, 2 models, on this revision

## What the case is

A credit desk holds a note of Pioneer Power Solutions, Inc. (CIK 0001449792).
On 6 June 2024 the issuer filed an Item 4.02 8-K withdrawing reliance on its
fiscal 2022 annual statements and its 2023 interim statements. The desk's
policy freezes the internal rating until the affected periods are restated
and every periodic report is current. Snapshot is 20 August 2024. Record one
disposition.

The filing index covers the twenty-four months before the snapshot, which is
the desk's standing lookback, and holds 39 periodic and current reports.
Section 16 ownership reports are outside it and the index node says so.

## Why the obvious route is empty

The cure for a non-reliance statement is normally an amended report, so the
first move is to look for a 10-K/A or a 10-Q/A. The frozen amendment view
returns six of them — the issuer has filed amendments five times — and the
most recent covers fiscal 2019. None covers an affected period, and none ever
will: the fiscal 2023 annual report is a **Comprehensive Form 10-K** that
restates the affected periods inside itself, and says so:

> We have not filed, and do not intend to file, amendments to the previously
> filed Form 10-Qs, nor the previously filed 2022 10-K.

That sentence sits in the report's Explanatory Note, one level below the
index row. An agent that reads the index, sees a 10-K on file for fiscal
2023, and stops has not learned whether anything was restated.

The trap is the issuer's, not ours. `test_no_amendment_covers_an_affected_period`
asserts it against the frozen corpus rather than leaving it to prose.

## The rule the answer turns on

`DTB-CR-2024B` is in force on the snapshot and supersedes `DTB-CR-2023A`,
which recognised only amended reports as a cure. Under the governing version
the affected periods are cured, but a Rule 12b-25 notification for the first
quarter of 2024 is outstanding and the report itself is not on file. Counting
from the extended date that notification claims, it has been delinquent for
91 days. The policy freezes the rating while any report is delinquent and
refers the case to committee past 60 days. No trustee notice of default is on
file, so a reporting default is not available.

Two Rule 12b-25 notifications are outstanding and they resolve in opposite
directions. The annual one, filed 2 April 2024, has its report behind it: the
comprehensive 10-K arrived on 26 July. The first-quarter one, filed 16 May
2024, does not — no 10-Q for the quarter ended 31 March is anywhere in the
index. So the affected periods are cured and the issuer is still behind.

Correct disposition: `freeze-pending-current-reporting`.

## Each way of being wrong lands somewhere different

This is the property the task was rebuilt around, and it is checked at build
time (`readings_reach_different_actions`) rather than argued for here.

| reading | disposition |
|---|---|
| the periods were cured by the comprehensive report, the issuer is behind | **`freeze-pending-current-reporting`** ✓ |
| no amendment exists, so the periods are uncured | `freeze-pending-restatement` |
| `DTB-CR-2023A` applied, which recognises only amendments as a cure | `freeze-pending-restatement` |
| the first-quarter notification missed, so nothing is outstanding | `restore-rating` |

The first build of this task did not have that property. Every reading landed
on the same freeze, because the case starts frozen and both "never restated"
and "restated but behind" said keep it frozen. The comprehensive-10-K finding
— the whole point of the task — cost nothing to get wrong, and neither did
the policy version. Three dispositions fix it.

## Decision types on the oracle path

1. which periods reliance was withdrawn from
2. which dated policy version governs the snapshot
3. whether a comprehensive annual report is a cure under that version
4. which of the two outstanding notifications still has no report behind it
5. which of three terminal actions the rule supports

Five schemas, mutually dependent. Interaction depth is 12; decision depth is
5.

## No fact the graph does not carry

Delinquency is "a notification is on file and its report is not", which the
index answers by itself. An earlier version keyed referral to a report being
delinquent for more than sixty days; that count runs from the prescribed due
date plus five, and the prescribed due date is nowhere in the graph, so the
agent would have needed to know the filing deadline for a 10-Q. That is the
rule deciding the answer with outside help, which `DESIGN.md` rules out.
`test_the_rule_needs_no_fact_the_graph_does_not_carry` keeps it out.

## Frozen pilot

Eight episodes on this revision. Runs made before the disposition wording fix
are excluded: the ticket text changed, so they are not comparable.

| model | success | steps | attainment | progress | NDR |
|---|---|---|---:|---:|---:|
| Claude Opus 5 | **3/3** | 17 / 17 / 17 | 0.706 | 1.000 | 0.417 |
| DeepSeek V4 Pro | **2/5** | 14 / 16 / — / — / — | 0.321 | 0.850 | 0.550 |

No terminal failures and no give-ups in either arm. Every DeepSeek failure is
budget exhaustion with a remaining bound of exactly 3 — the review, the
disposition and the commit — so the packet was never completed rather than the
answer being got wrong.

**The two models fail differently, and success rate alone hides it.** Opus
finishes every time and finishes at 1.42× the bound, the same route to the
step on all three runs. DeepSeek finishes less than half the time but its
successes run at 1.17× and 1.33×, tighter than anything Opus produced. More
reliable and less efficient is a real distinction and this is the metric that
shows it.

Where the extra steps go is visible in the trajectories. Opus spends two of
them probing the review gate before the packet is complete, one on the
amendment view, one on the second quarterly notification, and one on an Item
3.01 listing-deficiency notice it checks on its own initiative. All five are
real records; none of them changes the answer.

## What the pilot caught that the build checks could not

The first Opus arm was 0/5, every episode `gave_up` with a remaining bound of
1: it selected the correct disposition and then stopped without committing it.
The cause was a sentence in the ticket — "a recorded disposition closes it" —
written to convey that there is one attempt, and read, correctly, as saying
the case ends when the disposition is recorded. The model was doing what the
task told it.

Eleven build checks and nineteen tests passed throughout. Only a real
trajectory shows a task contradicting itself.

`19_enterprise_duplicate_incident` carries the same shape and its single Opus
pilot has the same signature (`gave_up`, remaining bound 1, recoverable). One
episode per model cannot separate that from variance; five can.

## Known limits

**The gate enforces the policy version rather than testing it.** `policy_2024b`
is in the review gate's `requires_visited`, so an agent that reads only the
superseded version is told something is missing instead of being allowed to
answer wrongly. Currency is therefore tested at the point of application —
the disposition — and not at the point of selection. Tasks 19 to 21 have the
same shape.

**One snapshot, one answer direction.** Only `freeze-pending-current-reporting`
is correct here. The other two directions are real at other snapshots (20 June
2024 gives `freeze-pending-restatement`, 1 November 2024 gives
`restore-rating`) but no instance has been built for them yet, so this task
cannot carry an answer-distinctness claim on its own.

**Contamination is untested.** The filings are public and dated 2024, so a
model may recognise the issuer. Nothing here has been compared against a
paraphrased control.

## Provenance boundary

Filing metadata, the Item 4.02 statement, the Explanatory Note and the Rule
12b-25 notification are observed in the frozen SEC EDGAR extract and quoted
as filed. The credit policy, case packet, trustee-correspondence fact and
write actions are authored DetourBench overlays. They are not any
institution's credit process, and nothing here expresses a view on the
issuer.

## Rebuild

    python3 fetch_edgar_ppsi.py        # refreeze from EDGAR
    python3 generate_finance_suite.py  # rebuild and verify this directory
    python3 -m unittest test_finance_topologies
