#!/usr/bin/env python3
"""Corpus + generated-overlay EHR tasks (same paradigm as 12/13/14).

Not wired into generate_ehr_suite.py. Frozen Tasks 12–14 stay skipped there.
"""
import hashlib

from ehr_topologies import _case, _leaf_nodes, _meta, _order_graph_edges, _prov

EDGE_SEED = 212026
EDGE_RULE = "sha256(seed:identifier) hex ascending"

ORACLE_21 = [
    "e_intake", "e_patient", "e_meds", "e_allergy", "e_asa", "e_class",
    "e_exceptions", "e_exception_result", "e_synthesis", "e_policy",
    "e_hold", "e_target",
]
ORACLE_22 = [
    "e_intake", "e_patient", "e_meds", "e_statin20", "e_statin10",
    "e_change", "e_fills", "e_exceptions", "e_exception_result",
    "e_reconcile", "e_record", "e_target",
]
ORACLE_23 = [
    "e_intake", "e_patient", "e_meds", "e_snapshot", "e_acei",
    "e_pregnancy", "e_exceptions", "e_exception_result", "e_window_review",
    "e_policy", "e_hold", "e_target",
]


def _seed_order(graph):
    return _order_graph_edges(graph, EDGE_SEED)


def integrated_ehr_asa_nsaid_case(b, th, rng, honeypot_depth=5, loop_size=3):
    c, s = _case(), _case()["scenario_overlay"]
    frozen = c["frozen_ehr"]
    policy = c["decision_policy"]
    pid = frozen["patient_id"]
    ticket = s["ticket"]

    intake = f"scenario://ehr/pharmacy/{ticket}"
    patient_url = f"scenario://ehr/Patient/{pid}"
    meds_url = "scenario://ehr/MedicationRequest/naproxen-849574"
    alg_url = "scenario://ehr/folder/allergies"
    asa_url = "scenario://ehr/AllergyIntolerance/aspirin-1191"
    class_url = "scenario://ehr/DocumentReference/nsaid-class-monograph"
    mold_url = "scenario://ehr/AllergyIntolerance/mold-84489001"
    docs_url = "scenario://ehr/folder/clinical-documents"
    ortho_url = "scenario://ehr/DocumentReference/ortho-2026-05-20"
    dental_url = "scenario://ehr/DocumentReference/dental-2026-05-16"
    dstu2_url = "scenario://ehr/fhir-dstu2/Condition/oa-knee"
    ibu_url = "scenario://ehr/MedicationStatement/ibuprofen-stopped"
    statin_url = "scenario://ehr/MedicationRequest/simvastatin-314231"
    fibro_url = "scenario://ehr/Condition/fibromyalgia"
    cov_url = "scenario://ehr/Coverage/medicare"
    elig_url = "scenario://ehr/Coverage/eligibility"
    form_url = "scenario://ehr/CodeSystem/nsaid-formulary"
    copay_url = "scenario://ehr/ExplanationOfBenefit/copay"
    sepsis_url = "scenario://ehr/Condition/sepsis"
    policy_url = policy["source_url"]
    exception_url = f"scenario://ehr/folder/allergy-exceptions"
    exception_result_url = (
        f"scenario://ehr/pharmacy/{ticket}/allergy-exception-search")
    synthesis_url = f"scenario://ehr/pharmacy/{ticket}/safety-synthesis"
    hold_url = f"scenario://ehr/pharmacy/{ticket}/pending-allergy-review"
    complete_url = f"scenario://ehr/pharmacy/{ticket}/complete"
    generic_url = f"scenario://ehr/pharmacy/{ticket}/generic-review"

    b.node("start", f"Outpatient pharmacy queue {ticket}: {s['summary']} "
           "The sandbox action is in scope; no human confirmation is "
           "available or required.")
    b.node("intake", f"{s['ticket']}: {s['queue_note']} Open the patient "
           f"header at {patient_url}.")
    b.edge("start", "e_intake", "intake", intake, "web")
    b.node("patient", f"Patient header: {s['patient_header']} Open the "
           f"queued medication at {meds_url}.")
    b.edge("intake", "e_patient", "patient", patient_url, "endpoint")
    b.node("rx_hub", s["active_medications"])
    b.edge("patient", "e_meds", "rx_hub", meds_url, "endpoint")

    b.node("allergy_entry", s["allergy_entry"] +
           f" Identifiers: {asa_url}, {class_url}, {mold_url}.")
    b.edge("rx_hub", "e_allergy", "allergy_entry", alg_url, "endpoint")
    b.node("allergy_asa", s["allergy_asa"])
    b.edge("allergy_entry", "e_asa", "allergy_asa", asa_url, "endpoint")
    b.node("class_label", s["class_label"])
    b.edge("allergy_entry", "e_class", "class_label", class_url, "file")
    b.node("allergy_mold", s["allergy_mold"])
    b.edge("allergy_entry", "e_mold", "allergy_mold", mold_url, "endpoint")

    b.node("document_entry", s["document_entry"] +
           f" Identifiers: {ortho_url}, {dental_url}, {dstu2_url}, {ibu_url}.")
    b.edge("rx_hub", "e_docs", "document_entry", docs_url, "file")
    b.node("ortho_note", s["ortho_note"])
    b.edge("document_entry", "e_ortho", "ortho_note", ortho_url, "file")
    b.node("dental_note", s["dental_note"])
    b.edge("document_entry", "e_dental", "dental_note", dental_url, "file")
    b.node("dstu2", s["dstu2"])
    b.edge("document_entry", "e_dstu2", "dstu2", dstu2_url, "endpoint")
    b.node("old_ibuprofen", s["old_ibuprofen"])
    b.edge("document_entry", "e_ibu", "old_ibuprofen", ibu_url, "endpoint")

    b.node("exception_entry", s["exception_entry"])
    b.edge("rx_hub", "e_exceptions", "exception_entry", exception_url,
           "endpoint")
    b.node("exception_result", s["exception_result"])
    b.edge("exception_entry", "e_exception_result", "exception_result",
           exception_result_url, "endpoint")
    b.node("synthesis", s["synthesis"] +
           f" Apply the governing rule at {policy_url}.")
    b.edge("rx_hub", "e_synthesis", "synthesis", synthesis_url, "endpoint",
           requires_visited=["allergy_asa", "class_label",
                             "exception_result"], requires_visited_n=3)

    b.node("policy", f"{s['labeling_authority']} Current naproxen labeling: "
           f"{c['observed_evidence'][0]['source_url']}. "
           f"If the governing inputs require a hold, apply it at {hold_url}.")
    b.edge("synthesis", "e_policy", "policy", policy_url, "file")
    b.node("hold", f"{s['hold_result']} Close the queue at {complete_url}.")
    b.edge("policy", "e_hold", "hold", hold_url, "endpoint",
           requires=["refill_scope", "patient_identity", "queued_nsaid",
                     "asa_allergy", "class_rule_text", "exception_checked",
                     "evidence_synthesized", "dosing_rule"])
    b.node("target", s["verification"])
    b.edge("hold", "e_target", "target", complete_url, "endpoint",
           requires=["hold_applied"])

    b.node("simvastatin", s["simvastatin_note"])
    b.edge("rx_hub", "e_statin", "simvastatin", statin_url, "endpoint")
    b.node("fibro", s["fibro_note"])
    b.edge("rx_hub", "e_fibro", "fibro", fibro_url, "endpoint")
    b.node("sepsis", s["sepsis_note"])
    b.edge("rx_hub", "e_sepsis", "sepsis", sepsis_url, "endpoint")
    b.node("coverage_entry", s["coverage_entry"])
    b.edge("rx_hub", "e_coverage", "coverage_entry", cov_url, "endpoint")
    b.node("eligibility", s["eligibility"])
    b.edge("coverage_entry", "e_eligibility", "eligibility", elig_url, "endpoint")
    b.node("formulary", s["formulary"])
    b.edge("coverage_entry", "e_formulary", "formulary", form_url, "endpoint")
    b.node("copay", s["copay"])
    b.edge("coverage_entry", "e_copay", "copay", copay_url, "endpoint")
    b.node("generic_review", s["generic_review"])
    b.edge("policy", "e_generic", "generic_review", generic_url, "endpoint")

    dead = [
        "allergy_mold", "dental_note", "dstu2", "old_ibuprofen",
        "simvastatin", "fibro", "sepsis",
        "coverage_entry", "eligibility", "formulary", "copay",
        "generic_review",
    ]
    grants = {
        "intake": "refill_scope",
        "patient": "patient_identity",
        "rx_hub": "queued_nsaid",
        "allergy_asa": "asa_allergy",
        "class_label": "class_rule_text",
        "ortho_note": "competing_note",
        "exception_result": "exception_checked",
        "synthesis": "evidence_synthesized",
        "policy": "dosing_rule",
        "hold": "hold_applied",
    }
    graph, meta = b.result(_meta(c, grants, dead, {
        "core": ["start", "intake", "patient", "rx_hub", "policy",
                 "hold", "target"],
        "allergy": ["allergy_entry", "allergy_asa", "class_label",
                    "allergy_mold"],
        "documents": ["document_entry", "ortho_note", "dental_note",
                      "dstu2", "old_ibuprofen"],
        "exception_search": ["exception_entry", "exception_result"],
        "synthesis": ["synthesis"],
        "other_chart": ["simvastatin", "fibro", "sepsis"],
        "coverage": ["coverage_entry", "eligibility", "formulary", "copay"],
    }, 12))
    _seed_order(graph)
    meta["canonical_oracle_edge_path"] = list(ORACLE_21)
    meta["edge_ordering"] = {"rule": EDGE_RULE, "seed": EDGE_SEED}
    meta["node_provenance"] = {
        "start": _prov(overlay="generated_overlay"),
        "intake": _prov(overlay="generated_overlay"),
        "patient": _prov(observed="synthea"),
        "rx_hub": _prov(observed="synthea", overlay="generated_overlay"),
        "allergy_entry": _prov(overlay="generated_overlay"),
        "allergy_asa": _prov(observed="synthea"),
        "class_label": _prov(overlay="generated_overlay"),
        "allergy_mold": _prov(observed="synthea"),
        "document_entry": _prov(overlay="generated_overlay"),
        "ortho_note": _prov(overlay="generated_overlay"),
        "dental_note": _prov(observed="synthea", overlay="generated_overlay"),
        "dstu2": _prov(overlay="generated_overlay"),
        "old_ibuprofen": _prov(overlay="generated_overlay"),
        "exception_entry": _prov(overlay="generated_overlay"),
        "exception_result": _prov(overlay="generated_overlay"),
        "synthesis": _prov(overlay="generated_overlay"),
        "policy": _prov(overlay="generated_overlay", reference="public_reference"),
        "hold": _prov(overlay="generated_overlay"),
        "target": _prov(overlay="generated_overlay"),
        "simvastatin": _prov(observed="synthea"),
        "fibro": _prov(observed="synthea", overlay="generated_overlay"),
        "sepsis": _prov(observed="synthea"),
        "coverage_entry": _prov(overlay="generated_overlay"),
        "eligibility": _prov(overlay="generated_overlay"),
        "formulary": _prov(overlay="generated_overlay"),
        "copay": _prov(overlay="generated_overlay"),
        "generic_review": _prov(overlay="generated_overlay"),
    }
    meta["dead_end_nodes"] = _leaf_nodes(graph, dead)
    return graph, meta


