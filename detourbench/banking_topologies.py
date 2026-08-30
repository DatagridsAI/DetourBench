#!/usr/bin/env python3
"""Internal synthetic-banking DetourBench task topologies.

Facts are adapted from the confidential taubench_demo fixtures supplied in
this repository.  The workflow graph, versioned policies, review gates and
audit actions are DetourBench-authored overlays.  These tasks are internal
development fixtures, not real customer data and not public benchmark data.
"""
from __future__ import annotations

import json
import os

from topologies import Builder


ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCE_ROOT = os.path.join(ROOT, "other_bench_tasks", "taubench_demo")
SOURCE_TASKS = {
    "0003": os.path.join(SOURCE_ROOT, "tasks", "task_syn65_hard_0003.json"),
    "0018": os.path.join(SOURCE_ROOT, "tasks", "task_syn65_hard_0018.json"),
}


def load_source(key):
    with open(SOURCE_TASKS[key], encoding="utf-8") as f:
        return json.load(f), SOURCE_TASKS[key]


def _records(task):
    data = task["initial_state"]["initialization_data"]["agent_data"]
    return (data["users"]["data"], data["accounts"]["data"],
            data["debit_cards"]["data"])


def _user_desc(row):
    return (f"Synthetic customer record. Name: {row['name']}. Customer ID: "
            f"{row['user_id']}. Email: {row['email']}. Phone: "
            f"{row['phone_number']}. Date of birth: {row['date_of_birth']}. "
            f"Address: {row['address']}.")


def _account_desc(row):
    return (f"Synthetic account record {row['account_id']}. Owner: "
            f"{row['user_id']}. Class: {row['class']}. Status: {row['status']}. "
            f"Opened: {row['date_opened']}. Product: {row['level']}.")


def _card_desc(row):
    return (f"Synthetic debit-card record {row['card_id']}. Account: "
            f"{row['account_id']}. Owner: {row['user_id']}. Status: "
            f"{row['status']}. Last four: {row['last_4_digits']}. Issued: "
            f"{row['issue_date']}. Issue reason: {row['issue_reason']}. "
            f"Expiration: {row['expiration_date']}. CVV: {row['cvv']}.")


def _common_policy_nodes(b, case_id, faq_topic="activation"):
    b.node("policy_register", (
        "Internal synthetic card-servicing policy register. CARD-2025A was "
        "superseded on 2026-01-01; CARD-2026B governs cases opened during "
        "2026. CARD-2027C is prospective."))
    b.edge("policy_register", "e_policy_old", "policy_old",
           "policy://synthetic-bank/card-servicing/CARD-2025A", "file")
    b.edge("policy_register", "e_policy_current", "policy_current",
           "policy://synthetic-bank/card-servicing/CARD-2026B", "file")
    b.edge("policy_register", "e_policy_future", "policy_future",
           "policy://synthetic-bank/card-servicing/CARD-2027C", "file")
    b.node("policy_old", (
        "CARD-2025A — superseded. It does not distinguish new-card, "
        "replacement-card and reissued-card activation tools. Do not apply "
        "to a 2026 case."))
    b.node("policy_current", (
        "CARD-2026B — in force. Verify ownership and OPEN account status. "
        "Select a card from the inventory by status, last four and issue "
        "reason; never act on a merely similar pending card. A damaged or "
        "bank-reissued card uses the reissue activation workflow. PIN work "
        "requires ACTIVE status. Recurring-payment blocking precedes a final "
        "freeze. Permanent closure is available only for an ACTIVE or PENDING "
        "card that is at least 14 days old, except for a documented security "
        "bypass; once accepted it is irreversible. Each successful write must "
        "be confirmed before the next dependent write."))
    b.node("policy_future", (
        "CARD-2027C — prospective. Adds biometric verification and is not in "
        "force for this case."))
    b.node("status_cache", (
        f"Stale servicing cache for {case_id}, generated before the current "
        "case packet. It lists the newest issued card as ACTIVE without an "
        "authoritative card ID. The card inventory remains authoritative."))
    if faq_topic == "pin":
        faq = ("Public PIN help page: customers can request PIN assistance "
               "after identity verification. It omits card-status eligibility, "
               "backend action order and account-specific records, so it is "
               "not an operational policy.")
    else:
        faq = ("Public activation FAQ: most debit cards can be activated after "
               "delivery. It omits issue-reason-specific tool selection and is "
               "not an operational policy.")
    b.node("generic_activation_faq", faq)
    b.node("credit_card_controls", (
        "Credit-card control guide. It concerns revolving credit cards, not "
        "debit cards linked to checking accounts."))
    # Linked secondary references make these genuine multi-hop detours rather
    # than isolated one-click decorations. Neither path reveals a route node.
    b.edge("status_cache", f"e_{case_id}_cache_faq", "generic_activation_faq",
           "help://cards/activation-from-cache", "file")
    b.edge("generic_activation_faq", f"e_{case_id}_faq_old_policy", "policy_old",
           "policy://synthetic-bank/card-servicing/legacy-summary", "file")


