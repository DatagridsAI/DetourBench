# 25 — finance_comment_letter_settled

Classification: Integrated development challenge. SEC EDGAR filing metadata
and the quoted correspondence are observed; the disclosure-review policy,
case packet and write actions are authored benchmark overlays.

- Frozen corpus: `corpora_edgar_hear.json`
- Task revision: `finance-edgar-v1`
- Evidence cluster: `edgar-hear-2023-nongaap-review`
- Nodes: 62 · Edges: 113 · edges/nodes 1.82
- Exact lower bound: 12 · Hard budget: 18 · bound/nodes 0.19
- Identifiers available per step along the oracle, median: 57
- Primary mechanism: **Sufficiency**
- Supporting mechanisms: Currency, Depth, Breadth
- Oracle witness: replayed successfully in 12 steps
- Semantic necessity audit: passed
- Pilots: none yet

## What the case is

Diligence flagged the non-GAAP presentation in Turtle Beach Corporation's
fiscal 2022 annual report. Snapshot is 30 April 2024. Record one disposition.

Between August and December 2023 the Division of Corporation Finance ran a
three-round review of exactly that disclosure. It named the rule:

> Your presentation appears to give greater prominence to the non-GAAP
> measures and does not comply with Item 10(e)(1)(i)(A) of Regulation S-K and
> Question 102.10 of the Division's Compliance & Disclosure Interpretations

The issuer undertook to revise, a second comment on the adjustments
themselves was raised and undertaken in the same way, and the staff closed
the review.

## Why deriving the answer is the wrong move

This is Sufficiency in the sense `DESIGN.md` gives it: an authoritative
answer already exists, and working one out from Item 10(e) is correct on its
own terms and refused. The governing policy version says so; the superseded
one says the opposite, which is what makes the version a decision rather
than a formality.

## And why the closing letter is not clearance

The staff's closing letter says what completing a review means, and it is
not what an agent looking for a clean bill of health would like it to say:

> We have completed our review of your filing. We remind you that the company
> and its management are responsible for the accuracy and adequacy of their
> disclosures, **notwithstanding any review, comments, action or absence of
> action by the staff.**

Both wrong answers are refuted in the documents' own words. Neither is
authored.

## Each way of being wrong lands somewhere different

| reading | disposition |
|---|---|
| the staff commented and the issuer undertook to revise | **`staff-comment-governs`** ✓ |
| no staff comment reaches this disclosure, so determine it yourself | `derive-independent-determination` |
| `DTB-DR-2022A` applied, which tells the desk to determine it itself | `derive-independent-determination` |
| the completed review means the staff approved the disclosure | `treat-review-as-clearance` |

Checked at build time by `readings_reach_different_actions`.

## Decision types on the oracle path

1. whether a staff review reached this disclosure at all
2. which dated policy version governs the snapshot
3. what the staff actually required, and whether the issuer undertook it
4. whether both comments were resolved, not only the first
5. what completing a review does and does not mean
6. which of three terminal actions the rule supports

Interaction depth 12; decision depth 6.

## Provenance boundary

Filing metadata, the staff's comments and closing letter, and the issuer's
responses are observed in the frozen SEC EDGAR extract and quoted as filed.
The disclosure-review policy, case packet and write actions are authored
DetourBench overlays. They are not any institution's review process, and
nothing here expresses a view on the issuer.

## Rebuild

    python3 fetch_edgar_hear.py
    python3 generate_finance_suite.py
    python3 -m unittest test_finance_topologies
