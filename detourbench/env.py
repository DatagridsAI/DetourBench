#!/usr/bin/env python3
"""Stateful DetourBench environment — globally-addressable-resource model.

Interaction model (post-reskin): a real `read_file`/`run_sql`/`call_endpoint`
tool has no notion of "you must be standing next to this to use it" — you can
open any file, query any table, hit any URL you know the identifier for. So
addressability here is governed by *discovery*, not position: a resource
becomes accessible the moment its identifier has been revealed (via an
initial reveal, or by successfully accessing whatever node exposes it), and
stays accessible for the rest of the episode regardless of what else the
agent has done since. Available actions are
``union(OutEdges(v) for v in visited)``, not ``OutEdges(current_node)``.
This is what "partial observability" actually means in this framing — you
can't reach what you haven't discovered yet, but once discovered, there's
no artificial positional gate on using it.

Physical isolation contract is unchanged: this class holds the full graph in
memory (loaded from generate.py's grader-only output); the only way any of
it reaches the agent is through look()/access() return values.
"""
import json
import random


PERTURB_LEVELS = ["INFO", "DEBUG", "WARN"]


def _req_list(info):
    """`requires` may be None, a single item, or a list (dual_key topology)."""
    r = info.get("requires")
    if not r:
        return []
    return [r] if isinstance(r, str) else list(r)


def _visited_ok(info, visited):
    """`requires_visited` may be None, a single node, or a list of which
    `requires_visited_n` must have been visited (evidence_synthesis's
    N-of-M corroboration gate)."""
    rv = info.get("requires_visited")
    if not rv:
        return True
    rv = [rv] if isinstance(rv, str) else list(rv)
    need = info.get("requires_visited_n") or len(rv)
    return sum(1 for x in rv if x in visited) >= need


def _tokens_ok(info, inventory):
    """`requires_any` is N-of-M over inventory tokens (category
    equivalence). Independent of the AND-list `requires`."""
    ra = info.get("requires_any")
    if not ra:
        return True
    ra = [ra] if isinstance(ra, str) else list(ra)
    need = info.get("requires_any_n") or len(ra)
    return sum(1 for token in ra if token in inventory) >= need


def render_loop_desc(rng, meta):
    host = rng.choice(meta["loop_host_vocab"])
    lvl = rng.choice(PERTURB_LEVELS)
    n = rng.randint(1000, 9999)
    return meta["loop_desc_template"].format(host=host, level=lvl, n=n)


def render_loop_token(rng, meta):
    """A live, per-visit identifier for a loop-trap edge. This must be the
    exact, complete string a call_endpoint(url=...) call would use — earlier
    drafts returned a bare `tok_xxxx` token and expected the model to pass
    that alone, which doesn't match how any real paginated API actually
    works (you always see next_token embedded in a full next-page URL/link,
    never a bare token you're expected to guess how to submit). A model
    that behaves *realistically* here (constructing `...logs?next_token=…`
    itself) was getting penalized with a spurious not_found — i.e. the bug
    rewarded literal-string luck over realistic tool use. Returning the
    complete URL removes the ambiguity entirely."""
    tok = "".join(rng.choice("0123456789abcdef") for _ in range(10))
    return f"{meta['loop_base_url']}?next_token=tok_{tok}"


def _norm_ident(v):
    """A section identifier reduced to what identifies it.

    The graph prints "\u00a7 226.5b"; an agent may write that, "226.5b",
    "Section 226.5b" or "sec. 226.5b". They name the same provision, and
    which one an agent reaches for is a habit rather than a capability.
    """
    s = str(v).strip().lower()
    for junk in ("\u00a7", "sections", "section", "secs.", "sec.", "secs",
                 "sec"):
        s = s.replace(junk, " ")
    return " ".join(s.split()).replace(" ", "")


