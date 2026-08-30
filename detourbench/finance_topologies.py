#!/usr/bin/env python3
"""Finance integrated task: is the issuer's financial reporting reliable?

The mechanism this family adds is one the regulatory corpora cannot carry:
a stated fact about a company can be *withdrawn* and later *replaced*, and
the replacement need not arrive in the form the withdrawal implies. Here an
Item 4.02 8-K withdraws reliance on eight reporting periods, and the cure
arrives as a Comprehensive Form 10-K - a filing that restates prior periods
inside a current annual report. The issuer says in that filing that it will
never amend the original reports.

So the route an analyst reaches for first, a search for 10-K/A and 10-Q/A,
returns six real amendments, the most recent covering fiscal 2019, and none
covering the affected periods. That is not a decoy we wrote. It is what the
company filed.

Provenance: filing metadata and the quoted passages are observed in EDGAR.
The credit policy, the review packet, the trustee-notice fact and the three
write actions are authored DetourBench overlay and are marked as such in
node_provenance. Nothing here evaluates the issuer.
"""
import json
import os

from topologies import Builder

ROOT = os.path.dirname(os.path.abspath(__file__))
CORPUS_FILE = "corpora_edgar_ppsi.json"

SNAPSHOT = "2024-08-20"
EDGAR = "edgar://cik/1449792"

# Rows the task reaches by accession number. Everything else in the frozen
# index is real, addressable, and off route.
ACC_8K_402 = "0001493152-24-022972"
ACC_TENK_2023 = "0001493152-24-029269"
ACC_NT10Q_Q1 = "0001493152-24-020241"
ACC_NT10Q_Q2 = "0001493152-24-032617"
ACC_NT10K = "0001493152-24-012853"

# The reports the two quoted passages name by period. Both the Item 4.02
# statement and the explanatory note list these four and nothing else, so the
# edges out of those nodes are the filings the source itself cites - the same
# relation eCFR's "Cross-references" line carries.
ACC_AFFECTED = (
    "0001493152-23-011850",   # 10-K, fiscal year ended 2022-12-31
    "0001493152-23-017462",   # 10-Q, quarter ended 2023-03-31
    "0001493152-23-028464",   # 10-Q, quarter ended 2023-06-30
    "0001493152-23-041076",   # 10-Q, quarter ended 2023-09-30
)

# Three dispositions a credit committee would actually distinguish, and the
# reason they are these three: each of the two ways of getting this case wrong
# lands on a different one. Reading the superseded policy, or looking for an
# amendment and not finding one, both say the historicals are still bad -
# freeze-pending-restatement. Missing the outstanding quarterly notification
# says everything is fine - restore-rating. Only the correct reading, that a
# comprehensive annual report cured the periods while the issuer stayed behind
# on its quarterlies, lands on freeze-pending-current-reporting.
CANDIDATE_ACTIONS = ("restore-rating", "freeze-pending-restatement",
                     "freeze-pending-current-reporting")
CORRECT_ACTION = "freeze-pending-current-reporting"


def load_corpus():
    path = os.path.join(ROOT, CORPUS_FILE)
    with open(path, encoding="utf-8") as f:
        return json.load(f), path


def _row_desc(row):
    """A filing index row in the words EDGAR uses for it."""
    items = f" Items {row['items']}." if row.get("items") else ""
    described = row.get("primaryDocDescription") or row["form"]
    return (f"{row['form']} filed {row['filingDate']}, period of report "
            f"{row['reportDate'] or 'n/a'}.{items} Primary document: "
            f"{described}. Accession {row['accessionNumber']}. "
            f"File number {row.get('fileNumber') or 'n/a'}.")


def _accession_uri(accession):
    return f"{EDGAR}/accession/{accession}"


def _node_id(accession):
    return "f_" + accession.replace("-", "")


