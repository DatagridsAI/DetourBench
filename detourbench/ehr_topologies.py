#!/usr/bin/env python3
"""Corpus-backed EHR Integrated Tasks built from frozen Synthea charts."""

import hashlib

EHR_CORPUS = None

WARFARIN_EDGE_ORDER_SEED = 3306
WARFARIN_EDGE_ORDER_RULE = "sha256(seed:identifier) hex ascending"
WARFARIN_CANONICAL_ORACLE = [
    "e_intake", "e_patient", "e_meds", "e_inr_clinic", "e_inr_ed",
    "e_afib", "e_docs", "e_precedence", "e_policy", "e_escalate",
    "e_target",
]

OXYCODONE_EDGE_ORDER_SEED = 4611
OXYCODONE_EDGE_ORDER_RULE = "sha256(seed:identifier) hex ascending"
OXYCODONE_CANONICAL_ORACLE = [
    "e_intake", "e_patient", "e_meds", "e_fibro", "e_snapshot",
    "e_pdmp", "e_agreement", "e_policy_folder", "e_policy_2026",
    "e_hold", "e_target",
]
OXYCODONE_LONG_SUCCESS = [
    "e_intake", "e_patient", "e_meds", "e_fibro", "e_history",
    "e_y2023", "e_y2024", "e_cii_continuity",
    "e_review_due", "e_policy_folder", "e_policy_2026", "e_hold",
    "e_target",
]


VARIANT_TO_TOPOLOGY = {
    "ehr_source_precedence": "integrated_ehr_metformin_egfr_case",
    "ehr_provenance_refill": "integrated_ehr_hctz_provenance_case",
    "ehr_inr_conflict": "integrated_ehr_warfarin_inr_case",
    "ehr_controlled_refill": "integrated_ehr_oxycodone_apap_case",
}


def _case():
    if EHR_CORPUS is None:
        raise RuntimeError("ehr topology needs --ehr-corpus")
    return EHR_CORPUS


def supported_topologies(corpus):
    topology = VARIANT_TO_TOPOLOGY.get(corpus.get("integrated_variant"))
    return [topology] if topology else []


def _meta(c, grants, dead, regions, informed_lower_bound, **extra):
    payload = {
        "start": "start",
        "target": "target",
        "token_grants": grants,
        "requirement_labels": {
            key: value.replace("_", " ") for key, value in {
                token: token for token in set(
                    item for grant in grants.values()
                    for item in ([grant] if isinstance(grant, str) else grant)
                )
            }.items()
        },
        "dead_end_nodes": dead,
        "mechanism_regions": regions,
        "informed_lower_bound": informed_lower_bound,
        "corpus_case_id": c["case_id"],
        "evidence_cluster_id": c["evidence_cluster_id"],
        "source_kinds": ["synthea frozen chart", "public labeling",
                         "generated scenario overlay"],
        "theme_orthogonal": False,
    }
    payload.update(extra)
    return payload


def _edge_order_key(identifier, seed=WARFARIN_EDGE_ORDER_SEED):
    return hashlib.sha256(f"{seed}:{identifier}".encode("utf-8")).hexdigest()


def _order_graph_edges(graph, seed=WARFARIN_EDGE_ORDER_SEED):
    """Deterministic sibling order that does not put a preferred route first."""
    for node, edges in graph["edges"].items():
        if len(edges) > 1:
            graph["edges"][node] = sorted(
                edges, key=lambda e: _edge_order_key(e["desc"], seed))
    return graph


def _leaf_nodes(graph, candidates):
    return [n for n in candidates if not graph["edges"].get(n)]


def integrated_ehr_metformin_egfr_case(
        b, th, rng, honeypot_depth=5, loop_size=3):
    """Pharmacy refill: Observation effective time outranks C-CDA export time."""
    c, s = _case(), _case()["scenario_overlay"]
    frozen = c["frozen_ehr"]
    policy = c["decision_policy"]

    b.node("start", f"Outpatient pharmacy queue {s['ticket']}: {s['summary']} "
           "The sandbox action is in scope; no human confirmation is "
           "available or required.")
    patient_url = f"scenario://ehr/Patient/{frozen['patient_id']}"
    meds_url = "scenario://ehr/MedicationRequest/metformin-860975"
    b.node("queue", f"{s['ticket']}: {s['queue_note']} Open the patient "
           f"header at {patient_url} before reviewing medications.")
    b.edge("start", "e_queue", "queue",
           f"scenario://ehr/pharmacy/{s['ticket']}", "web")

    b.node("patient", f"Patient header: {s['patient_header']} Open the active "
           f"medication list at {meds_url}; do not dispense from identity "
           "data alone.")
    b.edge("queue", "e_patient", "patient", patient_url, "endpoint")

    ccda_url = "scenario://ehr/DocumentReference/continuity-of-care"
    renal_url = "scenario://ehr/Observation/renal-laboratory"
    policy_url = policy["source_url"]
    hold_url = "scenario://ehr/MedicationRequest/metformin-860975/hold"
    complete_url = f"scenario://ehr/pharmacy/{s['ticket']}/complete"
    b.node("meds", s["active_medications"])
    b.edge("patient", "e_meds", "meds", meds_url, "endpoint")

    b.node("ccda_doc", s["ccda_document"])
    b.edge("meds", "e_ccda", "ccda_doc", ccda_url, "file")

    b.node("r4_observation", s["r4_observation"])
    b.edge("meds", "e_r4", "r4_observation", renal_url, "endpoint")

    b.node("policy", f"{s['labeling_authority']} "
           f"Public labeling records the same eGFR threshold "
           f"({c['observed_evidence'][0]['source_url']}). "
           f"If the governing Observation requires a hold, apply it at "
           f"{hold_url}.")
    b.edge("meds", "e_policy", "policy", policy_url, "file",
           requires_visited=["ccda_doc", "r4_observation"],
           requires_visited_n=2)

    b.node("hold", f"Hold applied: {s['hold_result']} Close the pharmacy "
           f"queue at {complete_url} after the hold is recorded.")
    b.edge("policy", "e_hold", "hold", hold_url, "endpoint")

    b.node("target", f"Queue closed: {s['verification']}")
    b.edge("hold", "e_verify", "target", complete_url, "endpoint",
           requires=["refill_scope", "patient_identity", "active_metformin",
                     "renal_observation", "source_precedence", "hold_applied"])

    distractors = [
        ("a1c", s["a1c_trend"],
         "scenario://ehr/Observation/hemoglobin-a1c-4548-4"),
        ("coverage", s["coverage_note"],
         "scenario://ehr/Coverage/medicare"),
        ("simvastatin", s["simvastatin_note"],
         "scenario://ehr/MedicationStatement/simvastatin-314231"),
        ("dstu2", s["dstu2_problem_list"],
         "scenario://ehr/fhir-dstu2/Condition/t2dm"),
    ]
    dead = []
    for node, desc, ident in distractors:
        b.node(node, desc)
        b.edge("meds", "e_" + node, node, ident, "endpoint")
        dead.append(node)

    b.node("renew", s["renew_as_written"])
    b.edge("meds", "e_renew", "renew",
           "scenario://ehr/MedicationRequest/metformin-860975/renew",
           "endpoint")
    dead.append("renew")

    grants = {
        "queue": "refill_scope",
        "patient": "patient_identity",
        "meds": "active_metformin",
        "r4_observation": "renal_observation",
        "policy": "source_precedence",
        "hold": "hold_applied",
        "ccda_doc": "ccda_document",
    }
    return b.result(_meta(c, grants, dead, {
        "queue": ["start", "queue", "patient", "meds"],
        "conflicting_sources": ["ccda_doc", "r4_observation"],
        "precedence": ["policy"],
        "remediation": ["hold", "target"],
        "false_summit": ["renew"],
        "plausible_distractors": [row[0] for row in distractors],
    }, 8))


