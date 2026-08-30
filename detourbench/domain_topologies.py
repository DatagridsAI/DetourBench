#!/usr/bin/env python3
"""Integrated tasks outside the finance family.

The finance five share one shape: a versioned policy, scoped searches, an
all-of-N evidence gate, three dispositions. That shape is fine and it is also
the only one they have. These tasks deliberately vary the graph mechanism -
two routes of different length, N-of-M corroboration, credentials that a
document grants - because a suite whose members differ only in subject matter
is a reskin, and because the mechanism that RSR cannot see is exactly the one
that argues for measuring detour at all.
"""
import json
import os
import re

from finance_topologies import (add_disposition_block, add_paged_views,
                                add_policy_register, add_scoped_view)
from topologies import Builder

ROOT = os.path.dirname(os.path.abspath(__file__))


def _rid(number):
    return "r_" + str(number).replace("-", "_").replace(".", "_")


def _hid(code):
    return "h_" + str(code).replace(".", "_")


# ---------------------------------------------------------------------------
# Task 33 — customs_ruling_supersession
#
# Currency, and the first task in the suite built on two routes of different
# length. A CBP classification ruling that is directly on point by subject was
# revoked four months after it issued, and the ruling that revoked it puts the
# article under a different heading. The revocation is a structured field on
# the ruling itself, so the short route is one step. The tariff schedule is
# also in the graph, and walking it from the heading down to the statistical
# suffix reaches the same answer three steps later. Both routes are legal,
# neither wastes a step on an invalid or duplicate access, and the ratio to
# the bound is the only thing that tells them apart - which is the case
# HANDOFF.md records RSR being blind to.
# ---------------------------------------------------------------------------

CBP_CORPUS = "corpora_cbp_rulings.json"
HTS_PATH = "/data/benchmarks/raw-corpora/rules-and-sops/hts-usitc/hts_full.json"
CBP_SNAPSHOT = "2024-06-30"
CBP_SEED = "083084"
CBP_SUPERSEDING = "085482"
CBP_ACTIONS = ("classify-under-superseding-ruling",
               "classify-under-ruling-on-point",
               "refer-for-new-ruling-request")
CBP_CORRECT = "classify-under-superseding-ruling"


def _hts_lines():
    with open(HTS_PATH, encoding="utf-8") as f:
        rows = json.load(f)
    return [r for r in rows if r.get("htsno")]


def customs_ruling_supersession_case():
    """DTB-CBP-33."""
    path = os.path.join(ROOT, CBP_CORPUS)
    with open(path, encoding="utf-8") as f:
        corpus = json.load(f)
    rulings = corpus["observed_rulings"]
    superseding = corpus["observed_superseding_rulings"]
    hts = {r["htsno"]: r for r in _hts_lines()}
    b = Builder()

    seed = rulings[CBP_SEED]
    new = superseding[CBP_SUPERSEDING]
    old_code = (seed.get("tariffs") or [""])[0]
    new_code = (new.get("tariffs") or [""])[0]

    b.node("start", (
        "Classification case DTB-CBP-33, snapshot 2024-06-30. A broker asks "
        "how a cardboard-frame jewelry box covered in textile with a glass "
        "beaded top classifies under the Harmonized Tariff Schedule, and "
        "whether Customs has ruled on it. Establish the classification that "
        "governs on the snapshot date and record one disposition under the "
        "policy version in force. Selecting a disposition forecloses the "
        "others, so there is one attempt. A selected disposition is not filed "
        "until it has been committed to the case file, which is the step "
        "that closes the case."))
    b.edge("start", "e_case", "case", "workflow://DTB-CBP-33", "endpoint")

    b.node("case", (
        "Case packet DTB-CBP-33. Article: cardboard-frame jewelry box, outer "
        "surface of textile, glass beaded top, fitted interior.\n"
        "A search of the Customs Rulings Online Search System returned one "
        "ruling whose subject matches the article.\n"
        "The tariff schedule is available for lookup by heading.\n"
        "[Case annotation: this packet, the policy register and the "
        "disposition actions are DetourBench overlay. Ruling records and "
        "tariff text are CBP and USITC publications.]"))
    b.edge("case", "e_seed", _rid(CBP_SEED),
           f"cross://ruling/{CBP_SEED}", "file")

    add_policy_register(b, "classification", [
        ("policy_2019a", "DTB-CL-2019A", "2019-01-01 through 2022-12-31", (
            "DTB-CL-2019A (in force 2019-01-01 .. 2022-12-31).\n"
            "1. Where a ruling is on point for the article, classify under "
            "it.\n"
            "2. A ruling is on point when its described merchandise matches "
            "the article.")),
        ("policy_2023b", "DTB-CL-2023B", "2023-01-01 through 2026-12-31", (
            "DTB-CL-2023B (in force 2023-01-01 .. 2026-12-31). Supersedes "
            "DTB-CL-2019A.\n"
            "1. A ruling that has been revoked or modified does not state the "
            "classification in force, whatever its merchandise description "
            "says. Check the revocation record on every ruling relied on, "
            "including the one that superseded an earlier ruling.\n"
            "2. The classification adopted must be a provision that exists in "
            "the tariff schedule and reaches the article.\n"
            "3. Record exactly one disposition:\n"
            "   classify-under-superseding-ruling — a ruling on point was "
            "superseded and the superseding ruling states a classification;\n"
            "   classify-under-ruling-on-point — a ruling on point is in "
            "force and has not been superseded;\n"
            "   refer-for-new-ruling-request — no ruling reaches the "
            "article.")),
        ("policy_2027c", "DTB-CL-2027C", "from 2027-01-01",
         "DTB-CL-2027C (in force from 2027-01-01). Not applicable to "
         "snapshots before 2027-01-01."),
    ], note="Classification policy register.")

    def ruling_node(number, rec, extra=""):
        nid = _rid(number)
        rel = []
        for k, label in (("revokedBy", "Revoked by"),
                         ("modifiedBy", "Modified by"),
                         ("revokes", "Revokes"), ("modifies", "Modifies")):
            if rec.get(k):
                rel.append(f"{label}: {', '.join(rec[k])}")
        b.node(nid, (
            f"CBP ruling {number} ({rec.get('collection', '')}), "
            f"{str(rec.get('rulingDate'))[:10]}. "
            f"Subject: {rec.get('subject')}. "
            f"Category: {', '.join(rec.get('categories') or [])}. "
            f"Tariff numbers cited: {', '.join(rec.get('tariffs') or []) or 'none'}.\n"
            + ("Relations of record: " + "; ".join(rel) + "\n" if rel else
               "Relations of record: none\n")
            + extra + ("\n\n" + (rec.get("text") or "")[:1400]
                       if rec.get("text") else "")))
        return nid

    ruling_node(CBP_SEED, seed)
    ruling_node(CBP_SUPERSEDING, new)
    # The revocation is a field on the ruling, so the short route is one step
    # from the ruling that was revoked.
    b.edge(_rid(CBP_SEED), "e_revocation", _rid(CBP_SUPERSEDING),
           f"cross://ruling/{CBP_SUPERSEDING}", "file")

    # Other superseded rulings in the same extract. They are real, they are
    # about other articles, and their presence is why checking the revocation
    # record is a discipline rather than a trick played once.
    others = [n for n, rec in rulings.items()
              if (rec.get("revokedBy") or rec.get("modifiedBy"))
              and n != CBP_SEED]
    for n in others:
        ruling_node(n, rulings[n])
    b.node("view_superseded", (
        "CROSS search, rulings in this extract carrying a revocation or "
        f"modification record, {len(others) + 1} records.\n"
        + "\n".join(
            f"{str(rulings[n]['rulingDate'])[:10]}  {n:<8} "
            f"{(rulings[n].get('subject') or '')[:56]}"
            for n in [CBP_SEED] + others)))
    b.edge("case", "e_view_superseded", "view_superseded",
           "cross://search?flag=superseded", "endpoint")
    for n in [CBP_SEED] + others:
        b.edge("view_superseded", f"e_sup_{_rid(n)}", _rid(n),
               f"cross://ruling/{n}", "file")

    # The tariff schedule. Walking it from the heading to the statistical
    # suffix reaches the same classification the superseding ruling states -
    # legally, and three steps later.
    # The 1989 ruling cites a statistical suffix the schedule no longer
    # carries - it was renumbered. Mapping a spent suffix forward is a real
    # customs question and not one this task decides: the determination is at
    # the heading the superseding ruling identifies, and the walk goes down
    # from it through provisions that exist today.
    chain = ["4202", "4202.92", "4202.92.93", "4202.92.93.15"]
    prev = None
    for code in chain:
        rec = hts.get(code)
        if rec is None:
            continue
        nid = _hid(code)
        kids = [r for r in hts.values()
                if r["htsno"].startswith(code + ".")
                and r["htsno"].count(".") == code.count(".") + 1][:6]
        b.node(nid, (
            f"HTSUS {code} (indent {rec.get('indent')}). "
            f"{rec.get('description')}\n"
            + ("Subordinate provisions: "
               + "; ".join(f"{k['htsno']} {k['description'][:44]}"
                           for k in kids) if kids else
               f"General rate of duty: {rec.get('general') or 'n/a'}. "
               f"A statistical suffix; no subordinate provisions.")))
        b.edge(prev if prev else "case",
               f"e_hts_{nid}", nid, f"hts://{code}", "file")
        prev = nid
    n_hts_leaf = _hid(chain[-1])

    old_head = old_code.split(".")[0]
    for code in (old_head, ".".join(old_code.split(".")[:2])):
        rec = hts.get(code)
        if rec is None:
            continue
        nid = _hid(code)
        if nid in b.nodes:
            continue
        b.node(nid, (f"HTSUS {code} (indent {rec.get('indent')}). "
                     f"{rec.get('description')}"))
        b.edge("case", f"e_hts_{nid}", nid, f"hts://{code}", "file")

    # Rulings that cite either heading. Real records about other articles:
    # a classifier browses analogous rulings, and every one of them costs a
    # step and settles nothing here.
    heads = {old_code.split(".")[0], new_code.split(".")[0]}
    analogous = sorted(
        n for n, rec in rulings.items()
        if n not in {CBP_SEED} | set(others)
        and any((t or "").split(".")[0] in heads for t in rec.get("tariffs") or []))
    for n in analogous:
        ruling_node(n, rulings[n])
    add_paged_views(
        b, "view_by_heading", lambda n: f"cross://ruling/{n}",
        "CROSS search, rulings citing heading "
        + " or ".join(sorted(heads)),
        [{"filingDate": str(rulings[n]["rulingDate"])[:10],
          "form": rulings[n].get("collection", ""),
          "reportDate": None, "items": "",
          "accessionNumber": n} for n in analogous],
        per_page=6, uri_tmpl="cross://search?heading=4202&page={n}",
        id_of=_rid)

    # Sibling provisions. The schedule is a tree and its neighbours are the
    # provisions a classifier rules out.
    for parent in ("4202", "4823", "4202.92"):
        sibs = [r for r in hts.values()
                if r["htsno"].startswith(parent + ".")
                and r["htsno"].count(".") == parent.count(".") + 1]
        for rec in sibs[:5]:
            nid = _hid(rec["htsno"])
            if nid in b.nodes:
                continue
            b.node(nid, (f"HTSUS {rec['htsno']} (indent {rec.get('indent')}). "
                         f"{rec.get('description')}"))
            pid = _hid(parent)
            b.edge(pid if pid in b.nodes else "case",
                   f"e_hts_{nid}", nid, f"hts://{rec['htsno']}", "file")

    required = ["policy_2023b", _rid(CBP_SEED), _rid(CBP_SUPERSEDING),
                _hid(chain[0]), n_hts_leaf]
    add_disposition_block(
        b, "DTB-CBP-33", CBP_ACTIONS, CBP_CORRECT, required,
        {"classify-under-superseding-ruling": ("classified", (
            "Disposition selected: classified in heading 4202, per the "
            "ruling that revoked the ruling on point. Not yet filed. Commit "
            "it to the case file to close the case.")),
         "classify-under-ruling-on-point": ("classified_old", (
             "Disposition selected: classified in heading 4823, per the "
             "ruling whose merchandise description matches. No further step "
             "is available on this case.")),
         "refer-for-new-ruling-request": ("referred", (
             "Disposition selected: referred for a new ruling request, no "
             "ruling reaches the article. No further step is available on "
             "this case."))},
        ("Review packet DTB-CBP-33 assembled. Governing policy version, the "
         "ruling returned by subject, its revocation record and the ruling "
         "that superseded it, and the tariff provisions are on file. Record "
         "one disposition."))

    observed = ([_rid(n) for n in
                 [CBP_SEED, CBP_SUPERSEDING] + others + analogous]
                + [n for n in b.nodes if n.startswith(("h_", "view_"))])
    spec = {
        "run_name": "customs_ruling_supersession",
        "theme": "customs_classification",
        "evidence_cluster_id": "cbp-cross-083084-revocation",
        "objective": (
            "Classification case DTB-CBP-33, snapshot 2024-06-30. Establish "
            "the classification in force for the article and record one "
            "disposition under the policy version in force."),
        "corpus_file": CBP_CORPUS,
        "corpus_path": path,
        "provenance_boundary": (
            "Ruling records, their revocation and modification fields, and "
            "the tariff provisions are observed in the frozen CBP CROSS "
            "extract and the USITC Harmonized Tariff Schedule. The "
            "classification policy, case packet and write actions are "
            "authored DetourBench overlays. They are not CBP practice and "
            "state no view on any importer."),
        "source_kinds": ["frozen CBP CROSS ruling record",
                         "USITC Harmonized Tariff Schedule",
                         "authored local classification policy"],
        "terminal_fail_nodes": ["classified_old", "referred"],
        "candidate_actions": list(CBP_ACTIONS),
        "correct_action": CBP_CORRECT,
        "primary_mechanism": "Currency",
        "supporting_mechanisms": ["Depth", "Breadth", "Disposition"],
        "unsupported_not_claimed": ["Sufficiency", "Time"],
        "crosswalk_basis": {
            "Currency": "the ruling a subject search returns was revoked four months after it issued and states a heading that is no longer the classification in force",
            "Depth": "the tariff schedule reaches the same answer through heading, subheading, tariff line and statistical suffix, three steps longer than the revocation record",
            "Breadth": "the classification has to exist in the schedule as well as be stated in a ruling, and the extract holds other superseded rulings so the check is a discipline rather than a single trick",
            "Disposition": "three terminal actions follow the same packet, separated by whether a ruling on point is still in force",
        },
        "domain_mechanisms": [
            "revocation recorded as a field on the ruling it revokes",
            "two routes of different length to the same classification",
            "a superseding ruling that must itself be checked for supersession",
        ],
        "mechanism_regions": {
            "observed_rulings": [_rid(n) for n in
                                 [CBP_SEED, CBP_SUPERSEDING] + others],
            "observed_tariff_schedule": [n for n in b.nodes
                                         if n.startswith("h_")],
            "observed_relationship": ["view_superseded"],
            "policy_currency": ["policy_register", "policy_2019a",
                                "policy_2023b", "policy_2027c"],
            "decision": ["review", "classified", "target", "classified_old",
                         "referred"],
            "off_route_context": [_rid(n) for n in others + analogous],
        },
        "semantic_required_nodes": required,
        "semantic_necessity": {
            "policy_2023b": "states that a revoked ruling does not give the classification in force and that the provision adopted must exist in the schedule",
            _rid(CBP_SEED): "is the ruling a subject search returns, and carries the revocation record",
            _rid(CBP_SUPERSEDING): "states the classification that replaced it, and carries its own revocation record",
            _hid(chain[0]): "is the heading the superseding ruling puts the article under",
            n_hts_leaf: "is the provision actually adopted, and the only place the schedule confirms it reaches the article",
        },
        "observed_nodes": observed,
        "authored_nodes": [
            "start", "case", "policy_register", "policy_2019a",
            "policy_2023b", "policy_2027c", "review", "classified",
            "classified_old", "referred", "target"],
        "provenance_origin": "observed_cbp_cross_and_hts",
    }
    grants = {"review": "packet_complete", "classified": "disposition_recorded"}
    return b, spec, grants