def restatement_reliance_case():
    """DTB-SEC-22. Returns (graph, meta_fragments) for generate_finance_suite."""
    corpus, corpus_path = load_corpus()
    index = corpus["observed_filing_index"]
    excerpts = corpus["observed_excerpts"]
    issuer = corpus["issuer"]
    b = Builder()

    # ---------------------------------------------------------------- packet
    b.node("start", (
        "Credit review case DTB-SEC-22, snapshot 2024-08-20. The desk holds a "
        "privately placed note of Pioneer Power Solutions, Inc. (CIK "
        "0001449792). Internal policy freezes the issuer's internal rating "
        "once the issuer states that previously issued financial statements "
        "may no longer be relied upon, and keeps it frozen until the affected "
        "periods have been restated and every periodic report is current. "
        "Determine the status of the affected periods as of the snapshot "
        "under the policy version in force, and record one final disposition. "
        "Selecting a disposition forecloses the others, so there is one "
        "attempt. A selected disposition is not filed until it has been "
        "committed to the credit file, which is the step that closes the "
        "case."))
    b.edge("start", "e_case", "case", "workflow://DTB-SEC-22", "endpoint")

    b.node("case", (
        "Case packet DTB-SEC-22. Issuer: "
        f"{issuer['name']}, CIK {issuer['cik']}, "
        f"{'/'.join(issuer['tickers'])} on {'/'.join(issuer['exchanges'])}. "
        f"Fiscal year end {issuer['fiscal_year_end']}. "
        "Position: senior unsecured note, held at amortised cost.\n"
        "The desk's credit policy is versioned; the register lists which "
        "version governs a given snapshot date. The issuer's filing history "
        "is available as a periodic-report index.\n"
        "[Case annotation: this packet, the policy register and the "
        "disposition actions are DetourBench overlay. Filing records and "
        "quoted passages are the issuer's own SEC filings.]"))
    b.edge("case", "e_policy_register", "policy_register",
           "policy://detourbench/credit-review/register", "file")
    # The filing diligence actually flagged. The packet names it the way a
    # regulatory ticket names its opening provision; everything else is
    # reached from documents that cite it or from a scoped search.
    b.edge("case", "e_seed", _node_id(ACC_8K_402), _accession_uri(ACC_8K_402),
           "file")
    b.edge("case", "e_amendment_search", "amendment_search",
           f"{EDGAR}/filings?type=10-K%2FA,10-Q%2FA", "endpoint")

    # -------------------------------------------------------------- currency
    b.node("policy_register", (
        "Credit policy register — non-reliance and reporting currency.\n"
        "DTB-CR-2023A  in force 2023-01-01 through 2024-03-31\n"
        "DTB-CR-2024B  in force 2024-04-01 through 2026-12-31\n"
        "DTB-CR-2027C  in force from 2027-01-01\n"
        "The version in force on the snapshot date governs the case."))
    for vid, label, span in (
            ("policy_2023a", "DTB-CR-2023A", "2023-01-01 .. 2024-03-31"),
            ("policy_2024b", "DTB-CR-2024B", "2024-04-01 .. 2026-12-31"),
            ("policy_2027c", "DTB-CR-2027C", "from 2027-01-01")):
        b.edge("policy_register", f"e_{vid}", vid,
               f"policy://detourbench/credit-review/{label}", "file")

    b.node("policy_2023a", (
        "DTB-CR-2023A (in force 2023-01-01 .. 2024-03-31).\n"
        "1. On an issuer statement of non-reliance, freeze the internal "
        "rating.\n"
        "2. The affected periods are cured only when the issuer files an "
        "amended periodic report (Form 10-K/A or Form 10-Q/A) for each "
        "affected period.\n"
        "3. While any affected period is uncured, record "
        "freeze-pending-restatement. This version does not distinguish "
        "delinquent reporting from unreliable reporting."))
    b.node("policy_2024b", (
        "DTB-CR-2024B (in force 2024-04-01 .. 2026-12-31). Supersedes "
        "DTB-CR-2023A.\n"
        "1. On an issuer statement of non-reliance, freeze the internal "
        "rating.\n"
        "2. The affected periods are cured when restated financial statements "
        "for those periods have been filed in any periodic report, including "
        "a comprehensive annual report that restates prior periods within it. "
        "An amended periodic report is one permitted form of cure, not the "
        "only one.\n"
        "3. A periodic report is delinquent when a Rule 12b-25 notification "
        "has been filed for it and the report itself is not on file at the "
        "snapshot date. A report filed after its notification is not "
        "delinquent, whenever it was filed.\n"
        "4. Record exactly one disposition:\n"
        "   restore-rating — every affected period is cured and no periodic "
        "report is delinquent;\n"
        "   freeze-pending-restatement — any affected period is uncured;\n"
        "   freeze-pending-current-reporting — every affected period is cured "
        "and at least one periodic report is delinquent.\n"
        "5. Rule 4 is read in order: an uncured period governs over a "
        "delinquent report."))
    b.node("policy_2027c", (
        "DTB-CR-2027C (in force from 2027-01-01). Not applicable to snapshots "
        "before 2027-01-01. Adds an issuer-level auditor-change review that "
        "DTB-CR-2024B does not contain."))

    # --------------------------------------------------- observed EDGAR index
    # EDGAR is searched by form type and by 8-K item, and that is how the
    # graph exposes it. A single index node listing every filing would hand
    # over the whole map in one step: DESIGN.md measured large search spaces
    # not to create difficulty, and an agent that has seen everything is no
    # longer paying for discovery. Each view is a real filter and costs a
    # step, so what an agent knows depends on what it thought to ask for.
    listed = []
    for row in index:
        nid = _node_id(row["accessionNumber"])
        listed.append((nid, row))
        b.node(nid, _row_desc(row))

    def _view(vid, uri, headline, subset):
        b.node(vid, (
            f"{headline} CIK {issuer['cik']}, "
            f"{len(subset)} records.\n" + "\n".join(
                f"{r['filingDate']}  {r['form']:<9} period "
                f"{r['reportDate'] or '-':<10}"
                f"  {('items ' + r['items']) if r.get('items') else '':<22}"
                f"  {r['accessionNumber']}" for r in subset)))
        b.edge("case", f"e_{vid}", vid, uri, "endpoint")
        for r in subset:
            b.edge(vid, f"e_{vid}_{_node_id(r['accessionNumber'])}",
                   _node_id(r["accessionNumber"]),
                   _accession_uri(r["accessionNumber"]), "file")

    annual = [r for r in index if r["form"] == "10-K"]
    quarterly = [r for r in index if r["form"] == "10-Q"]
    late = [r for r in index if r["form"].startswith("NT ")]
    material = [r for r in index if r["form"] == "8-K"
                and any(i in (r["items"] or "")
                        for i in ("4.01", "4.02", "3.01"))]
    routine = [r for r in index if r["form"] == "8-K" and r not in material]
    other = [r for r in index
             if r["form"] not in ("10-K", "10-Q", "8-K")
             and not r["form"].startswith("NT ")]

    _view("view_annual", f"{EDGAR}/filings?type=10-K",
          "EDGAR search, annual reports on Form 10-K for", annual)
    _view("view_quarterly", f"{EDGAR}/filings?type=10-Q",
          "EDGAR search, quarterly reports on Form 10-Q for", quarterly)
    _view("view_late", f"{EDGAR}/filings?type=NT",
          "EDGAR search, Rule 12b-25 late-filing notifications for", late)
    _view("view_material_8k", f"{EDGAR}/filings?type=8-K&items=3.01,4.01,4.02",
          "EDGAR search, current reports carrying an accountant, "
          "non-reliance or listing-compliance item for", material)
    # Routine current reports are paginated the way task 21 pages its batch:
    # the count is large and no single step should hand all of it over.
    for i in range(0, len(routine), 7):
        page = routine[i:i + 7]
        n = i // 7 + 1
        _view(f"view_routine_8k_p{n}",
              f"{EDGAR}/filings?type=8-K&page={n}",
              f"EDGAR search, other current reports, page {n} of "
              f"{-(-len(routine) // 7)}, for", page)
    _view("view_other", f"{EDGAR}/filings?type=other",
          "EDGAR search, proxy, registration and correspondence filings for",
          other)

    # The amendment view: real, non-empty, and about other periods entirely.
    amendments = corpus["observed_amendment_view"]
    b.node("amendment_search", (
        "EDGAR filing index for CIK 0001449792 filtered to Form 10-K/A and "
        f"Form 10-Q/A, all dates through {SNAPSHOT}, {len(amendments)} "
        "records.\n"
        + "\n".join(
            f"{r['filingDate']}  {r['form']:<7} period {r['reportDate']}"
            f"  {r['accessionNumber']}" for r in amendments)))

    # ------------------------------------------------- documents on the route
    node_402 = "f_" + ACC_8K_402.replace("-", "")
    node_10k = "f_" + ACC_TENK_2023.replace("-", "")

    b.nodes[node_402]["desc"] = (
        _row_desc(next(r for r in index
                       if r["accessionNumber"] == ACC_8K_402))
        + "\n\n" + excerpts["item_402"])

    b.nodes[node_10k]["desc"] = (
        _row_desc(next(r for r in index
                       if r["accessionNumber"] == ACC_TENK_2023))
        + "\n\nThe filing opens with a section headed EXPLANATORY NOTE, "
        "before Part I, describing what this report contains and which "
        "previously filed periods it covers.")
    b.edge(node_10k, "e_explanatory", "explanatory_note",
           _accession_uri(ACC_TENK_2023) + "/explanatory-note", "file")

    b.node("explanatory_note", (
        "Form 10-K for the fiscal year ended December 31, 2023 — EXPLANATORY "
        "NOTE.\n\n" + excerpts["explanatory_note"]
        + "\n\n" + excerpts["no_amendments_sentence"]))

    node_nt_q1 = "f_" + ACC_NT10Q_Q1.replace("-", "")
    node_nt_q2 = "f_" + ACC_NT10Q_Q2.replace("-", "")
    b.nodes[node_nt_q1]["desc"] = (
        _row_desc(next(r for r in index
                       if r["accessionNumber"] == ACC_NT10Q_Q1))
        + "\n\n" + excerpts["nt10q_q1"])

    # ------------------------------------------- cross-references the source makes
    # Both quoted passages name the four affected reports by period, and the
    # explanatory note names the 8-K by its filing date. Those citations are
    # the issuer's own; they are edges for the same reason a section's
    # "Cross-references" line is an edge.
    for i, accession in enumerate(ACC_AFFECTED):
        b.edge(node_402, f"e_402_ref{i}", _node_id(accession),
               _accession_uri(accession), "file")
        b.edge("explanatory_note", f"e_note_ref{i}", _node_id(accession),
               _accession_uri(accession), "file")
    b.edge("explanatory_note", "e_note_ref_8k", node_402,
           _accession_uri(ACC_8K_402), "file")
    # "delays in compiling information required to be included in the
    # Company's Annual Report on Form 10-K for the year ended December 31,
    # 2023" - the notification's own words.
    b.edge(node_nt_q1, "e_nt_ref_10k", node_10k,
           _accession_uri(ACC_TENK_2023), "file")

    # ---------------------------------------------------------- the decision
    node_nt_10k = _node_id(ACC_NT10K)
    b.nodes[node_nt_10k]["desc"] = (
        _row_desc(next(r for r in index
                       if r["accessionNumber"] == ACC_NT10K))
        + "\n\nRule 12b-25 notification of late filing for the annual report "
        "on Form 10-K for the year ended December 31, 2023.")
    required = ["policy_2024b", node_402, node_10k, "explanatory_note",
                node_nt_10k, node_nt_q1]
    b.node("review", (
        "Review packet DTB-SEC-22 assembled. Governing policy version, the "
        "issuer's periodic-report index, the non-reliance statement, the "
        "annual report and its explanatory note, the outstanding Rule 12b-25 "
        "notification and both outstanding late-filing notifications are all "
        "on file. Record one disposition."))
    b.edge("case", "e_review", "review", "workflow://DTB-SEC-22/review",
           "endpoint", requires_visited=required)

    b.node("restored", (
        "Disposition selected: internal rating restored. No further step is "
        "available on this case."))
    b.node("frozen_restatement", (
        "Disposition selected: rating frozen pending restatement of the "
        "affected periods. No further step is available on this case."))
    b.node("frozen_reporting", (
        "Disposition selected: rating frozen pending the issuer becoming "
        "current on its periodic reporting. Not yet filed. Commit it to the "
        "credit file to close the case."))
    for action, node in (("restore-rating", "restored"),
                         ("freeze-pending-restatement", "frozen_restatement"),
                         ("freeze-pending-current-reporting",
                          "frozen_reporting")):
        b.edge("review", f"e_{action}", node,
               f"workflow://DTB-SEC-22/actions/{action}", "endpoint",
               requires="packet_complete")

    b.node("target", (
        "Disposition committed to the credit file for DTB-SEC-22."))
    b.edge("frozen_reporting", "e_target", "target",
           "audit://DTB-SEC-22/commit",
           "endpoint", requires="disposition_recorded")

    spec = {
        "run_name": "finance_restatement_reliance",
        "corpus_file": CORPUS_FILE,
        "corpus_path": corpus_path,
        "terminal_fail_nodes": ["restored", "frozen_restatement"],
        "candidate_actions": list(CANDIDATE_ACTIONS),
        "correct_action": CORRECT_ACTION,
        "primary_mechanism": "Disposition",
        "supporting_mechanisms": ["Currency", "Depth", "Breadth"],
        "unsupported_not_claimed": ["Sufficiency", "Time"],
        "crosswalk_basis": {
            "Disposition": "three terminal actions follow the same evidence packet",
            "Currency": "the superseded version recognises only an amended report as a cure, so reading it records freeze-pending-restatement where the version in force records freeze-pending-current-reporting - the two disagree on the answer, not only on the wording",
            "Depth": "the cure is stated only inside the annual report's explanatory note, one level below the index row",
            "Breadth": "the non-reliance statement, the explanatory note, the outstanding notification and the policy are all required",
        },
        "domain_mechanisms": [
            "non-reliance and cure",
            "comprehensive annual report in place of amendments",
            "delinquency as an unfiled report behind a live notification",
            "absent amendment with a real but off-period amendment history",
        ],
        "mechanism_regions": {
            "observed_filing_evidence": [
                "filing_index", node_402, node_10k, "explanatory_note",
                node_nt_q1, node_nt_q2],
            "observed_relationship": ["amendment_search"],
            "policy_currency": ["policy_register", "policy_2023a",
                                "policy_2024b", "policy_2027c"],
            "decision": ["review", "frozen_reporting", "target", "restored",
                         "frozen_restatement"],
            "off_route_context": [
                nid for nid, _ in listed
                if nid not in {node_402, node_10k, node_nt_q1, node_nt_q2}],
        },
        "semantic_required_nodes": required,
        "semantic_necessity": {
            "policy_2024b": "states the cure definition and the delinquency and referral rules in force on the snapshot",
            node_402: "names the periods on which reliance was withdrawn",
            node_10k: "is the filing that carries the restatement, and points at its explanatory note",
            "explanatory_note": "states that this comprehensive report restates the affected periods and that no amendments will be filed",
            node_nt_q1: "establishes the outstanding first-quarter notification whose report is not on file at the snapshot",
            node_nt_10k: "establishes the annual notification whose report was filed, the check that has to come back negative before any report can be called delinquent",
        },
        "observed_nodes": [nid for nid, _ in listed] + [
            "amendment_search", "explanatory_note",
            "view_annual", "view_quarterly", "view_late",
            "view_material_8k", "view_other"]
        + [f"view_routine_8k_p{i}" for i in range(1, 6)],
        "authored_nodes": [
            "start", "case", "policy_register", "policy_2023a",
            "policy_2024b", "policy_2027c", "review", "restored",
            "frozen_restatement", "frozen_reporting", "target"],
        "route_nodes_for_readme": required,
    }
    grants = {"review": "packet_complete",
              "frozen_reporting": "disposition_recorded"}
    return b, spec, grants