def integrated_ehr_hctz_provenance_case(
        b, th, rng, honeypot_depth=5, loop_size=3):
    """40-node HCTZ refill: provenance, competing labs, recon, admin, alt plan."""
    c, s = _case(), _case()["scenario_overlay"]
    frozen = c["frozen_ehr"]
    policy = c["decision_policy"]
    pid = frozen["patient_id"]

    intake = f"scenario://ehr/pharmacy/{s['ticket']}"
    patient_url = f"scenario://ehr/Patient/{pid}"
    meds_url = "scenario://ehr/MedicationRequest/hctz-310798"
    renal_url = "scenario://ehr/panel/renal-laboratory"
    cr_url = "scenario://ehr/Observation/creatinine-38483-4"
    egfr_url = "scenario://ehr/Observation/egfr-33914-3"
    ckd_url = "scenario://ehr/Condition/ckd-stage3"
    k_url = "scenario://ehr/Observation/potassium-6298-4"
    cad_url = "scenario://ehr/panel/coronary-meds"
    anti_url = "scenario://ehr/MedicationStatement/antiplatelet-bundle"
    img_url = "scenario://ehr/ImagingStudy/heart-2024-12"
    plt_url = "scenario://ehr/Observation/platelets-777-3"
    ntg_url = "scenario://ehr/MedicationRequest/nitroglycerin-705129"
    pain_url = "scenario://ehr/panel/pain-meds"
    hc_url = "scenario://ehr/MedicationRequest/hydrocodone-856987"
    pain_dx_url = "scenario://ehr/Condition/chronic-pain"
    apap_url = "scenario://ehr/Observation/acetaminophen-ceiling"
    dm_url = "scenario://ehr/panel/diabetes"
    ins_url = "scenario://ehr/MedicationRequest/insulin-106892"
    a1c_url = "scenario://ehr/Observation/hba1c-4548-4"
    predm_url = "scenario://ehr/Condition/prediabetes"
    cov_url = "scenario://ehr/Coverage/anthem"
    elig_url = "scenario://ehr/Coverage/eligibility"
    form_url = "scenario://ehr/CodeSystem/hctz-formulary"
    copay_url = "scenario://ehr/ExplanationOfBenefit/copay"
    docs_url = "scenario://ehr/folder/clinical-documents"
    ccd_url = "scenario://ehr/DocumentReference/continuity-of-care"
    cardio_url = "scenario://ehr/DocumentReference/cardiology-medrec"
    note_url = "scenario://ehr/DocumentReference/ambulatory-note"
    dstu2_url = "scenario://ehr/fhir-dstu2/Condition/ckd"
    fills_url = "scenario://ehr/MedicationDispense/hctz-history"
    alt_url = "scenario://ehr/plan/diuretic-alternative"
    loop_url = "scenario://ehr/MedicationKnowledge/furosemide"
    ix_url = "scenario://ehr/ClinicalImpression/loop-metoprolol"
    dose_url = "scenario://ehr/plan/loop-dose-table"
    preview_url = "scenario://ehr/plan/diuretic-preview"
    policy_url = policy["source_url"]
    hold_url = "scenario://ehr/MedicationRequest/hctz-310798/hold"
    complete_url = f"scenario://ehr/pharmacy/{s['ticket']}/complete"

    b.node("start", f"Outpatient pharmacy queue {s['ticket']}: {s['summary']} "
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

    # --- renal tree (oracle: entry, creatinine, ckd; eGFR/K optional)
    b.node("renal_entry", s["renal_entry"] +
           f" Identifiers: {cr_url}, {ckd_url}, {egfr_url}, {k_url}.")
    b.edge("rx_hub", "e_renal", "renal_entry", renal_url, "endpoint")
    b.node("creatinine", s["creatinine"])
    b.edge("renal_entry", "e_creatinine", "creatinine", cr_url, "endpoint")
    b.node("ckd_stage3", s["ckd_stage"])
    b.edge("renal_entry", "e_ckd", "ckd_stage3", ckd_url, "endpoint")
    b.node("egfr", s["egfr"])
    b.edge("renal_entry", "e_egfr", "egfr", egfr_url, "endpoint")
    b.node("potassium", s["potassium"])
    b.edge("renal_entry", "e_potassium", "potassium", k_url, "endpoint")

    # --- source-conflict documents (oracle: folder then CCD)
    b.node("document_entry", s["document_entry"] +
           f" Identifiers: {ccd_url}, {cardio_url}, {note_url}, {dstu2_url}, {fills_url}.")
    b.edge("rx_hub", "e_docs", "document_entry", docs_url, "file")
    b.node("ccd", s["ccd"] + f" The thiazide-refill policy is at {policy_url}.")
    b.edge("document_entry", "e_ccd", "ccd", ccd_url, "file")
    b.node("cardio_medrec", s["cardio_medrec"])
    b.edge("document_entry", "e_cardio", "cardio_medrec", cardio_url, "file")
    b.node("ambulatory_note", s["ambulatory_note"])
    b.edge("document_entry", "e_note", "ambulatory_note", note_url, "file")
    b.node("dstu2", s["dstu2"])
    b.edge("document_entry", "e_dstu2", "dstu2", dstu2_url, "endpoint")
    b.node("fill_history", s["fill_history"])
    b.edge("document_entry", "e_fills", "fill_history", fills_url, "endpoint")

    # Policy is NOT an outgoing edge of rx_hub. It becomes visible only
    # after the continuity-of-care document is opened, and it is always
    # readable (no requires / requires_visited). Hold is revealed from
    # policy and is token-gated, so oracle never needs a locked click.
    b.node("policy", f"{s['labeling_authority']} "
           f"Public thiazide labeling: {c['observed_evidence'][0]['source_url']}. "
           f"If the governing inputs require a hold, apply it at {hold_url}.")
    b.edge("ccd", "e_policy", "policy", policy_url, "file")

    b.node("hold_hctz", f"{s['hold_result']} Close the queue at {complete_url}.")
    b.edge("policy", "e_hold", "hold_hctz", hold_url, "endpoint",
           requires=["refill_scope", "patient_identity", "queued_hctz",
                     "creatinine_result", "ckd_stage", "document_scope",
                     "dosing_rule"])
    b.node("target", s["verification"])
    b.edge("hold_hctz", "e_target", "target", complete_url, "endpoint",
           requires=["hold_applied"])

    # --- competing medication-reconciliation trees
    b.node("cad_entry", s["cad_entry"])
    b.edge("rx_hub", "e_cad", "cad_entry", cad_url, "endpoint")
    b.node("antiplatelet", s["antiplatelet"])
    b.edge("cad_entry", "e_antiplatelet", "antiplatelet", anti_url, "endpoint")
    b.node("ihd_imaging", s["ihd_imaging"])
    b.edge("cad_entry", "e_imaging", "ihd_imaging", img_url, "endpoint")
    b.node("platelets", s["platelets"])
    b.edge("cad_entry", "e_platelets", "platelets", plt_url, "endpoint")
    b.node("ntg", s["ntg"])
    b.edge("cad_entry", "e_ntg", "ntg", ntg_url, "endpoint")

    b.node("pain_entry", s["pain_entry"])
    b.edge("rx_hub", "e_pain", "pain_entry", pain_url, "endpoint")
    b.node("hydrocodone", s["hydrocodone"])
    b.edge("pain_entry", "e_hydrocodone", "hydrocodone", hc_url, "endpoint")
    b.node("pain_dx", s["pain_dx"])
    b.edge("pain_entry", "e_pain_dx", "pain_dx", pain_dx_url, "endpoint")
    b.node("apap_ceiling", s["apap_ceiling"])
    b.edge("pain_entry", "e_apap", "apap_ceiling", apap_url, "endpoint")

    b.node("dm_entry", s["dm_entry"])
    b.edge("rx_hub", "e_dm", "dm_entry", dm_url, "endpoint")
    b.node("insulin", s["insulin"])
    b.edge("dm_entry", "e_insulin", "insulin", ins_url, "endpoint")
    b.node("a1c", s["a1c"])
    b.edge("dm_entry", "e_a1c", "a1c", a1c_url, "endpoint")
    b.node("prediabetes", s["prediabetes"])
    b.edge("dm_entry", "e_prediabetes", "prediabetes", predm_url, "endpoint")

    b.node("coverage_entry", s["coverage_entry"])
    b.edge("rx_hub", "e_coverage", "coverage_entry", cov_url, "endpoint")
    b.node("eligibility", s["eligibility"])
    b.edge("coverage_entry", "e_eligibility", "eligibility", elig_url, "endpoint")
    b.node("formulary", s["formulary"])
    b.edge("coverage_entry", "e_formulary", "formulary", form_url, "endpoint")
    b.node("copay", s["copay"])
    b.edge("coverage_entry", "e_copay", "copay", copay_url, "endpoint")

    b.node("alt_entry", s["alt_entry"])
    b.edge("rx_hub", "e_alt", "alt_entry", alt_url, "file")
    b.node("loop_candidate", s["loop_candidate"])
    b.edge("alt_entry", "e_loop", "loop_candidate", loop_url, "file")
    b.node("interaction", s["interaction"])
    b.edge("alt_entry", "e_interaction", "interaction", ix_url, "endpoint")
    b.node("dose_table", s["dose_table"])
    b.edge("alt_entry", "e_dose", "dose_table", dose_url, "file")
    b.node("preview", s["preview"])
    b.edge("alt_entry", "e_preview", "preview", preview_url, "file")

    dead = [
        "egfr", "potassium",
        "cardio_medrec", "ambulatory_note", "dstu2", "fill_history",
        "cad_entry", "antiplatelet", "ihd_imaging", "platelets", "ntg",
        "pain_entry", "hydrocodone", "pain_dx", "apap_ceiling",
        "dm_entry", "insulin", "a1c", "prediabetes",
        "coverage_entry", "eligibility", "formulary", "copay",
        "alt_entry", "loop_candidate", "interaction", "dose_table", "preview",
    ]
    grants = {
        "intake": "refill_scope",
        "patient": "patient_identity",
        "rx_hub": "queued_hctz",
        "creatinine": "creatinine_result",
        "ckd_stage3": "ckd_stage",
        "ccd": "document_scope",
        "policy": "dosing_rule",
        "hold_hctz": "hold_applied",
    }
    return b.result(_meta(c, grants, dead, {
        "core": ["start", "intake", "patient", "rx_hub", "policy",
                 "hold_hctz", "target"],
        "renal_labs": ["renal_entry", "creatinine", "egfr", "ckd_stage3",
                       "potassium"],
        "cad_recon": ["cad_entry", "antiplatelet", "ihd_imaging", "platelets",
                      "ntg"],
        "pain_recon": ["pain_entry", "hydrocodone", "pain_dx", "apap_ceiling"],
        "diabetes_recon": ["dm_entry", "insulin", "a1c", "prediabetes"],
        "coverage_admin": ["coverage_entry", "eligibility", "formulary",
                           "copay"],
        "provenance_documents": ["document_entry", "ccd", "cardio_medrec",
                                 "ambulatory_note", "dstu2", "fill_history"],
        "alternative_plan": ["alt_entry", "loop_candidate", "interaction",
                             "dose_table", "preview"],
    }, 11))


def integrated_ehr_warfarin_inr_case(
        b, th, rng, honeypot_depth=5, loop_size=3):
    """40-node warfarin refill: discordant laboratory INRs, AF dual_key."""
    c, s = _case(), _case()["scenario_overlay"]
    frozen = c["frozen_ehr"]
    policy = c["decision_policy"]
    pid = frozen["patient_id"]
    ticket = s["ticket"]

    intake = f"scenario://ehr/pharmacy/{ticket}"
    patient_url = f"scenario://ehr/Patient/{pid}"
    meds_url = "scenario://ehr/MedicationRequest/warfarin-855332"
    clinic_url = "scenario://ehr/Observation/inr-clinic-6301-6"
    ed_url = "scenario://ehr/Observation/inr-ed-6301-6"
    afib_url = "scenario://ehr/Condition/cond-8f3c91ab"
    docs_url = "scenario://ehr/folder/clinical-documents"
    prec_url = "scenario://ehr/DocumentReference/anticoag-clerk-note"
    policy_url = policy["source_url"]
    july_url = "scenario://ehr/DocumentReference/anticoag-clinic-july"
    poc_url = "scenario://ehr/Observation/inr-poc-strip"
    fills_url = "scenario://ehr/MedicationDispense/warfarin-history"
    hist_url = "scenario://ehr/folder/anticoagulation-history"
    prior_url = "scenario://ehr/Observation/inr-2026-05-06"
    cardio_url = "scenario://ehr/folder/cardiovascular-context"
    range_url = "scenario://ehr/DocumentReference/inr-interval-card"
    clop_url = "scenario://ehr/MedicationRequest/clopidogrel-309362"
    cabg_url = "scenario://ehr/Condition/cabg-history"
    nstemi_url = "scenario://ehr/Condition/nstemi-2014"
    hgb_url = "scenario://ehr/Observation/hemoglobin-718-7"
    ckd_url = "scenario://ehr/Condition/ckd-stage3"
    cr_url = "scenario://ehr/Observation/creatinine-38483-4"
    cov_url = "scenario://ehr/Coverage/member-year"
    form_url = "scenario://ehr/CodeSystem/warfarin-formulary"
    copay_url = "scenario://ehr/ExplanationOfBenefit/copay"
    other_url = "scenario://ehr/panel/other-chart"
    neck_url = "scenario://ehr/Condition/chronic-neck-pain"
    dm_url = "scenario://ehr/panel/diabetes"
    a1c_url = "scenario://ehr/Observation/hba1c-4548-4"
    met_url = "scenario://ehr/MedicationRequest/metoprolol-866412"
    ntg_url = "scenario://ehr/MedicationRequest/nitroglycerin-705129"
    dstu2_url = "scenario://ehr/fhir-dstu2/problem-list-export"
    alt_url = "scenario://ehr/plan/alternative-anticoagulation"
    doac_url = "scenario://ehr/MedicationKnowledge/doac-class"
    renal_url = "scenario://ehr/plan/doac-renal-eligibility"
    ix_url = "scenario://ehr/ClinicalImpression/doac-clopidogrel"
    scope_url = "scenario://ehr/plan/alternative-anticoagulation/preview"
    coumadin_url = "scenario://ehr/MedicationStatement/coumadin-brand"
    jantoven_url = "scenario://ehr/MedicationStatement/jantoven-ed"
    rxnorm_url = "scenario://ehr/CodeSystem/rxnorm-855332"
    escalate_url = f"scenario://ehr/pharmacy/{ticket}/escalate-review"
    complete_url = f"scenario://ehr/pharmacy/{ticket}/pending-anticoag-review"

    b.node("start", f"Outpatient pharmacy queue {ticket}: {s['summary']}")
    b.node("intake", f"{ticket}: {s['queue_note']} Open the patient "
           f"header at {patient_url}.")
    b.edge("start", "e_intake", "intake", intake, "web")

    b.node("patient", f"Patient header: {s['patient_header']} Open the "
           f"queued medication at {meds_url}.")
    b.edge("intake", "e_patient", "patient", patient_url, "endpoint")

    b.node("warfarin_rx", s["active_medications"])
    b.edge("patient", "e_meds", "warfarin_rx", meds_url, "endpoint")

    b.node("inr_clinic", s["inr_clinic"])
    b.edge("warfarin_rx", "e_inr_clinic", "inr_clinic", clinic_url, "endpoint")
    b.node("inr_ed", s["inr_ed"])
    b.edge("warfarin_rx", "e_inr_ed", "inr_ed", ed_url, "endpoint")
    b.node("afib", s["afib"])
    b.edge("warfarin_rx", "e_afib", "afib", afib_url, "endpoint")

    b.node("documents", s["document_entry"])
    b.edge("warfarin_rx", "e_docs", "documents", docs_url, "file")

    b.node("precedence", s["precedence"])
    b.edge("documents", "e_precedence", "precedence", prec_url, "file")
    b.node("policy", f"{s['labeling_authority']} "
           f"Public warfarin labeling: {c['observed_evidence'][0]['source_url']}.")
    b.edge("precedence", "e_policy", "policy", policy_url, "file")

    generic_url = f"scenario://ehr/pharmacy/{ticket}/pending-clinical-review"
    b.node("generic_review", s["generic_review"])
    b.edge("policy", "e_generic_review", "generic_review", generic_url,
           "endpoint")

    b.node("review_referral", f"{s['hold_result']} Submit the handoff "
           f"record at {complete_url}.")
    b.edge("afib", "e_escalate", "review_referral", escalate_url, "endpoint",
           requires=["refill_scope", "patient_identity", "queued_warfarin",
                     "inr_clinic", "inr_ed", "conflict_noted", "afib_dx",
                     "review_policy"])
    b.node("target", s["verification"])
    b.edge("review_referral", "e_target", "target", complete_url, "endpoint",
           requires=["review_routed"])

    b.node("july_clinic_note", s["july_clinic_note"])
    b.edge("documents", "e_july", "july_clinic_note", july_url, "file")
    b.node("inr_range_reference", s["inr_range_reference"])
    b.edge("documents", "e_range", "inr_range_reference", range_url, "file")
    b.node("dstu2_export", s["dstu2_export"])
    b.edge("documents", "e_dstu2", "dstu2_export", dstu2_url, "endpoint")
    b.edge("documents", "e_coumadin_alias", "warfarin_rx", coumadin_url,
           "endpoint")
    b.edge("documents", "e_jantoven_alias", "warfarin_rx", jantoven_url,
           "endpoint")
    b.edge("documents", "e_rxnorm_alias", "warfarin_rx", rxnorm_url,
           "endpoint")

    b.node("old_anticoag_letter", s["old_anticoag_letter"])
    b.edge("warfarin_rx", "e_letter", "old_anticoag_letter", hist_url, "file")
    b.node("poc_inr", s["poc_inr"])
    b.edge("old_anticoag_letter", "e_poc", "poc_inr", poc_url, "endpoint")
    b.node("warfarin_fill_history", s["warfarin_fill_history"])
    b.edge("old_anticoag_letter", "e_fills", "warfarin_fill_history",
           fills_url, "endpoint")
    b.node("prior_inr_may", s["prior_inr_may"])
    b.edge("old_anticoag_letter", "e_prior_inr", "prior_inr_may", prior_url,
           "endpoint")

    b.node("bleed_risk_context", s["bleed_risk_context"])
    b.edge("warfarin_rx", "e_bleed", "bleed_risk_context", cardio_url,
           "endpoint")
    b.node("clopidogrel", s["clopidogrel"])
    b.edge("bleed_risk_context", "e_clopidogrel", "clopidogrel", clop_url,
           "endpoint")
    b.node("cabg_history", s["cabg_history"])
    b.edge("bleed_risk_context", "e_cabg", "cabg_history", cabg_url,
           "endpoint")
    b.node("nstemi_history", s["nstemi_history"])
    b.edge("bleed_risk_context", "e_nstemi", "nstemi_history", nstemi_url,
           "endpoint")
    b.node("hemoglobin", s["hemoglobin"])
    b.edge("bleed_risk_context", "e_hgb", "hemoglobin", hgb_url, "endpoint")
    b.node("metoprolol", s["metoprolol"])
    b.edge("bleed_risk_context", "e_metoprolol", "metoprolol", met_url,
           "endpoint")
    b.node("ntg", s["ntg"])
    b.edge("bleed_risk_context", "e_ntg", "ntg", ntg_url, "endpoint")

    b.node("ckd_stage3", s["ckd_stage3"])
    b.edge("warfarin_rx", "e_ckd", "ckd_stage3", ckd_url, "endpoint")
    b.node("creatinine", s["creatinine"])
    b.edge("ckd_stage3", "e_creatinine", "creatinine", cr_url, "endpoint")

    b.node("coverage_entry", s["coverage_entry"])
    b.edge("warfarin_rx", "e_coverage", "coverage_entry", cov_url, "endpoint")
    b.node("formulary", s["formulary"])
    b.edge("coverage_entry", "e_formulary", "formulary", form_url, "endpoint")
    b.node("copay", s["copay"])
    b.edge("coverage_entry", "e_copay", "copay", copay_url, "endpoint")

    b.node("pain_entry", s["pain_entry"])
    b.edge("warfarin_rx", "e_pain", "pain_entry", other_url, "endpoint")
    b.node("chronic_pain", s["chronic_pain"])
    b.edge("pain_entry", "e_neck", "chronic_pain", neck_url, "endpoint")
    b.node("diabetes", s["diabetes"])
    b.edge("pain_entry", "e_dm", "diabetes", dm_url, "endpoint")
    b.node("a1c", s["a1c"])
    b.edge("diabetes", "e_a1c", "a1c", a1c_url, "endpoint")

    b.node("alt_entry", s["alt_entry"])
    b.edge("warfarin_rx", "e_alt", "alt_entry", alt_url, "file")
    b.node("doac_candidate", s["doac_candidate"])
    b.edge("alt_entry", "e_doac", "doac_candidate", doac_url, "file")
    b.node("doac_renal", s["doac_renal"])
    b.edge("alt_entry", "e_doac_renal", "doac_renal", renal_url, "file")
    b.node("interaction_preview", s["interaction_preview"])
    b.edge("alt_entry", "e_doac_ix", "interaction_preview", ix_url, "endpoint")
    b.node("alt_scope_boundary", s["alt_scope_boundary"])
    b.edge("alt_entry", "e_alt_scope", "alt_scope_boundary", scope_url, "file")

    off_path = [
        "july_clinic_note", "poc_inr", "warfarin_fill_history",
        "old_anticoag_letter", "prior_inr_may", "bleed_risk_context",
        "inr_range_reference", "clopidogrel", "cabg_history",
        "nstemi_history", "hemoglobin", "metoprolol", "ntg",
        "ckd_stage3", "creatinine", "coverage_entry", "formulary", "copay",
        "pain_entry", "chronic_pain", "diabetes", "a1c", "dstu2_export",
        "alt_entry", "doac_candidate", "doac_renal", "interaction_preview",
        "alt_scope_boundary", "generic_review",
    ]
    grants = {
        "intake": "refill_scope",
        "patient": "patient_identity",
        "warfarin_rx": "queued_warfarin",
        "inr_clinic": "inr_clinic",
        "inr_ed": "inr_ed",
        "afib": "afib_dx",
        "precedence": "conflict_noted",
        "policy": "review_policy",
        "review_referral": "review_routed",
    }
    regions = {
        "core": ["start", "intake", "patient", "warfarin_rx", "documents",
                 "policy", "review_referral", "target"],
        "dual_key": ["inr_clinic", "inr_ed", "afib"],
        "conflicting_authority": ["inr_clinic", "inr_ed", "precedence"],
        "false_summit": ["july_clinic_note"],
        "alias_maze": ["warfarin_rx"],
        "anticoagulation_history": [
            "old_anticoag_letter", "poc_inr", "warfarin_fill_history",
            "prior_inr_may"],
        "cardiovascular_context": [
            "bleed_risk_context", "clopidogrel", "cabg_history",
            "nstemi_history", "hemoglobin", "metoprolol", "ntg"],
        "renal_context": ["ckd_stage3", "creatinine"],
        "administrative_context": ["coverage_entry", "formulary", "copay"],
        "other_chart": ["pain_entry", "chronic_pain", "diabetes", "a1c"],
        "alternative_anticoagulation": [
            "alt_entry", "doac_candidate", "doac_renal",
            "interaction_preview", "alt_scope_boundary"],
        "anticoag_optional": [
            "poc_inr", "warfarin_fill_history", "old_anticoag_letter",
            "prior_inr_may", "bleed_risk_context", "inr_range_reference",
            "clopidogrel", "cabg_history", "nstemi_history", "hemoglobin",
            "alt_entry", "doac_candidate", "doac_renal",
            "interaction_preview", "alt_scope_boundary"],
    }
    provenance = {
        "start": {"origin": "generated_overlay"},
        "intake": {"origin": "generated_overlay"},
        "patient": {"origin": "synthea"},
        "warfarin_rx": {"origin": "synthea"},
        "inr_clinic": {"origin": "generated_overlay"},
        "inr_ed": {"origin": "generated_overlay"},
        "afib": {"origin": "synthea"},
        "documents": {"origin": "generated_overlay"},
        "precedence": {"origin": "generated_overlay"},
        "policy": {"origin": "public_reference"},
        "review_referral": {"origin": "generated_overlay"},
        "target": {"origin": "generated_overlay"},
        "july_clinic_note": {"origin": "generated_overlay"},
        "old_anticoag_letter": {"origin": "generated_overlay"},
        "inr_range_reference": {"origin": "generated_overlay"},
        "dstu2_export": {"origin": "generated_overlay"},
        "poc_inr": {"origin": "generated_overlay"},
        "warfarin_fill_history": {"origin": "generated_overlay"},
        "prior_inr_may": {"origin": "generated_overlay"},
        "bleed_risk_context": {"origin": "generated_overlay"},
        "clopidogrel": {"origin": "synthea"},
        "cabg_history": {"origin": "synthea"},
        "nstemi_history": {"origin": "synthea"},
        "hemoglobin": {"origin": "generated_overlay"},
        "metoprolol": {"origin": "synthea"},
        "ntg": {"origin": "synthea"},
        "ckd_stage3": {"origin": "synthea"},
        "creatinine": {"origin": "synthea"},
        "coverage_entry": {"origin": "generated_overlay"},
        "formulary": {"origin": "generated_overlay"},
        "copay": {"origin": "generated_overlay"},
        "pain_entry": {"origin": "generated_overlay"},
        "chronic_pain": {"origin": "synthea"},
        "diabetes": {"origin": "synthea"},
        "a1c": {"origin": "synthea"},
        "alt_entry": {"origin": "generated_overlay"},
        "doac_candidate": {"origin": "generated_overlay"},
        "doac_renal": {"origin": "generated_overlay"},
        "interaction_preview": {"origin": "generated_overlay"},
        "alt_scope_boundary": {"origin": "generated_overlay"},
        "generic_review": {"origin": "generated_overlay"},
    }
    graph, meta = b.result(_meta(c, grants, off_path, regions, 11))
    _order_graph_edges(graph)
    meta["dead_end_nodes"] = _leaf_nodes(graph, off_path)
    meta["off_path_nodes"] = list(off_path)
    meta["canonical_oracle_edge_path"] = list(WARFARIN_CANONICAL_ORACLE)
    meta["edge_ordering"] = {
        "rule": WARFARIN_EDGE_ORDER_RULE,
        "seed": WARFARIN_EDGE_ORDER_SEED,
    }
    meta["node_provenance"] = provenance
    meta["aliased_nodes"] = ["warfarin_rx"]
    return graph, meta


def _prov(observed=None, overlay=None, reference=None):
    origins = [x for x in (observed, overlay, reference) if x]
    if reference and not observed and not overlay:
        origin = "public_reference"
    elif observed and not overlay:
        origin = "synthea"
    else:
        origin = "generated_overlay" if overlay and not observed else (
            "synthea" if observed else "generated_overlay")
    if observed and overlay:
        origin = "synthea"
    return {
        "observed_fact": observed,
        "scenario_logic": overlay,
        "reference": reference,
        "origin": origin,
    }


def integrated_ehr_oxycodone_apap_case(
        b, th, rng, honeypot_depth=5, loop_size=3):
    """Controlled-substance refill: evidence subset, policy version, two routes."""
    c, s = _case(), _case()["scenario_overlay"]
    frozen = c["frozen_ehr"]
    pid = frozen["patient_id"]
    ticket = s["ticket"]

    intake = f"scenario://ehr/pharmacy/{ticket}"
    patient_url = f"scenario://ehr/Patient/{pid}"
    meds_url = "scenario://ehr/MedicationRequest/oxycodone-apap-1049625"
    fibro_url = "scenario://ehr/Condition/cond-3a91c2e0"
    snap_url = "scenario://ehr/folder/monitoring-records"
    pdmp_url = "scenario://ehr/DocumentReference/pdmp-q3-4611"
    agr_url = "scenario://ehr/DocumentReference/csa-4611"
    apap_url = "scenario://ehr/DocumentReference/apap-existing-orders"
    filllog_url = "scenario://ehr/MedicationDispense/in-pharmacy-log"
    hist_url = "scenario://ehr/folder/combination-tablet-history"
    y2023_url = "scenario://ehr/MedicationRequest/46fcc34a-97a1-f038-c186-c441ade3e3df"
    y2024_url = "scenario://ehr/MedicationRequest/46fcc34a-97a1-f038-a98f-c658b5a74b45"
    y2025_url = "scenario://ehr/MedicationRequest/46fcc34a-97a1-f038-e42e-36415b133408"
    review_url = "scenario://ehr/Condition/46fcc34a-97a1-f038-medreview-2025"
    continuity_url = "scenario://ehr/DocumentReference/cii-continuity-4611"
    pol_folder_url = "scenario://ehr/folder/workflow-memos"
    pol_2019_url = "scenario://ehr/policy/rxq-4611/memo-20191101"
    pol_2026_url = "scenario://ehr/policy/rxq-4611/memo-20260101"
    hold_url = f"scenario://ehr/pharmacy/{ticket}/pending-controlled-medication-review"
    complete_url = f"scenario://ehr/pharmacy/{ticket}/pending-controlled-medication-review/commit"
    legacy_url = f"scenario://ehr/pharmacy/{ticket}/legacy-autofulfill"
    generic_url = f"scenario://ehr/pharmacy/{ticket}/pending-clinical-review"
    disp_url = f"scenario://ehr/pharmacy/{ticket}/dispense-preview"
    dose_url = "scenario://ehr/MedicationKnowledge/strength-table"
    dc_url = f"scenario://ehr/pharmacy/{ticket}/discontinue-preview"
    tram_url = "scenario://ehr/plan/alternative-analgesic"
    other_url = "scenario://ehr/panel/other-chart"
    dental_url = "scenario://ehr/MedicationAdministration/fluoride-1535362"
    ging_url = "scenario://ehr/Condition/gingivitis-66383009"
    unemp_url = "scenario://ehr/Condition/unemployed-73438004"
    cpain_url = "scenario://ehr/Condition/chronic-pain-82423001"
    lbp_url = "scenario://ehr/Condition/low-back-pain-278860009"
    pt_url = "scenario://ehr/CarePlan/therapy-2014"
    cov_url = "scenario://ehr/Coverage/member-year"
    copay_url = "scenario://ehr/ExplanationOfBenefit/copay"
    epi_url = "scenario://ehr/MedicationRequest/epinephrine-1870230"
    terf_url = "scenario://ehr/MedicationRequest/terfenadine-141918"
    mir_url = "scenario://ehr/MedicationAdministration/mirena-807283"
    dstu2_url = "scenario://ehr/fhir-dstu2/problem-list-export"
    percocet_url = "scenario://ehr/MedicationStatement/percocet-brand"
    rxnorm_url = "scenario://ehr/CodeSystem/rxnorm-1049625"
    apap_alias_url = "scenario://ehr/MedicationStatement/apap-oxycodone"

    b.node("start", f"Outpatient pharmacy queue {ticket}: {s['summary']}")
    b.node("intake", f"{ticket}: {s['queue_note']} Open the patient "
           f"header at {patient_url}.")
    b.edge("start", "e_intake", "intake", intake, "web")

    b.node("patient", f"Patient header: {s['patient_header']}")
    b.edge("intake", "e_patient", "patient", patient_url, "endpoint")

    b.node("oxycodone_rx", s["active_medications"])
    b.edge("patient", "e_meds", "oxycodone_rx", meds_url, "endpoint")

    b.node("fibro", s["fibro"])
    b.edge("oxycodone_rx", "e_fibro", "fibro", fibro_url, "endpoint")

    b.node("snapshot", s["snapshot_entry"])
    b.edge("oxycodone_rx", "e_snapshot", "snapshot", snap_url, "file")
    b.node("pdmp", s["pdmp"])
    b.edge("snapshot", "e_pdmp", "pdmp", pdmp_url, "file")
    b.node("agreement", s["agreement"])
    b.edge("snapshot", "e_agreement", "agreement", agr_url, "file")
    b.node("apap", s["apap_check"])
    b.edge("snapshot", "e_apap", "apap", apap_url, "file")
    b.node("pharmacy_fill_log", s["pharmacy_fill_log"])
    b.edge("snapshot", "e_filllog", "pharmacy_fill_log", filllog_url, "endpoint")

    b.node("history", s["history_entry"])
    b.edge("oxycodone_rx", "e_history", "history", hist_url, "file")
    b.node("y2023", s["y2023"])
    b.edge("history", "e_y2023", "y2023", y2023_url, "endpoint")
    b.node("y2024", s["y2024"])
    b.edge("y2023", "e_y2024", "y2024", y2024_url, "endpoint")
    b.edge("y2024", "e_y2025", "oxycodone_rx", y2025_url, "endpoint")
    b.node("cii_continuity", s["cii_continuity"])
    b.edge("y2024", "e_cii_continuity", "cii_continuity", continuity_url, "file")
    b.node("review_due", s["review_due"])
    b.edge("history", "e_review_due", "review_due", review_url, "endpoint")

    b.node("policy_folder", s["policy_folder"])
    b.edge("oxycodone_rx", "e_policy_folder", "policy_folder",
           pol_folder_url, "file")
    b.node("policy_2019", s["policy_2019"])
    b.edge("policy_folder", "e_policy_2019", "policy_2019",
           pol_2019_url, "file")
    b.node("policy_2026", s["policy_2026"])
    b.edge("policy_folder", "e_policy_2026", "policy_2026",
           pol_2026_url, "file")

    b.node("hold", f"{s['hold_result']} Submit the queue disposition "
           f"at {complete_url}.")
    b.edge("policy_2026", "e_hold", "hold", hold_url, "endpoint",
           requires=["refill_scope", "patient_identity", "queued_med",
                     "pain_indication", "governing_policy"],
           requires_any=["cii_history", "clinic_monitoring",
                         "apap_existing_orders"],
           requires_any_n=2)
    b.node("target", s["verification"])
    b.edge("hold", "e_target", "target", complete_url, "endpoint",
           requires=["review_routed"])

    b.node("legacy_autorefill", s["legacy_autorefill"])
    b.edge("policy_2019", "e_legacy", "legacy_autorefill", legacy_url,
           "endpoint")
    b.node("generic_review", s["generic_review"])
    b.edge("policy_2019", "e_generic_review", "generic_review",
           generic_url, "endpoint")
    b.node("dispense_preview", s["dispense_preview"])
    b.edge("policy_2026", "e_dispense", "dispense_preview", disp_url,
           "endpoint")
    b.node("dose_table", s["dose_table"])
    b.edge("policy_2026", "e_dose", "dose_table", dose_url, "file")
    b.node("discontinue", s["discontinue"])
    b.edge("policy_2026", "e_discontinue", "discontinue", dc_url, "endpoint")
    b.node("tramadol_switch", s["tramadol_switch"])
    b.edge("oxycodone_rx", "e_tramadol", "tramadol_switch", tram_url, "file")

    b.node("other_chart", s["other_chart"])
    b.edge("oxycodone_rx", "e_other", "other_chart", other_url, "endpoint")
    b.node("dental", s["dental"])
    b.edge("other_chart", "e_dental", "dental", dental_url, "endpoint")
    b.node("gingivitis", s["gingivitis"])
    b.edge("dental", "e_gingivitis", "gingivitis", ging_url, "endpoint")
    b.node("unemployed", s["unemployed"])
    b.edge("other_chart", "e_unemployed", "unemployed", unemp_url, "endpoint")
    b.node("chronic_pain_generic", s["chronic_pain_generic"])
    b.edge("other_chart", "e_chronic_pain", "chronic_pain_generic",
           cpain_url, "endpoint")
    b.node("lbp", s["lbp"])
    b.edge("other_chart", "e_lbp", "lbp", lbp_url, "endpoint")
    b.node("careplan_pt", s["careplan_pt"])
    b.edge("other_chart", "e_careplan", "careplan_pt", pt_url, "endpoint")
    b.node("coverage", s["coverage"])
    b.edge("other_chart", "e_coverage", "coverage", cov_url, "endpoint")
    b.node("copay", s["copay"])
    b.edge("coverage", "e_copay", "copay", copay_url, "endpoint")
    b.node("epinephrine", s["epinephrine"])
    b.edge("other_chart", "e_epinephrine", "epinephrine", epi_url, "endpoint")
    b.node("terfenadine", s["terfenadine"])
    b.edge("other_chart", "e_terfenadine", "terfenadine", terf_url, "endpoint")
    b.node("mirena", s["mirena"])
    b.edge("other_chart", "e_mirena", "mirena", mir_url, "endpoint")
    b.node("dstu2", s["dstu2"])
    b.edge("other_chart", "e_dstu2", "dstu2", dstu2_url, "endpoint")
    b.edge("dstu2", "e_percocet_alias", "oxycodone_rx", percocet_url,
           "endpoint")
    b.edge("history", "e_rxnorm_alias", "oxycodone_rx", rxnorm_url,
           "endpoint")
    b.edge("history", "e_apap_alias", "oxycodone_rx", apap_alias_url,
           "endpoint")

    off_canonical = [
        "pharmacy_fill_log", "y2023", "y2024", "cii_continuity",
        "review_due", "history", "policy_2019", "legacy_autorefill",
        "generic_review", "dispense_preview", "dose_table", "discontinue",
        "tramadol_switch", "other_chart", "dental", "gingivitis",
        "unemployed", "chronic_pain_generic", "lbp", "careplan_pt",
        "coverage", "copay", "epinephrine", "terfenadine", "mirena",
        "dstu2", "apap",
    ]
    grants = {
        "intake": "refill_scope",
        "patient": "patient_identity",
        "oxycodone_rx": "queued_med",
        "fibro": "pain_indication",
        "pdmp": "cii_history",
        "cii_continuity": "cii_history",
        "agreement": "clinic_monitoring",
        "review_due": "clinic_monitoring",
        "apap": "apap_existing_orders",
        "policy_2026": "governing_policy",
        "hold": "review_routed",
    }
    regions = {
        "core": ["start", "intake", "patient", "oxycodone_rx", "fibro",
                 "snapshot", "policy_folder", "policy_2026", "hold",
                 "target"],
        "evidence_synthesis": ["snapshot", "pdmp", "agreement", "apap",
                               "pharmacy_fill_log", "cii_continuity",
                               "review_due"],
        "version_constraint": ["policy_folder", "policy_2019", "policy_2026"],
        "two_routes": ["snapshot", "pdmp", "agreement", "history", "y2023",
                       "y2024", "cii_continuity", "review_due"],
        "alias_maze": ["oxycodone_rx"],
        "longitudinal_history": ["history", "y2023", "y2024",
                                 "cii_continuity", "review_due"],
        "other_chart": ["other_chart", "dental", "gingivitis", "unemployed",
                        "chronic_pain_generic", "lbp", "careplan_pt",
                        "coverage", "copay", "epinephrine", "terfenadine",
                        "mirena", "dstu2"],
    }
    provenance = {
        "start": _prov(overlay="generated_overlay"),
        "intake": _prov(overlay="generated_overlay"),
        "patient": _prov(observed="synthea"),
        "oxycodone_rx": _prov(observed="synthea", overlay="generated_overlay"),
        "fibro": _prov(observed="synthea", overlay="generated_overlay"),
        "snapshot": _prov(overlay="generated_overlay"),
        "pdmp": _prov(overlay="generated_overlay"),
        "agreement": _prov(overlay="generated_overlay"),
        "apap": _prov(observed="synthea", overlay="generated_overlay",
                      reference="public_reference"),
        "pharmacy_fill_log": _prov(overlay="generated_overlay"),
        "history": _prov(overlay="generated_overlay"),
        "y2023": _prov(observed="synthea"),
        "y2024": _prov(observed="synthea"),
        "cii_continuity": _prov(observed="synthea", overlay="generated_overlay"),
        "review_due": _prov(observed="synthea"),
        "policy_folder": _prov(overlay="generated_overlay"),
        "policy_2019": _prov(overlay="generated_overlay"),
        "policy_2026": _prov(overlay="generated_overlay",
                             reference="public_reference"),
        "hold": _prov(overlay="generated_overlay"),
        "target": _prov(overlay="generated_overlay"),
        "legacy_autorefill": _prov(overlay="generated_overlay"),
        "generic_review": _prov(overlay="generated_overlay"),
        "dispense_preview": _prov(overlay="generated_overlay"),
        "dose_table": _prov(overlay="generated_overlay",
                            reference="public_reference"),
        "discontinue": _prov(overlay="generated_overlay"),
        "tramadol_switch": _prov(overlay="generated_overlay"),
        "other_chart": _prov(overlay="generated_overlay"),
        "dental": _prov(observed="synthea"),
        "gingivitis": _prov(observed="synthea"),
        "unemployed": _prov(observed="synthea"),
        "chronic_pain_generic": _prov(observed="synthea"),
        "lbp": _prov(observed="synthea"),
        "careplan_pt": _prov(observed="synthea"),
        "coverage": _prov(overlay="generated_overlay"),
        "copay": _prov(overlay="generated_overlay"),
        "epinephrine": _prov(observed="synthea"),
        "terfenadine": _prov(observed="synthea"),
        "mirena": _prov(observed="synthea"),
        "dstu2": _prov(overlay="generated_overlay"),
    }
    graph, meta = b.result(_meta(c, grants, off_canonical, regions, 11))
    _order_graph_edges(graph, OXYCODONE_EDGE_ORDER_SEED)
    meta["dead_end_nodes"] = [
        n for n, es in graph["edges"].items()
        if not es and n != "target" and n not in grants
    ]
    meta["dead_end_definition"] = (
        "outdegree-zero nodes that grant no success token; "
        "evidence leaves and long-route monitors are not dead ends")
    meta["off_canonical_oracle_nodes"] = list(off_canonical)
    meta["canonical_oracle_edge_path"] = list(OXYCODONE_CANONICAL_ORACLE)
    meta["alternative_success_edge_path"] = list(OXYCODONE_LONG_SUCCESS)
    meta["edge_ordering"] = {
        "rule": OXYCODONE_EDGE_ORDER_RULE,
        "seed": OXYCODONE_EDGE_ORDER_SEED,
    }
    meta["node_provenance"] = provenance
    meta["aliased_nodes"] = ["oxycodone_rx"]
    meta["requirement_labels"].update({
        "cii_history": "CII history",
        "clinic_monitoring": "clinic monitoring",
        "apap_existing_orders": "acetaminophen existing-order check",
    })
    meta["evidence_rule"] = {
        "mandatory_tokens": ["pain_indication"],
        "categories": {
            "cii_history": ["pdmp", "cii_continuity"],
            "clinic_monitoring": ["agreement", "review_due"],
            "apap_existing_orders": ["apap"],
        },
        "threshold": 2,
        "lookalikes": ["pharmacy_fill_log", "chronic_pain_generic", "lbp",
                       "careplan_pt", "dental"],
    }
    return graph, meta