# ---------------------------------------------------------------------------
# Task 34 — ontology_obsoletion_remap
#
# Disposition, and the first task in the suite with an irreversible failure
# reachable before the review gate. The Gene Ontology retires a term in two
# different ways. `replaced_by` names the term that took the concept over and
# an annotation can be remapped onto it mechanically. `consider` names terms a
# curator might look at instead, and the obsoletion comment says why that is
# weaker - the concept is only partly covered, or it mixed a function with a
# component. Both fields hold current, valid GO identifiers, so a `consider`
# entry reads exactly like a replacement. Writing one is a bad annotation and
# the graph lets that happen the moment the entry is seen, not after review.
# ---------------------------------------------------------------------------

GO_CORPUS = "corpora_go_obsoletion.json"
GO_SNAPSHOT = "2024-06-30"
GO_WITH_CONSIDER = "GO:0000988"
GO_WITH_REPLACEMENT = "GO:0000274"
GO_ACTIONS = ("remap-all-obsolete-terms",
              "remap-replaced-refer-considered",
              "retain-obsolete-annotations")
GO_CORRECT = "remap-replaced-refer-considered"


def _gid(term):
    return "t_" + term.replace(":", "_")


def ontology_obsoletion_remap_case():
    """DTB-GO-34."""
    path = os.path.join(ROOT, GO_CORPUS)
    with open(path, encoding="utf-8") as f:
        corpus = json.load(f)
    terms = corpus["observed_terms"]
    counts = corpus["counts"]
    b = Builder()

    b.node("start", (
        "Annotation-maintenance case DTB-GO-34, snapshot 2024-06-30. A "
        "release check flagged terms in the annotation set as obsolete. "
        "Establish which terms those are and, for each, what "
        "the ontology says should happen to annotations that use it, and "
        "record one disposition under the policy version in force. Selecting "
        "a disposition forecloses the others, so there is one attempt. A "
        "selected disposition is not filed until it has been committed to "
        "the release record, which is the step that closes the case."))
    b.edge("start", "e_case", "case", "workflow://DTB-GO-34", "endpoint")

    b.node("case", (
        "Case packet DTB-GO-34. Annotation set: two terms flagged obsolete "
        "by the release check.\n"
        f"Source: Gene Ontology, {counts['terms_in_source']} terms, of which "
        f"{counts['obsolete_in_source']} are obsolete. "
        f"{counts['with_replaced_by']} of those carry a replaced_by entry and "
        f"{counts['with_consider_only']} carry consider entries with no "
        "replaced_by.\n"
        "[Case annotation: this packet, the policy register and the write "
        "actions are DetourBench overlay. Term records are the ontology's "
        "own fields.]"))
    # The release-check report is the only place the flagged set is named.
    # An earlier build put one of the two terms in the ticket and hung its
    # edge on the packet: the model was told a third of its addresses before
    # it looked at anything, and the one episode that solved this task hit
    # the exact optimum. Both terms come from the report now, so finding
    # which terms are flagged is work the graph makes you do.
    b.node("flagged_report", (
        "Release check DTB-GO-34, obsolete-term report. Two annotations in "
        "the set use terms the ontology has retired.\n"
        f"{GO_WITH_CONSIDER}\n{GO_WITH_REPLACEMENT}"))
    b.edge("case", "e_flagged", "flagged_report",
           "workflow://DTB-GO-34/release-check", "file")
    for _t in (GO_WITH_CONSIDER, GO_WITH_REPLACEMENT):
        b.edge("flagged_report", f"e_flag_{_gid(_t)}", _gid(_t),
               f"go://term/{_t}", "file")

    add_policy_register(b, "annotation-maintenance", [
        ("policy_2021a", "DTB-AM-2021A", "2021-01-01 through 2023-12-31", (
            "DTB-AM-2021A (in force 2021-01-01 .. 2023-12-31).\n"
            "1. An annotation on an obsolete term is remapped onto the term "
            "the ontology points at.\n"
            "2. replaced_by and consider are both pointers for this "
            "purpose.")),
        ("policy_2024b", "DTB-AM-2024B", "2024-01-01 through 2026-12-31", (
            "DTB-AM-2024B (in force 2024-01-01 .. 2026-12-31). Supersedes "
            "DTB-AM-2021A.\n"
            "1. replaced_by names the term that took over the concept. An "
            "annotation on the obsolete term is remapped onto it without "
            "review.\n"
            "2. consider names terms a curator may look at. It is not a "
            "replacement and an annotation is never remapped onto a consider "
            "entry automatically, whatever the entry is. Read the obsoletion "
            "comment: it says what was lost.\n"
            "3. A term with consider entries and no replaced_by is referred "
            "to curation.\n"
            "4. A replacement is only adopted if it is itself current.\n"
            "5. Record exactly one disposition:\n"
            "   remap-replaced-refer-considered — each term handled by what "
            "the ontology gives it;\n"
            "   remap-all-obsolete-terms — every flagged term has a "
            "replacement;\n"
            "   retain-obsolete-annotations — no flagged term has one.")),
        ("policy_2027c", "DTB-AM-2027C", "from 2027-01-01",
         "DTB-AM-2027C (in force from 2027-01-01). Not applicable to "
         "snapshots before 2027-01-01."),
    ], note="Annotation-maintenance policy register.")

    def term_node(gid):
        nid = _gid(gid)
        if nid in b.nodes:
            return nid
        t = terms[gid]
        rel = []
        if t["replaced_by"]:
            rel.append("replaced_by: " + ", ".join(t["replaced_by"]))
        if t["consider"]:
            rel.append("consider: " + ", ".join(t["consider"]))
        if t["is_a"]:
            rel.append("is_a: " + ", ".join(t["is_a"][:4]))
        b.node(nid, (
            f"{gid}  {t['name']}\n"
            f"namespace: {t['namespace']}\n"
            f"obsolete: {'true' if t['is_obsolete'] else 'false'}\n"
            + (("\n".join(rel) + "\n") if rel else "no outgoing relations\n")
            + (f"definition: {t['definition'][:300]}\n"
               if t["definition"] else "")
            + (f"comment: {t['comment'][:400]}" if t["comment"] else "")))
        return nid

    for gid in terms:
        term_node(gid)
    for gid, t in terms.items():
        for other in t["replaced_by"] + t["consider"] + t["is_a"]:
            if other in terms:
                b.edge(_gid(gid), f"e_{_gid(gid)}_{_gid(other)}", _gid(other),
                       f"go://term/{other}", "file")

    obsolete_others = [g for g, t in terms.items()
                       if t["is_obsolete"]
                       and g not in (GO_WITH_CONSIDER, GO_WITH_REPLACEMENT)]
    add_paged_views(
        b, "view_obsolete", lambda g: f"go://term/{g}",
        "Ontology report, obsolete terms in these namespaces",
        [{"filingDate": g, "form": terms[g]["namespace"][:10],
          "reportDate": None, "items": "",
          "accessionNumber": g} for g in obsolete_others],
        per_page=6, uri_tmpl="go://report/obsolete?page={n}",
        id_of=_gid)

    # Writing a consider entry into the annotation set is the failure this
    # task is about, and it is available as soon as the entry is seen. Every
    # other task in the family puts its irreversible steps after review.
    b.node("miswritten", (
        "Annotation rewritten onto a consider entry. The ontology does not "
        "sanction this substitution and the release record now carries an "
        "assertion the source does not support. No further step is available "
        "on this case."))
    for target in terms[GO_WITH_CONSIDER]["consider"]:
        if target in terms:
            b.edge(_gid(target), f"e_apply_{_gid(target)}", "miswritten",
                   f"annotations://DTB-GO-34/rewrite?to={target}", "endpoint")

    n_seed = _gid(GO_WITH_CONSIDER)
    n_repl_seed = _gid(GO_WITH_REPLACEMENT)
    n_repl = _gid(terms[GO_WITH_REPLACEMENT]["replaced_by"][0])
    required = ["policy_2024b", "flagged_report", n_seed, n_repl_seed,
                n_repl] + [
        _gid(t) for t in terms[GO_WITH_CONSIDER]["consider"] if t in terms]

    add_disposition_block(
        b, "DTB-GO-34", GO_ACTIONS, GO_CORRECT, required,
        {"remap-all-obsolete-terms": ("remapped_all", (
            "Disposition selected: every flagged term remapped. No further "
            "step is available on this case.")),
         "remap-replaced-refer-considered": ("split", (
             "Disposition selected: the term with a replaced_by entry "
             "remapped, the term with consider entries referred to curation. "
             "Not yet filed. Commit it to the release record to close the "
             "case.")),
         "retain-obsolete-annotations": ("retained", (
             "Disposition selected: both annotations left on obsolete terms. "
             "No further step is available on this case."))},
        ("Review packet DTB-GO-34 assembled. Governing policy version, both "
         "flagged terms, what each points at and whether those targets are "
         "current are on file. Record one disposition."))

    spec = {
        "run_name": "ontology_obsoletion_remap",
        "theme": "ontology_curation",
        "evidence_cluster_id": "go-obo-0000988-0000274",
        "objective": (
            "Annotation-maintenance case DTB-GO-34, snapshot 2024-06-30. "
            "Establish what the ontology directs for each flagged obsolete "
            "term and record one disposition."),
        "corpus_file": GO_CORPUS,
        "corpus_path": path,
        "provenance_boundary": (
            "Term records, their obsoletion status, replaced_by and consider "
            "relations and obsoletion comments are the Gene Ontology's own "
            "fields, quoted as published. The maintenance policy, case packet "
            "and write actions are authored DetourBench overlays."),
        "source_kinds": ["frozen Gene Ontology term record",
                         "authored local annotation policy"],
        "provenance_origin": "observed_gene_ontology",
        "terminal_fail_nodes": ["remapped_all", "retained", "miswritten"],
        "candidate_actions": list(GO_ACTIONS),
        "correct_action": GO_CORRECT,
        "primary_mechanism": "Disposition",
        "supporting_mechanisms": ["Breadth", "Currency", "Depth"],
        "unsupported_not_claimed": ["Sufficiency", "Time"],
        "crosswalk_basis": {
            "Disposition": "the two flagged terms are handled differently and the disposition that treats them alike is available and wrong",
            "Breadth": "both flagged terms have to be resolved, and the consider entries have to be read before the second can be",
            "Currency": "the superseded policy treats consider and replaced_by as the same pointer, which records a different disposition",
            "Depth": "a replacement is adopted only after its own record shows it is current",
        },
        "domain_mechanisms": [
            "replaced_by is a substitution, consider is not",
            "consider entries are valid current identifiers and read like replacements",
            "an irreversible bad write available before review",
        ],
        "mechanism_regions": {
            "observed_flagged_terms": [n_seed, n_repl_seed],
            "observed_targets": [n_repl] + [
                _gid(t) for t in terms[GO_WITH_CONSIDER]["consider"]
                if t in terms],
            "observed_relationship": [n for n in b.nodes
                                      if n.startswith("view_")],
            "policy_currency": ["policy_register", "policy_2021a",
                                "policy_2024b", "policy_2027c"],
            "decision": ["review", "split", "target", "remapped_all",
                         "retained", "miswritten"],
            "off_route_context": [_gid(g) for g in obsolete_others],
        },
        "semantic_required_nodes": required,
        "semantic_necessity": {
            "policy_2024b": "states that consider is not a replacement and that a term carrying only consider entries is referred",
            "flagged_report": "is the only record of the flagged set; nothing else names the two terms and the disposition turns on both",
            n_seed: "carries the consider entries and the comment saying the concept is only partly covered",
            n_repl_seed: "carries the replaced_by entry that makes the other half of the set remappable",
            n_repl: "is the replacement, and the only record that shows it is itself current",
            **{_gid(t): "is a consider entry, a current identifier that is not a sanctioned substitution"
               for t in terms[GO_WITH_CONSIDER]["consider"] if t in terms},
        },
        "observed_nodes": [_gid(g) for g in terms]
        + [n for n in b.nodes if n.startswith("view_")],
        "authored_nodes": [
            "start", "case", "flagged_report", "policy_register",
            "policy_2021a", "policy_2024b", "policy_2027c", "review", "split",
            "remapped_all", "retained", "miswritten", "target"],
    }
    grants = {"review": "packet_complete", "split": "disposition_recorded"}
    return b, spec, grants