# ---------------------------------------------------------------------------
# Task 25 — finance_comment_letter_settled
#
# Sufficiency, in the sense DESIGN.md gives it: an authoritative answer
# already exists, and deriving one is correct on its own terms and refused.
# The Division of Corporation Finance ran a three-round non-GAAP review of
# this issuer to completion. It named the rule, the company undertook to
# revise, and the staff closed the review with a letter saying that closing
# it does not transfer responsibility for the disclosure. So there are two
# ways to be wrong and they are opposites: derive your own determination when
# one already exists, or read the closing letter as clearance when it says it
# is not.
# ---------------------------------------------------------------------------

HEAR_CORPUS_FILE = "corpora_edgar_hear.json"
HEAR_SNAPSHOT = "2024-04-30"
HEAR_EDGAR = "edgar://cik/1493761"

HEAR_ACTIONS = ("derive-independent-determination", "staff-comment-governs",
                "treat-review-as-clearance")
HEAR_CORRECT = "staff-comment-governs"


def _hear_uri(accession):
    return f"{HEAR_EDGAR}/accession/{accession}"


def comment_letter_settled_case():
    """DTB-SEC-25. Returns (builder, spec, grants)."""
    path = os.path.join(ROOT, HEAR_CORPUS_FILE)
    with open(path, encoding="utf-8") as f:
        corpus = json.load(f)
    index = corpus["observed_filing_index"]
    ex = corpus["observed_excerpts"]
    acc = corpus["accessions"]
    issuer = corpus["issuer"]
    b = Builder()

    b.node("start", (
        "Disclosure-review case DTB-SEC-25, snapshot 2024-04-30. Pre-trade "
        "diligence on Turtle Beach Corporation (CIK 0001493761) flagged the "
        "non-GAAP presentation in the fiscal 2022 annual report as possibly "
        "non-compliant. Establish how that question stands as of the "
        "snapshot and record one disposition. Desk policy is versioned and "
        "the register says which version governs a snapshot date. Selecting "
        "a disposition forecloses the others, so there is one attempt. A "
        "selected disposition is not filed until it has been committed to "
        "the review file, which is the step that closes the case."))
    b.edge("start", "e_case", "case", "workflow://DTB-SEC-25", "endpoint")

    b.node("case", (
        f"Case packet DTB-SEC-25. Issuer: {issuer['name']}, CIK "
        f"{issuer['cik']}, {'/'.join(issuer['tickers'])} on "
        f"{'/'.join(issuer['exchanges'])}. Fiscal year end "
        f"{issuer['fiscal_year_end']}.\n"
        "The question raised in diligence: whether the fiscal 2022 non-GAAP "
        "presentation complied, and what the issuer is now required to do.\n"
        "Available: the registrant's filing index for the review window, and "
        "the desk's disclosure-review policy register.\n"
        "[Case annotation: this packet, the policy register and the "
        "disposition actions are DetourBench overlay. Filing records and "
        "quoted passages are SEC EDGAR documents.]"))
    b.edge("case", "e_policy_register", "policy_register",
           "policy://detourbench/disclosure-review/register", "file")
    # The filing diligence flagged. Named in the packet the way a regulatory
    # ticket names its opening provision.
    b.edge("case", "e_seed", _node_id(acc["tenk_2022"]),
           _hear_uri(acc["tenk_2022"]), "file")

    b.node("policy_register", (
        "Disclosure-review policy register.\n"
        "DTB-DR-2022A  in force 2022-01-01 through 2023-06-30\n"
        "DTB-DR-2023B  in force 2023-07-01 through 2026-12-31\n"
        "DTB-DR-2027C  in force from 2027-01-01\n"
        "The version in force on the snapshot date governs the case."))
    for vid, label in (("policy_2022a", "DTB-DR-2022A"),
                       ("policy_2023b", "DTB-DR-2023B"),
                       ("policy_2027c", "DTB-DR-2027C")):
        b.edge("policy_register", f"e_{vid}", vid,
               f"policy://detourbench/disclosure-review/{label}", "file")

    b.node("policy_2022a", (
        "DTB-DR-2022A (in force 2022-01-01 .. 2023-06-30).\n"
        "1. Where diligence questions a disclosure, the desk makes its own "
        "determination against the governing rule and records it.\n"
        "2. Staff correspondence is background. It does not substitute for "
        "the desk's determination."))
    b.node("policy_2023b", (
        "DTB-DR-2023B (in force 2023-07-01 .. 2026-12-31). Supersedes "
        "DTB-DR-2022A.\n"
        "1. Where the Division of Corporation Finance has commented on the "
        "same disclosure and the issuer has responded, the staff comment and "
        "the issuer's undertaking dispose of the question. The desk records "
        "that, and does not make a parallel determination of its own.\n"
        "2. Rule 1 applies whether or not the staff review is closed. A "
        "closed review is evidence the exchange finished, not evidence the "
        "disclosure was approved.\n"
        "3. Completion of a staff review is never recorded as clearance. "
        "The staff's closing letter states what it does and does not mean; "
        "read it rather than inferring.\n"
        "4. Record exactly one disposition:\n"
        "   staff-comment-governs — the staff commented and the issuer "
        "undertook to revise;\n"
        "   derive-independent-determination — no staff comment reaches this "
        "disclosure;\n"
        "   treat-review-as-clearance — the staff has affirmatively approved "
        "the disclosure."))
    b.node("policy_2027c", (
        "DTB-DR-2027C (in force from 2027-01-01). Not applicable to "
        "snapshots before 2027-01-01."))

    listed = []
    for row in index:
        nid = _node_id(row["accessionNumber"])
        listed.append((nid, row))
        b.node(nid, _row_desc(row))

    def _view(vid, uri, headline, subset):
        b.node(vid, (
            f"{headline} CIK {issuer['cik']}, {len(subset)} records.\n"
            + "\n".join(
                f"{r['filingDate']}  {r['form']:<9} period "
                f"{r['reportDate'] or '-':<10}"
                f"  {('items ' + r['items']) if r.get('items') else '':<22}"
                f"  {r['accessionNumber']}" for r in subset)))
        b.edge("case", f"e_{vid}", vid, uri, "endpoint")
        for r in subset:
            b.edge(vid, f"e_{vid}_{_node_id(r['accessionNumber'])}",
                   _node_id(r["accessionNumber"]),
                   _hear_uri(r["accessionNumber"]), "file")

    corr = [r for r in index if r["form"] in ("UPLOAD", "CORRESP")]
    annual = [r for r in index if r["form"] in ("10-K", "10-K/A", "NT 10-K")]
    quarterly = [r for r in index
                 if r["form"] in ("10-Q", "10-Q/A", "NT 10-Q")]
    current = [r for r in index if r["form"].startswith("8-K")]
    # Correspondence is paged the way task 21 pages its review batch: the
    # later rounds are behind a continuation, so an agent that stops at the
    # first page has the opening comment and not the resolution. Two rounds
    # per page follows the exchange's own round structure.
    half = (len(corr) + 1) // 2
    pages = [corr[:half], corr[half:]]
    for n, page in enumerate(pages, 1):
        vid = f"view_correspondence_p{n}"
        tail = ("A continuation page remains."
                if n < len(pages) else "End of the correspondence file.")
        b.node(vid, (
            f"EDGAR search, staff correspondence for CIK {issuer['cik']}, "
            f"page {n} of {len(pages)}, {len(page)} records. {tail}\n"
            + "\n".join(
                f"{r['filingDate']}  {r['form']:<9} {r['accessionNumber']}"
                for r in page)))
        if n == 1:
            b.edge("case", f"e_{vid}", vid,
                   f"{HEAR_EDGAR}/filings?type=UPLOAD,CORRESP&page=1",
                   "endpoint")
        else:
            b.edge(f"view_correspondence_p{n - 1}", f"e_{vid}", vid,
                   f"{HEAR_EDGAR}/filings?type=UPLOAD,CORRESP&page={n}",
                   "endpoint")
        for r in page:
            b.edge(vid, f"e_{vid}_{_node_id(r['accessionNumber'])}",
                   _node_id(r["accessionNumber"]),
                   _hear_uri(r["accessionNumber"]), "file")
    _view("view_annual", f"{HEAR_EDGAR}/filings?type=10-K",
          "EDGAR search, annual filings for", annual)
    _view("view_quarterly", f"{HEAR_EDGAR}/filings?type=10-Q",
          "EDGAR search, quarterly filings for", quarterly)
    for i in range(0, len(current), 7):
        n = i // 7 + 1
        _view(f"view_current_p{n}", f"{HEAR_EDGAR}/filings?type=8-K&page={n}",
              f"EDGAR search, current reports, page {n} of "
              f"{-(-len(current) // 7)}, for", current[i:i + 7])

    n_10k = _node_id(acc["tenk_2022"])
    n_up1 = _node_id(acc["upload_1"])
    n_cor1 = _node_id(acc["corresp_1"])
    n_cor3 = _node_id(acc["corresp_3"])
    n_close = _node_id(acc["upload_close"])

    b.nodes[n_10k]["desc"] += (
        "\n\nAnnual report for fiscal 2022. Item 7 carries a section headed "
        "Key Performance Indicators and Non-GAAP Measures.")
    b.nodes[n_up1]["desc"] += (
        "\n\nLetter from the Division of Corporation Finance.\n\n"
        + ex["review_scope"] + "\n\n" + ex["comment_prominence"])
    b.nodes[n_cor1]["desc"] += (
        "\n\nResponse from the registrant.\n\n" + ex["undertaking_prominence"])
    b.nodes[n_cor3]["desc"] += (
        "\n\nResponse from the registrant, third round.\n\n"
        + ex["comment_adjustments"] + "\n\n" + ex["undertaking_adjustments"])
    b.nodes[n_close]["desc"] += (
        "\n\nLetter from the Division of Corporation Finance.\n\n"
        + ex["review_completed"])

    # The exchange is a chain, and each document names the one before it.
    b.edge(n_up1, "e_up1_to_10k", n_10k, _hear_uri(acc["tenk_2022"]), "file")
    b.edge(n_cor1, "e_cor1_to_up1", n_up1, _hear_uri(acc["upload_1"]), "file")
    b.edge(n_up1, "e_up1_to_cor1", n_cor1, _hear_uri(acc["corresp_1"]), "file")
    b.edge(n_cor3, "e_cor3_to_close", n_close, _hear_uri(acc["upload_close"]),
           "file")
    b.edge(n_close, "e_close_to_10k", n_10k, _hear_uri(acc["tenk_2022"]),
           "file")

    required = ["policy_2023b", n_10k, n_up1, n_cor1, n_cor3, n_close]
    b.node("review", (
        "Review packet DTB-SEC-25 assembled. Governing policy version, the "
        "reviewed annual report, the staff's comment, "
        "the issuer's undertakings and the staff's closing letter are all on "
        "file. Record one disposition."))
    b.edge("case", "e_review", "review", "workflow://DTB-SEC-25/review",
           "endpoint", requires_visited=required)

    b.node("derived", (
        "Disposition selected: the desk records its own determination against "
        "Item 10(e). No further step is available on this case."))
    b.node("governs", (
        "Disposition selected: the staff comment and the issuer's "
        "undertakings dispose of the question. Not yet filed. Commit it to "
        "the review file to close the case."))
    b.node("cleared", (
        "Disposition selected: the completed staff review is recorded as "
        "clearance of the disclosure. No further step is available on this "
        "case."))
    for action, node in (("derive-independent-determination", "derived"),
                         ("staff-comment-governs", "governs"),
                         ("treat-review-as-clearance", "cleared")):
        b.edge("review", f"e_{action}", node,
               f"workflow://DTB-SEC-25/actions/{action}", "endpoint",
               requires="packet_complete")
    b.node("target", "Disposition committed to the review file for DTB-SEC-25.")
    b.edge("governs", "e_target", "target", "audit://DTB-SEC-25/commit",
           "endpoint", requires="disposition_recorded")

    spec = {
        "run_name": "finance_comment_letter_settled",
        "evidence_cluster_id": "edgar-hear-2023-nongaap-review",
        "objective": (
            "Disclosure-review case DTB-SEC-25, snapshot 2024-04-30. "
            "Establish how the fiscal 2022 non-GAAP question stands after "
            "the staff review and record one disposition under the policy "
            "version in force."),
        "corpus_file": HEAR_CORPUS_FILE,
        "corpus_path": path,
        "terminal_fail_nodes": ["derived", "cleared"],
        "candidate_actions": list(HEAR_ACTIONS),
        "correct_action": HEAR_CORRECT,
        "primary_mechanism": "Sufficiency",
        "supporting_mechanisms": ["Currency", "Depth", "Breadth"],
        "unsupported_not_claimed": ["Disposition", "Time"],
        "crosswalk_basis": {
            "Sufficiency": "an authoritative resolution of the same disclosure already exists, so deriving one is correct on its own terms and refused",
            "Currency": "the superseded version tells the desk to make its own determination, which records a different disposition than the version in force",
            "Depth": "the undertaking is reached through the comment that prompted it, and the closing letter through the round that preceded it",
            "Breadth": "two separate comments were raised and both had to be resolved before the review closed",
        },
        "domain_mechanisms": [
            "staff comment and issuer undertaking as a disposition",
            "completed review is not clearance, and says so",
            "multi-round correspondence chain",
        ],
        "mechanism_regions": {
            "observed_correspondence": [n_up1, n_cor1, n_cor3, n_close],
            "observed_filing_evidence": [n_10k],
            "observed_relationship": ["view_correspondence_p1",
                                      "view_correspondence_p2",
                                      "view_annual", "view_quarterly"],
            "policy_currency": ["policy_register", "policy_2022a",
                                "policy_2023b", "policy_2027c"],
            "decision": ["review", "governs", "target", "derived", "cleared"],
            "off_route_context": [nid for nid, _ in listed
                                  if nid not in {n_10k, n_up1, n_cor1,
                                                 n_cor3, n_close}],
        },
        "semantic_required_nodes": required,
        "semantic_necessity": {
            "policy_2023b": "states that a staff comment plus an issuer undertaking disposes of the question, and that a closed review is not clearance",
            n_10k: "is the filing the review was of, and the only place the presentation the comment describes can be seen",
            n_up1: "carries the staff comment and the rule it names",
            n_cor1: "carries the issuer's undertaking on the prominence comment",
            n_cor3: "carries the second comment and its undertaking, without which the review is not fully resolved",
            n_close: "states that the review is complete and that completing it does not transfer responsibility for the disclosure",
        },
        "observed_nodes": [nid for nid, _ in listed] + [
            "view_correspondence_p1", "view_correspondence_p2",
            "view_annual", "view_quarterly"]
        + [f"view_current_p{i}" for i in range(1, 4)],
        "authored_nodes": [
            "start", "case", "policy_register", "policy_2022a",
            "policy_2023b", "policy_2027c", "review", "derived", "governs",
            "cleared", "target"],
    }
    grants = {"review": "packet_complete", "governs": "disposition_recorded"}
    return b, spec, grants


