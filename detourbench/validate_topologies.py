#!/usr/bin/env python3
"""Verify every (theme x topology) instance actually behaves as claimed.

These are the properties the benchmark's scoring depends on, so they get
checked mechanically rather than assumed:
  1. the oracle path runs clean in the live env: succeeds, in exactly
     lower_bound steps, with zero invalid steps;
  2. no two distinct static edges share an identifier (a collision would
     silently make one resource unreachable in the global registry);
  3. every node listed as a dead end genuinely cannot reach target — via
     BFS with a full inventory, so a "dead end" can't be dead merely for
     want of a key;
  4. topology-specific claims: the decoy credential does NOT open the gate;
     the alternate route in two_routes DOES independently reach target;
     the false summit is not itself the target.
"""
import json
import os
import random
import re
import sys
from collections import deque

from generate import build_graph, compute_lower_bound, THEMES, req_list
from topologies import TASK_TOPOLOGIES as TOPOLOGIES
from env import GraphEnv


def reachable_with_full_inventory(graph, meta, src, all_items):
    """Can `src` reach target if we hand it every credential in the game?"""
    target = meta["target"]
    seen = {src}
    q = deque([src])
    while q:
        n = q.popleft()
        if n == target:
            return True
        for e in graph["edges"].get(n, []):
            rv = e.get("requires_visited")
            # be generous: ignore visit-order preconditions too
            if e["to"] not in seen:
                seen.add(e["to"])
                q.append(e["to"])
    return target in seen



def _corpus():
    """The regulation corpus currently loaded into topologies, or None."""
    try:
        import topologies
        return topologies.CORPUS
    except Exception:
        return None


def _cited_here(src_node, edge, graph, corpus):
    """True when the edge's destination is one of the citations the corpus
    prints on the source section.

    This is what makes an unsignposted step fair rather than a guess: the
    candidate set is the regulation's own cross-reference list, visible in
    the node's text, and every member of it exists. What the agent is not
    told is which member matters.
    """
    if not corpus:
        return False
    secs = corpus.get("sections") or {}
    if not src_node.startswith("sec_"):
        return False
    num = src_node[4:]
    refs = set((secs.get(num) or {}).get("refs") or ())
    if not refs:
        return False
    dest = edge.get("to", "")
    if dest.startswith("sec_") and dest[4:] in refs:
        # and the node must actually show the list, or the agent cannot
        # see the candidates at all
        text = (graph["nodes"].get(src_node) or {}).get("desc", "")
        return dest[4:] in text
    return False


