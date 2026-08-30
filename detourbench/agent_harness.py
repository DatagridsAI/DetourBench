#!/usr/bin/env python3
"""Tool-calling loop for the data-pipeline-skinned DetourBench.

The model gets four tools that read like a real internal toolkit:
`list_related_resources`, `read_file`, `run_sql`, `call_endpoint`. None of
them are real — each is a closed-vocabulary lookup against identifiers the
environment has revealed so far (see env.py), never a real shell, SQL
engine, or HTTP client. This is deliberate: giving the model an actual
execution surface (real bash, a real SQL parser) would let it bypass the
partial-observability premise entirely by reading the full graph off disk or
solving the topology analytically instead of navigating it — which is
exactly the failure mode this benchmark exists to avoid.

Routing: whichever of read_file/run_sql/call_endpoint is called, the
identifier string the model supplies (a path, a `FROM <table>` clause, or a
URL) is looked up directly via env.access(identifier) — against the
environment's *global* revealed-resource registry, not just what's exposed
from wherever the agent "currently" is. That's a deliberate departure from a
literal spatial maze: a real read_file/run_sql/call_endpoint has no concept
of standing next to a resource, so once the model has learned an identifier
exists, it should always be able to attempt it, right or wrong. Getting the
tool type wrong for a resource's real type isn't specially penalized here —
env.access() doesn't check resource_type at all — but the identifier still
has to be one that's actually been revealed.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time

from openai import OpenAI

from env import GraphEnv


def log(msg):
    print(msg, file=sys.stderr, flush=True)



# Offered only when the instance declares a verdict_spec. A task that ends
# in a filing keeps the four-tool interface it was measured on.
DETERMINATION_TOOL = {
    "type": "function",
    "function": {
        "name": "file_determination",
        "description": (
            "File the determination for this matter. State which provisions "
            "govern and on what basis. This is the submission: a case admits "
            "one, and a determination that is not correct disposes of the "
            "case wrongly."),
        "parameters": {
            "type": "object",
            "properties": {
                "provisions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": ("Every provision that governs the matter, "
                                    "by section number, e.g. \"4.81\"."),
                },
                "basis": {
                    "type": "string",
                    "description": ("The basis on which the determination is "
                                    "made, as the procedure for this matter "
                                    "describes it."),
                },
                "year": {
                    "type": "string",
                    "description": ("Where the matter turns on when a "
                                    "provision stood in a particular form, "
                                    "the four-digit year of the amendment "
                                    "the determination rests on."),
                },
            },
            "required": ["provisions", "basis"],
        },
    },
}


PROMPT_VERSION = "closed-benchmark-v3"


def build_system_prompt(ticket_text):
    """The ticket line comes straight from the graph's own start-node text
    (theme-specific, see generate.py's THEMES) rather than being duplicated
    here — everything else below is domain-agnostic and applies to any
    theme."""
    return f"""\
You are an engineer given this ticket: {ticket_text}

This is a closed benchmark over frozen records. The supplied tools are \
simulated and have no external effects. Work independently, and verify the \
evidence before any one-shot or terminal action.

Discovered resources stay available. Resource opens are charged, so avoid \
speculative or repeated opens. If a resource is unavailable or not ready, \
inspect other listed records. Follow the tool schemas and call \
`list_related_resources` first.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_related_resources",
            "description": "List tables, files, and endpoints discoverable "
                            "from your current investigation context. Free "
                            "to call; does not change state.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a config/doc file by path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": "Retrieve one record from a record store by "
                            "its identifier. A lookup by name, not "
                            "a query language: projections, filters "
                            "and joins are not supported, and table "
                            "catalogues cannot be listed.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "call_endpoint",
            "description": "Call an internal HTTP endpoint by URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "headers": {"type": "object",
                                "description": "Optional request headers."},
                },
                "required": ["url"],
            },
        },
    },
]

TOOL_TO_RTYPE = {"read_file": "file", "run_sql": "table",
                  "call_endpoint": "endpoint"}