# ---------------------------------------------------------------------------
# Shared scaffolding for the finance family.
#
# Three tasks in and the same four blocks kept being written out: a versioned
# policy register, EDGAR searches scoped by form or item, a review gate over
# the evidence, and three dispositions of which one commits. Extracting them
# keeps the differences between tasks visible - which is the point, since a
# family whose members differ only in prose is a reskin, not a suite.
# ---------------------------------------------------------------------------

def add_policy_register(b, prefix, versions, note=""):
    """versions: [(node_id, label, span, body)]. First edge from `case`."""
    b.node("policy_register", (
        f"{note}\n" if note else "")
        + "\n".join(f"{label}  in force {span}" for _, label, span, _ in versions)
        + "\nThe version in force on the snapshot date governs the case.")
    b.edge("case", "e_policy_register", "policy_register",
           f"policy://detourbench/{prefix}/register", "file")
    for nid, label, _, body in versions:
        b.node(nid, body)
        b.edge("policy_register", f"e_{nid}", nid,
               f"policy://detourbench/{prefix}/{label}", "file")


def add_scoped_view(b, vid, uri, headline, subset, uri_of, parent="case",
                    tail="", id_of=None):
    """One EDGAR search. Never a dump: callers pass a filtered subset.

    The check this exists to satisfy is `max_reveal_per_node`. A single index
    listing every filing hands over the map in one step, and DESIGN.md
    measured large search spaces not to create difficulty.
    """
    b.node(vid, (
        f"{headline} {len(subset)} records."
        + (f" {tail}" if tail else "") + "\n"
        + "\n".join(
            f"{r['filingDate']}  {r['form']:<9} period "
            f"{r['reportDate'] or '-':<10}"
            f"  {('items ' + r['items']) if r.get('items') else '':<22}"
            f"  {r['accessionNumber']}" for r in subset)))
    b.edge(parent, f"e_{vid}", vid, uri, "endpoint")
    # `id_of` lets a task whose records already exist under its own node ids
    # point at those. Without it a view mints a second node for the same
    # document under the same identifier, and `known` keeps whichever was
    # revealed last - two bodies, one address.
    nid_of = id_of or _node_id
    for r in subset:
        b.edge(vid, f"e_{vid}_{nid_of(r['accessionNumber'])}",
               nid_of(r["accessionNumber"]),
               uri_of(r["accessionNumber"]), "file")


def add_paged_views(b, base, uri_of, headline, rows_, per_page=7,
                    uri_tmpl=None, parent="case", id_of=None):
    """Pages chain: page n+1 is reached from page n, as task 21 does it."""
    pages = [rows_[i:i + per_page] for i in range(0, len(rows_), per_page)]
    for n, page in enumerate(pages, 1):
        vid = f"{base}_p{n}"
        tail = ("A continuation page remains." if n < len(pages)
                else "End of this search.")
        add_scoped_view(
            b, vid, (uri_tmpl or (base + "?page={n}")).format(n=n),
            f"{headline}, page {n} of {len(pages)}, ", page, uri_of,
            parent=parent if n == 1 else f"{base}_p{n - 1}", tail=tail,
            id_of=id_of)
    return [f"{base}_p{n}" for n in range(1, len(pages) + 1)]


def add_disposition_block(b, case_id, actions, correct, required, bodies,
                          review_text):
    """Three terminal actions, one of which still has to be committed.

    The wording matters and cost an Opus arm five episodes to learn: an
    action node that says "recorded" reads as the end of the task, so the
    two wrong ones say no further step is available and the right one says
    it is not yet filed.
    """
    b.node("review", review_text)
    b.edge("case", "e_review", "review", f"workflow://{case_id}/review",
           "endpoint", requires_visited=required)
    for action in actions:
        node, body = bodies[action]
        b.node(node, body)
        b.edge("review", f"e_{action}", node,
               f"workflow://{case_id}/actions/{action}", "endpoint",
               requires="packet_complete")
    b.node("target", f"Disposition committed to the case file for {case_id}.")
    b.edge(bodies[correct][0], "e_target", "target",
           f"audit://{case_id}/commit", "endpoint",
           requires="disposition_recorded")