# ---------------------------------------------------------------------------
# Task 35 — protocol_spec_status
#
# Currency, and the first task in this family with an N-of-M corroboration
# gate. The RFC index records two relations that look alike and mean
# different things. `obsoleted-by` replaces a document. `updated-by` leaves it
# standing and changes part of it somewhere else - the base document's own
# text is unchanged and says nothing about the change, which is why reading
# the specification is not how you find out. One cited specification is
# current with three updates against it; the other was updated once and then
# obsoleted, and the document that obsoleted it swept up the update too.
# ---------------------------------------------------------------------------

RFC_CORPUS = "corpora_rfc_status.json"
RFC_SNAPSHOT = "2024-06-30"
RFC_CURRENT = "RFC6749"
RFC_OBSOLETE = "RFC7540"
RFC_ACTIONS = ("clear-both-as-cited", "one-obsolete-one-updated",
               "escalate-both-obsolete")
RFC_CORRECT = "one-obsolete-one-updated"


def _fid(doc):
    return "d_" + doc.lower()


def protocol_spec_status_case():
    """DTB-RFC-35."""
    path = os.path.join(ROOT, RFC_CORPUS)
    with open(path, encoding="utf-8") as f:
        corpus = json.load(f)
    idx = corpus["observed_index"]
    ex = corpus["observed_excerpts"]
    b = Builder()

    b.node("start", (
        "Interoperability review DTB-RFC-35, snapshot 2024-06-30. A vendor "
        "integration declares conformance to two specifications by number: "
        "RFC 6749 and RFC 7540. Establish, for each, whether the document "
        "cited still states the specification, and record one disposition "
        "under the policy version in force. Selecting a disposition "
        "forecloses the others, so there is one attempt. A selected "
        "disposition is not filed until it has been committed to the review "
        "record, which is the step that closes the case."))
    b.edge("start", "e_case", "case", "workflow://DTB-RFC-35", "endpoint")

    b.node("case", (
        "Case packet DTB-RFC-35. Declared conformance: RFC 6749 and RFC "
        f"7540. The RFC index is available; it holds "
        f"{corpus['counts']['entries_in_index']} entries.\n"
        "[Case annotation: this packet, the policy register and the write "
        "actions are DetourBench overlay. Index entries and specification "
        "text are IETF publications.]"))

    def doc_node(rid):
        nid = _fid(rid)
        if nid in b.nodes:
            return nid
        r = idx[rid]
        rel = []
        for k, label in (("obsoleted_by", "Obsoleted by"),
                         ("updated_by", "Updated by"),
                         ("obsoletes", "Obsoletes"), ("updates", "Updates")):
            if r[k]:
                rel.append(f"{label}: {', '.join(r[k])}")
        b.node(nid, (
            f"{rid}  {r['title']}\n"
            f"Published: {r['date']}. Status: {r['current_status']}.\n"
            + (("\n".join(rel) + "\n") if rel else
               "No obsoletion or update relations of record\n")
            + (f"\nAbstract: {r['abstract'][:420]}"
               if r.get("abstract") else "")
            + (f"\n\nDocument text, opening:\n{ex[rid][:900]}"
               if rid in ex else "")))
        return nid

    for rid in idx:
        doc_node(rid)
    for rid, r in idx.items():
        for k in ("obsoleted_by", "updated_by", "obsoletes", "updates"):
            for other in r[k]:
                if other in idx:
                    b.edge(_fid(rid), f"e_{_fid(rid)}_{k}_{_fid(other)}",
                           _fid(other), f"rfc://index/{other}", "file")

    b.edge("case", f"e_seed_{_fid(RFC_CURRENT)}", _fid(RFC_CURRENT),
           f"rfc://index/{RFC_CURRENT}", "file")
    b.edge("case", f"e_seed_{_fid(RFC_OBSOLETE)}", _fid(RFC_OBSOLETE),
           f"rfc://index/{RFC_OBSOLETE}", "file")

    add_policy_register(b, "conformance-review", [
        ("policy_2021a", "DTB-CR-2021A", "2021-01-01 through 2023-12-31", (
            "DTB-CR-2021A (in force 2021-01-01 .. 2023-12-31).\n"
            "1. A declared specification is accepted if the document is "
            "published and its status is a standards-track status.\n"
            "2. Relations between documents are not assessed.")),
        ("policy_2024b", "DTB-CR-2024B", "2024-01-01 through 2026-12-31", (
            "DTB-CR-2024B (in force 2024-01-01 .. 2026-12-31). Supersedes "
            "DTB-CR-2021A.\n"
            "1. Obsoleted and updated are different findings. A document "
            "that has been obsoleted no longer states the specification. A "
            "document that has been updated still does, in part, and the "
            "updates state the rest.\n"
            "2. Status alone does not settle either question: an obsoleted "
            "document keeps the standards-track status it was published "
            "with.\n"
            "3. Where a document has been updated, the desk records it as "
            "materially modified once at least two of its updates have been "
            "assessed. A third adds no finding.\n"
            "4. A document that obsoletes another may also obsolete that "
            "document's updates; the successor's own record says which.\n"
            "5. Record exactly one disposition:\n"
            "   one-obsolete-one-updated — one cited document has been "
            "replaced and the other stands with modifications;\n"
            "   clear-both-as-cited — neither has been replaced or "
            "modified;\n"
            "   escalate-both-obsolete — both have been replaced.")),
        ("policy_2027c", "DTB-CR-2027C", "from 2027-01-01",
         "DTB-CR-2027C (in force from 2027-01-01). Not applicable to "
         "snapshots before 2027-01-01."),
    ], note="Conformance-review policy register.")

    updates = [u for u in idx[RFC_CURRENT]["updated_by"] if u in idx]
    b.node("modification_finding", (
        "Modification finding for RFC 6749. Recorded once at least two of "
        "the documents that update it have been assessed; the policy treats "
        "a third as adding no finding.\n"
        "Assessed updates establish that the cited document states the "
        "specification only in part."))
    # Recorded from the updates, not from the packet: the finding is what
    # reading them produces, and the gate needs two of the three.
    for u in updates:
        b.edge(_fid(u), f"e_modification_{_fid(u)}", "modification_finding",
               "workflow://DTB-RFC-35/modification-finding", "endpoint",
               requires_visited=[_fid(x) for x in updates],
               requires_visited_n=2)

    # The obsoleted side used to cost one hop: read 7540, see "obsoleted by
    # 9113", done. Policy rule 4 already said a successor may also obsolete
    # the document's updates - a rule nothing in the graph made anyone act
    # on. RFC 8740 updates 7540 and is itself obsoleted by 9113, both of
    # which the index states, so the finding that 7540 stands under no
    # surviving update is real work over two records rather than one.
    successor = idx[RFC_OBSOLETE]["obsoleted_by"][0]
    swept = [u for u in idx[RFC_OBSOLETE]["updated_by"] if u in idx]
    b.node("supersession_finding", (
        f"Supersession finding for {RFC_OBSOLETE[3:]}. Recorded once the "
        "successor and every update of the cited document have been "
        "assessed.\n"
        "Assessed records establish that no update of the cited document "
        "survives its replacement."))
    for src in [successor] + swept:
        b.edge(_fid(src), f"e_supersession_{_fid(src)}",
               "supersession_finding",
               "workflow://DTB-RFC-35/supersession-finding", "endpoint",
               requires_visited=[_fid(successor)] + [_fid(x) for x in swept])

    others = [r for r in idx
              if r not in {RFC_CURRENT, RFC_OBSOLETE, successor}
              and r not in updates and r not in swept]
    add_paged_views(
        b, "view_index", lambda r: f"rfc://index/{r}",
        "RFC index, entries carrying an obsoletion or update relation",
        [{"filingDate": idx[r]["date"], "form": idx[r]["current_status"][:18],
          "reportDate": None, "items": "", "accessionNumber": r}
         for r in others],
        per_page=6, uri_tmpl="rfc://index/search?relation=any&page={n}",
        id_of=_fid)

    required = ["policy_2024b", _fid(RFC_CURRENT), _fid(RFC_OBSOLETE),
                _fid(successor), "modification_finding",
                "supersession_finding"]
    add_disposition_block(
        b, "DTB-RFC-35", RFC_ACTIONS, RFC_CORRECT, required,
        {"clear-both-as-cited": ("cleared", (
            "Disposition selected: both declarations accepted as cited. No "
            "further step is available on this case.")),
         "one-obsolete-one-updated": ("split", (
             "Disposition selected: one cited document has been replaced, "
             "the other stands with modifications. Not yet filed. Commit it "
             "to the review record to close the case.")),
         "escalate-both-obsolete": ("escalated", (
             "Disposition selected: both cited documents have been replaced. "
             "No further step is available on this case."))},
        ("Review packet DTB-RFC-35 assembled. Governing policy version, both "
         "cited index entries, the successor document, the modification "
         "finding and the supersession finding are on file. Record one "
         "disposition."))

    spec = {
        "run_name": "protocol_spec_status",
        "theme": "protocol_conformance",
        "evidence_cluster_id": "ietf-rfc6749-rfc7540-status",
        "objective": (
            "Interoperability review DTB-RFC-35, snapshot 2024-06-30. "
            "Establish whether each cited specification still states the "
            "specification and record one disposition."),
        "corpus_file": RFC_CORPUS,
        "corpus_path": path,
        "provenance_boundary": (
            "Index entries, statuses and obsoletion or update relations, and "
            "the opening text of the cited specifications, are IETF "
            "publications quoted as published. The conformance policy, case "
            "packet and write actions are authored DetourBench overlays."),
        "source_kinds": ["frozen IETF RFC index entry",
                         "IETF specification text",
                         "authored local conformance policy"],
        "provenance_origin": "observed_ietf_rfc_index",
        "terminal_fail_nodes": ["cleared", "escalated"],
        "candidate_actions": list(RFC_ACTIONS),
        "correct_action": RFC_CORRECT,
        "primary_mechanism": "Currency",
        "supporting_mechanisms": ["Breadth", "Depth", "Disposition"],
        "unsupported_not_claimed": ["Sufficiency", "Time"],
        "crosswalk_basis": {
            "Currency": "one cited document has been replaced and keeps the standards-track status it was published with, so status does not show it",
            "Breadth": "the modification finding needs two of the three updates, and neither cited document's own text mentions any of them",
            "Depth": "the supersession finding needs the successor and the obsoleted document's own update, and only the update's record shows it did not survive",
            "Disposition": "three terminal actions follow the same packet, separated by which of the two documents is in which condition",
        },
        "domain_mechanisms": [
            "obsoleted and updated are different relations",
            "status is unchanged by obsoletion",
            "a base specification's own text never mentions its updates",
        ],
        "mechanism_regions": {
            "observed_cited_documents": [_fid(RFC_CURRENT),
                                         _fid(RFC_OBSOLETE)],
            "observed_successor": [_fid(successor)],
            "observed_updates": [_fid(u) for u in updates + swept],
            "observed_relationship": [n for n in b.nodes
                                      if n.startswith("view_")],
            "policy_currency": ["policy_register", "policy_2021a",
                                "policy_2024b", "policy_2027c"],
            "decision": ["review", "split", "target", "cleared", "escalated",
                         "modification_finding", "supersession_finding"],
            "off_route_context": [_fid(r) for r in others],
        },
        "semantic_required_nodes": required,
        "semantic_necessity": {
            "policy_2024b": "states that obsoleted and updated are different findings, that status does not settle either, and how many updates the modification finding needs",
            _fid(RFC_CURRENT): "carries the update relations that its own text does not mention",
            _fid(RFC_OBSOLETE): "carries the obsoletion relation while still showing a standards-track status",
            _fid(successor): "is the document that replaced it, and shows that it also swept up the update",
            "modification_finding": "is the corroborated record that the current document states the specification only in part",
            "supersession_finding": "is the corroborated record that no update of the replaced document survives it, which the replaced document's own entry does not show",
        },
        "observed_nodes": [_fid(r) for r in idx]
        + [n for n in b.nodes if n.startswith("view_")],
        "authored_nodes": [
            "start", "case", "policy_register", "policy_2021a",
            "policy_2024b", "policy_2027c", "modification_finding", "review",
            "split", "cleared", "escalated", "target"],
    }
    grants = {"review": "packet_complete", "split": "disposition_recorded"}
    return b, spec, grants