def extract_identifier(tool_name, args):
    """Tolerant of the common parameter-name variants a model might
    reasonably use instead of our declared schema name (e.g. `file_path`
    instead of `path`) — a strict single-key lookup silently returns "" on
    a mismatch, which then reads as a bogus not_found error and can send a
    model down a long, wrong-diagnosis rabbit hole (confirmed: one episode
    inflated from ~8 genuine steps to 33 wasted ones chasing "the read_file
    tool must be broken" before it worked around the parameter mismatch
    entirely). This benchmark measures navigation efficiency, not whether a
    model can guess an undocumented exact parameter name — that's noise we
    don't want contaminating RSR."""
    if tool_name == "read_file":
        for key in ("path", "file_path", "filepath", "filename"):
            if args.get(key):
                return args[key]
        return ""
    if tool_name == "run_sql":
        for key in ("query", "sql", "sql_query"):
            q = args.get(key)
            if q:
                m = re.search(r"FROM\s+([A-Za-z0-9_.]+)", q, re.IGNORECASE)
                return m.group(1) if m else q
        return ""
    if tool_name == "call_endpoint":
        for key in ("url", "endpoint", "uri"):
            if args.get(key):
                return args[key]
        return ""
    return ""


def not_found_message(tool_name, identifier):
    if tool_name == "read_file":
        return f"FileNotFoundError: [Errno 2] No such file or directory: '{identifier}'"
    if tool_name == "run_sql":
        return f'psycopg2.errors.UndefinedTable: relation "{identifier}" does not exist'
    if tool_name == "call_endpoint":
        return f"ConnectionError: 404 Not Found — {identifier}"
    return "Error: not found"


def locked_message(tool_name, requirement):
    if tool_name == "call_endpoint":
        return (f"HTTPError: 401 Unauthorized — missing '{requirement}'. "
                f"Obtain the required evidence or credential from the "
                f"already-discovered resources before retrying.")
    return f"PermissionError: access requires '{requirement}', which was not supplied."


def not_ready_message(tool_name):
    if tool_name == "call_endpoint":
        return ("HTTPError: 409 Conflict — this workflow action is not ready. "
                "One or more prerequisite records have not been opened; "
                "collect the remaining discovered evidence, then retry this "
                "same endpoint.")
    return ("Error: not ready — prerequisite records remain unread. "
            "Collect the remaining discovered evidence, then retry.")


def route_tool_call(env, tool_name, args):
    """Resolve a read_file/run_sql/call_endpoint call against the env's
    global revealed-resource registry, and translate the result into a
    realistic per-tool response."""
    identifier = extract_identifier(tool_name, args)
    result = env.access(identifier)

    if not result["ok"]:
        if result["reason"] == "not_found":
            return {"ok": False, "error": not_found_message(tool_name, identifier)}
        if result["reason"] == "locked":
            return {"ok": False,
                     "error": locked_message(tool_name, result["requirement"])}
        if result["reason"] == "not_ready":
            return {"ok": False, "error": not_ready_message(tool_name)}
        if result["reason"] == "not_yet_reachable":
            return {"ok": False,
                     "error": "HTTPError: 403 Forbidden — this resource "
                              "exists but is not yet released to you; it "
                              "becomes available once the record that "
                              "references it has been read."}
        return {"ok": False, "error": "Error: episode already ended"}

    if result.get("episode_done") and result.get("success"):
        return {"ok": True, "result": result["result"], "task_complete": True}

    new_look = env.look()
    return {"ok": True, "result": result["result"],
            "known_resources": new_look["known_resources"]}


FULL_VISIBILITY_NOTE = """\

You have been given the full resource map up front: \
`list_related_resources` already lists every table, file and endpoint in \
this environment, what each one leads on to, and what each one requires. \
Nothing further needs to be discovered. Reading a resource still costs an \
access, so the map is there to let you plan the shortest route to the \
answer rather than to be worked through.
"""



# Gateways that reject non-streaming requests. glm-5.2 on the secondary gateway answers those
# with 429 model_stream_required.
STREAM_ONLY_MODELS = {"glm-5.2"}
# the primary gateway's OpenAI-compat converter drops Claude tool-use on non-streaming
# multi-turn histories: HTTP 200, content=null, tool_calls=[], finish_reason
# stop. Streaming keeps the native tool-call deltas. Confirmed on
# 01_regulatory_t21: Qwen completes the same graph; Opus dies after the
# packet is in the tool history.
STREAM_PREFERRED_MODELS_PREFIX = "claude"
MAX_COMPLETION_TOKENS = 16384
MAX_CONSECUTIVE_API_ERRORS = 5
MAX_CONSECUTIVE_EMPTY_COMPLETIONS = 5
TOOL_REQUIRED_ARGS = {
    "read_file": ("path",),
    "run_sql": ("query",),
    "call_endpoint": ("url",),
    "file_determination": ("provisions", "basis"),
}