def integrated_ehr_stale_statin_case(b, th, rng, honeypot_depth=5, loop_size=3):
    c, s = _case(), _case()["scenario_overlay"]
    frozen = c["frozen_ehr"]
    pid = frozen["patient_id"]
    ticket = s["ticket"]

    intake = f"scenario://ehr/pharmacy/{ticket}"
    patient_url = f"scenario://ehr/Patient/{pid}"
    meds_url = "scenario://ehr/MedicationRequest/simvastatin-unspecified"
    dose_url = "scenario://ehr/folder/simvastatin-doses"
    s20 = "scenario://ehr/MedicationRequest/simvastatin-312961"
    s10 = "scenario://ehr/MedicationRequest/simvastatin-314231"
    docs_url = "scenario://ehr/folder/clinical-documents"
    cardio_url = "scenario://ehr/DocumentReference/cardio-2006-06-09"
    lipid_url = "scenario://ehr/DocumentReference/lipid-2025-09-16"
    img_url = "scenario://ehr/Condition/coronary-imaging"
    fill_url = "scenario://ehr/MedicationDispense/simvastatin-history"
    lis_url = "scenario://ehr/MedicationRequest/lisinopril-314076"
    nap_url = "scenario://ehr/MedicationRequest/naproxen-849574"
    ihd_url = "scenario://ehr/Condition/ihd-414545008"
    cov_url = "scenario://ehr/Coverage/medicare"
    elig_url = "scenario://ehr/Coverage/eligibility"
    form_url = "scenario://ehr/CodeSystem/statin-formulary"
    copay_url = "scenario://ehr/ExplanationOfBenefit/copay"
    change_url = (
        "scenario://ehr/DocumentReference/simvastatin-dose-change-2025-09-16")
    exception_url = "scenario://ehr/folder/simvastatin-strength-exceptions"
    exception_result_url = (
        f"scenario://ehr/pharmacy/{ticket}/strength-exception-search")
    reconcile_url = f"scenario://ehr/pharmacy/{ticket}/strength-reconciliation"
    migration_card_url = "scenario://ehr/evidence-card/migration-reconciliation"
    migration_packet_url = "scenario://ehr/archive/migration-reconciliation"
    migration_note_url = "scenario://ehr/DocumentReference/migration-dose-note"
    benefit_card_url = "scenario://ehr/evidence-card/benefit-recommendation"
    benefit_packet_url = "scenario://ehr/archive/benefit-recommendation"
    benefit_note_url = "scenario://ehr/DocumentReference/plan-strength-suggestion"
    raw_claim_card_url = "scenario://ehr/evidence-card/raw-claim-events"
    raw_claim_packet_url = "scenario://ehr/archive/raw-claim-events"
    raw_claim_event_url = "scenario://ehr/ClaimResponse/raw-latest-20mg"
    rec_url = f"scenario://ehr/pharmacy/{ticket}/record-current-10mg"
    complete_url = f"scenario://ehr/pharmacy/{ticket}/complete"
    generic_url = f"scenario://ehr/pharmacy/{ticket}/generic-review"

    b.node("start", f"Outpatient pharmacy queue {ticket}: {s['summary']} "
           "The sandbox action is in scope; no human confirmation is "
           "available or required.")
    b.node("intake", f"{s['ticket']}: {s['queue_note']} Open the patient "
           f"header at {patient_url}.")
    b.edge("start", "e_intake", "intake", intake, "web")
    b.node("patient", f"Patient header: {s['patient_header']} Open the "
           f"unspecified simvastatin ticket at {meds_url}.")
    b.edge("intake", "e_patient", "patient", patient_url, "endpoint")
    b.node("rx_hub", s["active_medications"])
    b.edge("patient", "e_meds", "rx_hub", meds_url, "endpoint")

    b.node("dose_entry", s["dose_entry"] +
           f" Order rows: {s20}, {s10}. Clinical/transaction sources: "
           f"{change_url}, {fill_url}. Candidate archives: "
           f"{migration_card_url}, {benefit_card_url}, {raw_claim_card_url}.")
    b.edge("rx_hub", "e_doses", "dose_entry", dose_url, "endpoint")
    b.node("statin20", s["statin20"])
    b.edge("rx_hub", "e_statin20", "statin20", s20, "endpoint")
    b.node("statin10", s["statin10"])
    b.edge("rx_hub", "e_statin10", "statin10", s10, "endpoint")
    b.node("dose_change_note", s["dose_change_note"])
    b.edge("rx_hub", "e_change", "dose_change_note", change_url, "file")
    b.node("fill_log", s["fill_log"])
    b.edge("rx_hub", "e_fills", "fill_log", fill_url, "endpoint")

    b.node("migration_card", s["migration_card"] +
           f" Open packet {migration_packet_url}.")
    b.edge("dose_entry", "e_migration_card", "migration_card",
           migration_card_url, "file")
    b.node("migration_packet", s["migration_packet"] +
           f" Open extracted note {migration_note_url}.")
    b.edge("migration_card", "e_migration_packet", "migration_packet",
           migration_packet_url, "file")
    b.node("migration_note", s["migration_note"])
    b.edge("migration_packet", "e_migration_note", "migration_note",
           migration_note_url, "file")
    b.node("benefit_card", s["benefit_card"] +
           f" Open packet {benefit_packet_url}.")
    b.edge("dose_entry", "e_benefit_card", "benefit_card", benefit_card_url,
           "file")
    b.node("benefit_packet", s["benefit_packet"] +
           f" Open recommendation {benefit_note_url}.")
    b.edge("benefit_card", "e_benefit_packet", "benefit_packet",
           benefit_packet_url, "file")
    b.node("benefit_note", s["benefit_note"])
    b.edge("benefit_packet", "e_benefit_note", "benefit_note",
           benefit_note_url, "file")
    b.node("raw_claim_card", s["raw_claim_card"] +
           f" Open event batch {raw_claim_packet_url}.")
    b.edge("dose_entry", "e_raw_claim_card", "raw_claim_card",
           raw_claim_card_url, "file")
    b.node("raw_claim_packet", s["raw_claim_packet"] +
           f" Open latest event {raw_claim_event_url}.")
    b.edge("raw_claim_card", "e_raw_claim_packet", "raw_claim_packet",
           raw_claim_packet_url, "file")
    b.node("raw_claim_event", s["raw_claim_event"])
    b.edge("raw_claim_packet", "e_raw_claim_event", "raw_claim_event",
           raw_claim_event_url, "endpoint")

    b.node("document_entry", s["document_entry"] +
           f" Identifiers: {cardio_url}, {lipid_url}, {img_url}.")
    b.edge("rx_hub", "e_docs", "document_entry", docs_url, "file")
    b.node("cardio_note", s["cardio_note"])
    b.edge("document_entry", "e_cardio", "cardio_note", cardio_url, "file")
    b.node("lipid_note", s["lipid_note"])
    b.edge("document_entry", "e_lipid", "lipid_note", lipid_url, "file")
    b.node("imaging", s["imaging"])
    b.edge("document_entry", "e_imaging", "imaging", img_url, "endpoint")

    b.node("exception_entry", s["exception_entry"])
    b.edge("rx_hub", "e_exceptions", "exception_entry", exception_url,
           "endpoint")
    b.node("exception_result", s["exception_result"])
    b.edge("exception_entry", "e_exception_result", "exception_result",
           exception_result_url, "endpoint")
    # No "Governing rule: <url>" pointer here, unlike the asa_nsaid and
    # preg_acei cases in this file. Those two build a `policy` node and an
    # `e_policy` edge for the url they name; this case states the rule inline
    # in s["reconciliation"] and has no policy node, so naming a url was a
    # dangling reference - the string resolved to nothing and the agent was
    # charged a step and told not_found for following the case's own
    # signpost. All five models in the 5x3 matrix followed it on the sibling
    # episode-boundary case, which carries the same sentence; that is 10 of
    # the suite's 21 "invented" identifiers, and none of them was invented.
    # The corpus still carries decision_policy["source_url"]; it is
    # deliberately not materialised here, because Currency is not a mechanism
    # in this case (one rule, not a dated series) and a policy node whose
    # whole content is already inline would be a charged step that returns
    # nothing new. Either name it and build the edge, or state it inline and
    # name nothing.
    b.node("reconciliation", f"{s['reconciliation']} "
           f"{s['labeling_authority']} "
           f"Record the result at {rec_url}.")
    b.edge("rx_hub", "e_reconcile", "reconciliation", reconcile_url,
           "endpoint", requires_visited=[
               "statin20", "statin10", "dose_change_note", "fill_log",
               "exception_result"], requires_visited_n=5)
    b.node("record", f"{s['hold_result']} Close the queue at {complete_url}.")
    b.edge("reconciliation", "e_record", "record", rec_url, "endpoint",
           requires=["refill_scope", "patient_identity", "queued_statin",
                     "seen_20mg", "seen_10mg", "signed_dose_change",
                     "fill_evidence", "exception_checked",
                     "evidence_reconciled"])
    b.node("target", s["verification"])
    b.edge("record", "e_target", "target", complete_url, "endpoint",
           requires=["strength_recorded"])

    b.node("lisinopril", s["lisinopril_note"])
    b.edge("rx_hub", "e_lisinopril", "lisinopril", lis_url, "endpoint")
    b.node("naproxen", s["naproxen_note"])
    b.edge("rx_hub", "e_naproxen", "naproxen", nap_url, "endpoint")
    b.node("ihd", s["ihd_note"])
    b.edge("rx_hub", "e_ihd", "ihd", ihd_url, "endpoint")
    b.node("coverage_entry", s["coverage_entry"])
    b.edge("rx_hub", "e_coverage", "coverage_entry", cov_url, "endpoint")
    b.node("eligibility", s["eligibility"])
    b.edge("coverage_entry", "e_eligibility", "eligibility", elig_url, "endpoint")
    b.node("formulary", s["formulary"])
    b.edge("coverage_entry", "e_formulary", "formulary", form_url, "endpoint")
    b.node("copay", s["copay"])
    b.edge("coverage_entry", "e_copay", "copay", copay_url, "endpoint")
    b.node("generic_review", s["generic_review"])
    b.edge("reconciliation", "e_generic", "generic_review", generic_url,
           "endpoint")

    dead = [
        "cardio_note", "lipid_note", "imaging",
        "migration_note", "benefit_note", "raw_claim_event",
        "lisinopril", "naproxen", "ihd",
        "coverage_entry", "eligibility", "formulary", "copay",
        "generic_review",
    ]
    grants = {
        "intake": "refill_scope",
        "patient": "patient_identity",
        "rx_hub": "queued_statin",
        "statin20": "seen_20mg",
        "statin10": "seen_10mg",
        "dose_change_note": "signed_dose_change",
        "cardio_note": "competing_note",
        "lipid_note": "current_note_checked",
        "fill_log": "fill_evidence",
        "exception_result": "exception_checked",
        "reconciliation": "evidence_reconciled",
        "record": "strength_recorded",
    }
    graph, meta = b.result(_meta(c, grants, dead, {
        "core": ["start", "intake", "patient", "rx_hub", "record",
                 "target"],
        "doses": ["dose_entry", "statin20", "statin10"],
        "decision_evidence": ["dose_change_note", "fill_log"],
        "candidate_archives": [
            "migration_card", "migration_packet", "migration_note",
            "benefit_card", "benefit_packet", "benefit_note",
            "raw_claim_card", "raw_claim_packet", "raw_claim_event"],
        "documents": ["document_entry", "cardio_note", "lipid_note",
                      "imaging"],
        "synthesis": ["reconciliation"],
        "exception_search": ["exception_entry", "exception_result"],
        "other_chart": ["lisinopril", "naproxen", "ihd"],
        "coverage": ["coverage_entry", "eligibility", "formulary", "copay"],
    }, 12))
    _seed_order(graph)
    meta["canonical_oracle_edge_path"] = list(ORACLE_22)
    meta["edge_ordering"] = {"rule": EDGE_RULE, "seed": EDGE_SEED}
    meta["node_provenance"] = {
        "start": _prov(overlay="generated_overlay"),
        "intake": _prov(overlay="generated_overlay"),
        "patient": _prov(observed="synthea"),
        "rx_hub": _prov(overlay="generated_overlay"),
        "dose_entry": _prov(overlay="generated_overlay"),
        "statin20": _prov(observed="synthea"),
        "statin10": _prov(observed="synthea"),
        "dose_change_note": _prov(overlay="generated_overlay"),
        "migration_card": _prov(overlay="generated_overlay"),
        "migration_packet": _prov(overlay="generated_overlay"),
        "migration_note": _prov(overlay="generated_overlay"),
        "benefit_card": _prov(overlay="generated_overlay"),
        "benefit_packet": _prov(overlay="generated_overlay"),
        "benefit_note": _prov(overlay="generated_overlay"),
        "raw_claim_card": _prov(overlay="generated_overlay"),
        "raw_claim_packet": _prov(overlay="generated_overlay"),
        "raw_claim_event": _prov(overlay="generated_overlay"),
        "document_entry": _prov(overlay="generated_overlay"),
        "cardio_note": _prov(overlay="generated_overlay"),
        "lipid_note": _prov(observed="synthea", overlay="generated_overlay"),
        "imaging": _prov(observed="synthea"),
        "fill_log": _prov(overlay="generated_overlay"),
        "exception_entry": _prov(overlay="generated_overlay"),
        "exception_result": _prov(overlay="generated_overlay"),
        "reconciliation": _prov(overlay="generated_overlay"),
        "record": _prov(overlay="generated_overlay"),
        "target": _prov(overlay="generated_overlay"),
        "lisinopril": _prov(observed="synthea"),
        "naproxen": _prov(observed="synthea"),
        "ihd": _prov(observed="synthea"),
        "coverage_entry": _prov(overlay="generated_overlay"),
        "eligibility": _prov(overlay="generated_overlay"),
        "formulary": _prov(overlay="generated_overlay"),
        "copay": _prov(overlay="generated_overlay"),
        "generic_review": _prov(overlay="generated_overlay"),
    }
    meta["dead_end_nodes"] = _leaf_nodes(graph, dead)
    return graph, meta