# ---------------------------------------------------------------------------
# Task 36 — recall_scope_by_lot
#
# Breadth, with a credential that is load-bearing rather than boilerplate. One
# lot of one product is covered by two recalls from the same firm on the same
# day under different classifications. The Class II record lists it among
# thirty other lots and says the seal may be breached; the Class I record
# names it alone and says the product is non-sterile with a named organism.
# Finding the lot on the Class II record is correct as far as it goes and
# understates the hazard by a class. The quarantine action needs a token only
# the Class I record grants, so an agent cannot take the right action without
# having found the record that justifies it.
# ---------------------------------------------------------------------------

FDA_CORPUS = "corpora_openfda_recall.json"
FDA_SNAPSHOT = "2026-07-15"
FDA_ACTIONS = ("return-per-class-ii", "quarantine-and-notify-class-i",
               "no-action-lot-not-affected")
FDA_CORRECT = "quarantine-and-notify-class-i"


def _recid(number):
    return "rec_" + number.replace("-", "_")


def recall_scope_by_lot_case():
    """DTB-FDA-36."""
    path = os.path.join(ROOT, FDA_CORPUS)
    with open(path, encoding="utf-8") as f:
        corpus = json.load(f)
    event = corpus["observed_event"]
    lot = corpus["held_lot"]
    lot2 = corpus["second_lot"]
    b = Builder()
    covering = [r for r in event if lot in (r["code_info"] or "")]
    class_i = [r for r in covering if r["classification"] == "Class I"][0]
    class_ii = [r for r in covering if r["classification"] == "Class II"][0]

    b.node("start", (
        f"Recall check DTB-FDA-36, snapshot {FDA_SNAPSHOT}. Hospital pharmacy "
        f"inventory holds two BD ChloraPrep items: Clear 1 mL applicators, "
        f"lot {lot}, and FREPP Clear 1.5 mL applicators, lot {lot2}. "
        "Establish every enforcement report that covers either lot, the "
        "highest classification among them, and record one disposition under "
        "the policy version in force. Selecting a disposition forecloses the "
        "others, so there is one attempt. A selected disposition is not filed "
        "until it has been committed to the pharmacy record, which is the "
        "step that closes the case."))
    b.edge("start", "e_case", "case", "workflow://DTB-FDA-36", "endpoint")

    b.node("case", (
        f"Case packet DTB-FDA-36. Inventory: BD ChloraPrep Clear, 2% "
        f"chlorhexidine gluconate and 70% isopropyl alcohol, 1 mL "
        f"applicator, lot {lot}; and BD ChloraPrep FREPP Clear, 1.5 mL "
        f"applicator, lot {lot2}.\n"
        # The packet used to enumerate the three search axes here. Naming
        # them - one of which is the short route - is the signpost DESIGN.md
        # measured at 72% -> 36%. The three searches are still revealed as
        # identifiers; which one to reach for is the agent's problem.
        "[Case annotation: this packet, the policy register and the write "
        "actions are DetourBench overlay. Enforcement reports are openFDA "
        "records quoted as published.]"))

    def rec_node(r):
        nid = _recid(r["recall_number"])
        if nid in b.nodes:
            return nid
        b.node(nid, (
            f"Enforcement report {r['recall_number']}. "
            f"Classification: {r['classification']}. Status: {r['status']}. "
            f"Event {r['event_id']}.\n"
            f"Firm: {r['recalling_firm']} ({r.get('city')}, "
            f"{r.get('country')}).\n"
            f"Product: {r['product_description'][:260]}\n"
            f"Reason for recall: {r['reason_for_recall'][:300]}\n"
            f"Code info: {(r['code_info'] or '')[:520]}\n"
            f"Initiated {r['recall_initiation_date']}, classified "
            f"{r['center_classification_date']}, reported {r['report_date']}. "
            f"Distribution: {r.get('distribution_pattern')}"))
        return nid

    for r in event + corpus["observed_same_firm"] + \
            corpus["observed_same_ingredient"]:
        rec_node(r)

    add_policy_register(b, "recall-response", [
        ("policy_2023a", "DTB-RR-2023A", "2023-01-01 through 2025-12-31", (
            "DTB-RR-2023A (in force 2023-01-01 .. 2025-12-31).\n"
            "1. Where an enforcement report covers a held lot, act on that "
            "report's classification.\n"
            "2. One report per lot is assumed.")),
        ("policy_2026b", "DTB-RR-2026B", "2026-01-01 through 2028-12-31", (
            "DTB-RR-2026B (in force 2026-01-01 .. 2028-12-31). Supersedes "
            "DTB-RR-2023A.\n"
            "1. A lot may be covered by more than one enforcement report. "
            "Every report covering the lot is assessed and the highest "
            "classification among them governs.\n"
            "2. A search by product description does not establish the set: "
            "reports covering the same product differ in which lots they "
            "name. The lot number is what settles coverage.\n"
            "3. Class I means a reasonable probability of serious adverse "
            "health consequences. A Class I report is quarantined and "
            "notified, never returned through routine channels.\n"
            "4. Record exactly one disposition:\n"
            "   quarantine-and-notify-class-i — any report covering the lot "
            "is Class I;\n"
            "   return-per-class-ii — every report covering the lot is Class "
            "II or lower;\n"
            "   no-action-lot-not-affected — no report covers the lot.")),
        ("policy_2029c", "DTB-RR-2029C", "from 2029-01-01",
         "DTB-RR-2029C (in force from 2029-01-01). Not applicable to "
         "snapshots before 2029-01-01."),
    ], note="Recall-response policy register.")

    add_scoped_view(
        b, "view_by_product", "openfda://enforcement?product=ChloraPrep",
        "openFDA enforcement search by product description, chlorhexidine "
        "gluconate applicators,",
        [{"filingDate": r["report_date"], "form": r["classification"],
          "reportDate": None, "items": r["status"],
          "accessionNumber": r["recall_number"]}
         for r in event[:2] + corpus["observed_same_ingredient"][:3]],
        lambda n: f"openfda://enforcement/{n}", id_of=_recid)
    add_paged_views(
        b, "view_by_firm", lambda n: f"openfda://enforcement/{n}",
        "openFDA enforcement search by recalling firm",
        [{"filingDate": r["report_date"], "form": r["classification"],
          "reportDate": None, "items": r["status"],
          "accessionNumber": r["recall_number"]}
         for r in corpus["observed_same_firm"]],
        per_page=5, uri_tmpl="openfda://enforcement?firm=BD&page={n}",
        id_of=_recid)
    add_paged_views(
        b, "view_by_ingredient", lambda n: f"openfda://enforcement/{n}",
        "openFDA enforcement search by active ingredient",
        [{"filingDate": r["report_date"], "form": r["classification"],
          "reportDate": None, "items": r["status"],
          "accessionNumber": r["recall_number"]}
         for r in corpus["observed_same_ingredient"]],
        per_page=6, uri_tmpl="openfda://enforcement?ingredient=CHG&page={n}",
        id_of=_recid)

    # The search that settles it. Reached from a report that already lists
    # the lot, because that is where an analyst learns the lot is searchable.
    covering2 = [r for r in event if lot2 in (r["code_info"] or "")]
    for tag, held, cov, parent in (("view_by_lot", lot, covering,
                                    _recid(class_ii["recall_number"])),
                                   ("view_by_lot2", lot2, covering2,
                                    "view_by_lot")):
        b.node(tag, (
            f"openFDA enforcement search by lot number {held}, "
            f"{len(cov)} records.\n"
            + "\n".join(f"{r['report_date']}  {r['recall_number']}  "
                        f"{r['classification']}  {r['status']}"
                        for r in cov)))
        b.edge(parent, f"e_{tag}", tag,
               f"openfda://enforcement?lot={held}", "endpoint")
        for r in cov:
            b.edge(tag, f"e_{tag}_{_recid(r['recall_number'])}",
                   _recid(r["recall_number"]),
                   f"openfda://enforcement/{r['recall_number']}", "file")

    b.edge("case", "e_seed", _recid(class_ii["recall_number"]),
           f"openfda://enforcement/{class_ii['recall_number']}", "file")

    n_i = _recid(class_i["recall_number"])
    n_ii = _recid(class_ii["recall_number"])
    n_ii2 = _recid(covering2[0]["recall_number"])
    required = ["policy_2026b", n_ii, "view_by_lot", n_i, "view_by_lot2",
                n_ii2]
    add_disposition_block(
        b, "DTB-FDA-36", FDA_ACTIONS, FDA_CORRECT, required,
        {"return-per-class-ii": ("returned", (
            "Disposition selected: returned through routine channels under a "
            "Class II report. No further step is available on this case.")),
         "quarantine-and-notify-class-i": ("quarantined", (
             "Disposition selected: lot quarantined and clinical areas "
             "notified under a Class I report. Not yet filed. Commit it to "
             "the pharmacy record to close the case.")),
         "no-action-lot-not-affected": ("no_action", (
             "Disposition selected: no report covers the lot. No further "
             "step is available on this case."))},
        ("Review packet DTB-FDA-36 assembled. Governing policy version, the "
         "reports covering each held lot and their classifications are on "
         "file. Record one disposition."))
    # The Class I record is what authorises the quarantine, so the action
    # carries a token only that record grants. An agent cannot take the right
    # action on a hunch.
    for e in b.edges["review"]:
        if e["to"] == "quarantined":
            e["requires"] = ["packet_complete", "class_i_confirmed"]

    spec = {
        "run_name": "recall_scope_by_lot",
        "theme": "pharmacy_recall_response",
        "evidence_cluster_id": "openfda-event-99114-chloraprep",
        "objective": (
            f"Recall check DTB-FDA-36, snapshot {FDA_SNAPSHOT}. Establish "
            f"every enforcement report covering either held lot, the highest "
            "classification among them, and record one disposition."),
        "corpus_file": FDA_CORPUS,
        "corpus_path": path,
        "provenance_boundary": (
            "Enforcement reports, their classifications, lot lists and stated "
            "reasons are openFDA records quoted as published. The recall-"
            "response policy, case packet and write actions are authored "
            "DetourBench overlays. They are not any pharmacy's procedure and "
            "state no view on the recalling firm."),
        "source_kinds": ["frozen openFDA enforcement report",
                         "authored local recall-response policy"],
        "provenance_origin": "observed_openfda_enforcement",
        "terminal_fail_nodes": ["returned", "no_action"],
        "candidate_actions": list(FDA_ACTIONS),
        "correct_action": FDA_CORRECT,
        "primary_mechanism": "Breadth",
        "supporting_mechanisms": ["Disposition", "Currency", "Depth"],
        "unsupported_not_claimed": ["Sufficiency", "Time"],
        "crosswalk_basis": {
            "Breadth": "one lot is covered by two reports of different classification and the search that returns the product returns only the lower one",
            "Disposition": "three terminal actions follow the same packet, and the one that matches the hazard is gated on the record that establishes it",
            "Currency": "the superseded policy assumes one report per lot, which records a different disposition",
            "Depth": "the lot search is reached from a report that already lists the lot, not from the packet",
        },
        "domain_mechanisms": [
            "one lot covered by two recalls of different classification",
            "product search and lot search return different sets",
            "the higher classification governs",
        ],
        "mechanism_regions": {
            "observed_covering_reports": [n_ii, n_i],
            "observed_event": [_recid(r["recall_number"]) for r in event],
            "observed_relationship": [n for n in b.nodes
                                      if n.startswith("view_")],
            "policy_currency": ["policy_register", "policy_2023a",
                                "policy_2026b", "policy_2029c"],
            "decision": ["review", "quarantined", "target", "returned",
                         "no_action"],
            "off_route_context": [
                _recid(r["recall_number"])
                for r in corpus["observed_same_firm"]
                + corpus["observed_same_ingredient"]],
        },
        "semantic_required_nodes": required,
        "semantic_necessity": {
            "policy_2026b": "states that a lot may be covered by more than one report, that the highest classification governs, and that a product search does not establish the set",
            n_ii: "is the report a product search returns, lists the lot among thirty others, and is where the lot search is reached from",
            "view_by_lot": "is the only record of the complete set of reports covering the lot",
            n_i: "carries the Class I classification and the named organism, and grants the authority the quarantine action requires",
            "view_by_lot2": "is the complete set of reports covering the second held lot, which the policy assesses as well",
            n_ii2: "is the only report covering the second lot, and the check that comes back Class II",
        },
        "observed_nodes": [n for n in b.nodes
                           if n.startswith(("rec_", "view_"))],
        "authored_nodes": [
            "start", "case", "policy_register", "policy_2023a",
            "policy_2026b", "policy_2029c", "review", "quarantined",
            "returned", "no_action", "target"],
    }
    grants = {"review": "packet_complete",
              _recid(class_i["recall_number"]): "class_i_confirmed",
              "quarantined": "disposition_recorded"}
    return b, spec, grants