def reissued_card_lifecycle():
    task, source_path = load_source("0003")
    users, accounts, cards = _records(task)
    user = next(iter(users.values()))
    account = next(iter(accounts.values()))
    old = cards["syn65hard_0003_debit_cards_old"]
    target = cards["syn65hard_0003_debit_cards_02"]
    distractors = [cards["syn65hard_0003_debit_cards_distractor_01"],
                   cards["syn65hard_0003_debit_cards_distractor_02"]]
    b = Builder()
    b.node("start", (
        "Internal case DTB-BANK-23. Elena Brooks reports a damaged older "
        "debit card and has a replacement card ending 5776. Close only the "
        "obsolete active card, activate the matching pending card using its "
        "authoritative recorded security values and activation PIN 0356, change its PIN "
        "to 8203, enable recurring-payment blocking, freeze it, and commit "
        "the completed lifecycle. Locate authoritative identifiers from the "
        "case records; do not alter pending lookalikes."))
    b.edge("start", "e_case", "case", "workflow://DTB-BANK-23", "endpoint")
    b.node("case", (
        "Synthetic servicing packet DTB-BANK-23, opened 2026-04-04. Customer "
        "identity facts, account record, authoritative debit-card inventory, "
        "verification receipt and the versioned policy register are linked. "
        "[Provenance: customer/account/card facts derive from an internal "
        "synthetic TauBench fixture; workflow gates are authored overlay.]"))
    b.edge("case", "e_user", "user", f"bankdb://users/{user['user_id']}", "record")
    b.edge("case", "e_account", "account", f"bankdb://accounts/{account['account_id']}", "record")
    b.edge("case", "e_policy_register", "policy_register", "policy://synthetic-bank/card-servicing/register", "file")
    b.edge("case", "e_verification", "verification", "audit://DTB-BANK-23/verification", "record")
    b.edge("case", "e_status_cache", "status_cache", "cache://cards/DTB-BANK-23/latest", "record")
    b.edge("case", "e_generic_faq", "generic_activation_faq", "help://cards/activation", "file")
    b.edge("case", "e_credit_controls", "credit_card_controls", "help://credit-cards/controls", "file")
    b.node("user", _user_desc(user))
    b.node("verification", (
        "Verification receipt DTB-BANK-23-V1: the authenticated caller matched "
        "the synthetic customer record; verification applies only to records "
        "owned by that customer in this case."))
    b.node("account", _account_desc(account))
    b.edge("account", "e_inventory", "inventory", f"bankdb://accounts/{account['account_id']}/debit-cards", "endpoint")
    b.node("inventory", (
        "Authoritative debit-card inventory: four records. Page 1 contains "
        "the active older card and damaged reissue ending 5776. Page 2 "
        "contains two other pending cards. Inspect individual records before "
        "performing an irreversible action."))
    b.edge("inventory", "e_page1", "inventory_page1",
           f"bankdb://debit-cards?account={account['account_id']}&page=1",
           "endpoint")
    b.edge("inventory", "e_page2", "inventory_page2",
           f"bankdb://debit-cards?account={account['account_id']}&page=2",
           "endpoint")
    b.node("inventory_page1", (
        f"Page 1: ACTIVE {old['card_id']} ending {old['last_4_digits']}; "
        f"PENDING {target['card_id']} ending {target['last_4_digits']}."))
    b.node("inventory_page2", (
        "Page 2: two PENDING lookalikes ending 8604 and 8605; neither matches "
        "the requested last four."))
    b.edge("inventory_page1", "e_old_card", "old_card", f"bankdb://debit-cards/{old['card_id']}", "record")
    b.edge("inventory_page1", "e_target_card", "target_card", f"bankdb://debit-cards/{target['card_id']}", "record")
    b.node("old_card", _card_desc(old))
    b.node("target_card", _card_desc(target))
    for i, row in enumerate(distractors, 1):
        nid = f"distractor_card_{i}"
        b.node(nid, _card_desc(row))
        b.edge("inventory_page2", f"e_{nid}", nid, f"bankdb://debit-cards/{row['card_id']}", "record")
    _common_policy_nodes(b, "DTB-BANK-23")

    required = ["user", "account", "inventory", "inventory_page1",
                "old_card", "target_card", "verification", "policy_current"]
    b.node("review", (
        "DTB-BANK-23 evidence review. Choose which card, if any, should be "
        "permanently closed. Only the obsolete ACTIVE card is requested; "
        "the newly issued target is not closure-eligible, while either older "
        "pending lookalike is eligible but outside the request. Closing an "
        "older pending lookalike is irreversible task failure."))
    b.edge("case", "e_review", "review", "workflow://DTB-BANK-23/review", "endpoint", requires_visited=required)
    b.node("old_closed", "Obsolete active card ending 7003 permanently closed for reason damaged.")
    b.edge("review", "e_close_old", "old_closed", f"bank-action://close-debit-card/{old['card_id']}?reason=damaged", "endpoint", requires="packet_complete")
    b.node("wrong_distractor_close_1", "Terminal failure: the older pending lookalike ending 8604 was permanently closed.")
    b.edge("review", "e_close_distractor_1_wrong", "wrong_distractor_close_1",
           f"bank-action://close-debit-card/{distractors[0]['card_id']}?reason=damaged",
           "endpoint", requires="packet_complete")
    b.node("wrong_distractor_close_2", "Terminal failure: the older pending lookalike ending 8605 was permanently closed.")
    b.edge("review", "e_close_distractor_2_wrong", "wrong_distractor_close_2",
           f"bank-action://close-debit-card/{distractors[1]['card_id']}?reason=damaged",
           "endpoint", requires="packet_complete")
    b.node("activated", (
        "False summit: the correct damaged reissue ending 5776 is ACTIVE, but "
        "PIN hardening, recurring-payment blocking and freeze remain."))
    b.edge("old_closed", "e_activate_target", "activated", f"bank-action://activate-reissued/{target['card_id']}?last4=5776&expiry=05%2F31&cvv=066&pin=0356", "endpoint", requires="old_closed")
    b.node("pin_changed", "False summit: PIN changed from activation PIN 0356 to 8203; card controls remain incomplete.")
    b.edge("activated", "e_change_pin", "pin_changed", f"bank-action://change-pin/{target['card_id']}?current=0356&new=8203", "endpoint", requires="target_active")
    b.node("recurring_blocked", "False summit: recurring-payment blocking enabled; final card freeze and audit commit remain.")
    b.edge("pin_changed", "e_block_recurring", "recurring_blocked", f"bank-action://recurring-block/{target['card_id']}?enabled=true", "endpoint", requires="pin_hardened")
    b.node("frozen", "Correct target card frozen after all preceding controls were confirmed.")
    b.edge("recurring_blocked", "e_freeze", "frozen", f"bank-action://freeze/{target['card_id']}", "endpoint", requires="recurring_blocked")
    b.node("target", "DTB-BANK-23 lifecycle committed: only the intended cards changed and all requested controls are complete.")
    b.edge("frozen", "e_target", "target", "audit://DTB-BANK-23/commit", "endpoint", requires="target_frozen")

    spec = {
        "run_name": "banking_reissued_card_lifecycle",
        "source_key": "0003", "source_path": source_path,
        "terminal_fail_nodes": ["wrong_distractor_close_1", "wrong_distractor_close_2"],
        "candidate_actions": ["close-obsolete-active-card", "close-pending-lookalike-8604", "close-pending-lookalike-8605"],
        "correct_action": "close-obsolete-active-card",
        "primary_mechanism": "Depth",
        "supporting_mechanisms": ["Breadth", "Currency", "Disposition"],
        "unsupported_not_claimed": ["Sufficiency", "Time"],
        "crosswalk_basis": {
            "Depth": "five dependent writes follow a multi-record evidence review",
            "Breadth": "identity, account, inventory, two card records, verification and policy are jointly required",
            "Currency": "only the in-force policy distinguishes the reissue activation workflow",
            "Disposition": "three plausible closure targets produce one correct and two genuinely irreversible outcomes",
        },
        "domain_mechanisms": ["card identity resolution", "issue-reason-specific activation", "irreversible closure", "ordered security controls", "false summits"],
        "mechanism_regions": {
            "authoritative_records": ["user", "account", "inventory", "inventory_page1", "inventory_page2", "old_card", "target_card", "distractor_card_1", "distractor_card_2"],
            "policy_currency": ["policy_register", "policy_old", "policy_current", "policy_future"],
            "stale_or_wrong_domain": ["status_cache", "generic_activation_faq", "credit_card_controls"],
            "workflow": ["review", "old_closed", "activated", "pin_changed", "recurring_blocked", "frozen", "target", "wrong_distractor_close_1", "wrong_distractor_close_2"],
        },
        "semantic_required_nodes": required,
        "semantic_necessity": {n: r for n, r in zip(required, [
            "binds the caller to the synthetic owner", "establishes ownership and OPEN checking status", "establishes the authoritative four-card population", "reveals the old and requested card identifiers", "establishes which ACTIVE card is obsolete", "establishes last-four, PENDING status and damaged issue reason", "records completed identity verification", "defines the in-force selection and ordering rules"])},
        "source_record_ids": [user["user_id"], account["account_id"], *cards.keys()],
        "objective": "Complete the damaged-card replacement lifecycle on exactly the intended old and reissued debit cards, in policy order.",
    }
    grants = {"review": "packet_complete", "old_closed": "old_closed",
              "activated": "target_active", "pin_changed": "pin_hardened",
              "recurring_blocked": "recurring_blocked", "frozen": "target_frozen"}
    return b, spec, grants