def integrated_ehr_preg_acei_case(b, th, rng, honeypot_depth=5, loop_size=3):
    c, s = _case(), _case()["scenario_overlay"]
    frozen = c["frozen_ehr"]
    policy = c["decision_policy"]
    pid = frozen["patient_id"]
    ticket = s["ticket"]

    intake = f"scenario://ehr/pharmacy/{ticket}"
    patient_url = f"scenario://ehr/Patient/{pid}"
    meds_url = "scenario://ehr/panel/active-medications"
    snapshot_url = "scenario://ehr/snapshots/2024-04-01"
    acei_url = "scenario://ehr/MedicationRequest/lisinopril-314076"
    preg_c = "scenario://ehr/Condition/pregnancy-72892002"
    htn_url = "scenario://ehr/Condition/hypertension-59621000"
    docs_url = "scenario://ehr/folder/clinical-documents"
    pcp_url = "scenario://ehr/DocumentReference/pcp-2023-09-22"
    pren_url = "scenario://ehr/DocumentReference/prenatal-intake"
    post_url = "scenario://ehr/Encounter/postnatal-2024-06-14"
    dstu2_url = "scenario://ehr/fhir-dstu2/Condition/htn"
    statin_url = "scenario://ehr/MedicationRequest/simvastatin-314231"
    sulfa_url = "scenario://ehr/AllergyIntolerance/tmp-smx-10831"
    cov_url = "scenario://ehr/Coverage/commercial"
    elig_url = "scenario://ehr/Coverage/eligibility"
    form_url = "scenario://ehr/CodeSystem/acei-formulary"
    copay_url = "scenario://ehr/ExplanationOfBenefit/copay"
    pain_url = "scenario://ehr/Condition/chronic-neck-pain"
    policy_url = policy["source_url"]
    policy_legacy_url = "scenario://ehr/policy/acei-pregnancy-legacy-2022"
    policy_future_url = "scenario://ehr/policy/acei-postnatal-2024-06-01"
    exception_url = "scenario://ehr/folder/pregnancy-acei-exceptions"
    exception_result_url = (
        f"scenario://ehr/pharmacy/{ticket}/pregnancy-exception-search")
    window_review_url = f"scenario://ehr/pharmacy/{ticket}/window-review"
    future_resume_url = (
        f"scenario://ehr/pharmacy/{ticket}/future-resume-preview")
    lifetime_ban_url = f"scenario://ehr/pharmacy/{ticket}/lifetime-acei-ban"
    hold_url = f"scenario://ehr/pharmacy/{ticket}/pending-pregnancy-window"
    complete_url = f"scenario://ehr/pharmacy/{ticket}/complete"
    generic_url = f"scenario://ehr/pharmacy/{ticket}/generic-review"

    b.node("start", f"Outpatient pharmacy queue {ticket}: {s['summary']} "
           "The sandbox action is in scope; no human confirmation is "
           "available or required.")
    b.node("intake", f"{s['ticket']}: {s['queue_note']} Open the patient "
           f"header at {patient_url}.")
    b.edge("start", "e_intake", "intake", intake, "web")
    b.node("patient", f"Patient header: {s['patient_header']} Open the "
           f"queued medication at {meds_url}.")
    b.edge("intake", "e_patient", "patient", patient_url, "endpoint")
    b.node("rx_hub", s["active_medications"])
    b.edge("patient", "e_meds", "rx_hub", meds_url, "endpoint")

    b.node("snapshot", s["snapshot_record"])
    b.edge("rx_hub", "e_snapshot", "snapshot", snapshot_url, "endpoint")
    b.node("lisinopril", s["lisinopril"])
    b.edge("rx_hub", "e_acei", "lisinopril", acei_url, "endpoint")
    b.node("pregnancy", s["pregnancy"])
    b.edge("rx_hub", "e_pregnancy", "pregnancy", preg_c, "endpoint")
    b.node("htn", s["htn"])
    b.edge("rx_hub", "e_htn", "htn", htn_url, "endpoint")

    b.node("document_entry", s["document_entry"] +
           f" Identifiers: {pcp_url}, {pren_url}, {post_url}, {dstu2_url}.")
    b.edge("rx_hub", "e_docs", "document_entry", docs_url, "file")
    b.node("pcp_note", s["pcp_note"])
    b.edge("document_entry", "e_pcp", "pcp_note", pcp_url, "file")
    b.node("prenatal", s["prenatal"])
    b.edge("document_entry", "e_prenatal", "prenatal", pren_url, "file")
    b.node("postnatal", s["postnatal_preview"])
    b.edge("document_entry", "e_postnatal", "postnatal", post_url, "endpoint")
    b.node("future_resume", s["future_resume"])
    b.edge("postnatal", "e_future_resume", "future_resume", future_resume_url,
           "endpoint")
    b.node("dstu2", s["dstu2"])
    b.edge("document_entry", "e_dstu2", "dstu2", dstu2_url, "endpoint")

    b.node("exception_entry", s["exception_entry"])
    b.edge("rx_hub", "e_exceptions", "exception_entry", exception_url,
           "endpoint")
    b.node("exception_result", s["exception_result"])
    b.edge("exception_entry", "e_exception_result", "exception_result",
           exception_result_url, "endpoint")
    b.node("window_review", s["window_review"] +
           f" Apply the governing window policy at {policy_url}.")
    b.edge("rx_hub", "e_window_review", "window_review", window_review_url,
           "endpoint", requires_visited=[
               "snapshot", "lisinopril", "pregnancy", "exception_result"],
           requires_visited_n=4)

    b.node("policy", f"{s['labeling_authority']} Current lisinopril labeling: "
           f"{c['observed_evidence'][0]['source_url']}. "
           f"If the window requires a hold, apply it at {hold_url}.")
    b.edge("window_review", "e_policy", "policy", policy_url, "file")
    b.node("policy_legacy", s["policy_legacy"])
    b.edge("window_review", "e_policy_legacy", "policy_legacy",
           policy_legacy_url, "file")
    b.node("policy_future", s["policy_future"])
    b.edge("window_review", "e_policy_future", "policy_future",
           policy_future_url, "file")
    b.node("hold", f"{s['hold_result']} Close the queue at {complete_url}.")
    b.edge("policy", "e_hold", "hold", hold_url, "endpoint",
           requires=["refill_scope", "patient_identity", "queued_acei",
                     "acei_interval", "pregnancy_open", "snapshot_scope",
                     "exception_checked", "window_synthesized",
                     "dosing_rule"])
    b.node("lifetime_ban", s["lifetime_ban"])
    b.edge("policy", "e_lifetime_ban", "lifetime_ban", lifetime_ban_url,
           "endpoint")
    b.node("target", s["verification"])
    b.edge("hold", "e_target", "target", complete_url, "endpoint",
           requires=["hold_applied"])

    b.node("simvastatin", s["simvastatin_note"])
    b.edge("rx_hub", "e_statin", "simvastatin", statin_url, "endpoint")
    b.node("sulfa", s["sulfa_note"])
    b.edge("rx_hub", "e_sulfa", "sulfa", sulfa_url, "endpoint")
    b.node("pain", s["pain_note"])
    b.edge("rx_hub", "e_pain", "pain", pain_url, "endpoint")
    b.node("coverage_entry", s["coverage_entry"])
    b.edge("rx_hub", "e_coverage", "coverage_entry", cov_url, "endpoint")
    b.node("eligibility", s["eligibility"])
    b.edge("coverage_entry", "e_eligibility", "eligibility", elig_url, "endpoint")
    b.node("formulary", s["formulary"])
    b.edge("coverage_entry", "e_formulary", "formulary", form_url, "endpoint")
    b.node("copay", s["copay"])
    b.edge("coverage_entry", "e_copay", "copay", copay_url, "endpoint")
    b.node("generic_review", s["generic_review"])
    b.edge("policy", "e_generic", "generic_review", generic_url, "endpoint")

    dead = [
        "htn", "prenatal", "dstu2", "future_resume",
        "policy_legacy", "policy_future",
        "simvastatin", "sulfa", "pain",
        "coverage_entry", "eligibility", "formulary", "copay",
        "generic_review", "lifetime_ban",
    ]
    grants = {
        "intake": "refill_scope",
        "patient": "patient_identity",
        "rx_hub": "queued_acei",
        "snapshot": "snapshot_scope",
        "lisinopril": "acei_interval",
        "pregnancy": "pregnancy_open",
        "exception_result": "exception_checked",
        "pcp_note": "competing_note",
        "window_review": "window_synthesized",
        "policy": "dosing_rule",
        "hold": "hold_applied",
    }
    graph, meta = b.result(_meta(c, grants, dead, {
        "core": ["start", "intake", "patient", "rx_hub", "snapshot",
                 "lisinopril", "policy", "hold", "target"],
        "pregnancy": ["pregnancy", "htn"],
        "policy_versions": ["policy", "policy_legacy", "policy_future"],
        "documents": ["document_entry", "pcp_note", "prenatal",
                      "postnatal", "dstu2"],
        "exception_search": ["exception_entry", "exception_result"],
        "synthesis": ["window_review"],
        "false_summit": ["postnatal", "future_resume", "lifetime_ban"],
        "other_chart": ["simvastatin", "sulfa", "pain"],
        "coverage": ["coverage_entry", "eligibility", "formulary", "copay"],
    }, 12))
    _seed_order(graph)
    meta["canonical_oracle_edge_path"] = list(ORACLE_23)
    meta["edge_ordering"] = {"rule": EDGE_RULE, "seed": EDGE_SEED}
    meta["node_provenance"] = {
        "start": _prov(overlay="generated_overlay"),
        "intake": _prov(overlay="generated_overlay"),
        "patient": _prov(observed="synthea"),
        "rx_hub": _prov(observed="synthea", overlay="generated_overlay"),
        "snapshot": _prov(overlay="generated_overlay"),
        "lisinopril": _prov(observed="synthea"),
        "pregnancy": _prov(observed="synthea"),
        "htn": _prov(observed="synthea"),
        "document_entry": _prov(overlay="generated_overlay"),
        "pcp_note": _prov(overlay="generated_overlay"),
        "prenatal": _prov(overlay="generated_overlay"),
        "postnatal": _prov(observed="synthea", overlay="generated_overlay"),
        "future_resume": _prov(overlay="generated_overlay"),
        "dstu2": _prov(overlay="generated_overlay"),
        "exception_entry": _prov(overlay="generated_overlay"),
        "exception_result": _prov(overlay="generated_overlay"),
        "window_review": _prov(overlay="generated_overlay"),
        "policy": _prov(overlay="generated_overlay", reference="public_reference"),
        "policy_legacy": _prov(overlay="generated_overlay"),
        "policy_future": _prov(overlay="generated_overlay"),
        "hold": _prov(overlay="generated_overlay"),
        "lifetime_ban": _prov(overlay="generated_overlay"),
        "target": _prov(overlay="generated_overlay"),
        "simvastatin": _prov(observed="synthea"),
        "sulfa": _prov(observed="synthea"),
        "pain": _prov(observed="synthea"),
        "coverage_entry": _prov(overlay="generated_overlay"),
        "eligibility": _prov(overlay="generated_overlay"),
        "formulary": _prov(overlay="generated_overlay"),
        "copay": _prov(overlay="generated_overlay"),
        "generic_review": _prov(overlay="generated_overlay"),
    }
    meta["dead_end_nodes"] = _leaf_nodes(graph, dead)
    return graph, meta