# ---------------------------------------------------------------------------
# Task 38 — cluster_api_removal_triage
#
# Breadth, and the first task in this family with no review gate at all. The
# terminal action is reached when three credentials have been picked up along
# the way, which is the shape tasks 3 to 11 use and none of the finance five
# do. It also changes what the environment tells a stuck agent: a visited-set
# gate says only that something is missing, while a credential gate names the
# kind of check that has not been recorded.
#
# The case crosses two releases, and the guide is organised by release, so an
# upgrade that reads only its target misses half the removals. Within one
# release, PodDisruptionBudget and PodSecurityPolicy are both policy/v1beta1
# and only one of them has a replacement API version - the other needs a
# different admission mechanism entirely, which is not a manifest rewrite.
# ---------------------------------------------------------------------------

K8S_CORPUS = "corpora_k8s_deprecations.json"
K8S_FROM, K8S_TO = "v1.24", "v1.26"
K8S_ACTIONS = ("proceed-target-release-clear",
               "rewrite-manifests-and-proceed",
               "block-pending-admission-migration")
K8S_CORRECT = "block-pending-admission-migration"


def _relid(rel):
    return "rel_" + rel.replace(".", "_")


def _entid(anchor):
    return "api_" + anchor.replace("-", "_").replace(".", "_")