# ---------------------------------------------------------------------------
# Task 30 — finance_listing_cure_period
#
# Currency. Two Nasdaq deficiencies are open at once and they cure on
# different terms. The bid-price deadline of 17 December 2024 is still in the
# record and reading it says the cure period has run out; a later notice
# replaced it with an extension to 16 June 2025. The annual-meeting
# deficiency cures through a plan the exchange accepts at its discretion, not
# automatically, and that distinction is what the disposition turns on.
# ---------------------------------------------------------------------------

CLRO_CORPUS_FILE = "corpora_edgar_clro.json"
CLRO_SNAPSHOT = "2025-02-14"
CLRO_EDGAR = "edgar://cik/840715"
CLRO_ACTIONS = ("exit-cure-period-expired", "hold-and-flag-discretionary-cure",
                "hold-unconditionally")
CLRO_CORRECT = "hold-and-flag-discretionary-cure"


def _clro_uri(accession):
    return f"{CLRO_EDGAR}/accession/{accession}"


def listing_cure_period_case():
    """DTB-SEC-30."""
    path = os.path.join(ROOT, CLRO_CORPUS_FILE)
    with open(path, encoding="utf-8") as f:
        corpus = json.load(f)
    index = corpus["observed_filing_index"]
    ex = corpus["observed_excerpts"]
    acc = corpus["accessions"]
    issuer = corpus["issuer"]
    b = Builder()

    b.node("start", (
        "Continued-listing case DTB-SEC-30, snapshot 2025-02-14. The book "
        "holds common stock of ClearOne, Inc. (CIK 0000840715). Compliance "
        "monitoring flagged a Nasdaq notice. Establish every continued-"
        "listing deficiency that is open on the snapshot date, the cure "
        "period running on each, and record one disposition under the policy "
        "version in force. Selecting a disposition forecloses the others, so "
        "there is one attempt. A selected disposition is not filed until it "
        "has been committed to the case file, which is the step that closes "
        "the case."))
    b.edge("start", "e_case", "case", "workflow://DTB-SEC-30", "endpoint")

    b.node("case", (
        f"Case packet DTB-SEC-30. Issuer: {issuer['name']}, CIK "
        f"{issuer['cik']}, {'/'.join(issuer['tickers'])} on "
        f"{'/'.join(issuer['exchanges'])}.\n"
        "Position: common stock, held long.\n"
        "What monitoring flagged: the current report filed 2025-01-15 "
        "carrying a continued-listing item.\n"
        "[Case annotation: this packet, the policy register and the "
        "disposition actions are DetourBench overlay. Filing records and "
        "quoted passages are SEC EDGAR documents.]"))
    b.edge("case", "e_seed", _node_id(acc["meeting_notice"]),
           _clro_uri(acc["meeting_notice"]), "file")

    add_policy_register(b, "listing-watch", [
        ("policy_2023a", "DTB-LW-2023A", "2023-01-01 through 2024-09-30", (
            "DTB-LW-2023A (in force 2023-01-01 .. 2024-09-30).\n"
            "1. Exit the position when the cure period for any open "
            "continued-listing deficiency has expired.\n"
            "2. The cure period is the one stated in the exchange's notice "
            "of the deficiency.")),
        ("policy_2024b", "DTB-LW-2024B", "2024-10-01 through 2026-12-31", (
            "DTB-LW-2024B (in force 2024-10-01 .. 2026-12-31). Supersedes "
            "DTB-LW-2023A.\n"
            "1. The cure period for a deficiency is the one currently in "
            "force. Where a later notice extends or replaces a stated date, "
            "the later date governs and the earlier one is spent.\n"
            "2. Every open deficiency is assessed, not only the one "
            "monitoring flagged.\n"
            "3. A cure is conditional where the exchange grants the "
            "exception at its discretion rather than on the issuer meeting a "
            "stated test. A conditional cure does not by itself require an "
            "exit, and must be flagged to the risk committee.\n"
            "4. Record exactly one disposition:\n"
            "   hold-unconditionally — every open deficiency has an "
            "unexpired cure and none of them is conditional;\n"
            "   hold-and-flag-discretionary-cure — every open deficiency has "
            "an unexpired cure and at least one is conditional;\n"
            "   exit-cure-period-expired — any open deficiency has no "
            "unexpired cure period.")),
        ("policy_2027c", "DTB-LW-2027C", "from 2027-01-01",
         "DTB-LW-2027C (in force from 2027-01-01). Not applicable to "
         "snapshots before 2027-01-01."),
    ], note="Continued-listing watch policy register.")

    listed = []
    for row in index:
        listed.append((_node_id(row["accessionNumber"]), row))
        b.node(_node_id(row["accessionNumber"]), _row_desc(row))

    listing = [r for r in index
               if r["form"].startswith("8-K") and "3.01" in (r["items"] or "")]
    annual = [r for r in index if r["form"] in ("10-K", "10-K/A", "NT 10-K")]
    quarterly = [r for r in index
                 if r["form"] in ("10-Q", "10-Q/A", "NT 10-Q")]
    proxy = [r for r in index if r["form"].startswith("DEF")]
    routine = [r for r in index if r["form"].startswith("8-K")
               and r not in listing]

    # Paged newest first. The oldest notice carries a compliance date that
    # expired over a year before the snapshot, and it is on the second page:
    # an agent that stops at page one cannot say which deficiencies are open.
    listing_pages = add_paged_views(
        b, "view_listing", _clro_uri,
        "EDGAR search, current reports carrying a continued-listing item",
        sorted(listing, key=lambda r: r["filingDate"], reverse=True),
        per_page=2,
        uri_tmpl=CLRO_EDGAR + "/filings?type=8-K&items=3.01&page={n}")
    add_scoped_view(b, "view_annual", f"{CLRO_EDGAR}/filings?type=10-K",
                    "EDGAR search, annual filings,", annual, _clro_uri)
    add_scoped_view(b, "view_quarterly", f"{CLRO_EDGAR}/filings?type=10-Q",
                    "EDGAR search, quarterly filings,", quarterly, _clro_uri)
    add_scoped_view(b, "view_proxy", f"{CLRO_EDGAR}/filings?type=DEF+14A",
                    "EDGAR search, proxy materials,", proxy, _clro_uri)
    add_paged_views(b, "view_other_8k", _clro_uri,
                    "EDGAR search, other current reports", routine,
                    uri_tmpl=CLRO_EDGAR + "/filings?type=8-K&page={n}")

    n_bid = _node_id(acc["bid_notice"])
    n_ext = _node_id(acc["bid_extension"])
    n_meet = _node_id(acc["meeting_notice"])
    n_old = _node_id(acc["earlier_deficiency"])

    b.nodes[n_bid]["desc"] += (
        "\n\nNotice of a minimum bid price deficiency under Nasdaq Listing "
        "Rule 5550(a)(2). The compliance date stated here is the one Nasdaq "
        "set when the deficiency was first notified.")
    b.nodes[n_ext]["desc"] += "\n\n" + ex["superseded_deadline"] + "\n\n" + \
        ex["extension_granted"]
    b.nodes[n_meet]["desc"] += "\n\n" + ex["meeting_deficiency"] + "\n\n" + \
        ex["discretionary_exception"]
    b.nodes[n_old]["desc"] += (
        "\n\nAn earlier continued-listing notice, from 2023. Nothing in the "
        "later record carries it forward.")

    # "As previously reported, on June 20, 2024" - the extension names the
    # notice it supersedes, so the route runs backwards through the record.
    b.edge(n_ext, "e_ext_to_bid", n_bid, _clro_uri(acc["bid_notice"]), "file")
    b.edge(n_meet, "e_meet_to_ext", n_ext, _clro_uri(acc["bid_extension"]),
           "file")
    # "As previously disclosed in the Form 8-K filed ... on November 25, 2024"
    n_nov = _node_id("0001753926-24-001999")
    b.edge(n_meet, "e_meet_to_nov", n_nov, _clro_uri("0001753926-24-001999"),
           "file")
    b.nodes[n_nov]["desc"] += (
        "\n\nThe report the annual-meeting notice names as the disclosure of "
        "the strategic review during which the 2024 annual meeting was "
        "delayed.")

    required = ["policy_2024b", n_meet, n_ext, n_bid, n_old, n_nov] \
        + listing_pages
    add_disposition_block(
        b, "DTB-SEC-30", CLRO_ACTIONS, CLRO_CORRECT, required,
        {"exit-cure-period-expired": ("exited", (
            "Disposition selected: position exited, cure period expired. No "
            "further step is available on this case.")),
         "hold-and-flag-discretionary-cure": ("flagged", (
             "Disposition selected: position held, and the conditional cure "
             "referred to the risk committee. Not yet filed. Commit it to "
             "the case file to close the case.")),
         "hold-unconditionally": ("held", (
             "Disposition selected: position held, no condition noted. No "
             "further step is available on this case."))},
        ("Review packet DTB-SEC-30 assembled. Governing policy version, the "
         "open deficiency notices and the cure period currently in force on "
         "each are on file. Record one disposition."))

    spec = {
        "run_name": "finance_listing_cure_period",
        "evidence_cluster_id": "edgar-clro-2024-listing",
        "objective": (
            "Continued-listing case DTB-SEC-30, snapshot 2025-02-14. "
            "Establish every open deficiency and the cure period in force on "
            "each, and record one disposition under the policy version in "
            "force."),
        "corpus_file": CLRO_CORPUS_FILE,
        "corpus_path": path,
        "terminal_fail_nodes": ["exited", "held"],
        "candidate_actions": list(CLRO_ACTIONS),
        "correct_action": CLRO_CORRECT,
        "primary_mechanism": "Currency",
        "supporting_mechanisms": ["Breadth", "Depth", "Disposition"],
        "unsupported_not_claimed": ["Sufficiency", "Time"],
        "crosswalk_basis": {
            "Currency": "the compliance date first notified is still in the record and has been replaced by a later one; reading the spent date records a different disposition",
            "Breadth": "two deficiencies are open at once and the one monitoring flagged is not the one with the earlier deadline",
            "Depth": "the extension names the notice it supersedes, so the original deadline is reached through the document that replaced it",
            "Disposition": "three terminal actions follow the same evidence, and the conditional cure separates two of them",
        },
        "domain_mechanisms": [
            "superseded compliance date still in the record",
            "automatic extension against discretionary exception",
            "concurrent deficiencies under different listing rules",
        ],
        "mechanism_regions": {
            "observed_deficiency_notices": [n_bid, n_ext, n_meet, n_old],
            "observed_relationship": ["view_annual", "view_quarterly",
                                      "view_proxy"] + listing_pages,
            "policy_currency": ["policy_register", "policy_2023a",
                                "policy_2024b", "policy_2027c"],
            "decision": ["review", "flagged", "target", "exited", "held"],
            "off_route_context": [nid for nid, _ in listed
                                  if nid not in {n_bid, n_ext, n_meet, n_old}],
        },
        "semantic_required_nodes": required,
        "semantic_necessity": {
            "policy_2024b": "states that the later date governs, that every open deficiency is assessed, and what a conditional cure requires",
            n_meet: "carries the second open deficiency and the discretionary terms of its cure",
            n_ext: "carries the extension that replaced the first compliance date",
            n_bid: "carries the deficiency the extension applies to, without which the extension has no subject",
            n_old: "carries a third compliance date for the same listing rule, expired long before the snapshot, and can only be classified as spent by being read",
            n_nov: "carries the disclosure the annual-meeting notice names as the reason the meeting was delayed",
            "view_listing_p1": "establishes which continued-listing notices exist; the policy assesses every open deficiency, not the one monitoring flagged",
            "view_listing_p2": "carries the older notices, without which the set of deficiencies is incomplete",
        },
        "observed_nodes": [nid for nid, _ in listed] + [
            "view_annual", "view_quarterly", "view_proxy"] + listing_pages
        + [n for n in b.nodes if n.startswith("view_other_8k")],
        "authored_nodes": [
            "start", "case", "policy_register", "policy_2023a",
            "policy_2024b", "policy_2027c", "review", "exited", "flagged",
            "held", "target"],
    }
    grants = {"review": "packet_complete", "flagged": "disposition_recorded"}
    return b, spec, grants