class _Fn:
    def __init__(self, name, arguments):
        self.name, self.arguments = name, arguments


class _ToolCall:
    def __init__(self, id, name, arguments):
        self.id, self.type = id, "function"
        self.function = _Fn(name, arguments)

    def model_dump(self):
        """The loop feeds the assistant turn back into `messages`, and
        every SDK tool-call object supports this. Same wire shape."""
        return {"id": self.id, "type": "function",
                "function": {"name": self.function.name,
                             "arguments": self.function.arguments}}


class _Msg:
    def __init__(self, content, tool_calls, reasoning_content=None,
                 finish_reason=None):
        self.content, self.tool_calls = content, tool_calls
        self.reasoning_content = reasoning_content
        self.finish_reason = finish_reason
        self.role = "assistant"


def _uses_streaming(model):
    return (model in STREAM_ONLY_MODELS
            or model.startswith(STREAM_PREFERRED_MODELS_PREFIX))


def _parsed_tool_args(tc):
    raw = getattr(getattr(tc, "function", None), "arguments", None) or ""
    if not str(raw).strip():
        return None
    try:
        args = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return args if isinstance(args, dict) else None


def filter_usable_tool_calls(tool_calls):
    """Keep tool calls whose required arguments survived conversion.

    the primary gateway's Opus converter often keeps the function name and drops the
    path/url payload. A mixed burst (two complete reads plus one
    `read_file({})`) must not discard the complete calls.
    """
    usable = []
    for tc in tool_calls or []:
        name = getattr(getattr(tc, "function", None), "name", None)
        required = TOOL_REQUIRED_ARGS.get(name)
        if not required:
            usable.append(tc)
            continue
        args = _parsed_tool_args(tc)
        if args is not None and all(args.get(key) for key in required):
            usable.append(tc)
    return usable


def tool_calls_lost_in_conversion(tool_calls):
    """True when every tool-use block is missing required arguments."""
    if not tool_calls:
        return False
    return not filter_usable_tool_calls(tool_calls)


def summarize_tool_calls(tool_calls):
    rows = []
    for tc in tool_calls or []:
        fn = getattr(tc, "function", None)
        name = getattr(fn, "name", None) or "?"
        raw = getattr(fn, "arguments", None) or ""
        rows.append(f"{name}({str(raw)[:120]})")
    return rows


def is_dropped_gateway_completion(msg, tool_calls, finish_reason=None):
    """HTTP-200 responses that are not a model decision.

    Observed the primary gateway/Opus shapes:
    - content=null, tool_calls=[], refusal=null, finish_reason=stop
    - finish_reason=length with only an "Oops." reasoning stub
    - tool_calls present but every required argument payload stripped
    """
    if filter_usable_tool_calls(tool_calls):
        return False
    if tool_calls:
        return True
    content = (getattr(msg, "content", None) or "").strip()
    reasoning = (getattr(msg, "reasoning_content", None) or "").strip()
    if not content:
        return True
    truncated = (finish_reason == "length"
                 and content.lower().rstrip(".") == "oops"
                 and (not reasoning or reasoning.lower().rstrip(".") == "oops"))
    return truncated


def _coerce_arg_fragment(value):
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


def ingest_stream_tool_call(acc, tc, *, overwrite_args=False, fallback_index=0):
    """Merge one streamed tool-call fragment into the index-keyed accumulator."""
    index = getattr(tc, "index", None)
    if index is None:
        index = fallback_index
    slot = acc.setdefault(index, {"id": None, "name": None, "args": []})
    if getattr(tc, "id", None):
        slot["id"] = tc.id
    fn = getattr(tc, "function", None)
    if fn is None:
        return
    if getattr(fn, "name", None):
        slot["name"] = fn.name
    frag = _coerce_arg_fragment(getattr(fn, "arguments", None))
    if frag is None:
        return
    if overwrite_args:
        slot["args"] = [frag]
    else:
        slot["args"].append(frag)


def _wire_messages(messages):
    """Coerce null assistant content to empty string for Anthropic replay."""
    out = []
    for message in messages:
        row = dict(message)
        if (row.get("role") in {"assistant", "user", "system"}
                and row.get("content") is None):
            row["content"] = ""
        out.append(row)
    return out