def cluster_api_removal_triage_case():
    """DTB-K8S-38."""
    path = os.path.join(ROOT, K8S_CORPUS)
    with open(path, encoding="utf-8") as f:
        corpus = json.load(f)
    releases = corpus["observed_releases"]
    b = Builder()
    crossed = ["v1.25", "v1.26"]

    b.node("start", (
        f"Upgrade triage DTB-K8S-38. A cluster running {K8S_FROM} is planned "
        f"for {K8S_TO}. Three workload manifests are in scope. Establish "
        "every API version the upgrade stops serving, what each one migrates "
        "to, and record one disposition under the policy version in force. "
        "Selecting a disposition forecloses the others, so there is one "
        "attempt. Recording a disposition needs the checks it rests on to "
        "have been carried out."))
    b.edge("start", "e_case", "case", "workflow://DTB-K8S-38", "endpoint")

    b.node("case", (
        f"Case packet DTB-K8S-38. Cluster at {K8S_FROM}; target {K8S_TO}.\n"
        "The manifests in scope are listed in the change request's inventory.\n"
        # "organised by the release in which each API version stopped being
        # served" used to follow. That sentence is the task's central
        # mechanism - an upgrade crosses every intermediate release - handed
        # over before the agent opens anything. The guide's own opening line
        # still says how it is arranged, which is where that belongs.
        "The project publishes a deprecated API migration guide.\n"
        "[Case annotation: this packet, the policy register and the write "
        "actions are DetourBench overlay. The migration guide and release "
        "notes are Kubernetes documentation.]"))

    add_policy_register(b, "upgrade-triage", [
        ("policy_2023a", "DTB-UT-2023A", "2023-01-01 through 2024-12-31", (
            "DTB-UT-2023A (in force 2023-01-01 .. 2024-12-31).\n"
            "1. Check the removals published for the target release.\n"
            "2. Where an API version is removed, rewrite the manifest to the "
            "replacement version.")),
        ("policy_2025b", "DTB-UT-2025B", "2025-01-01 through 2027-12-31", (
            "DTB-UT-2025B (in force 2025-01-01 .. 2027-12-31). Supersedes "
            "DTB-UT-2023A.\n"
            "1. An upgrade crosses every release between the current version "
            "and the target. The removals of each crossed release apply, not "
            "only the target's.\n"
            "2. A removal is a manifest rewrite only where the guide names a "
            "replacement API version. Where it names none, the capability is "
            "withdrawn and the migration is to a different mechanism; that is "
            "not a manifest change and cannot be done during the upgrade.\n"
            "3. Two resources may share an API group and version and migrate "
            "differently. The entry for the resource governs, not the entry "
            "for its neighbour.\n"
            "4. Record exactly one disposition:\n"
            "   proceed-target-release-clear — no crossed release removes an "
            "API version in scope;\n"
            "   rewrite-manifests-and-proceed — every removal in scope has a "
            "replacement API version;\n"
            "   block-pending-admission-migration — a removal in scope has no "
            "replacement API version.")),
        ("policy_2028c", "DTB-UT-2028C", "from 2028-01-01",
         "DTB-UT-2028C (in force from 2028-01-01). Not applicable before "
         "2028-01-01."),
    ], note="Upgrade-triage policy register.")

    b.node("inventory", (
        "Change request DTB-K8S-38, manifest inventory. Three manifests are "
        "in scope for this upgrade.\n"
        "  workloads/pdb.yaml             apiVersion: policy/v1beta1, "
        "kind: PodDisruptionBudget\n"
        "  workloads/psp-restricted.yaml  apiVersion: policy/v1beta1, "
        "kind: PodSecurityPolicy\n"
        "  workloads/hpa-api.yaml         apiVersion: autoscaling/v2beta2, "
        "kind: HorizontalPodAutoscaler\n"
        "Two of the three declare the same API group and version."))
    b.edge("case", "e_inventory", "inventory",
           "workflow://DTB-K8S-38/manifest-inventory", "file")

    b.node("guide", (
        "Deprecated API migration guide. Sections, one per release, listing "
        "the API versions that release stopped serving.\n"
        + "\n".join(f"{rel}  ({len(entries)} resources)"
                    for rel, entries in sorted(releases.items()))))
    b.edge("case", "e_guide", "guide",
           "k8s://docs/reference/using-api/deprecation-guide", "file")

    for rel, entries in sorted(releases.items()):
        nid = _relid(rel)
        b.node(nid, (
            f"Deprecated API migration guide, {rel}. The {rel} release "
            f"stopped serving the following API versions.\n"
            + "\n".join(
                f"  {e['resource']}: {e['removed_api_version']}"
                + (f"  ->  {e['replacement_api_version']} "
                   f"(available since {e['replacement_available_since']})"
                   if e["replacement_api_version"] else
                   "  ->  no replacement API version is named")
                for e in entries.values())))
        b.edge("guide", f"e_{nid}", nid,
               f"k8s://docs/reference/using-api/deprecation-guide#{rel}",
               "file")
        for anchor, e in entries.items():
            eid = _entid(anchor)
            b.node(eid, (
                f"{e['resource']} — removed in {e['removed_in']}.\n"
                f"API version no longer served: {e['removed_api_version']}\n"
                + (f"Replacement API version: {e['replacement_api_version']}, "
                   f"available since {e['replacement_available_since']}\n"
                   if e["replacement_api_version"]
                   else "No replacement API version is named.\n")
                + "\n" + e["text"][:900]))
            b.edge(nid, f"e_{nid}_{eid}", eid,
                   f"k8s://docs/reference/using-api/deprecation-guide"
                   f"#{anchor}", "file")

    # The release notes are real posts and real detours: they announce the
    # same removals in prose, without the replacement API versions the guide
    # states outright. Each is a node before the search lists it - a listing
    # whose entries resolve to nothing is not a distractor, it is a crash.
    notes = corpus["observed_release_notes"]
    for name, rec in notes.items():
        b.node(_node_id_safe(name),
               f"{rec['title']}\n\n{rec['text'][:800]}")
    add_paged_views(
        b, "view_release_notes", lambda n: f"k8s://blog/{n}",
        "Release notes announcing removals and deprecations",
        [{"filingDate": n[:24], "form": "blog", "reportDate": None,
          "items": "", "accessionNumber": n} for n in sorted(notes)],
        per_page=4, uri_tmpl="k8s://blog/index?page={n}",
        id_of=_node_id_safe)

    psp = _entid("psp-v125")
    pdb = _entid("poddisruptionbudget-v125")
    hpa = _entid("horizontalpodautoscaler-v126")

    b.node("blocked", (
        "Disposition selected: upgrade blocked pending an admission-"
        "mechanism migration. Not yet filed. Commit it to the change record "
        "to close the case."))
    b.node("rewritten", (
        "Disposition selected: manifests rewritten to replacement API "
        "versions and the upgrade proceeds. No further step is available on "
        "this case."))
    b.node("proceeded", (
        "Disposition selected: no API version in scope is removed by the "
        "upgrade. No further step is available on this case."))
    # No review gate. The action is reached when the checks it rests on have
    # actually been carried out, and the environment names which is missing.
    # Each disposition is reached once the checks it rests on have actually
    # been carried out, and the environment names the kind of check that is
    # missing rather than saying only that something is.
    for action, node, req in (
            ("proceed-target-release-clear", "proceeded",
             ["scope_established", "policy_in_force_read",
              "target_release_checked"]),
            ("rewrite-manifests-and-proceed", "rewritten",
             ["scope_established", "policy_in_force_read",
              "target_release_checked", "crossing_release_checked",
              "replacement_named_confirmed", "target_removal_checked"]),
            ("block-pending-admission-migration", "blocked",
             ["scope_established", "policy_in_force_read",
              "target_release_checked", "crossing_release_checked",
              "replacement_named_confirmed", "target_removal_checked",
              "withdrawal_confirmed"])):
        b.edge("case", f"e_{action}", node,
               f"workflow://DTB-K8S-38/actions/{action}", "endpoint",
               requires=req)
    b.node("target", "Disposition committed to the change record for "
                     "DTB-K8S-38.")
    b.edge("blocked", "e_target", "target", "audit://DTB-K8S-38/commit",
           "endpoint", requires="disposition_recorded")

    required = ["inventory", "policy_2025b", _relid("v1.25"),
                _relid("v1.26"), psp, pdb, hpa]
    observed = (["guide"] + [_relid(r) for r in releases]
                + [_entid(a) for rel in releases for a in releases[rel]]
                + [n for n in b.nodes if n.startswith("view_release_notes")]
                + [_node_id_safe(n) for n in notes])
    spec = {
        "run_name": "cluster_api_removal_triage",
        "theme": "cluster_upgrade_triage",
        "evidence_cluster_id": "k8s-deprecation-guide-v125-v126",
        "objective": (
            f"Upgrade triage DTB-K8S-38. Establish every API version the "
            f"{K8S_FROM} to {K8S_TO} upgrade stops serving, what each "
            "migrates to, and record one disposition."),
        "corpus_file": K8S_CORPUS,
        "corpus_path": path,
        "provenance_boundary": (
            "The migration guide, its per-release sections and the release "
            "notes are Kubernetes project documentation quoted as published. "
            "The upgrade-triage policy, case packet, manifest inventory and "
            "write actions are authored DetourBench overlays."),
        "source_kinds": ["frozen Kubernetes documentation",
                         "authored local upgrade policy"],
        "provenance_origin": "observed_kubernetes_docs",
        "terminal_fail_nodes": ["proceeded", "rewritten"],
        "candidate_actions": list(K8S_ACTIONS),
        "correct_action": K8S_CORRECT,
        "primary_mechanism": "Breadth",
        "supporting_mechanisms": ["Currency", "Depth", "Disposition"],
        "unsupported_not_claimed": ["Sufficiency", "Time"],
        "crosswalk_basis": {
            "Breadth": "the upgrade crosses two releases and the guide is organised by release, so reading the target's section finds half the removals",
            "Currency": "the superseded policy checks the target release only and rewrites every removal, which records a different disposition",
            "Depth": "whether a removal is a rewrite is stated in the resource's own entry, one level below the release section that lists it",
            "Disposition": "three terminal actions, each reached only once the checks it rests on have been carried out",
        },
        "domain_mechanisms": [
            "an upgrade crosses every release between current and target",
            "two resources sharing an API group and version migrate differently",
            "a removal with no replacement API is a mechanism change, not a rewrite",
        ],
        "mechanism_regions": {
            "observed_guide": ["guide"] + [_relid(r) for r in releases],
            "observed_entries": [_entid(a) for rel in releases
                                 for a in releases[rel]],
            "observed_relationship": [n for n in b.nodes
                                      if n.startswith("view_")],
            "policy_currency": ["policy_register", "policy_2023a",
                                "policy_2025b", "policy_2028c"],
            "decision": ["blocked", "target", "rewritten", "proceeded"],
            "off_route_context": [_entid(a) for rel in releases
                                  for a in releases[rel]
                                  if _entid(a) not in (psp, pdb, hpa)],
        },
        "semantic_required_nodes": required,
        "semantic_necessity": {
            "inventory": "is the only record of which manifests are in scope, and of the fact that two of them declare the same API group and version",
            "policy_2025b": "states that every crossed release applies, that a removal without a replacement is a mechanism change, and that a neighbour's entry does not govern",
            _relid("v1.25"): "carries the removals of the release the upgrade passes through rather than lands on",
            _relid("v1.26"): "carries the removals of the target release",
            psp: "is the entry that names no replacement API version, which is what separates the correct disposition from the other two",
            pdb: "shares an API group and version with the PodSecurityPolicy entry and does name a replacement, which is what makes the neighbour rule bite",
            hpa: "is the target release's removal in scope and does name a replacement",
        },
        "observed_nodes": observed,
        "authored_nodes": [
            "start", "case", "inventory", "policy_register", "policy_2023a",
            "policy_2025b", "policy_2028c", "blocked", "rewritten",
            "proceeded", "target"],
        "no_review_gate": True,
    }
    grants = {
        "inventory": "scope_established",
        "policy_2025b": "policy_in_force_read",
        _relid("v1.26"): "target_release_checked",
        _relid("v1.25"): "crossing_release_checked",
        pdb: "replacement_named_confirmed",
        hpa: "target_removal_checked",
        psp: "withdrawal_confirmed",
        "blocked": "disposition_recorded",
    }
    return b, spec, grants