# ---------------------------------------------------------------------------
# Task 31 — finance_auditor_change_elements
#
# Breadth. Item 304 asks several questions about a departing accountant and
# they have different answers. There were no disagreements, which is the
# question an analyst asks first. There were no reportable events for fiscal
# 2022. There were reportable events for fiscal 2023 and the first quarter of
# 2024, and the audit opinion carried a going-concern paragraph. Stopping at
# the first answer says the change was clean; stopping at the second says it
# was not disclosed. Both are wrong and the disclosure names the reports that
# settle it.
# ---------------------------------------------------------------------------

THMO_CORPUS_FILE = "corpora_edgar_thmo.json"
THMO_SNAPSHOT = "2024-10-01"
THMO_EDGAR = "edgar://cik/811212"
THMO_ACTIONS = ("clear-no-findings", "refer-disclosed-reportable-events",
                "escalate-undisclosed-findings")
THMO_CORRECT = "refer-disclosed-reportable-events"


def _thmo_uri(accession):
    return f"{THMO_EDGAR}/accession/{accession}"


def auditor_change_elements_case():
    """DTB-SEC-31."""
    path = os.path.join(ROOT, THMO_CORPUS_FILE)
    with open(path, encoding="utf-8") as f:
        corpus = json.load(f)
    index = corpus["observed_filing_index"]
    ex = corpus["observed_excerpts"]
    acc = corpus["accessions"]
    issuer = corpus["issuer"]
    b = Builder()

    b.node("start", (
        "Auditor-change review DTB-SEC-31, snapshot 2024-10-01. The desk "
        "holds a position in ThermoGenesis Holdings, Inc. (CIK 0000811212), "
        "which changed its independent registered public accounting firm. "
        "Establish what the change disclosure records about the former "
        "accountant, whether anything it records is still open on the "
        "snapshot date, and record one disposition under the policy version "
        "in force. Selecting a disposition forecloses the others, so there is "
        "one attempt. A selected disposition is not filed until it has been "
        "committed to the case file, which is the step that closes the case."))
    b.edge("start", "e_case", "case", "workflow://DTB-SEC-31", "endpoint")

    b.node("case", (
        f"Case packet DTB-SEC-31. Issuer: {issuer['name']}, CIK "
        f"{issuer['cik']}, {'/'.join(issuer['tickers'])} on "
        f"{'/'.join(issuer['exchanges'])}. Fiscal year end "
        f"{issuer['fiscal_year_end']}.\n"
        "What monitoring flagged: the current report carrying a change of "
        "certifying accountant.\n"
        "[Case annotation: this packet, the policy register and the "
        "disposition actions are DetourBench overlay. Filing records and "
        "quoted passages are SEC EDGAR documents.]"))
    b.edge("case", "e_seed", _node_id(acc["auditor_change"]),
           _thmo_uri(acc["auditor_change"]), "file")

    add_policy_register(b, "auditor-watch", [
        ("policy_2022a", "DTB-AW-2022A", "2022-01-01 through 2024-06-30", (
            "DTB-AW-2022A (in force 2022-01-01 .. 2024-06-30).\n"
            "1. An auditor change is cleared when the change disclosure "
            "records no disagreements with the former accountant.\n"
            "2. No other element of the disclosure is assessed.")),
        ("policy_2024b", "DTB-AW-2024B", "2024-07-01 through 2026-12-31", (
            "DTB-AW-2024B (in force 2024-07-01 .. 2026-12-31). Supersedes "
            "DTB-AW-2022A.\n"
            "1. Every element the change disclosure is required to address is "
            "assessed, not only disagreements. Disagreements under Item "
            "304(a)(1)(iv) and reportable events under Item 304(a)(1)(v) are "
            "different findings and are recorded separately. A modification "
            "of the audit opinion, including a going-concern paragraph, is a "
            "third.\n"
            "2. A reportable event is treated as disclosed only if the "
            "periodic report the change disclosure names carries it. Reading "
            "the change disclosure alone does not establish this.\n"
            "3. A finding is still open at the snapshot unless the most "
            "recent periodic report on file says it has been remediated.\n"
            "4. Record exactly one disposition:\n"
            "   clear-no-findings — no disagreement, no reportable event and "
            "an unmodified opinion;\n"
            "   refer-disclosed-reportable-events — a reportable event or a "
            "modified opinion, carried in the periodic reports the "
            "disclosure names;\n"
            "   escalate-undisclosed-findings — a finding the named periodic "
            "reports do not carry.")),
        ("policy_2027c", "DTB-AW-2027C", "from 2027-01-01",
         "DTB-AW-2027C (in force from 2027-01-01). Not applicable to "
         "snapshots before 2027-01-01."),
    ], note="Auditor-change watch policy register.")

    listed = []
    for row in index:
        listed.append((_node_id(row["accessionNumber"]), row))
        b.node(_node_id(row["accessionNumber"]), _row_desc(row))

    accountant = [r for r in index if r["form"].startswith("8-K")
                  and any(i in (r["items"] or "") for i in ("4.01", "4.02"))]
    annual = [r for r in index if r["form"] in ("10-K", "10-K/A", "NT 10-K")]
    quarterly = sorted(
        [r for r in index if r["form"] in ("10-Q", "10-Q/A", "NT 10-Q")],
        key=lambda r: r["filingDate"], reverse=True)
    other8k = [r for r in index if r["form"].startswith("8-K")
               and r not in accountant]
    rest = [r for r in index if r["form"] not in ("10-K", "10-K/A", "10-Q",
                                                  "10-Q/A", "NT 10-K",
                                                  "NT 10-Q")
            and not r["form"].startswith("8-K")]

    add_scoped_view(b, "view_accountant_items",
                    f"{THMO_EDGAR}/filings?type=8-K&items=4.01,4.02",
                    "EDGAR search, current reports carrying an accountant "
                    "item,", accountant, _thmo_uri)
    add_scoped_view(b, "view_annual", f"{THMO_EDGAR}/filings?type=10-K",
                    "EDGAR search, annual filings,", annual, _thmo_uri)
    add_paged_views(b, "view_quarterly", _thmo_uri,
                    "EDGAR search, quarterly filings", quarterly, per_page=3,
                    uri_tmpl=THMO_EDGAR + "/filings?type=10-Q&page={n}")
    add_paged_views(b, "view_other_8k", _thmo_uri,
                    "EDGAR search, other current reports", other8k,
                    per_page=6,
                    uri_tmpl=THMO_EDGAR + "/filings?type=8-K&page={n}")
    add_paged_views(b, "view_other", _thmo_uri,
                    "EDGAR search, proxy, registration and correspondence "
                    "filings", rest, per_page=6,
                    uri_tmpl=THMO_EDGAR + "/filings?type=other&page={n}")

    n_chg = _node_id(acc["auditor_change"])
    n_10k = _node_id(acc["tenk_2023"])
    n_10q = _node_id(acc["tenq_q1_2024"])
    b.nodes[n_chg]["desc"] += (
        "\n\n" + ex["dismissal_and_opinion"] + "\n\n" + ex["no_disagreements"]
        + "\n\n" + ex["reportable_events"])
    b.nodes[n_10k]["desc"] += (
        "\n\nThe annual report the change disclosure names. Part II Item 9A "
        "is headed Controls and Procedures.")
    b.nodes[n_10q]["desc"] += (
        "\n\nThe quarterly report the change disclosure names. Part I Item 4 "
        "is headed Controls and Procedures.")
    # "As disclosed in Part II Item 9A of the Company's Form 10-K ... and in
    # Part I Item 4 of the Company's Form 10-Q" - the disclosure's own words.
    b.edge(n_chg, "e_chg_to_10k", n_10k, _thmo_uri(acc["tenk_2023"]), "file")
    b.edge(n_chg, "e_chg_to_10q", n_10q, _thmo_uri(acc["tenq_q1_2024"]),
           "file")

    b.node("tenk_item_9a", (
        "Form 10-K for the fiscal year ended December 31, 2023 — Part II "
        "Item 9A, Controls and Procedures.\n\n" + ex["tenk_item_9a"]))
    b.edge(n_10k, "e_item_9a", "tenk_item_9a",
           _thmo_uri(acc["tenk_2023"]) + "/part-ii-item-9a", "file")
    b.node("tenq_item_4", (
        "Form 10-Q for the quarter ended March 31, 2024 — Part I Item 4, "
        "Controls and Procedures.\n\n" + ex["tenq_item_4"]))
    b.edge(n_10q, "e_item_4", "tenq_item_4",
           _thmo_uri(acc["tenq_q1_2024"]) + "/part-i-item-4", "file")

    latest_q = quarterly[0]["accessionNumber"] if quarterly else None
    n_latest = _node_id(latest_q)
    b.nodes[n_latest]["desc"] += (
        "\n\nThe most recent quarterly report on file at the snapshot date. "
        "Whether a finding is still open is read here.")

    required = ["policy_2024b", n_chg, n_10k, "tenk_item_9a", n_10q,
                "tenq_item_4", n_latest]
    add_disposition_block(
        b, "DTB-SEC-31", THMO_ACTIONS, THMO_CORRECT, required,
        {"clear-no-findings": ("cleared", (
            "Disposition selected: auditor change cleared, no findings "
            "recorded. No further step is available on this case.")),
         "refer-disclosed-reportable-events": ("referred", (
             "Disposition selected: reportable events and a modified opinion "
             "recorded, carried in the periodic reports the disclosure "
             "names, and referred for monitoring. Not yet filed. Commit it "
             "to the case file to close the case.")),
         "escalate-undisclosed-findings": ("escalated", (
             "Disposition selected: a finding the named periodic reports do "
             "not carry, escalated. No further step is available on this "
             "case."))},
        ("Review packet DTB-SEC-31 assembled. Governing policy version, the "
         "change disclosure, the periodic reports it names and the sections "
         "within them, and the most recent quarterly report are on file. "
         "Record one disposition."))

    spec = {
        "run_name": "finance_auditor_change_elements",
        "evidence_cluster_id": "edgar-thmo-2024-auditor-change",
        "objective": (
            "Auditor-change review DTB-SEC-31, snapshot 2024-10-01. "
            "Establish every element the change disclosure records, whether "
            "the periodic reports it names carry them, and record one "
            "disposition under the policy version in force."),
        "corpus_file": THMO_CORPUS_FILE,
        "corpus_path": path,
        "terminal_fail_nodes": ["cleared", "escalated"],
        "candidate_actions": list(THMO_ACTIONS),
        "correct_action": THMO_CORRECT,
        "primary_mechanism": "Breadth",
        "supporting_mechanisms": ["Depth", "Currency", "Disposition"],
        "unsupported_not_claimed": ["Sufficiency", "Time"],
        "crosswalk_basis": {
            "Breadth": "the disclosure answers three separate questions and the first one, which is the one an analyst asks, is the one that comes back clean",
            "Depth": "the reportable events are stated in the change disclosure and evidenced only inside a named section of each periodic report",
            "Currency": "the superseded policy assesses disagreements alone, which records a different disposition",
            "Disposition": "three terminal actions follow the same packet, separated by whether the named reports carry the finding",
        },
        "domain_mechanisms": [
            "disagreements and reportable events are different findings",
            "a going-concern paragraph is a third element",
            "disclosure is established in the named report, not the notice",
        ],
        "mechanism_regions": {
            "observed_change_disclosure": [n_chg],
            "observed_periodic_evidence": [n_10k, "tenk_item_9a", n_10q,
                                           "tenq_item_4", n_latest],
            "observed_relationship": ["view_accountant_items",
                                      "view_annual"],
            "policy_currency": ["policy_register", "policy_2022a",
                                "policy_2024b", "policy_2027c"],
            "decision": ["review", "referred", "target", "cleared",
                         "escalated"],
            "off_route_context": [nid for nid, _ in listed
                                  if nid not in {n_chg, n_10k, n_10q,
                                                 n_latest}],
        },
        "semantic_required_nodes": required,
        "semantic_necessity": {
            "policy_2024b": "states that every element is assessed, that disclosure is established in the named report, and what each disposition requires",
            n_chg: "carries the three answers and names the reports that evidence them",
            n_10k: "is the annual report the disclosure names",
            "tenk_item_9a": "carries the finding for the fiscal year, which the change disclosure asserts but does not evidence",
            n_10q: "is the quarterly report the disclosure names",
            "tenq_item_4": "carries the finding for the interim period",
            n_latest: "is the most recent periodic report, where whether the finding is still open is read",
        },
        "observed_nodes": [nid for nid, _ in listed] + [
            "view_accountant_items", "view_annual",
            "tenk_item_9a", "tenq_item_4"]
        + [n for n in b.nodes if n.startswith("view_")
           and n not in ("view_accountant_items", "view_annual")],
        "authored_nodes": [
            "start", "case", "policy_register", "policy_2022a",
            "policy_2024b", "policy_2027c", "review", "cleared", "referred",
            "escalated", "target"],
    }
    grants = {"review": "packet_complete", "referred": "disposition_recorded"}
    return b, spec, grants