class GraphEnv:
    """`visibility` selects between the two conditions the Local-vs-Full
    experiment compares.

    "local" (default) is the benchmark proper: identifiers become
    addressable only once something has revealed them, so a run pays for
    discovery as well as for execution.

    "full" hands over the map at step zero — every non-perturbed
    identifier, what each one exposes, and what each one requires — while
    still charging a step per access. Discovery is then free and any
    remaining excess over the lower bound is planning, not exploration.
    That is the whole point of the condition: it splits one number into
    the two bottlenecks it confounds.

    What "full" must never include is the evaluator's own answer key:
    which nodes are dead ends, which region each node belongs to, the
    lower bound, the oracle path, or which node is the target. Those live
    in the same `meta` dict as the graph, so the split is enforced here
    and asserted in validate_topologies rather than left to care. Note
    that a reader of the full map can *infer* that some branches lead
    nowhere — that inference is the planning ability under test, and is
    not the same thing as being handed the labels.
    """

    def __init__(self, instance_dir, seed=0, step_budget=40,
                 visibility="local"):
        with open(f"{instance_dir}/graph_full.json") as f:
            full = json.load(f)
        self.graph = full["graph"]
        self.meta = full["meta"]
        self.rng = random.Random(seed)

        self.cur = self.meta["start"]
        self.inventory = set()
        self.step_budget = step_budget
        self.steps_used = 0
        self.done = False
        self.success = False
        self.fail_reason = None

        # identifier (as shown to the agent) -> {edge_id, to, resource_type,
        # requires}. Accumulates for the whole episode; entries are never
        # removed. Perturbed (loop) edges get a freshly generated identifier
        # each time their source node is (re)visited, so the same underlying
        # edge can appear under several different identifiers over an
        # episode — deliberately, see generate.py's docstring.
        self.known = {}
        self.node_visit_count = {self.cur: 1}  # start counts as already visited
        self.trajectory = []  # grader-only bookkeeping
        # Set by the harness before each turn's tool calls are
        # dispatched, so a step records when it was issued and not
        # only its order. 0 when a caller never sets it.
        self.cur_turn = 0
        self.visibility = visibility

        self._reveal(self.cur)

        # The map is information, never a pass. An early version put every
        # identifier straight into `known`, which does not just remove the
        # cost of discovery — it removes the structure: alias_maze's route
        # runs through three superseded case records to reach the edge that
        # files the determination, and with that edge pre-granted
        # claude-opus-4-8 skipped the entire chain and finished in 3 steps
        # against a lower bound of 5. A run that cannot be compared to the
        # bound cannot be compared to the local condition either, which is
        # the whole experiment. So the full map lives separately from what
        # is reachable, and reachability keeps local semantics in both
        # conditions.
        #
        # Perturbed identifiers stay out of the map: they are regenerated
        # per visit by design, so there is no stable string to publish, and
        # listing them would quietly disable the memoryless-loop mechanism.
        self.full_map = {}
        if visibility == "full":
            for node in self.graph["nodes"]:
                for e in self.graph["edges"].get(node, []):
                    if not e.get("perturb"):
                        self.full_map.setdefault(e["desc"], {
                            "to": e["to"],
                            "resource_type": e["resource_type"],
                            "requires": e["requires"],
                            "requires_visited": e.get("requires_visited"),
                            "requires_visited_n": e.get("requires_visited_n"),
                            "requires_any": e.get("requires_any"),
                            "requires_any_n": e.get("requires_any_n"),
                        })

    # ------------------------------------------------------------- internal
    def _reveal(self, node):
        """Expose `node`'s outgoing edges as newly-known identifiers."""
        for e in self.graph["edges"][node]:
            ident = render_loop_token(self.rng, self.meta) if e.get("perturb") else e["desc"]
            self.known[ident] = {
                "edge_id": e["edge_id"], "to": e["to"],
                "resource_type": e["resource_type"], "requires": e["requires"],
                "requires_visited": e.get("requires_visited"),
                # must be carried through: without it an N-of-M gate
                # silently becomes M-of-M (defaults to len(list)), which
                # makes the generator's own oracle path unwalkable.
                "requires_visited_n": e.get("requires_visited_n"),
                "requires_any": e.get("requires_any"),
                "requires_any_n": e.get("requires_any_n"),
            }

    def _render_context(self, node):
        desc = self.graph["nodes"][node]["desc"]
        if not desc:
            desc = render_loop_desc(self.rng, self.meta)
        return desc

    # --------------------------------------------------------- agent-facing
    def look(self):
        """Everything discovered so far, plus a description of the latest
        successful access (for narrative continuity only — does not gate
        what's addressable)."""
        source = self.full_map if self.visibility == "full" else self.known
        resources = []
        for ident, v in source.items():
            row = {"identifier": ident, "resource_type": v["resource_type"]}
            if self.visibility == "full":
                # accessible now, or still behind something you haven't
                # opened — the map tells you the route, not a way past it
                row["accessible"] = ident in self.known
                # the map: what this one exposes, and what it demands.
                # Node *contents* still cost a step to read — only the
                # discovery of the structure is free in this condition.
                onward = [e["desc"] for e in self.graph["edges"].get(v["to"], [])
                          if not e.get("perturb")]
                if onward:
                    row["leads_to"] = onward
                req = _req_list(v)
                if req:
                    row["requires"] = req
                if v.get("requires_visited"):
                    rv = v["requires_visited"]
                    need = {rv} if isinstance(rv, str) else set(rv)
                    # translate internal node names into the identifiers an
                    # agent actually uses; the raw node ids ("loop_0",
                    # "ruling") are evaluator-side vocabulary and would leak
                    # structure the map is not supposed to spell out
                    row["requires_first"] = sorted(
                        {e["desc"] for es in self.graph["edges"].values()
                         for e in es if e["to"] in need and not e.get("perturb")})
            resources.append(row)
        return {"context": self._render_context(self.cur),
                "known_resources": resources,
                "actions_remaining": self.step_budget - self.steps_used}


    def submit_determination(self, fields):
        """Check a structured determination against what the task expects.

        `fields` is whatever the agent asserts - typically the provisions it
        holds to govern and the basis for that. The task declares the
        expected shape and values in meta["verdict_spec"]:

            {"required": {"provisions": ["4.81", "4.84"],
                          "basis": "text-in-force"},
             "unordered": ["provisions"]}

        Comparison is exact except for fields named in `unordered`, which are
        compared as sets so an agent is not penalised for listing correct
        provisions in a different order. A wrong determination ends a
        one-shot episode exactly as a wrong filing does; there is no partial
        credit, because a determination that is half right is not a
        determination.
        """
        if self.done:
            return {"ok": False, "reason": "episode_ended"}
        spec = (self.meta or {}).get("verdict_spec")
        if not spec:
            return {"ok": False, "reason": "no_determination_expected"}

        self.steps_used += 1
        entry = {"step": self.steps_used, "identifier": "<determination>",
                 "fields": fields}
        entry["turn"] = self.cur_turn

        required = spec.get("required") or {}
        unordered = set(spec.get("unordered") or ())
        prefix = set(spec.get("prefix_match") or ())
        wrong = []
        for key, want in required.items():
            got = fields.get(key)
            if key in unordered:
                ok = (got is not None
                      and set(map(_norm_ident, got))
                      == set(map(_norm_ident, want)))
            elif key in prefix:
                # the label has to be right; what follows it is the agent's
                # own reasoning and is not being marked
                ok = str(got or "").strip().lower().startswith(
                    str(want).strip().lower())
            else:
                ok = str(got) == str(want)
            if not ok:
                wrong.append(key)

        if wrong:
            entry.update(valid=True, correct=False, wrong_fields=wrong)
            self.trajectory.append(entry)
            # a determination is a filing: on one-shot tasks it is spent
            if self.meta.get("one_shot"):
                self.done = True
                self.success = False
                self.fail_reason = "terminal_state"
            else:
                self._maybe_end_budget()
            return {"ok": False, "reason": "wrong_determination",
                    "wrong_fields": wrong}

        entry.update(valid=True, correct=True)
        self.trajectory.append(entry)
        self.done = True
        self.success = True
        return {"ok": True, "result": spec.get("accepted_message")
                or "Determination accepted; the case is closed.",
                "episode_done": True, "success": True}

    def access(self, identifier):
        """Attempt to use a previously-revealed identifier. Returns a dict
        with ok/ new context / error — resource_type-agnostic; the harness
        formats the error message per calling tool."""
        if self.done:
            return {"ok": False, "reason": "episode_ended"}

        self.steps_used += 1
        entry = {"step": self.steps_used, "identifier": identifier,
                 "turn": self.cur_turn}

        info = self.known.get(identifier)
        if info is None:
            # In the full condition the map lists things that exist but are
            # not open yet. Reporting those as "not found" would be a lie
            # the agent can see through, and would make the map look
            # unreliable; it gets its own reason so the trajectory
            # distinguishes "invented an identifier" from "went for a real
            # one too early".
            if identifier in self.full_map:
                entry.update(valid=False, reason="not_yet_reachable")
                self.trajectory.append(entry)
                self._maybe_end_budget()
                return {"ok": False, "reason": "not_yet_reachable"}
            entry.update(valid=False, reason="unknown_identifier")
            self.trajectory.append(entry)
            self._maybe_end_budget()
            return {"ok": False, "reason": "not_found"}

        missing = [r for r in _req_list(info) if r not in self.inventory]
        if missing:
            entry.update(valid=False, reason="locked", to=info["to"])
            self.trajectory.append(entry)
            self._maybe_end_budget()
            if self.meta.get("hide_missing_requirements"):
                return {"ok": False, "reason": "locked",
                        "requirement": "additional evidence"}
            labels = self.meta.get("requirement_labels", {})
            missing_display = [labels.get(r, r) for r in missing]
            return {"ok": False, "reason": "locked",
                    "requirement": ", ".join(missing_display)}

        if not _visited_ok(info, self.node_visit_count):
            entry.update(valid=False, reason="not_ready", to=info["to"])
            self.trajectory.append(entry)
            self._maybe_end_budget()
            return {"ok": False, "reason": "not_ready"}

        if not _tokens_ok(info, self.inventory):
            entry.update(valid=False, reason="not_ready", to=info["to"])
            self.trajectory.append(entry)
            self._maybe_end_budget()
            return {"ok": False, "reason": "not_ready"}

        new_node = info["to"]
        was_known_node = new_node in self.node_visit_count
        self.node_visit_count[new_node] = self.node_visit_count.get(new_node, 0) + 1
        # A topology may hand out several distinct credentials, or a
        # deliberately stale one that satisfies no gate (see topologies.py).
        granted = self.meta.get("token_grants", {}).get(new_node)
        if granted:
            self.inventory.update([granted] if isinstance(granted, str)
                                  else granted)

        self.cur = new_node
        self._reveal(new_node)
        entry.update(valid=True, to=new_node, already_known=was_known_node,
                     revisit_count=self.node_visit_count[new_node])
        self.trajectory.append(entry)

        if new_node == self.meta["target"]:
            self.done = True
            self.success = True
            return {"ok": True, "episode_done": True, "success": True,
                    "result": self._render_context(new_node)}

        # Terminal failure states. Without these, a topology that declares
        # "one submission per ticket" doesn't actually have one: entering
        # the rejection node leaves every other submission edge revealed
        # and usable, so a model simply files again. Irreversibility has to
        # be enforced by the environment, not asserted in the prose.
        if new_node in (self.meta.get("terminal_fail_nodes") or []):
            self.done = True
            self.success = False
            self.fail_reason = "terminal_state"
            return {"ok": True, "episode_done": True, "success": False,
                    "result": self._render_context(new_node)}

        self._maybe_end_budget()
        return {"ok": True, "episode_done": self.done,
                "result": self._render_context(new_node)}

    def _maybe_end_budget(self):
        if self.steps_used >= self.step_budget and not self.done:
            self.done = True
            self.success = False

    def would_succeed_now(self):
        """True if some already-revealed edge from an already-visited node
        leads straight to target and every precondition it has (requires /
        requires_visited) is already satisfied — i.e. the episode could
        still be won with zero new discovery, just by committing to a
        known-good action. Used to distinguish a *recoverable* give-up
        (agent had already done the hard part and simply didn't follow
        through — e.g. dismissed a working path as "non-terminating" after
        one unlucky probe) from a genuinely stuck one (still missing a
        credential or hasn't found the real path at all). See agent_harness
        run_episode's outcome classification."""
        if self.done and not self.success:
            return False        # ended: a terminal failure is not recoverable
        target = self.meta["target"]
        for node in self.node_visit_count:
            for e in self.graph["edges"].get(node, []):
                if e["to"] != target:
                    continue
                if any(r not in self.inventory for r in _req_list(e)):
                    continue
                if not _visited_ok(e, self.node_visit_count):
                    continue
                if not _tokens_ok(e, self.inventory):
                    continue
                return True
        return False