def _node_id_safe(name):
    return "note_" + re.sub(r"[^0-9a-zA-Z]+", "_", name)[:40]


# ---------------------------------------------------------------------------
# Task 39 — handbook_entity_precedence
#
# Breadth. A rotation covers team members in three legal entities and the
# handbook layers its people policies: a general policy for everyone,
# entity-specific policies for the team members of one entity, and an index
# that says the entity-specific ones do not displace the code of conduct. The
# trap is in the text rather than in the layering. The Ireland policy's
# applicability section opens "applies to all team members regardless of
# position, tenure, and work location", which reads company-wide, and only
# the qualifier that follows and the pointer back to the entity index settle
# that it is one entity's policy.
# ---------------------------------------------------------------------------

HB_CORPUS = "corpora_handbook_policies.json"
HB_ACTIONS = ("apply-general-policy-uniformly",
              "apply-entity-policies-per-member",
              "apply-strictest-entity-policy-to-all")
HB_CORRECT = "apply-entity-policies-per-member"


def _pgid(key):
    return "p_" + key


def handbook_entity_precedence_case():
    """DTB-HB-39."""
    path = os.path.join(ROOT, HB_CORPUS)
    with open(path, encoding="utf-8") as f:
        corpus = json.load(f)
    pages = corpus["observed_pages"]
    b = Builder()

    b.node("start", (
        "Policy question DTB-HB-39. A manager is planning an out-of-hours "
        "support rotation. The team members on it are employed by three "
        "different GitLab legal entities. Establish which people policies "
        "govern the rotation for whom, and record one disposition under the "
        "policy version in force. Selecting a disposition forecloses the "
        "others, so there is one attempt. A selected disposition is not "
        "filed until it has been committed to the request record, which is "
        "the step that closes the case."))
    b.edge("start", "e_case", "case", "workflow://DTB-HB-39", "endpoint")

    b.node("case", (
        "Case packet DTB-HB-39. Rotation membership by employing entity:\n"
        "  GitLab Inc. (USA)          3 team members\n"
        "  GitLab Ireland Ltd         2 team members\n"
        "  GitLab France S.A.S.       1 team member\n"
        "The handbook holds "
        f"{corpus['counts']['handbook_markdown_files']} pages. The people "
        "policies index lists the general policies and points at the "
        "entity-specific ones.\n"
        "[Case annotation: this packet, the review policy and the write "
        "actions are DetourBench overlay. Handbook pages are quoted as "
        "published.]"))

    add_policy_register(b, "policy-review", [
        ("policy_2022a", "DTB-PR-2022A", "2022-01-01 through 2024-12-31", (
            "DTB-PR-2022A (in force 2022-01-01 .. 2024-12-31).\n"
            "1. Apply the general people policy to every team member.\n"
            "2. Entity pages are informational.")),
        ("policy_2025b", "DTB-PR-2025B", "2025-01-01 through 2027-12-31", (
            "DTB-PR-2025B (in force 2025-01-01 .. 2027-12-31). Supersedes "
            "DTB-PR-2022A.\n"
            "1. Where an employing entity has its own policy on a subject, "
            "that policy governs for that entity's team members. The general "
            "policy governs for the rest.\n"
            "2. An entity policy's own applicability wording describes its "
            "scope within that entity. It does not extend the policy to team "
            "members of other entities, whatever it appears to say. The "
            "entity index is what establishes which entity a policy belongs "
            "to.\n"
            "3. Applying one entity's policy to team members of another is "
            "not a conservative choice; it applies terms their employment is "
            "not subject to.\n"
            "4. Record exactly one disposition:\n"
            "   apply-entity-policies-per-member — at least one entity on "
            "the rotation has its own policy on the subject and at least one "
            "does not;\n"
            "   apply-general-policy-uniformly — no entity on the rotation "
            "has its own policy on the subject;\n"
            "   apply-strictest-entity-policy-to-all — one entity policy "
            "covers every member of the rotation.")),
        ("policy_2028c", "DTB-PR-2028C", "from 2028-01-01",
         "DTB-PR-2028C (in force from 2028-01-01). Not applicable before "
         "2028-01-01."),
    ], note="Policy-review register.")

    def page_node(key, extra=""):
        nid = _pgid(key)
        if nid in b.nodes:
            return nid
        p = pages[key]
        b.node(nid, (
            f"{p['title']}\n"
            f"Handbook path: {p['path']}. Length {p['length']} characters.\n"
            + (f"\nApplicability, as written:\n{p['applicability'][:900]}\n"
               if p["applicability"] else "")
            + (f"\n{extra}\n" if extra else "")
            + f"\nOpening:\n{p['opening'][:700]}"))
        return nid

    page_node("people_policies")
    page_node("entity_index")
    page_node("ireland_disconnect")
    page_node("france_disconnect")
    page_node("france_remote")
    page_node("usa_policies",
              "No right-to-disconnect policy is published for this entity.")
    page_node("india_policies",
              "This entity has no team member on the rotation.")

    b.edge("case", "e_index", _pgid("people_policies"),
           "handbook:///handbook/people-policies/", "file")
    # The index points at the entity list; the entity list is what says which
    # policy belongs to which entity.
    b.edge(_pgid("people_policies"), "e_entity_index", _pgid("entity_index"),
           "handbook:///handbook/entity/entity-specific-employment-policies/",
           "file")
    for key, url in (("usa_policies", "people-policies/inc-usa"),
                     ("india_policies", "people-policies/india-ltd"),
                     ("ireland_disconnect",
                      "people-policies/ireland-ltd/right-to-disconnect-policy"),
                     ("france_disconnect",
                      "people-policies/france-sas/right-to-disconnect-charter"),
                     ("france_remote",
                      "people-policies/france-sas/remote-work-charter")):
        b.edge(_pgid("entity_index"), f"e_ent_{key}", _pgid(key),
               f"handbook:///handbook/{url}/", "file")
    # The Ireland policy points back at the entity index in its own text.
    b.edge(_pgid("ireland_disconnect"), "e_ire_back", _pgid("entity_index"),
           "handbook:///handbook/people-policies/#entity-specific-employment-policies",
           "file")

    # Pages the index actually links to. Real handbook pages, none of which
    # publishes anything on out-of-hours contact, paged so no one access
    # hands the whole list over.
    # Drop the links that point at pages already modelled above. Keeping
    # them mints a second node for the same page under the same identifier,
    # and `known` keeps whichever was revealed last.
    modelled = {
        "/handbook/people-policies/",
        "/handbook/entity/entity-specific-employment-policies/",
        "/handbook/people-policies/inc-usa/",
        "/handbook/people-policies/india-ltd/",
        "/handbook/people-policies/ireland-ltd/right-to-disconnect-policy/",
        "/handbook/people-policies/france-sas/right-to-disconnect-charter/",
        "/handbook/people-policies/france-sas/remote-work-charter/",
    }

    def _modelled(u):
        v = u if u.endswith("/") else u + "/"
        return v in modelled

    links = [u for u in corpus["observed_links_from_index"]
             if not _modelled(u)]
    for u in links:
        nid = _node_id_safe(u)
        b.node(nid, (
            f"Handbook page {u}.\n"
            "Linked from the people policies index. Nothing on this page "
            "addresses out-of-hours contact or the right to disconnect."))
    pages_of = [links[i:i + 5] for i in range(0, len(links), 5)]
    for n, page in enumerate(pages_of, 1):
        vid = f"view_index_links_p{n}"
        tail = ("A continuation page remains." if n < len(pages_of)
                else "End of this listing.")
        b.node(vid, (
            f"People policies index, linked pages, page {n} of "
            f"{len(pages_of)}, {len(page)} entries. {tail}\n"
            + "\n".join("  " + u for u in page)))
        b.edge(_pgid("people_policies") if n == 1
               else f"view_index_links_p{n - 1}",
               f"e_{vid}", vid,
               f"handbook:///handbook/people-policies/#links{n}", "endpoint")
        for u in page:
            b.edge(vid, f"e_{vid}_{_node_id_safe(u)}", _node_id_safe(u),
                   f"handbook://{u}", "file")

    required = ["policy_2025b", _pgid("people_policies"),
                _pgid("entity_index"), _pgid("ireland_disconnect"),
                _pgid("france_disconnect"), _pgid("usa_policies")]
    add_disposition_block(
        b, "DTB-HB-39", HB_ACTIONS, HB_CORRECT, required,
        {"apply-general-policy-uniformly": ("uniform", (
            "Disposition selected: the general people policy applied to "
            "every member of the rotation. No further step is available on "
            "this case.")),
         "apply-entity-policies-per-member": ("per_member", (
             "Disposition selected: each member's employing entity's policy "
             "applied, and the general policy where the entity publishes "
             "none. Not yet filed. Commit it to the request record to close "
             "the case.")),
         "apply-strictest-entity-policy-to-all": ("strictest", (
             "Disposition selected: one entity's policy applied to the whole "
             "rotation. No further step is available on this case."))},
        ("Review packet DTB-HB-39 assembled. Governing review policy, the "
         "people policies index, the entity index and the policies published "
         "by each entity on the rotation are on file. Record one "
         "disposition."))

    observed = ([_pgid(k) for k in pages]
                + [n for n in b.nodes if n.startswith(("view_", "note_"))])
    spec = {
        "run_name": "handbook_entity_precedence",
        "theme": "internal_policy_review",
        "evidence_cluster_id": "gitlab-handbook-entity-disconnect",
        "objective": (
            "Policy question DTB-HB-39. Establish which people policies "
            "govern an out-of-hours rotation for team members of three legal "
            "entities and record one disposition."),
        "corpus_file": HB_CORPUS,
        "corpus_path": path,
        "provenance_boundary": (
            "Handbook pages, their applicability sections and the links "
            "between them are quoted from the published GitLab handbook. The "
            "review policy, case packet, rotation membership and write "
            "actions are authored DetourBench overlays and are not GitLab's "
            "process."),
        "source_kinds": ["frozen public handbook page",
                         "authored local review policy"],
        "provenance_origin": "observed_gitlab_handbook",
        "terminal_fail_nodes": ["uniform", "strictest"],
        "candidate_actions": list(HB_ACTIONS),
        "correct_action": HB_CORRECT,
        "primary_mechanism": "Breadth",
        "supporting_mechanisms": ["Currency", "Depth", "Disposition"],
        "unsupported_not_claimed": ["Sufficiency", "Time"],
        "crosswalk_basis": {
            "Breadth": "three entities are on the rotation and the answer differs for each, so checking one entity's page settles a third of it",
            "Currency": "the superseded review policy applies the general policy to everyone, which records a different disposition",
            "Depth": "which entity a policy belongs to is established by the entity index, one level below the people policies page",
            "Disposition": "three terminal actions follow the same packet, separated by how many entities publish their own policy",
        },
        "domain_mechanisms": [
            "an entity policy's applicability wording reads company-wide",
            "the entity index is what scopes a policy to an entity",
            "applying a stricter entity's policy to others is not conservative",
        ],
        "mechanism_regions": {
            "observed_general": [_pgid("people_policies"),
                                 _pgid("entity_index")],
            "observed_entity_pages": [_pgid(k) for k in
                                      ("ireland_disconnect",
                                       "france_disconnect", "france_remote",
                                       "usa_policies", "india_policies")],
            "observed_relationship": [n for n in b.nodes
                                      if n.startswith("view_")],
            "policy_currency": ["policy_register", "policy_2022a",
                                "policy_2025b", "policy_2028c"],
            "decision": ["review", "per_member", "target", "uniform",
                         "strictest"],
            "off_route_context": [n for n in b.nodes
                                  if n.startswith("note_")],
        },
        "semantic_required_nodes": required,
        "semantic_necessity": {
            "policy_2025b": "states that an entity policy governs for that entity's members, that its applicability wording does not extend it, and that applying one entity's policy to others is not conservative",
            _pgid("people_policies"): "is the general policy and the route to the entity index",
            _pgid("entity_index"): "is what establishes which entity each policy belongs to",
            _pgid("ireland_disconnect"): "is one entity's policy, and its applicability wording is what makes the uniform reading available",
            _pgid("france_disconnect"): "is a second entity's policy on the same subject, so the answer is not one policy for the rotation",
            _pgid("usa_policies"): "is the entity that publishes no policy on the subject, which is what makes the answer differ by member",
        },
        "observed_nodes": observed,
        "authored_nodes": [
            "start", "case", "policy_register", "policy_2022a",
            "policy_2025b", "policy_2028c", "review", "per_member", "uniform",
            "strictest", "target"],
    }
    grants = {"review": "packet_complete", "per_member": "disposition_recorded"}
    return b, spec, grants