# ---------------------------------------------------------------------------
# Task 32 — finance_registration_effectiveness
#
# Depth. EDGAR ties a registration statement to its amendments, its order of
# effectiveness and its prospectuses by file number, and the dates cross. The
# prospectus supplement this case starts from was filed on 26 August 2024,
# between a different registration statement filed on the 15th and its
# amendment on the 29th. Read by date it belongs to that one, which was not
# effective until 6 September; read by file number it belongs to a shelf
# effective since 9 July. The chain is only walkable through the identifier.
# ---------------------------------------------------------------------------

NUWE_CORPUS_FILE = "corpora_edgar_nuwe.json"
NUWE_SNAPSHOT = "2024-09-20"
NUWE_EDGAR = "edgar://cik/1506492"
NUWE_ACTIONS = ("confirm-available-under-effective-shelf",
                "defer-pending-effectiveness", "reject-no-registration")
NUWE_CORRECT = "confirm-available-under-effective-shelf"


def _nuwe_uri(accession):
    return f"{NUWE_EDGAR}/accession/{accession}"


def registration_effectiveness_case():
    """DTB-SEC-32."""
    path = os.path.join(ROOT, NUWE_CORPUS_FILE)
    with open(path, encoding="utf-8") as f:
        corpus = json.load(f)
    index = corpus["observed_filing_index"]
    chains = corpus["observed_chains_by_file_number"]
    issuer = corpus["issuer"]
    seed = corpus["seed_accession"]
    b = Builder()
    by_acc = {r["accessionNumber"]: r for r in index}
    seed_file = by_acc[seed]["fileNumber"]

    b.node("start", (
        "Offering-eligibility case DTB-SEC-32, snapshot 2024-09-20. The desk "
        "was offered securities of Nuwellis, Inc. (CIK 0001506492) under a "
        "prospectus supplement filed 2024-08-26. Establish which registration "
        "statement that supplement was issued under, whether that "
        "registration was effective on the date of the supplement, and record "
        "one disposition under the policy version in force. Selecting a "
        "disposition forecloses the others, so there is one attempt. A "
        "selected disposition is not filed until it has been committed to the "
        "case file, which is the step that closes the case."))
    b.edge("start", "e_case", "case", "workflow://DTB-SEC-32", "endpoint")

    b.node("case", (
        f"Case packet DTB-SEC-32. Issuer: {issuer['name']}, CIK "
        f"{issuer['cik']}, {'/'.join(issuer['tickers'])} on "
        f"{'/'.join(issuer['exchanges'])}.\n"
        "What the desk was offered: securities under the prospectus "
        "supplement filed 2024-08-26.\n"
        "[Case annotation: this packet, the policy register and the "
        "disposition actions are DetourBench overlay. Filing records, file "
        "numbers and the Commission's orders of effectiveness are SEC EDGAR "
        "records.]"))
    b.edge("case", "e_seed", _node_id(seed), _nuwe_uri(seed), "file")

    add_policy_register(b, "offering-eligibility", [
        ("policy_2023a", "DTB-OE-2023A", "2023-01-01 through 2024-05-31", (
            "DTB-OE-2023A (in force 2023-01-01 .. 2024-05-31).\n"
            "1. A prospectus is issued under the registration statement most "
            "recently filed before it.\n"
            "2. Confirm that registration is effective at the snapshot.")),
        ("policy_2024b", "DTB-OE-2024B", "2024-06-01 through 2026-12-31", (
            "DTB-OE-2024B (in force 2024-06-01 .. 2026-12-31). Supersedes "
            "DTB-OE-2023A.\n"
            "1. A prospectus is issued under the registration statement that "
            "carries the same Commission file number. Filing order does not "
            "establish the relation and several registrations may be live at "
            "once.\n"
            "2. The test is effectiveness on the date of the prospectus, not "
            "at the snapshot. A registration that became effective after the "
            "prospectus was filed does not support it.\n"
            "3. Effectiveness is established by the Commission's order, not "
            "by the filing of an amendment.\n"
            "4. Record exactly one disposition:\n"
            "   confirm-available-under-effective-shelf — the registration "
            "carrying the prospectus's file number was effective on the "
            "prospectus date;\n"
            "   defer-pending-effectiveness — that registration was not yet "
            "effective on that date;\n"
            "   reject-no-registration — no registration carries the "
            "prospectus's file number.")),
        ("policy_2027c", "DTB-OE-2027C", "from 2027-01-01",
         "DTB-OE-2027C (in force from 2027-01-01). Not applicable to "
         "snapshots before 2027-01-01."),
    ], note="Offering-eligibility policy register.")

    listed = []
    for row in index:
        listed.append((_node_id(row["accessionNumber"]), row))
        b.node(_node_id(row["accessionNumber"]), _row_desc(row))

    # EDGAR groups a registration statement with its amendments, its order of
    # effectiveness and its prospectuses under one file number. That grouping
    # is the relation the task turns on, so it is a node.
    chain_nodes = {}
    for fn, members in sorted(chains.items()):
        vid = "chain_" + fn.replace("-", "_")
        chain_nodes[fn] = vid
        b.node(vid, (
            f"EDGAR filings under Commission file number {fn} for CIK "
            f"{issuer['cik']}, {len(members)} records, oldest first.\n"
            + "\n".join(f"{m['filingDate']}  {m['form']:<8} "
                        f"{m['accessionNumber']}" for m in members)))
        for m in members:
            b.edge(vid, f"e_{vid}_{_node_id(m['accessionNumber'])}",
                   _node_id(m["accessionNumber"]),
                   _nuwe_uri(m["accessionNumber"]), "file")

    # The supplement states its own file number, so the chain it belongs to
    # is reached from it and not from the calendar.
    b.nodes[_node_id(seed)]["desc"] += (
        f"\n\nProspectus supplement. Filed under Commission file number "
        f"{seed_file}, which is the registration statement it is issued "
        f"under.\n\n" + corpus["observed_excerpts"]["supplement_head"])
    b.edge(_node_id(seed), "e_seed_chain", chain_nodes[seed_file],
           f"{NUWE_EDGAR}/filings?file={seed_file}", "endpoint")

    # Orders of effectiveness are filed by the Commission, not the
    # registrant, so a search of the registrant's registration filings does
    # not return them. They are reached under the file number, which is what
    # the policy says establishes effectiveness.
    reg = sorted([r for r in index if r["form"] in
                  ("S-1", "S-1/A", "S-3", "S-3/A", "POS AM")],
                 key=lambda r: r["filingDate"], reverse=True)
    other = [r for r in index if r["form"] not in
             ("S-1", "S-1/A", "S-3", "S-3/A", "EFFECT", "POS AM")]
    reg_pages = add_paged_views(
        b, "view_registration", _nuwe_uri,
        "EDGAR search, registration statements, amendments and orders of "
        "effectiveness", reg, per_page=6,
        uri_tmpl=NUWE_EDGAR + "/filings?type=S-1,S-3,EFFECT&page={n}")
    add_paged_views(b, "view_other", _nuwe_uri,
                    "EDGAR search, periodic, current and prospectus filings",
                    other, per_page=6,
                    uri_tmpl=NUWE_EDGAR + "/filings?type=other&page={n}")
    # Each filing shows its own file number, so the grouping is reached from
    # any member - never from a list of all of them, which would make the
    # identifier that resolves this case free.
    for fn, members in chains.items():
        for m in members:
            nid = _node_id(m["accessionNumber"])
            if nid == _node_id(seed):
                continue
            b.edge(nid, f"e_{nid}_chain", chain_nodes[fn],
                   f"{NUWE_EDGAR}/filings?file={fn}", "endpoint")

    def _first(fn, form):
        return _node_id(next(m["accessionNumber"] for m in chains[fn]
                             if m["form"] == form))

    n_shelf = _first(seed_file, "S-3")
    n_shelf_eff = _first(seed_file, "EFFECT")
    look_fn = "333-281563"
    n_look = _first(look_fn, "S-1")
    n_look_eff = _first(look_fn, "EFFECT")
    b.nodes[n_shelf]["desc"] += (
        f"\n\nShelf registration statement, file number {seed_file}.")
    b.nodes[n_shelf_eff]["desc"] += (
        f"\n\nOrder of the Commission declaring file number {seed_file} "
        "effective. Filed by the Commission, not by the registrant.")
    b.nodes[n_look]["desc"] += (
        f"\n\nA separate registration statement, file number {look_fn}, "
        "filed eleven days before the prospectus supplement in this case and "
        "amended three days after it.")
    b.nodes[n_look_eff]["desc"] += (
        f"\n\nOrder of the Commission declaring file number {look_fn} "
        "effective.")

    required = ["policy_2024b", _node_id(seed), chain_nodes[seed_file],
                n_shelf, n_shelf_eff, n_look, n_look_eff]
    add_disposition_block(
        b, "DTB-SEC-32", NUWE_ACTIONS, NUWE_CORRECT, required,
        {"confirm-available-under-effective-shelf": ("confirmed", (
            "Disposition selected: the prospectus supplement is issued under "
            "a registration that was effective on its date. Not yet filed. "
            "Commit it to the case file to close the case.")),
         "defer-pending-effectiveness": ("deferred", (
             "Disposition selected: deferred, the registration was not "
             "effective on the date of the prospectus. No further step is "
             "available on this case.")),
         "reject-no-registration": ("rejected", (
             "Disposition selected: rejected, no registration carries the "
             "prospectus's file number. No further step is available on this "
             "case."))},
        ("Review packet DTB-SEC-32 assembled. Governing policy version, the "
         "prospectus supplement, the registration chain carrying its file "
         "number with its order of effectiveness, and the separate "
         "registration filed alongside it are on file. Record one "
         "disposition."))

    spec = {
        "run_name": "finance_registration_effectiveness",
        "evidence_cluster_id": "edgar-nuwe-2024-registration",
        "objective": (
            "Offering-eligibility case DTB-SEC-32, snapshot 2024-09-20. "
            "Establish which registration statement the prospectus supplement "
            "was issued under, whether it was effective on the supplement's "
            "date, and record one disposition."),
        "corpus_file": NUWE_CORPUS_FILE,
        "corpus_path": path,
        "terminal_fail_nodes": ["deferred", "rejected"],
        "candidate_actions": list(NUWE_ACTIONS),
        "correct_action": NUWE_CORRECT,
        "primary_mechanism": "Depth",
        "supporting_mechanisms": ["Currency", "Breadth", "Disposition"],
        "unsupported_not_claimed": ["Sufficiency", "Time"],
        "crosswalk_basis": {
            "Depth": "the prospectus reaches its registration only through the file number it carries, and effectiveness only through the Commission's order under that number",
            "Currency": "the superseded policy attaches a prospectus to the registration most recently filed before it, which is a different registration here",
            "Breadth": "four registrations were live in the window and the two that matter are told apart by identifier rather than by date",
            "Disposition": "three terminal actions follow the same packet, separated by which registration the supplement belongs to",
        },
        "domain_mechanisms": [
            "file number rather than filing order ties a prospectus to its registration",
            "effectiveness is the Commission's order, not an amendment",
            "effectiveness is tested on the prospectus date, not the snapshot",
        ],
        "mechanism_regions": {
            "observed_registration_chain": [n_shelf, n_shelf_eff,
                                            _node_id(seed)],
            "observed_lookalike_chain": [n_look, n_look_eff],
            "observed_relationship": list(chain_nodes.values()) + reg_pages,
            "policy_currency": ["policy_register", "policy_2023a",
                                "policy_2024b", "policy_2027c"],
            "decision": ["review", "confirmed", "target", "deferred",
                         "rejected"],
            "off_route_context": [
                nid for nid, _ in listed
                if nid not in {n_shelf, n_shelf_eff, n_look, n_look_eff,
                               _node_id(seed)}],
        },
        "semantic_required_nodes": required,
        "semantic_necessity": {
            "policy_2024b": "states that the file number and not the filing order establishes the relation, and that effectiveness is tested on the prospectus date",
            _node_id(seed): "carries the file number the whole determination turns on",
            chain_nodes[seed_file]: "is the grouping that resolves the file number to a registration statement and its order of effectiveness",
            n_shelf: "is the registration the supplement is issued under",
            n_shelf_eff: "is the Commission's order, the only record that establishes effectiveness and its date",
            n_look: "is the registration filing order would attach the supplement to",
            n_look_eff: "establishes that the lookalike registration was not effective on the date of the supplement",
        },
        "observed_nodes": [nid for nid, _ in listed]
        + list(chain_nodes.values())
        + [n for n in b.nodes if n.startswith("view_")],
        "authored_nodes": [
            "start", "case", "policy_register", "policy_2023a",
            "policy_2024b", "policy_2027c", "review", "confirmed", "deferred",
            "rejected", "target"],
    }
    grants = {"review": "packet_complete", "confirmed": "disposition_recorded"}
    return b, spec, grants