def _assistant_history_message(msg, tool_calls):
    turn = {
        "role": "assistant",
        "content": msg.content if msg.content is not None else "",
        "tool_calls": [tc.model_dump() for tc in tool_calls],
    }
    reasoning = getattr(msg, "reasoning_content", None)
    if reasoning:
        # Dropping thinking/reasoning on replay is how OpenAI-compat
        # converters lose subsequent Claude tool_use blocks.
        turn["reasoning_content"] = reasoning
    return turn


def _stream_completion(client, **kw):
    """Run a streaming completion and return a message in the blocking shape.

    Tool calls arrive as deltas keyed by index: the id and function name
    typically land in the first chunk for that index and the arguments are
    split across later ones, so both are accumulated rather than assigned.
    """
    acc = {}
    content = []
    reasoning = []
    finish_reason = None
    for chunk in client.chat.completions.create(stream=True, **kw):
        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        if getattr(choice, "finish_reason", None):
            finish_reason = choice.finish_reason
        d = getattr(choice, "delta", None)
        if d is not None:
            if getattr(d, "content", None):
                content.append(d.content)
            rc = getattr(d, "reasoning_content", None)
            if rc:
                reasoning.append(rc)
            for tc in (getattr(d, "tool_calls", None) or []):
                ingest_stream_tool_call(
                    acc, tc, fallback_index=len(acc))
        # Some OpenAI-compat converters leave arguments off the deltas
        # and only attach a complete tool_calls array on choice.message.
        assembled = getattr(choice, "message", None)
        if assembled is not None:
            rc = getattr(assembled, "reasoning_content", None)
            if rc and not reasoning:
                reasoning.append(rc)
            if getattr(assembled, "content", None) and not content:
                content.append(assembled.content)
            for i, tc in enumerate(getattr(assembled, "tool_calls", None) or []):
                ingest_stream_tool_call(
                    acc, tc, overwrite_args=True, fallback_index=i)
    calls = [_ToolCall(v["id"] or f"call_{k}", v["name"], "".join(v["args"]))
             for k, v in sorted(acc.items()) if v["name"]]
    return _Msg("".join(content) or None, calls,
                "".join(reasoning) or None, finish_reason)