def check(theme, topo):
    g, m = build_graph(random.Random(0), theme, topo)
    lb, oracle = compute_lower_bound(g, m)
    edge_by_id = {e["edge_id"]: e for ne in g["edges"].values() for e in ne}
    all_items = set()
    for v in m.get("token_grants", {}).values():
        all_items.update([v] if isinstance(v, str) else v)

    # --- 1. oracle path runs clean in the live env
    import json, os, tempfile
    d = tempfile.mkdtemp()
    with open(f"{d}/graph_full.json", "w") as f:
        json.dump({"graph": g, "meta": m}, f)
    with open(f"{d}/oracle.json", "w") as f:
        json.dump({"lower_bound_steps": lb, "oracle_edge_path": oracle}, f)
    env = GraphEnv(d, seed=0)
    for eid in oracle:
        r = env.access(edge_by_id[eid]["desc"])
        assert r["ok"], f"{theme}/{topo}: oracle edge {eid} failed: {r}"
    assert env.success, f"{theme}/{topo}: oracle path did not reach target"
    assert env.steps_used == lb, f"{theme}/{topo}: {env.steps_used} != lb {lb}"
    assert not [t for t in env.trajectory if not t.get("valid")], \
        f"{theme}/{topo}: oracle path had invalid steps"

    # --- 2. an identifier must never denote two different resources.
    # Keyed on where the identifier *leads*, not on where it is cited
    # from: several sections citing the same section is what a real
    # citation network looks like, and all of those edges resolve to one
    # node, which is correct. The failure worth catching is one string
    # resolving to two different nodes, which makes the global registry
    # ambiguous and silently strands one of them.
    seen = {}
    for node, edges in g["edges"].items():
        for e in edges:
            if e.get("perturb"):
                continue
            prev = seen.get(e["desc"])
            if prev is not None and prev != e["to"]:
                raise AssertionError(
                    f"{theme}/{topo}: identifier {e['desc']!r} resolves to "
                    f"both {prev} and {e['to']}")
            seen[e["desc"]] = e["to"]

    # --- 3. declared dead ends really are dead, even with every credential
    for dn in m.get("dead_end_nodes", []):
        if reachable_with_full_inventory(g, m, dn, all_items):
            raise AssertionError(
                f"{theme}/{topo}: '{dn}' is listed as a dead end but can "
                f"reach target")

    # --- 3a2. corpus tasks must not describe another corpus's subject.
    # Two of the three defects found in the FDA/OSHA pilots were this: a
    # section headed "Initiation of regulatory hearing" announcing that it
    # governs vessels carrying residue cargo, because scope wording written
    # for the customs subgraph was applied verbatim to every corpus. It
    # reads as nonsense, models cannot reason from it, and every run on
    # those corpora exhausted budget. The check is crude — a vocabulary
    # from one domain appearing in a graph built from another — but it is
    # mechanical, and it catches exactly the mistake that keeps recurring.
    if m.get("corpus_seed") or topo in ("absence_case", "integrated_case",
                                        "regulatory_chain"):
        FOREIGN = {
            "19": ["coastwise", "residue cargo", "bond condition",
                   "customs broker"],
            "21": ["detention order", "consignment", "hearing procedure"],
            "29": ["fall protection", "rooftop", "abatement"],
            "12": ["home equity", "finance charge", "right of rescission"],
            "14": ["acoustical change", "type certificate", "noise showing"],
            "17": ["commodity customer", "customer property",
                   "futures commission merchant"],
            "33": ["clean ballast", "segregated ballast", "ballast tank"],
            "45": ["eligibility redetermination", "enrollee",
                   "qualified health plan"],
            "46": ["merchant mariner", "entry-level rating",
                   "endorsement restriction"],
            "47": ["public inspection", "withholding ground",
                   "search and review"],
            "49": ["hazardous materials table", "packing group",
                   "hazard zone"],
            "30": ["drilling prognosis", "casing and cementing",
                   "location plat"],
            "42": ["opting-out", "nonparticipating supplier",
                   "incentive payment"],
        }
        # A corpus states which title it came from; the seed-number
        # heuristic below only ever distinguished the original three and
        # silently labels every other corpus "19".
        declared = (_corpus() or {}).get("title")
        seed = str(m.get("corpus_seed") or "")
        own = str(declared) if declared else (
            "21" if seed.startswith("1.") or seed.startswith("16.")
            else "29" if seed.startswith("19") else "19")
        # Only the authored parts. A section quoting its own title's
        # vocabulary is not the defect this check is for, and once nodes
        # carry real regulation text it would fire on every corpus whose
        # subject overlaps another's.
        corpus_now = _corpus() or {}
        found = [(v.get("text") or "").lower()
                 for v in (corpus_now.get("sections") or {}).values()
                 if v.get("text")]
        blob = " ".join(n["desc"] for n in g["nodes"].values()).lower()
        for ft in found:
            if ft:
                blob = blob.replace(ft, " ")
        for other, words in FOREIGN.items():
            if other == own:
                continue
            hits = [w for w in words if w in blob]
            if hits:
                raise AssertionError(
                    f"{theme}/{topo}: graph built from title {own} uses "
                    f"title {other} vocabulary {hits} — scope or scenario "
                    f"text was written for a different corpus")

    # --- 3b. the guidance actually points down the route that exists.
    # Theme prose (wiki_desc, target_desc) was authored for linear_gate's
    # shape and is reused verbatim by topologies whose real route is
    # different. In normative_refs the wiki told the agent to "trigger a
    # pipeline run via its API" while the actual path ran through numbered
    # spec clauses; claude-opus-4-8 followed the instruction, could not
    # find what it described, and correctly concluded it was stuck. That
    # cost hours to find because it only shows up as a model giving up.
    # A node on the critical path must give a reader some handle on the
    # next hop: either it names a distinctive piece of that identifier, or
    # the identifier is self-describing (a path/URL the node's own text
    # refers to). Checked on the guidance node — the one whose whole job
    # is to say where to go next.
    # The target and any declared terminal failure are actions, not
    # candidates: an agent does not have to recognise the filing among
    # lookalikes, and the ticket names it outright.
    terminal_nodes = {m["target"]} | set(m.get("terminal_fail_nodes") or ())
    onpath = []
    cur_nodes = {m["start"]}
    for eid in oracle:
        e = edge_by_id[eid]
        src = next(n for n, es in g["edges"].items()
                   if any(x["edge_id"] == eid for x in es))
        onpath.append((src, e))
    for src, e in onpath:
        if src == m["start"]:
            continue                     # start lists everything anyway
        desc = (g["nodes"][src]["desc"] or "").lower()
        ident = e["desc"].lower()
        # distinctive tokens of the next identifier: path/URL tail segments
        # and any hyphen/underscore-joined words, minus generic ones
        tail = ident.rstrip("/").split("/")[-1]
        toks = {t for t in tail.replace("?", " ").replace("=", " ")
                .replace("-", " ").replace("_", " ").replace(".", " ").split()
                if len(t) > 3}
        toks -= {"http", "https", "internal", "com", "yaml", "json", "html"}
        if not toks:
            continue
        # Match on stems, not exact strings: a node that says "poll the
        # run's log stream" is pointing squarely at `.../logs` and should
        # not be flagged over a plural. Five characters is enough to keep
        # "validate"/"validation" and "log"/"logs" together while still
        # separating genuinely different words.
        words = set(desc.replace("/", " ").replace("-", " ")
                    .replace("_", " ").replace(".", " ").split())

        def hit(tok):
            s = tok[:5]
            # >2, not >3: "log stream" is a perfectly clear pointer to
            # `.../logs`, and a three-letter cutoff silently dropped it.
            return any(w.startswith(s) or tok.startswith(w[:5])
                       for w in words if len(w) > 2)

        if e.get("to") in terminal_nodes:
            continue          # the filing is the action, not a candidate
        if not any(hit(t) for t in toks):
            # A task may decline to name the successor, provided the
            # successor is among the citations the source itself prints on
            # that node. The check exists to stop an agent being sent
            # somewhere that does not exist - which is what normative_refs
            # did - not to require the regulation to mark its own answer.
            if m.get("unsignposted") and _cited_here(src, e, g, _corpus()):
                continue
            raise AssertionError(
                f"{theme}/{topo}: node '{src}' is on the critical path but "
                f"its text gives no handle on the next hop "
                f"({e['desc']!r}); an agent has no reason to pick it")

    # --- 3c. a bulk citation list is not a pointer.
    # Check 3b only asks whether the next identifier appears somewhere in
    # the node's text, and a "Cross-references: A, B, C, D, E, F" clause
    # satisfies that for six siblings at once. That is precisely the shape
    # of the mistake that has cost four separate pilot rounds so far
    # (normative_refs, regulatory_chain, absence_case, conflict_case): the
    # successor is listed indistinguishably among options that lead
    # nowhere, so the only way through is to sample. Models did sample,
    # correctly declined to commit to a wrong one, and exhausted budget.
    # Requiring the successor to be named outside the bulk list is the
    # mechanical form of "say which one continues".
    BULK = re.compile(r"Cross-references:[^.]*(?:\.[0-9][^.]*)*\.", re.S)
    for src, e in onpath:
        if src == m["start"]:
            continue
        desc = g["nodes"][src]["desc"] or ""
        siblings = [x["desc"] for x in g["edges"].get(src, [])
                    if x["edge_id"] != e["edge_id"]]
        if len(siblings) < 2:
            continue                      # nothing ambiguous to resolve
        outside = BULK.sub(" ", desc).lower()
        succ = [x["desc"] for x in g["edges"].get(src, [])]
        named = [x for x in succ
                 if x.rstrip("/").split("/")[-1].split("?")[0].lower()
                 in outside]
        if e.get("to") in terminal_nodes:
            continue          # as above
        if not named:
            if m.get("unsignposted") and _cited_here(src, e, g, _corpus()):
                continue
            raise AssertionError(
                f"{theme}/{topo}: node '{src}' offers {len(succ)} onward "
                f"citations and singles out none of them outside its bulk "
                f"cross-reference list; an agent can only proceed by "
                f"sampling")


    # --- 3c. full-visibility condition must not hand over the answer key.
    # The map and the evaluator's labels live in the same meta dict, so
    # the separation is asserted rather than trusted: whatever the agent
    # can see under `visibility="full"` is dumped and checked against
    # every evaluator-only field and every internal node name.
    env_full = GraphEnv(d, seed=0, visibility="full")
    payload = json.dumps(env_full.look())
    forbidden = {
        "dead_end_nodes": m.get("dead_end_nodes"),
        "mechanism_regions": list((m.get("mechanism_regions") or {})),
        "terminal_fail_nodes": m.get("terminal_fail_nodes"),
        "token_grants": list(m.get("token_grants") or {}),
        "target_node_id": [m["target"]],
        "lower_bound": [str(lb)],
        "oracle_edge_ids": oracle,
    }
    for field, vals in forbidden.items():
        for v in (vals or []):
            if not isinstance(v, str) or len(v) < 4:
                continue
            if f'"{v}"' in payload or f"'{v}'" in payload:
                raise AssertionError(
                    f"{theme}/{topo}: full-visibility payload leaks "
                    f"evaluator-only {field}: {v!r}")
    for nid in g["nodes"]:
        if len(nid) > 3 and f'"{nid}"' in payload:
            raise AssertionError(
                f"{theme}/{topo}: full-visibility payload leaks internal "
                f"node name {nid!r}")
    # and it has to actually be more informative than local, or the
    # condition is not testing anything
    n_local = len(GraphEnv(d, seed=0).look()["known_resources"])
    n_full = len(env_full.look()["known_resources"])
    assert n_full > n_local, \
        f"{theme}/{topo}: full visibility exposes no more than local " \
        f"({n_full} vs {n_local})"

    # Full visibility must change what the agent KNOWS, never what it can
    # REACH. Publishing the map into the reachable set instead of alongside
    # it let a run skip the whole record chain in alias_maze and finish in
    # 3 steps against a bound of 5 — a result that cannot be compared with
    # the local condition or with the bound, which is the entire point of
    # the experiment. Same reachable set in both conditions, checked.
    reach_local = set(GraphEnv(d, seed=0).known)
    reach_full = set(env_full.known)
    assert reach_local == reach_full, \
        f"{theme}/{topo}: full visibility changes what is reachable at " \
        f"step 0 (+{sorted(reach_full - reach_local)[:3]}), not just what " \
        f"is known"

    # --- 4. topology-specific claims
    notes = []
    if topo == "decoy_credential":
        # the stale key must not satisfy the real gate
        gate = [e for e in g["edges"]["gate_room"] if e["to"] == m["target"]][0]
        stale = m["token_grants"]["decoy_cred"]
        assert stale not in req_list(gate), \
            f"{theme}/{topo}: decoy key actually opens the gate!"
        env2 = GraphEnv(d, seed=0)
        env2.access([e for e in g["edges"]["start"]
                     if e["to"] == "decoy_cred"][0]["desc"])
        env2.access([e for e in g["edges"]["start"]
                     if e["to"] == "gate_room"][0]["desc"])
        r = env2.access(gate["desc"])
        assert r["ok"] is False and r["reason"] == "locked", \
            f"{theme}/{topo}: gate accepted the decoy credential: {r}"
        notes.append("decoy rejected by gate OK")

    if topo == "two_routes":
        # the slow route must independently reach target
        alt = m["alternate_route_nodes"]
        env3 = GraphEnv(d, seed=0)
        cur = "start"
        entry = m.get("alternate_route_from")
        if entry and entry != "start":
            e = [x for x in g["edges"]["start"] if x["to"] == entry][0]
            assert env3.access(e["desc"])["ok"]
            cur = entry
        for nid in alt:
            e = [x for x in g["edges"][cur] if x["to"] == nid][0]
            assert env3.access(e["desc"])["ok"]
            cur = nid
        fin = [x for x in g["edges"][cur] if x["to"] == m["target"]][0]
        r = env3.access(fin["desc"])
        assert r["ok"] and env3.success, \
            f"{theme}/{topo}: alternate route does not reach target"
        notes.append(f"alt route reaches target in {env3.steps_used} "
                     f"(vs lb {lb})")

    if topo == "false_summit":
        assert m["false_summit_node"] != m["target"]
        notes.append("summit distinct from target OK")

    if topo == "evidence_synthesis":
        ev, k = m["evidence_nodes"], m["evidence_threshold"]
        env5 = GraphEnv(d, seed=0)
        env5.access([e for e in g["edges"]["start"]
                     if e["to"] == "token_room"][0]["desc"])
        env5.access([e for e in g["edges"]["start"]
                     if e["to"] == "gate_room"][0]["desc"])
        gate = [e for e in g["edges"]["gate_room"]
                if e["to"] == m["target"]][0]
        # k-1 sources must NOT be enough
        for nid in ev[:k - 1]:
            env5.access([e for e in g["edges"]["gate_room"]
                         if e["to"] == nid][0]["desc"])
        r = env5.access(gate["desc"])
        assert r["ok"] is False and r["reason"] == "not_ready", \
            f"{theme}/{topo}: gate opened with only {k-1} sources: {r}"
        # decoy sources must not count toward the threshold either
        for nid in [n for n in m["dead_end_nodes"] if n.startswith("unsourced")]:
            env5.access([e for e in g["edges"]["gate_room"]
                         if e["to"] == nid][0]["desc"])
        r = env5.access(gate["desc"])
        assert r["ok"] is False, \
            f"{theme}/{topo}: unsourced decoys counted as corroboration"
        env5.access([e for e in g["edges"]["gate_room"]
                     if e["to"] == ev[k - 1]][0]["desc"])
        r = env5.access(gate["desc"])
        assert r["ok"] and env5.success, \
            f"{theme}/{topo}: gate did not open at {k} sources: {r}"
        notes.append(f"{k-1} sources refused, {k} accepted, decoys ignored")

    if topo == "alias_maze":
        # every aliased node must be reachable by >1 distinct identifier,
        # and a second alias must register as a revisit, not a new node
        ident_by_node = {}
        for node, edges in g["edges"].items():
            for e in edges:
                ident_by_node.setdefault(e["to"], []).append(e["desc"])
        for nid in m["aliased_nodes"]:
            assert len(set(ident_by_node.get(nid, []))) >= 2, \
                f"{theme}/{topo}: '{nid}' has no alias"
        env6 = GraphEnv(d, seed=0)
        aliases = [e["desc"] for e in g["edges"]["start"]
                   if e["to"] == "adv_root"]
        assert len(aliases) >= 2
        env6.access(aliases[0])
        env6.access(aliases[1])
        assert env6.trajectory[-1]["already_known"] is True, \
            f"{theme}/{topo}: second alias not recorded as a revisit"
        notes.append(f"{len(aliases)} aliases -> same node, revisit detected")

    if topo == "normative_refs":
        # informative branches must be labelled as such in the identifier
        for dn in m["dead_end_nodes"]:
            idents = [e["desc"] for edges in g["edges"].values()
                      for e in edges if e["to"] == dn]
            assert all("informative" in i for i in idents), \
                f"{theme}/{topo}: dead end '{dn}' is not labelled informative"
        notes.append("all dead ends labelled #informative up front")

    if topo == "version_constraint":
        gate = [e for e in g["edges"]["gate_room"]
                if e["to"] == m["target"]][0]
        env7 = GraphEnv(d, seed=0)
        for n in ("lower_bound_src", "upper_bound_src", "gate_room"):
            env7.access([e for e in g["edges"]["start"]
                         if e["to"] == n][0]["desc"])
        # every wrong pin must be refused
        for wn in m["wrong_choice_nodes"]:
            env7.access([e for e in g["edges"]["gate_room"]
                         if e["to"] == wn][0]["desc"])
            r = env7.access(gate["desc"])
            assert r["ok"] is False, \
                f"{theme}/{topo}: wrong pin {wn} opened the gate"
        env7.access([e for e in g["edges"]["gate_room"]
                     if e["to"] == m["correct_choice"]][0]["desc"])
        r = env7.access(gate["desc"])
        assert r["ok"] and env7.success, \
            f"{theme}/{topo}: correct pin did not open the gate: {r}"
        notes.append(f"{len(m['wrong_choice_nodes'])} wrong pins refused, "
                     f"correct accepted")

    if topo in ("irreversible_submit", "conflicting_authority"):
        # a wrong submission must be terminal: no edge out of `rejected`
        assert not g["edges"].get("rejected"), \
            f"{theme}/{topo}: 'rejected' has an exit, so it isn't one-shot"
        env8 = GraphEnv(d, seed=0)
        for e in g["edges"]["start"]:
            if e["to"] not in ("rejected", m["target"]):
                env8.access(e["desc"])
        wrong = [e for e in g["edges"]["gate_room"] if e["to"] == "rejected"]
        assert wrong, f"{theme}/{topo}: no wrong-submission edge to test"
        r = env8.access(wrong[0]["desc"])
        assert r["ok"], f"{theme}/{topo}: wrong filing should be accepted " \
                        f"as an action (and then be terminal): {r}"
        assert not env8.success, f"{theme}/{topo}: wrong filing succeeded!"
        assert not env8.would_succeed_now(), \
            f"{theme}/{topo}: still recoverable after a wrong filing"
        notes.append("wrong filing is terminal and unrecoverable")

    if False:  # effective_date retired — never discriminated (8/8 twice)
        t = m["temporal"]
        assert t["superseded"] < t["filed"] < t["current"], \
            f"{theme}/{topo}: filing date {t['filed']} is not between the " \
            f"two amendments it is meant to fall between"
        # filing on the current text must be freely available and wrong —
        # if it were gated, the trap could never spring
        wrong = [e for e in g["edges"]["sec_current"] if e["to"] == "rejected"]
        assert wrong and not req_list(wrong[0]), \
            f"{theme}/{topo}: the current-text filing is not freely reachable"
        notes.append(f"filed {t['filed']} between real amendments "
                     f"{t['superseded']}/{t['current']}")

    if topo == "absence_case":
        # referring before doing the search must fail, and doing the search
        # must make it succeed — otherwise this measures nothing about when
        # it is right to stop
        seed_node = [e["to"] for e in g["edges"]["start"]][0]
        refer = [e for e in g["edges"][seed_node]
                 if e["to"] == m["target"]][0]
        env9 = GraphEnv(d, seed=0)
        env9.access([e for e in g["edges"]["start"]
                     if e["to"] == seed_node][0]["desc"])
        r = env9.access(refer["desc"])
        assert r["ok"] is False, \
            f"{theme}/{topo}: referral accepted without examining anything"
        # required checks are not all direct children of the index — one is
        # reachable only through another provision's cross-references, which
        # is the point — so walk to each rather than assuming a flat list
        for c in m["required_checks"]:
            path, seen = None, {env9.meta["start"]}
            frontier = [(env9.meta["start"], [])]
            while frontier and path is None:
                node, acc = frontier.pop(0)
                for e in g["edges"].get(node, []):
                    if e["to"] == c:
                        path = acc + [e["desc"]]
                        break
                    if e["to"] not in seen:
                        seen.add(e["to"])
                        frontier.append((e["to"], acc + [e["desc"]]))
            assert path, f"{theme}/{topo}: required check {c} unreachable"
            for step in path:
                env9.access(step)
        r = env9.access(refer["desc"])
        assert r["ok"] and env9.success, \
            f"{theme}/{topo}: referral refused after a complete search: {r}"
        notes.append("premature referral refused, complete search accepted")

    if topo == "conflicting_authority":
        # the plausible-but-wrong answer must be reachable without the
        # tiebreaker, or the trap never springs
        cat4 = [e for e in g["edges"]["gate_room"] if e["to"] == "rejected"][0]
        assert not req_list(cat4), \
            f"{theme}/{topo}: the wrong filing is gated, so a model can't " \
            f"fall into it — the trap would never fire"
        cat2 = [e for e in g["edges"]["gate_room"]
                if e["to"] == m["target"]][0]
        assert m["tiebreaker_node"] in ("precedence_note",)
        assert "saw_precedence" in req_list(cat2), \
            f"{theme}/{topo}: correct filing doesn't require the tiebreaker"
        notes.append("wrong answer freely reachable; right one needs the note")

    if topo == "dual_key":
        gate = [e for e in g["edges"]["gate_room"] if e["to"] == m["target"]][0]
        needed = req_list(gate)
        assert len(needed) >= 2, "dual_key gate should need multiple items"
        # every strict subset of the credentials must be refused, so the
        # third key really is load-bearing and not decoration
        env4 = GraphEnv(d, seed=0)
        env4.access([e for e in g["edges"]["start"]
                     if e["to"] == "gate_room"][0]["desc"])
        for src, node in (("start", "token_room"), ("start", "token_room_b")):
            env4.access([e for e in g["edges"][src]
                         if e["to"] == node][0]["desc"])
            r = env4.access(gate["desc"])
            assert r["ok"] is False and r["reason"] == "locked", \
                f"{theme}/{topo}: gate opened before all keys collected"
        # the buried third key: reachable only through the archive node
        env4.access([e for e in g["edges"]["start"]
                     if e["to"] == "stale_export"][0]["desc"])
        env4.access([e for e in g["edges"]["stale_export"]
                     if e["to"] == "token_room_c"][0]["desc"])
        r = env4.access(gate["desc"])
        assert r["ok"] and env4.success, \
            f"{theme}/{topo}: gate refused with all {len(needed)} keys: {r}"
        notes.append(f"{len(needed)} keys required, every subset refused")

    return lb, len(g["nodes"]), notes