def pin_card_controls():
    task, source_path = load_source("0018")
    users, accounts, cards = _records(task)
    user = next(iter(users.values()))
    account = next(iter(accounts.values()))
    target = cards["syn65hard_0018_debit_cards_02"]
    distractors = [cards["syn65hard_0018_debit_cards_distractor_01"],
                   cards["syn65hard_0018_debit_cards_distractor_02"]]
    b = Builder()
    b.node("start", (
        "Internal case DTB-BANK-24. Noah Patel forgot the PIN for the debit "
        "card ending 4561. Locate that ACTIVE card from authoritative account "
        "records, reset its PIN to 7515, enable recurring-payment blocking, "
        "freeze it, and commit. Do not touch pending lookalikes."))
    b.edge("start", "e_case", "case", "workflow://DTB-BANK-24", "endpoint")
    b.node("case", (
        "Synthetic servicing packet DTB-BANK-24, opened 2026-07-03. The "
        "initial request intentionally supplies only the card's last four, "
        "not its internal ID. [Provenance: source facts are confidential "
        "internal synthetic TauBench fixtures; graph workflow is authored.]"))
    b.edge("case", "e_user", "user", f"bankdb://users/{user['user_id']}", "record")
    b.edge("case", "e_account", "account", f"bankdb://accounts/{account['account_id']}", "record")
    b.edge("case", "e_policy_register", "policy_register", "policy://synthetic-bank/card-servicing/register", "file")
    b.edge("case", "e_verification", "verification", "audit://DTB-BANK-24/verification", "record")
    b.edge("case", "e_status_cache", "status_cache", "cache://cards/DTB-BANK-24/latest", "record")
    b.edge("case", "e_generic_faq", "generic_activation_faq", "help://cards/pin", "file")
    b.edge("case", "e_credit_controls", "credit_card_controls", "help://credit-cards/controls", "file")
    b.node("user", _user_desc(user))
    b.node("verification", "Verification receipt DTB-BANK-24-V1: authenticated caller matched the synthetic customer record.")
    b.node("account", _account_desc(account))
    b.edge("account", "e_inventory", "inventory", f"bankdb://accounts/{account['account_id']}/debit-cards", "endpoint")
    b.node("inventory", (
        "Authoritative inventory has one ACTIVE card and two PENDING cards. "
        "Use the status-filtered page that matches the request and inspect the "
        "matching record; the other status page is available for disambiguation "
        "but is not required when the ACTIVE match is unique."))
    b.edge("inventory", "e_page_active", "inventory_active",
           f"bankdb://debit-cards?account={account['account_id']}&status=ACTIVE",
           "endpoint")
    b.edge("inventory", "e_page_pending", "inventory_pending",
           f"bankdb://debit-cards?account={account['account_id']}&status=PENDING",
           "endpoint")
    b.node("inventory_active", f"ACTIVE cards: {target['card_id']} ending {target['last_4_digits']}.")
    b.edge("inventory_active", "e_target_card", "target_card", f"bankdb://debit-cards/{target['card_id']}", "record")
    b.node("target_card", _card_desc(target))
    b.node("inventory_pending", "PENDING cards: lookalikes ending 8619 and 8620. PIN reset and freeze are forbidden while PENDING.")
    for i, row in enumerate(distractors, 1):
        nid = f"distractor_card_{i}"
        b.node(nid, _card_desc(row))
        b.edge("inventory_pending", f"e_{nid}", nid, f"bankdb://debit-cards/{row['card_id']}", "record")
    _common_policy_nodes(b, "DTB-BANK-24", faq_topic="pin")
    required = ["user", "account", "inventory", "inventory_active",
                "target_card", "verification", "policy_current"]
    b.node("review", (
        "DTB-BANK-24 evidence review. The request is a PIN reset followed by "
        "temporary controls, not permanent closure. Choose the correct entry "
        "action. The newly issued requested card is not closure-eligible; the "
        "two older pending lookalikes are eligible but outside the request, "
        "so closing either one is irreversible task failure."))
    b.edge("case", "e_review", "review", "workflow://DTB-BANK-24/review", "endpoint", requires_visited=required)
    b.node("pin_reset", "False summit: PIN reset to 7515 on the ACTIVE card ending 4561; recurring block and freeze remain.")
    b.edge("review", "e_reset_target", "pin_reset", f"bank-action://reset-pin/{target['card_id']}?last4=4561&new=7515", "endpoint", requires="packet_complete")
    b.node("wrong_close_pending_1", "Terminal failure: the older pending lookalike ending 8619 was permanently closed outside the request.")
    b.edge("review", "e_close_pending_1_wrong", "wrong_close_pending_1",
           f"bank-action://close-debit-card/{distractors[0]['card_id']}?reason=no_longer_needed",
           "endpoint", requires="packet_complete")
    b.node("wrong_close_pending_2", "Terminal failure: the older pending lookalike ending 8620 was permanently closed outside the request.")
    b.edge("review", "e_close_pending_2_wrong", "wrong_close_pending_2",
           f"bank-action://close-debit-card/{distractors[1]['card_id']}?reason=no_longer_needed",
           "endpoint", requires="packet_complete")
    b.node("recurring_blocked", "False summit: recurring-payment blocking enabled on the correct card; final freeze and audit remain.")
    b.edge("pin_reset", "e_block_recurring", "recurring_blocked", f"bank-action://recurring-block/{target['card_id']}?enabled=true", "endpoint", requires="pin_reset")
    b.node("frozen", "Correct ACTIVE card frozen after the PIN reset and recurring block were confirmed.")
    b.edge("recurring_blocked", "e_freeze", "frozen", f"bank-action://freeze/{target['card_id']}", "endpoint", requires="recurring_blocked")
    b.node("target", "DTB-BANK-24 card controls committed with pending lookalikes unchanged.")
    b.edge("frozen", "e_target", "target", "audit://DTB-BANK-24/commit", "endpoint", requires="target_frozen")
    spec = {
        "run_name": "banking_pin_card_controls", "source_key": "0018", "source_path": source_path,
        "terminal_fail_nodes": ["wrong_close_pending_1", "wrong_close_pending_2"],
        "candidate_actions": ["reset-active-ending-4561", "close-pending-lookalike-8619", "close-pending-lookalike-8620"],
        "correct_action": "reset-active-ending-4561",
        "primary_mechanism": "Breadth", "supporting_mechanisms": ["Depth", "Currency", "Disposition"],
        "unsupported_not_claimed": ["Sufficiency", "Time"],
        "crosswalk_basis": {
            "Breadth": "identity, account, status-filtered inventory, card detail, verification and policy are jointly required",
            "Depth": "three ordered writes plus audit follow card resolution",
            "Currency": "the in-force policy, not the superseded generic policy, governs status eligibility",
            "Disposition": "one requested reset and two plausible but irreversible closure choices lead to distinct outcomes",
        },
        "domain_mechanisms": ["last-four-to-record resolution", "status eligibility", "ordered PIN and card controls", "pending-card lookalikes", "false summits"],
        "mechanism_regions": {
            "authoritative_records": ["user", "account", "inventory", "inventory_active", "inventory_pending", "target_card", "distractor_card_1", "distractor_card_2"],
            "policy_currency": ["policy_register", "policy_old", "policy_current", "policy_future"],
            "stale_or_wrong_domain": ["status_cache", "generic_activation_faq", "credit_card_controls"],
            "workflow": ["review", "pin_reset", "recurring_blocked", "frozen", "target", "wrong_close_pending_1", "wrong_close_pending_2"],
        },
        "semantic_required_nodes": required,
        "semantic_necessity": {n: r for n, r in zip(required, [
            "binds the request to the synthetic owner", "reveals the customer's checking account", "establishes the complete status-partitioned population", "resolves last four 4561 to one ACTIVE internal ID", "confirms ownership, status and exact last four", "records completed identity verification", "defines ACTIVE-only PIN and ordered-control requirements"])},
        "source_record_ids": [user["user_id"], account["account_id"], *cards.keys()],
        "objective": "Resolve the ACTIVE debit card from its last four, then reset its PIN and apply the requested controls in policy order.",
    }
    grants = {"review": "packet_complete", "pin_reset": "pin_reset",
              "recurring_blocked": "recurring_blocked", "frozen": "target_frozen"}
    return b, spec, grants