def run_episode(instance_dir, model, base_url, api_key, out_path,
                 max_turns=60, step_budget=40, seed=0, visibility="local"):
    # max_retries=0: the SDK's own retries stack on top of the 90s
    # per-request timeout below, so a hung gateway took 273s to
    # surface. Retry policy belongs in the loop that logs it.
    client = OpenAI(base_url=base_url, api_key=api_key,
                    max_retries=0)
    # An instance may declare its own budget (difficulty is defined as a
    # multiple of that instance's provable lower bound — see
    # DIFFICULTY_BUDGET in generate.py). Instances generated before that
    # existed carry no budget and keep the old flat default, so previously
    # collected runs stay comparable.
    env = GraphEnv(instance_dir, seed=seed, step_budget=step_budget,
                   visibility=visibility)
    declared = env.meta.get("step_budget")
    if declared:
        env.step_budget = declared
    ticket_text = env.graph["nodes"][env.meta["start"]]["desc"]
    prompt = build_system_prompt(ticket_text)
    if visibility == "full":
        prompt += FULL_VISIBILITY_NOTE

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Begin. Call list_related_resources to "
                                     "see what's available."},
    ]
    turns_used = 0
    api_errors = 0
    empty_completions = 0
    consecutive_errors = 0
    no_tool_call_strikes = 0
    abort_reason = None

    log(f"[{model}] starting episode, max_turns={max_turns} "
        f"step_budget={env.step_budget}")
    # turns_used counts turns the model actually took. A gateway timeout or
    # a malformed HTTP-200 is not one: the model never saw the context and
    # never decided anything. Counting those against max_turns let gateway
    # contention end an episode as `budget_exhausted`, which is a model
    # verdict, and inflated turns_used - the denominator of every
    # calls-per-turn figure - by up to a third on an unwell provider.
    # `attempt` is the loop counter and is only for log lines.
    attempt = 0
    while not env.done and turns_used < max_turns:
        attempt += 1
        env.cur_turn = turns_used + 1
        t0 = time.time()
        try:
            tools = list(TOOLS)
            if env.meta.get("verdict_spec"):
                tools = tools + [DETERMINATION_TOOL]
            request = dict(
                model=model, messages=_wire_messages(messages),
                tools=tools, tool_choice="auto",
                max_tokens=MAX_COMPLETION_TOKENS,
            )
            # the primary gateway drops required arguments on Opus parallel tool_use
            # after a large tool result (Task 1: 3 empty read_file after
            # the packet). Sequential tool_use is the same charged-step
            # trajectory if the same resources are opened.
            if model.startswith(STREAM_PREFERRED_MODELS_PREFIX):
                request["parallel_tool_calls"] = False
            if _uses_streaming(model):
                # glm-5.2 on the secondary gateway needs ~105s; Opus-via-the primary gateway also
                # needs the stream so tool-call deltas are not dropped
                # by the non-streaming OpenAI-compat converter.
                msg_obj = _stream_completion(
                    client, timeout=300, **request)
                resp = type("R", (), {"choices": [
                    type("C", (), {
                        "message": msg_obj,
                        "finish_reason": msg_obj.finish_reason,
                    })()]})()
            else:
                resp = client.chat.completions.create(
                    timeout=90, **request)
            # A gateway can return HTTP 200 with a malformed/empty body
            # (confirmed: one glm-5.2 run got `choices: []`, which crashed
            # the whole episode with an uncaught IndexError instead of
            # being retried like any other flaky-gateway response — that
            # silently turned a transient hiccup into a fake data point).
            # Treat this the same as any other retryable API error.
            if not resp.choices:
                raise ValueError(f"empty choices in response: {resp!r}")
        except Exception as exc:
            log(f"[{model}] attempt {attempt} (turn {turns_used + 1}): "
                f"API ERROR after {time.time()-t0:.1f}s: {exc}")
            api_errors += 1
            consecutive_errors += 1
            if consecutive_errors >= MAX_CONSECUTIVE_API_ERRORS:
                abort_reason = "api_errors"
                log(f"[{model}] aborting after {consecutive_errors} "
                    f"consecutive API errors")
                break
            time.sleep(3)
            continue
        turns_used += 1
        env.cur_turn = turns_used
        log(f"[{model}] turn {turns_used}: got response in "
            f"{time.time()-t0:.1f}s")

        msg = resp.choices[0].message
        raw_tool_calls = msg.tool_calls or []
        finish_reason = getattr(resp.choices[0], "finish_reason", None)
        if is_dropped_gateway_completion(msg, raw_tool_calls, finish_reason):
            # A choice with neither content nor a usable tool call is no
            # more actionable than an empty choices array. the primary gateway's
            # Opus converter also emits HTTP 200 with stripped
            # arguments or a truncated "Oops." — counting those as an
            # agent decision creates a false `gave_up` / invalid-step
            # episode.
            consecutive_errors += 1
            empty_completions += 1
            turns_used -= 1        # not a turn the model took
            refusal = getattr(msg, "refusal", None)
            reasoning = getattr(msg, "reasoning_content", None)
            log(f"[{model}] attempt {attempt} (turn {turns_used + 1}): "
                f"EMPTY COMPLETION "
                f"({consecutive_errors}/"
                f"{MAX_CONSECUTIVE_EMPTY_COMPLETIONS}), "
                f"finish_reason={finish_reason!r}, "
                f"refusal={refusal!r}, "
                f"tool_calls={summarize_tool_calls(raw_tool_calls)}, "
                f"reasoning={(reasoning or '')[:500]!r}")
            if consecutive_errors >= MAX_CONSECUTIVE_EMPTY_COMPLETIONS:
                abort_reason = "empty_completions"
                log(f"[{model}] aborting after {consecutive_errors} "
                    "consecutive empty completions")
                break
            time.sleep(3)
            continue
        consecutive_errors = 0
        tool_calls = filter_usable_tool_calls(raw_tool_calls)
        if len(tool_calls) != len(raw_tool_calls):
            log(f"[{model}] turn {turns_used}: dropped "
                f"{len(raw_tool_calls) - len(tool_calls)} stripped "
                f"tool call(s); keeping {summarize_tool_calls(tool_calls)}")
        if not tool_calls:
            no_tool_call_strikes += 1
            log(f"[{model}] turn {turns_used}: NO TOOL CALL (strike "
                f"{no_tool_call_strikes}), content={(msg.content or '')[:500]!r}")
            messages.append({"role": "assistant", "content": msg.content or ""})
            if no_tool_call_strikes >= 2:
                break
            messages.append({"role": "user",
                             "content": "Please continue by calling one of "
                                         "your tools."})
            continue
        no_tool_call_strikes = 0

        messages.append(_assistant_history_message(msg, tool_calls))

        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if name == "file_determination":
                result = env.submit_determination(args)
            elif name == "list_related_resources":
                lr = env.look()
                result = {"context": lr["context"],
                          "known_resources": lr["known_resources"]}
            elif name in TOOL_TO_RTYPE:
                result = route_tool_call(env, name, args)
            else:
                result = {"ok": False, "error": f"Unknown tool {name}"}

            log(f"[{model}] turn {turns_used}: {name}({args}) -> "
                f"{json.dumps(result)[:160]}")
            messages.append({
                "role": "tool", "tool_call_id": tc.id,
                "content": json.dumps(result),
            })
            if env.done:
                break

    # Outcome taxonomy: distinct failure modes look identical if you only
    # look at success/fail, but they mean very different things about the
    # model's behavior. In particular "gave_up" (the model voluntarily
    # stopped calling tools) is worth splitting further into recoverable
    # (env.would_succeed_now() — every precondition for reaching target was
    # already satisfied; the model had done the hard part and just didn't
    # follow through, e.g. dismissing a working path as "non-terminating"
    # after one unlucky loop probe) vs genuinely stuck (still missing a
    # credential, or never found the real path). Conflating these into one
    # `success: false` bucket throws away exactly the diagnostic signal a
    # trajectory-level eval is supposed to produce.
    api_error_aborted = abort_reason is not None
    gave_up = no_tool_call_strikes >= 2
    if env.success:
        outcome = "success"
    elif api_error_aborted:
        outcome = "api_error_abort"
    elif getattr(env, "fail_reason", None) == "terminal_state":
        # committed to an irreversible wrong action (one-shot topologies) —
        # a different failure from running out of budget, and the one those
        # topologies exist to measure
        outcome = "terminal_failure"
    elif gave_up:
        outcome = "gave_up"
    elif env.done:
        outcome = "budget_exhausted"
    elif turns_used >= max_turns:
        outcome = "turn_limit_exhausted"
    else:
        outcome = "unknown"

    out = {
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "task_revision": env.meta.get("task_revision"),
        "visibility": visibility,
        "success": env.success,
        "outcome": outcome,
        "abort_reason": abort_reason,
        "gave_up_recoverable": env.would_succeed_now() if outcome == "gave_up" else None,
        "steps_total": env.steps_used,
        "steps_invalid": sum(1 for e in env.trajectory
                             if not e.get("valid", False)),
        "steps_duplicate": sum(1 for e in env.trajectory
                               if e.get("valid") and e.get("already_known")),
        "turns_used": turns_used,
        "gave_up": gave_up,
        "trajectory": env.trajectory,
    }
    oracle_path = os.path.join(instance_dir, "oracle.json")
    graph_path = os.path.join(instance_dir, "graph_full.json")
    if os.path.exists(graph_path):
        with open(graph_path, "rb") as f:
            out["graph_sha256"] = hashlib.sha256(f.read()).hexdigest()
    if os.path.exists(oracle_path):
        with open(oracle_path, "rb") as f:
            out["oracle_sha256"] = hashlib.sha256(f.read()).hexdigest()
        from metrics import METRIC_VERSION, InfrastructureOutcomeError
        from score import score_episode
        with open(oracle_path) as f:
            oracle = json.load(f)
        out["metric_version"] = METRIC_VERSION
        try:
            metrics = score_episode(env, oracle, outcome=outcome)
        except InfrastructureOutcomeError:
            metrics = {}
        for key in (
            "metric_version", "charged_steps", "lower_bound_steps",
            "informed_lower_bound", "step_budget", "remaining_lower_bound",
            "attainment", "progress", "ndr", "rsr",
            "excess_over_lower_bound",
        ):
            if key in metrics:
                out[key] = metrics[key]
    # Gateway health belongs with the episode, not in a log someone has to
    # grep later. A run made against an unwell provider is still a valid
    # episode, but whoever reads turns_used should be able to see what the
    # provider was doing at the time.
    out["api_error_count"] = api_errors
    out["empty_completion_count"] = empty_completions
    out["model_turns"] = turns_used
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    base_url = os.environ["LLM_BASE_URL"]
    api_key = os.environ["LLM_API_KEY"]
    out = run_episode(args.instance, args.model, base_url, api_key,
                      args.out, seed=args.seed)
    print(f"model={args.model} success={out['success']} "
          f"steps={out['steps_total']} invalid={out['steps_invalid']} "
          f"duplicate={out['steps_duplicate']} turns={out['turns_used']} "
          f"gave_up={out['gave_up']}")


if __name__ == "__main__":
    main()