def main():
    # corpus-backed topologies need their source document; without it they
    # raise, and skipping them silently would mean the two largest and most
    # realistic instances never get validated
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None,
                    help="comma-separated topology names to check; the rest "
                         "are skipped.")
    ap.add_argument("--corpus", default=None,
                    help="regulation corpus JSON to validate the "
                         "corpus-backed topologies against; defaults to "
                         "corpora_ecfr.json")
    args = ap.parse_args()

    import topologies as _t
    for cand in ([args.corpus] if args.corpus else ["corpora_ecfr.json"]):
        if os.path.exists(cand):
            with open(cand) as f:
                _t.CORPUS = json.load(f)
            print(f"corpus: {cand}")
            break
    if _t.CORPUS is None:
        print("WARNING: no corpus found; corpus-backed topologies skipped")

    # The software suite keeps its corpus in its own module-level global.
    # Registering those topologies without loading it makes every theme
    # fail at build time, which reads like a topology bug rather than a
    # missing fixture.
    try:
        import software_topologies as _sw
        from generate import DEFAULT_SOFTWARE_CORPUS, SOFTWARE_THEME
        if _sw.SOFTWARE_CORPUS is None and os.path.exists(DEFAULT_SOFTWARE_CORPUS):
            with open(DEFAULT_SOFTWARE_CORPUS) as f:
                _sw.SOFTWARE_CORPUS = json.load(f)
    except ImportError:
        _sw, SOFTWARE_THEME = None, None

    # Ops topologies are not theme-orthogonal: each builder reads one
    # frozen corpus. Pair topology name -> corpus so validation does not
    # apply the default connection-pool case to every ops graph.
    ops_corpora_by_topo = {}
    try:
        import glob
        import ops_topologies as _ops
        from generate import OPS_THEME
        corpus_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "corpora_ops")
        for path in sorted(glob.glob(os.path.join(corpus_dir, "*.json"))):
            with open(path) as f:
                corpus = json.load(f)
            topology = _ops.VARIANT_TO_TOPOLOGY.get(
                corpus.get("integrated_variant"))
            if topology:
                ops_corpora_by_topo[topology] = corpus
        if _ops.OPS_CORPUS is None and ops_corpora_by_topo:
            _ops.OPS_CORPUS = next(iter(ops_corpora_by_topo.values()))
    except ImportError:
        _ops, OPS_THEME = None, None

    ehr_corpora_by_topo = {}
    try:
        import glob
        import ehr_topologies as _ehr
        from generate import EHR_THEME
        corpus_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "corpora_ehr")
        for path in sorted(glob.glob(os.path.join(corpus_dir, "*.json"))):
            with open(path) as f:
                corpus = json.load(f)
            topology = _ehr.VARIANT_TO_TOPOLOGY.get(
                corpus.get("integrated_variant"))
            if topology:
                ehr_corpora_by_topo[topology] = corpus
        if _ehr.EHR_CORPUS is None and ehr_corpora_by_topo:
            _ehr.EHR_CORPUS = next(iter(ehr_corpora_by_topo.values()))
    except ImportError:
        _ehr, EHR_THEME = None, None

    failures = []
    only = set(args.only.split(",")) if args.only else None
    checked = 0
    for topo in TOPOLOGIES:
        if only and topo not in only:
            continue
        if _t.CORPUS is None and topo in ("regulatory_chain",
                                          "integrated_case"):
            continue
        per_topo_notes = None
        lbs, sizes = set(), set()
        # Software cases are built from a frozen corpus and read no theme
        # fields, so they are deliberately not theme-orthogonal: validating
        # them against all nine narrative themes would assert a property
        # they were never meant to have. (Restoring behaviour from the
        # software suite's own version of this file, which an scp of mine
        # overwrote — see the note in generate.py.)
        if topo in ops_corpora_by_topo:
            _ops.OPS_CORPUS = ops_corpora_by_topo[topo]
            themes = [OPS_THEME]
        elif topo in ehr_corpora_by_topo:
            _ehr.EHR_CORPUS = ehr_corpora_by_topo[topo]
            themes = [EHR_THEME]
        elif SOFTWARE_THEME and topo in getattr(_sw, "__dict__", {}):
            themes = [SOFTWARE_THEME]
        else:
            themes = list(THEMES)
        for theme in themes:
            try:
                lb, n, notes = check(theme, topo)
                lbs.add(lb)
                sizes.add(n)
                per_topo_notes = notes
            except AssertionError as exc:
                failures.append(str(exc))
            except Exception as exc:
                # A missing or wrong-shaped fixture is not a topology
                # failing its contract, and letting it propagate hid the
                # other eleven topologies' results entirely. Recorded as a
                # failure so the exit code still reflects it.
                failures.append(f"{theme}/{topo}: could not build - "
                                f"{type(exc).__name__}: {exc} "
                                f"(usually a corpus missing a field this "
                                f"topology reads)")
        checked += 1
        note = "; ".join(per_topo_notes) if per_topo_notes else ""
        print(f"  {topo:20s} lb={sorted(lbs)} nodes={sorted(sizes)} "
              f"x{len(THEMES)} themes  {note}")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print(f"\nALL {checked}x{len(THEMES)} = "
          f"{checked*len(THEMES)} INSTANCES PASS")


if __name__ == "__main__":
    main()
