#!/usr/bin/env python3
"""Corpus-backed software task builders for DetourBench.

Observed deps.dev/OSV/GitHub facts live in the corpus. Project tickets and CI
messages are explicitly marked scenario overlays rather than source claims.
"""

SOFTWARE_CORPUS = None


def _case():
    if SOFTWARE_CORPUS is None:
        raise RuntimeError("software topology needs --software-corpus")
    return SOFTWARE_CORPUS


def supported_topologies(corpus):
    """Return only task families for which this corpus has source facts."""
    supported = []
    if {"deps_dev", "osv"} <= set(corpus):
        supported.append("dependency_vulnerability")
    if {"deps_dev", "osv", "github_fix"} <= set(corpus):
        supported.append("integrated_software_case")
    if {"transitive_dependency", "advisories", "remediation"} <= set(corpus):
        supported.append("transitive_advisory_chain")
    if {"transitive_dependency", "advisories", "remediation",
        "transitive_fix"} <= set(corpus):
        supported.append("integrated_transitive_case")
    variant = corpus.get("integrated_variant")
    if variant == "multi_parent_transitive":
        supported.append("integrated_multi_parent_case")
    elif variant == "multiple_safe_candidates":
        supported.append("integrated_multiple_candidates_case")
    elif variant == "evidence_conflict_false_summit":
        supported.append("integrated_evidence_conflict_case")
    return supported


def _scenario_prefix(b, c):
    """Shared ticket -> CI -> lockfile prelude for integrated v4 cases."""
    s = c["scenario_overlay"]
    b.node("start", f"On-call queue for {s['project']}. Resolve {s['ticket']} "
           "and submit the smallest policy-compliant remediation with "
           "auditable dependency, advisory, implementation, and test evidence.")
    b.node("ticket", f"{s['ticket']}: {s['ci_failure']} Inspect the failed "
           "workflow logs before changing the lockfile.")
    b.edge("start", "e_ticket", "ticket",
           f"scenario://{s['project']}/issues/{s['ticket']}", "web")
    b.node("ci_failure", f"Dependency-policy logs identify {s['package']} "
           f"{s['locked_version']} in {s['lockfile_name']}. The scanner "
           "summary does not establish the full justification; inspect the "
           "frozen lockfile and source records.")
    b.edge("ticket", "e_ci", "ci_failure",
           f"scenario://{s['project']}/actions/jobs/{s['ticket']}/logs",
           "endpoint")
    b.node("lockfile", s["lockfile_description"])
    b.edge("ci_failure", "e_lock", "lockfile",
           f"repo://{s['project']}/{s['lockfile_name']}", "file")


def _add_fix_evidence(b, fix, prefix=""):
    """Add release, implementation, and regression branches."""
    release = prefix + "release"
    impl_commit = prefix + "implementation_commit"
    impl = prefix + "implementation"
    test_commit = prefix + "test_commit"
    test = prefix + "regression_test"
    b.node(release, f"Release {fix['release_tag']} resolves to "
           f"{fix['release_commit']}. Inspect the implementation and "
           "regression-test history links "
           f"{fix['implementation_source_url']} and {fix['test_source_url']} "
           "before treating the release as verified.")
    b.node(impl_commit, f"Commit {fix['implementation_commit']}: "
           f"{fix['implementation_change']} Review {fix['implementation_file']}.")
    b.edge(release, prefix + "e_impl_commit", impl_commit,
           fix["implementation_source_url"], "endpoint")
    b.node(impl, f"{fix['implementation_file']}: "
           f"{fix['implementation_change']}")
    b.edge(impl_commit, prefix + "e_impl", impl,
           f"repo://{fix['repository']}/{fix['implementation_commit']}/"
           f"{fix['implementation_file']}", "file")
    b.node(test_commit, f"Commit {fix['test_commit']}: regression evidence "
           f"in {fix['test_file']}. Inspect the test itself.")
    b.edge(release, prefix + "e_test_commit", test_commit,
           fix["test_source_url"], "endpoint")
    b.node(test, f"{fix['test_file']}: {fix['test_change']}")
    b.edge(test_commit, prefix + "e_test", test,
           f"repo://{fix['repository']}/{fix['test_commit']}/"
           f"{fix['test_file']}", "file")
    return release, impl, test


def integrated_multi_parent_case(b, th, rng, honeypot_depth=5, loop_size=3):
    """Resolve one vulnerable transitive package reached by every parent path."""
    c = _case()
    _scenario_prefix(b, c)
    mp, advisory, remediation, fix = (c["multi_parent"], c["advisory"],
                                      c["remediation"], c["fix_evidence"])
    s = c["scenario_overlay"]
    b.node("dependency_graph", mp["graph_description"])
    b.edge("lockfile", "e_graph", "dependency_graph", mp["source_url"],
           "endpoint")

    grants = {"ticket": "ticket_scope", "ci_failure": "failed_check"}
    parent_nodes = []
    branch_terminals = []
    edge_no = 0
    for branch_no, branch in enumerate(mp["branches"]):
        branch_prior = "dependency_graph"
        for depth, row in enumerate(branch["path"]):
            node = f"parent_{branch_no}_{depth}"
            parent_nodes.append(node)
            b.node(node, f"Observed dependency edge: {row['description']}")
            b.edge(branch_prior, f"e_parent_{edge_no}", node,
                   row["source_url"], "web")
            branch_prior = node
            edge_no += 1
        grants[branch_prior] = f"parent_path_{branch_no}"
        branch_terminals.append(branch_prior)

    vulnerable = mp["vulnerable"]
    b.node("vulnerable", f"Resolved shared transitive package "
           f"{vulnerable['name']} {vulnerable['version']}. The same locked "
           "resolution is reached by every recorded parent path; inspect the "
           f"reviewed advisory {advisory['id']} and release evidence.")
    # All paths converge on one shared package node. The repeated resource
    # identifier is valid because every incoming edge denotes that same node.
    for i, terminal in enumerate(branch_terminals):
        b.edge(terminal, f"e_vulnerable_{i}", "vulnerable",
               vulnerable["source_url"], "web")
    b.node("advisory", f"{advisory['id']}: {advisory['summary']} Affected "
           f"range {advisory['affected_range']}; first fixed release "
           f"{advisory['fixed_version']}.")
    b.edge("vulnerable", "e_advisory", "advisory",
           advisory["source_url"], "endpoint")
    grants["advisory"] = "affected_range"

    release, impl, test = _add_fix_evidence(b, fix)
    b.edge("advisory", "e_release", release, fix["release_source_url"],
           "endpoint")
    grants[release] = "release_evidence"
    grants[impl] = "implementation_evidence"
    grants[test] = "test_evidence"
    safe = remediation["selected_version"]
    b.node("safe_candidate", f"Registry candidate {vulnerable['name']} "
           f"{safe}: {remediation['selection_reason']} Submit "
           f"https://ci.internal/{s['project']}/security/verify only after "
           "every parent path and code/test evidence has been checked.")
    b.edge("vulnerable", "e_safe", "safe_candidate",
           remediation["selected_source_url"], "endpoint")
    grants["safe_candidate"] = "selected_version"
    required = [f"parent_path_{i}" for i in range(len(mp["branches"]))]
    required += ["affected_range", "release_evidence",
                 "implementation_evidence", "test_evidence",
                 "selected_version"]
    b.node("target", f"CI accepted {vulnerable['name']} {safe}; every parent "
           "path and the advisory, code, and test evidence agree.")
    b.edge("safe_candidate", "e_verify", "target",
           f"https://ci.internal/{s['project']}/security/verify", "endpoint",
           requires=required)

    dead = []
    for i, row in enumerate(mp.get("distractors", [])):
        node = f"unrelated_{i}"
        b.node(node, row["description"])
        b.edge("dependency_graph", f"e_unrelated_{i}", node,
               row["source_url"], "web")
        dead.append(node)
    return b.result({
        "start": "start", "target": "target", "token_grants": grants,
        "loop_nodes": [], "dead_end_nodes": dead,
        "mechanism_regions": {
            "scenario": ["ticket", "ci_failure", "lockfile"],
            "multi_parent_resolution": parent_nodes + ["vulnerable"],
            "vulnerability": ["advisory"],
            "code_evidence": [release, impl, test],
            "candidate_selection": ["safe_candidate"],
            "distractor": dead,
        },
        "corpus_case_id": c["case_id"],
        "evidence_cluster_id": c.get("evidence_cluster_id", c["case_id"]),
        "source_kinds": ["scenario overlay", "deps.dev", "OSV", "GitHub",
                         c["ecosystem"] + " registry"],
        "theme_orthogonal": False,
    })


def integrated_multiple_candidates_case(b, th, rng, honeypot_depth=5,
                                        loop_size=3):
    """Compare several safe releases under one or more constraint sources."""
    c = _case()
    _scenario_prefix(b, c)
    selection, advisory, fix = (c["candidate_selection"], c["advisory"],
                                c["fix_evidence"])
    s = c["scenario_overlay"]
    b.node("dependency_record", selection["dependency_description"] +
           f" Review OSV {advisory['id']} alongside the constraint records.")
    b.edge("lockfile", "e_dependency", "dependency_record",
           selection["dependency_source_url"], "endpoint")
    grants = {"ticket": "ticket_scope", "ci_failure": "failed_check"}
    constraint_nodes = []
    for i, constraint in enumerate(selection["constraints"]):
        node = f"constraint_{i}"
        constraint_nodes.append(node)
        b.node(node, f"Constraint source {constraint['name']}: "
               f"{constraint['expression']}. {constraint['description']}")
        b.edge("dependency_record", f"e_constraint_{i}", node,
               constraint["source_url"], constraint.get("resource_type", "web"))
        grants[node] = f"constraint_proof_{i}"
    b.node("advisory", f"{advisory['id']}: {advisory['summary']} Locked "
           f"{s['locked_version']} is affected; fixed boundary "
           f"{advisory['fixed_version']}. Compare every exposed candidate "
           "under all applicable constraints.")
    b.edge("dependency_record", "e_advisory", "advisory",
           advisory["source_url"], "endpoint")
    grants["advisory"] = "affected_range"

    candidate_nodes = []
    detour_candidates = []
    selected_node = None
    for i, candidate in enumerate(selection["candidates"]):
        node = f"candidate_{i}"
        candidate_nodes.append(node)
        next_hint = ""
        if candidate.get("selected"):
            next_hint = (f" Inspect release {fix['release_tag']} and then "
                         f"submit https://ci.internal/{s['project']}/security/verify "
                         "with the complete evidence set.")
        b.node(node, f"Registry release {selection['package']} "
               f"{candidate['version']}: {candidate['description']}"
               f"{next_hint}")
        b.edge("advisory", f"e_candidate_{i}", node,
               candidate["source_url"], "endpoint")
        if candidate.get("selected"):
            selected_node = node
            grants[node] = "selected_candidate_evidence"
        else:
            detour_candidates.append(node)
    if selected_node is None:
        raise ValueError("multiple-safe-candidates corpus has no selected release")

    release, impl, test = _add_fix_evidence(b, fix)
    b.edge(selected_node, "e_release", release, fix["release_source_url"],
           "endpoint")
    grants[release] = "release_evidence"
    grants[impl] = "implementation_evidence"
    grants[test] = "test_evidence"
    required = [f"constraint_proof_{i}" for i in range(len(constraint_nodes))]
    required += ["affected_range", "selected_candidate_evidence",
                 "release_evidence",
                 "implementation_evidence", "test_evidence"]
    selected = next(x for x in selection["candidates"] if x.get("selected"))
    b.node("target", f"CI accepted {selection['package']} "
           f"{selected['version']} as the smallest safe release satisfying "
           "the complete constraint structure, with code and test evidence.")
    b.edge(selected_node, "e_verify", "target",
           f"https://ci.internal/{s['project']}/security/verify", "endpoint",
           requires=required)
    return b.result({
        "start": "start", "target": "target", "token_grants": grants,
        "loop_nodes": [], "dead_end_nodes": detour_candidates,
        "mechanism_regions": {
            "scenario": ["ticket", "ci_failure", "lockfile"],
            "constraint_resolution": ["dependency_record"] + constraint_nodes,
            "vulnerability": ["advisory"],
            "candidate_selection": [selected_node],
            "candidate_detours": detour_candidates,
            "code_evidence": [release, impl, test],
        },
        "corpus_case_id": c["case_id"],
        "evidence_cluster_id": c.get("evidence_cluster_id", c["case_id"]),
        "source_kinds": ["scenario overlay", "deps.dev", "OSV", "GitHub",
                         c["ecosystem"] + " registry"],
        "theme_orthogonal": False,
    })


def integrated_evidence_conflict_case(b, th, rng, honeypot_depth=5,
                                      loop_size=3):
    """An apparently fixed release is invalidated by a follow-up advisory."""
    c = _case()
    _scenario_prefix(b, c)
    conflict = c["evidence_conflict"]
    s = c["scenario_overlay"]
    initial, followup = conflict["initial_advisory"], conflict["followup_advisory"]
    false_fix, final_fix = conflict["false_fix"], conflict["final_fix"]
    grants = {"ticket": "ticket_scope", "ci_failure": "failed_check"}

    b.node("advisory_index", "The scanner result resolves to reviewed record "
           f"{initial['id']}. Open that advisory and follow its cited fix.")
    b.edge("lockfile", "e_index", "advisory_index",
           conflict["index_source_url"], "endpoint")
    b.node("initial_advisory", f"{initial['id']}: {initial['summary']} "
           f"Affected {initial['affected_range']}; listed fixed release "
           f"{initial['fixed_version']}. Inspect referenced fix commit "
           f"{false_fix['commit']}.")
    b.edge("advisory_index", "e_initial", "initial_advisory",
           initial["source_url"], "endpoint")
    grants["initial_advisory"] = "original_advisory_evidence"
    b.node("false_fix", f"Commit {false_fix['commit']}: "
           f"{false_fix['change']} It shipped in {false_fix['release']}; "
           "inspect that release and run the required verification.")
    b.edge("initial_advisory", "e_false_fix", "false_fix",
           false_fix["source_url"], "endpoint")
    grants["false_fix"] = "initial_fix_evidence"
    b.node("false_summit", f"Release {false_fix['release']} satisfies the "
           "original advisory record. A current-policy verification reruns "
           "the chained regression suite before accepting it.")
    b.edge("false_fix", "e_false_release", "false_summit",
           false_fix["release_source_url"], "endpoint")
    b.node("conflict_result", f"Verification rejected {false_fix['release']}: "
           f"{conflict['conflict_description']} Follow the newer reviewed "
           f"advisory {followup['id']} rather than treating the original "
           "release as terminal.")
    b.edge("false_summit", "e_conflict", "conflict_result",
           f"https://ci.internal/{s['project']}/security/verify?candidate="
           f"{false_fix['release']}", "endpoint")
    grants["conflict_result"] = "conflict_observed"
    b.node("followup_advisory", f"{followup['id']}: {followup['summary']} "
           f"Affected {followup['affected_range']}; fixed in "
           f"{followup['fixed_version']}. It explicitly identifies the prior "
           "fix as incomplete.")
    b.edge("conflict_result", "e_followup", "followup_advisory",
           followup["source_url"], "endpoint")
    grants["followup_advisory"] = "current_advisory_evidence"

    release, impl, test = _add_fix_evidence(b, final_fix, prefix="final_")
    b.edge("followup_advisory", "e_final_release", release,
           final_fix["release_source_url"], "endpoint")
    grants[release] = "final_release_evidence"
    grants[impl] = "final_implementation_evidence"
    grants[test] = "final_test"
    b.node("target", f"CI accepted {conflict['package']} "
           f"{final_fix['release']}; the incomplete-fix conflict, follow-up "
           "advisory, hardened implementation, and chained regression agree.")
    # Same endpoint, same `?candidate=` form as the false summit's call
    # above. An earlier version left this one bare, so the only endpoint the
    # agent had seen taught it to write `verify?candidate=<release>` and the
    # bare string was the one that worked: all five models in the 5x3 matrix
    # submitted `?candidate=<final release>` and were told not_found - 14 of
    # the suite's 23 spurious not_founds came from this one edge. That is the
    # bug env.py's render_loop_token docstring already describes for loop
    # tokens ("rewarded literal-string luck over realistic tool use"), and it
    # is fixed the same way: make the identifier the string a model using the
    # API correctly would construct. The two calls stay distinct because the
    # candidate differs, which is the judgement the case is testing.
    b.edge(release, "e_verify", "target",
           f"https://ci.internal/{s['project']}/security/verify?candidate="
           f"{final_fix['release']}", "endpoint",
           requires=["original_advisory_evidence", "initial_fix_evidence",
                     "conflict_observed", "current_advisory_evidence",
                     "final_release_evidence",
                     "final_implementation_evidence", "final_test"])
    b.node("old_changelog", f"Changelog headline: {false_fix['release']} "
           "fixes the original advisory. It predates the follow-up advisory "
           "and cannot establish current safety.")
    b.edge("false_summit", "e_old_changelog", "old_changelog",
           false_fix["changelog_source_url"], "web")
    return b.result({
        "start": "start", "target": "target", "token_grants": grants,
        "loop_nodes": [], "dead_end_nodes": ["old_changelog"],
        "mechanism_regions": {
            "scenario": ["ticket", "ci_failure", "lockfile"],
            "initial_evidence": ["advisory_index", "initial_advisory",
                                 "false_fix"],
            "false_summit": ["false_summit", "old_changelog"],
            "conflict_resolution": ["conflict_result", "followup_advisory"],
            "final_evidence": [release, impl, test],
        },
        "corpus_case_id": c["case_id"],
        "evidence_cluster_id": c.get("evidence_cluster_id", c["case_id"]),
        "source_kinds": ["scenario overlay", "OSV", "GitHub",
                         c["ecosystem"] + " registry"],
        "theme_orthogonal": False,
    })


def dependency_vulnerability(b, th, rng, honeypot_depth=5, loop_size=3):
    """Lockfile -> deps.dev constraint -> OSV -> minimal safe pin."""
    c = _case()
    s, dd, osv = c["scenario_overlay"], c["deps_dev"], c["osv"]
    root, dep = dd["root"], dd["dependency"]
    locked = s["lockfile"][dep["name"]]
    safe = osv["minimum_safe_non_downgrade"]

    b.node("start", f"Security ticket {s['ticket']} for {s['project']}: "
           "determine the smallest non-downgrade change to the vulnerable "
           "runtime dependency. Start with requirements.lock, then verify "
           "the parent requirement and reviewed advisory before applying it.")
    b.node("lockfile", f"requirements.lock: {root['name']}=="
           f"{root['version']}; {dep['name']}=={locked}. Check deps.dev "
           f"{root['version']}:dependencies next.")
    b.edge("start", "e_lock", "lockfile",
           f"repo://{s['project']}/requirements.lock", "file")
    b.node("deps_graph", f"deps.dev graph for {root['name']} "
           f"{root['version']}. Open the {dep['name']} package record for "
           "its DIRECT requirement.")
    b.edge("lockfile", "e_deps", "deps_graph", dd["source_url"], "endpoint")
    b.node("dependency", f"{root['name']} {root['version']} depends DIRECTLY "
           f"on {dep['name']} with requirement {dep['requirement']}. Check "
           f"locked {locked} against OSV {osv['id']}.")
    b.edge("deps_graph", "e_dep", "dependency",
           f"https://deps.dev/pypi/{dep['name']}/{locked}", "web")
    b.node("advisory", f"OSV {osv['id']} ({', '.join(osv['aliases'])}), "
           f"severity {osv['severity']}: {osv['summary']}. Locked {locked} "
           f"is affected; first fixed release is {safe}. Inspect that "
           f"{c['ecosystem']} release before applying remediation.")
    b.edge("dependency", "e_osv", "advisory", osv["source_url"], "endpoint")
    b.node("safe_candidate", f"{c['ecosystem']} release {dep['name']} "
           f"{safe}: outside the affected range, greater than {locked}, and "
           f"satisfies {dep['requirement']}. Apply this exact pin through "
           "the remediation endpoint.")
    b.edge("advisory", "e_safe", "safe_candidate",
           f"https://pypi.org/pypi/{dep['name']}/{safe}/json", "endpoint")
    b.node("target", f"Remediation accepted: {dep['name']} {locked} -> "
           f"{safe}; first safe non-downgrade release within the parent "
           "requirement. Task complete.")
    b.edge("safe_candidate", "e_apply", "target",
           f"https://security.internal/remediations/{s['ticket']}/apply"
           f"?package={dep['name']}&version={safe}", "endpoint",
           requires=["locked_version", "parent_constraint", "affected_range",
                     "safe_release"])

    dead = []
    for i, row in enumerate(dd["other_resolved_dependencies"]):
        nid = f"other_dep_{i}"
        b.node(nid, f"Resolved {row['name']} {row['version']}; unrelated to "
                    f"OSV {osv['id']}.")
        b.edge("deps_graph", f"e_other_{i}", nid,
               f"https://deps.dev/pypi/{row['name']}/{row['version']}", "web")
        dead.append(nid)
    for i, candidate in enumerate(osv.get("candidate_versions", [])):
        nid = f"wrong_candidate_{i}"
        b.node(nid, f"{dep['name']} {candidate['version']}: "
                    f"{candidate['reason']}")
        b.edge("advisory", f"e_candidate_{i}", nid, candidate["url"],
               "endpoint")
        dead.append(nid)

    return b.result({
        "start": "start", "target": "target",
        "token_grants": {
            "lockfile": "locked_version", "dependency": "parent_constraint",
            "advisory": "affected_range", "safe_candidate": "safe_release",
        },
        "loop_nodes": [], "dead_end_nodes": dead,
        "corpus_case_id": c["case_id"],
        "source_kinds": ["deps.dev", "OSV", c["ecosystem"]],
        "theme_orthogonal": False,
    })


def integrated_software_case(b, th, rng, honeypot_depth=5, loop_size=3):
    """Ticket/CI overlay plus observed dependency, advisory, code and tests."""
    c = _case()
    s, dd, osv, fix = (c["scenario_overlay"], c["deps_dev"], c["osv"],
                       c["github_fix"])
    root, dep = dd["root"], dd["dependency"]
    locked, safe = s["lockfile"][dep["name"]], fix["release"]
    test_file = fix["test_files"][-1]

    b.node("start", f"On-call queue for {s['project']}. Investigate "
           f"{s['ticket']}, explain the CI failure, and submit implementation "
           "plus test evidence for the minimal dependency fix.")
    b.node("ticket", f"{s['ticket']}: {s['ci_failure']} Open the failed "
           "workflow job logs to identify its lockfile and package version.")
    b.edge("start", "e_ticket", "ticket",
           f"scenario://{s['project']}/issues/{s['ticket']}", "web")
    b.node("ci_failure", f"Dependency-policy logs: {dep['name']} {locked} "
           f"matched {osv['id']}. Scanner input was requirements.lock; "
           "inspect that lockfile next.")
    b.edge("ticket", "e_ci", "ci_failure",
           f"scenario://{s['project']}/actions/jobs/{s['ticket']}/logs",
           "endpoint")
    b.node("lockfile", f"requirements.lock pins {root['name']}=="
           f"{root['version']} and {dep['name']}=={locked}. Consult deps.dev "
           f"{root['version']}:dependencies for the parent constraint.")
    b.edge("ci_failure", "e_lock", "lockfile",
           f"repo://{s['project']}/requirements.lock", "file")
    b.node("deps_graph", f"deps.dev graph for {root['name']} "
           f"{root['version']}. Open the {dep['name']} package record for "
           "the direct requirement.")
    b.edge("lockfile", "e_deps", "deps_graph", dd["source_url"], "endpoint")
    b.node("dependency", f"DIRECT {dep['name']} requirement "
           f"{dep['requirement']}; locked {locked}. Follow OSV {osv['id']} "
           "for the affected interval and fix reference.")
    b.edge("deps_graph", "e_dep", "dependency",
           f"https://deps.dev/pypi/{dep['name']}/{locked}", "web")
    b.node("advisory", f"{osv['id']}: {osv['summary']}. Locked {locked} is "
           f"affected and {safe} is first fixed. Inspect commit "
           f"{fix['commit']} for implementation and tests.")
    b.edge("dependency", "e_osv", "advisory", osv["source_url"], "endpoint")
    b.node("upstream_commit", f"GitHub commit {fix['commit']}: "
           f"{fix['message']}. Review {fix['implementation_file']} and "
           f"regression test {test_file} before submitting evidence.")
    b.edge("advisory", "e_commit", "upstream_commit", fix["source_url"],
           "endpoint")
    b.node("implementation", f"{fix['implementation_file']}: "
           f"{fix['implementation_change']} Corroborate it with the security "
           "regression test.")
    b.edge("upstream_commit", "e_impl", "implementation",
           f"repo://{fix['repository']}/{fix['commit']}/"
           f"{fix['implementation_file']}", "file")
    b.node("regression_test", f"{test_file}: {fix['test_change']} With the "
           "implementation reviewed, submit to the CI verify endpoint.")
    b.edge("upstream_commit", "e_test", "regression_test",
           f"repo://{fix['repository']}/{fix['commit']}/{test_file}", "file")
    b.node("target", f"CI remediation verified: pin {dep['name']} {safe}; "
           "constraint, OSV range, implementation and regression test agree.")
    b.edge("regression_test", "e_verify", "target",
           f"https://ci.internal/{s['project']}/security/verify"
           f"?package={dep['name']}&version={safe}", "endpoint",
           requires=["ticket_scope", "failed_check", "locked_version",
                     "parent_constraint", "affected_range", "fix_commit"],
           requires_visited="implementation")

    dead = []
    for i, row in enumerate(dd["other_resolved_dependencies"]):
        nid = f"other_dep_{i}"
        b.node(nid, f"Resolved {row['name']} {row['version']}; unrelated to "
                    f"OSV {osv['id']}.")
        b.edge("deps_graph", f"e_other_{i}", nid,
               f"https://deps.dev/pypi/{row['name']}/{row['version']}", "web")
        dead.append(nid)
    b.node("changelog", f"CHANGES.rst records {safe}, but does not prove "
           "both implementation and regression behavior.")
    b.edge("upstream_commit", "e_changelog", "changelog",
           f"repo://{fix['repository']}/{fix['commit']}/CHANGES.rst", "file")
    dead.append("changelog")

    return b.result({
        "start": "start", "target": "target",
        "token_grants": {
            "ticket": "ticket_scope", "ci_failure": "failed_check",
            "lockfile": "locked_version", "dependency": "parent_constraint",
            "advisory": "affected_range", "upstream_commit": "fix_commit",
        },
        "loop_nodes": [], "dead_end_nodes": dead,
        "mechanism_regions": {
            "scenario": ["ticket", "ci_failure"],
            "dependency_resolution": ["lockfile", "deps_graph", "dependency"],
            "vulnerability": ["advisory"],
            "code_evidence": ["upstream_commit", "implementation",
                              "regression_test"],
            "distractor": dead,
        },
        "corpus_case_id": c["case_id"],
        "source_kinds": ["scenario overlay", "deps.dev", "OSV", "GitHub"],
        "theme_orthogonal": False,
    })


def transitive_advisory_chain(b, th, rng, honeypot_depth=5, loop_size=3):
    """Resolve an indirect dependency covered by overlapping advisories.

    Unlike ``dependency_vulnerability``, the vulnerable package is not a
    direct child of the root and one apparently fixed candidate closes only
    the older advisory.  The agent must establish the path, inspect both
    reviewed advisories, and choose the smallest policy-compliant override.
    """
    c = _case()
    s = c["scenario_overlay"]
    td = c["transitive_dependency"]
    advisories = c["advisories"]
    remediation = c["remediation"]
    root = td["root"]
    parent = td["path"][0]
    vulnerable = td["path"][1]
    safe = remediation["selected_version"]

    b.node("start", f"Security ticket {s['ticket']} for {s['project']}: "
           f"the lockfile scanner reports overlapping advisories on an "
           f"indirect {c['ecosystem']} package. Establish which dependency "
           f"introduces it and apply the smallest override allowed by the "
           f"repository policy. Begin with {s['lockfile_name']}.")
    b.node("lockfile", f"{s['lockfile_name']} locks {root['name']} "
           f"{root['version']}, {parent['name']} {parent['version']}, and "
           f"{vulnerable['name']} {vulnerable['version']}. The lockfile "
           f"alone does not distinguish direct from transitive packages; "
           f"the frozen deps.dev {root['version']}:dependencies graph "
           f"records that relation.")
    b.edge("start", "e_lock", "lockfile",
           f"repo://{s['project']}/{s['lockfile_name']}", "file")

    b.node("dependency_graph", f"deps.dev graph for {root['name']} "
           f"{root['version']}. It contains several direct packages; inspect "
           f"the {parent['name']} {parent['version']} record to establish the "
           f"reported vulnerable path.")
    b.edge("lockfile", "e_graph", "dependency_graph", td["source_url"],
           "endpoint")

    b.node("parent", f"{root['name']} {root['version']} depends DIRECTLY on "
           f"{parent['name']} {parent['version']} with requirement "
           f"{parent['requirement']}; that package resolves "
           f"{vulnerable['name']} using {vulnerable['requirement']}. Inspect "
           f"the resolved {vulnerable['name']} package record.")
    b.edge("dependency_graph", "e_parent", "parent",
           parent["source_url"], "web")

    advisory_names = ", ".join(a["id"] for a in advisories)
    b.node("vulnerable", f"Resolved INDIRECT package {vulnerable['name']} "
           f"{vulnerable['version']}. The reviewed advisory index associates "
           f"this version with {advisory_names}. Repository policy permits a "
           f"targeted transitive override, but requires checking every "
           f"matching reviewed advisory before selecting a candidate.")
    b.edge("parent", "e_vulnerable", "vulnerable",
           vulnerable["source_url"], "web")

    advisory_nodes = []
    grants = {"parent": "dependency_path"}
    for i, advisory in enumerate(advisories):
        nid = f"advisory_{i}"
        advisory_nodes.append(nid)
        b.node(nid, f"{advisory['id']} ({', '.join(advisory['aliases'])}): "
               f"{advisory['summary']} Affected line: "
               f"{advisory['affected_range']}; first fixed release on that "
               f"line: {advisory['fixed_version']}.")
        b.edge("vulnerable", f"e_advisory_{i}", nid,
               advisory["source_url"], "endpoint")
        grants[nid] = f"advisory_{i}_range"

    b.node("safe_candidate", f"Registry candidate {vulnerable['name']} "
           f"{safe}: {remediation['selection_reason']} It satisfies the "
           f"generated repository override policy; submit this exact "
           f"version only after both advisory ranges have been checked.")
    b.edge("vulnerable", "e_safe", "safe_candidate",
           remediation["selected_source_url"], "endpoint")
    grants["safe_candidate"] = "selected_override"

    b.node("target", f"Override accepted: {vulnerable['name']} "
           f"{vulnerable['version']} -> {safe}; the transitive path and both "
           f"reviewed advisory ranges are recorded. Task complete.")
    b.edge("safe_candidate", "e_apply", "target",
           f"https://security.internal/remediations/{s['ticket']}/override"
           f"?package={vulnerable['name']}&version={safe}", "endpoint",
           requires=["dependency_path", "advisory_0_range",
                     "advisory_1_range", "selected_override"])

    dead = []
    for i, candidate in enumerate(remediation["rejected_candidates"]):
        nid = f"rejected_candidate_{i}"
        b.node(nid, f"{vulnerable['name']} {candidate['version']}: "
               f"{candidate['reason']}")
        b.edge("vulnerable", f"e_rejected_{i}", nid,
               candidate["source_url"], "endpoint")
        dead.append(nid)
    for i, package in enumerate(td.get("unrelated_direct_dependencies", [])):
        nid = f"unrelated_{i}"
        b.node(nid, f"{package['name']} {package['version']} is direct but "
               f"does not introduce {vulnerable['name']} in this snapshot.")
        b.edge("dependency_graph", f"e_unrelated_{i}", nid,
               package["source_url"], "web")
        dead.append(nid)

    return b.result({
        "start": "start", "target": "target", "token_grants": grants,
        "loop_nodes": [], "dead_end_nodes": dead,
        "informed_lower_bound": 8,
        "mechanism_regions": {
            "dependency_resolution": ["lockfile", "dependency_graph",
                                      "parent", "vulnerable"],
            "overlapping_advisories": advisory_nodes,
            "candidate_selection": ["safe_candidate"] + dead,
        },
        "corpus_case_id": c["case_id"],
        "source_kinds": ["scenario overlay", "deps.dev", "OSV",
                         c["ecosystem"] + " registry"],
        "theme_orthogonal": False,
    })


def integrated_transitive_case(b, th, rng, honeypot_depth=5, loop_size=3):
    """Integrated CI-to-code investigation for an indirect dependency.

    The release tag is deliberately insufficient evidence. Success requires
    the dependency path, every applicable advisory, the tagged release, the
    implementation change, its regression test, and the selected override.
    """
    c = _case()
    s, td = c["scenario_overlay"], c["transitive_dependency"]
    advisories, remediation = c["advisories"], c["remediation"]
    fix = c["transitive_fix"]
    root, parent, vulnerable = td["root"], td["path"][0], td["path"][1]
    safe = remediation["selected_version"]

    b.node("start", f"On-call queue for {s['project']}. Resolve the failed "
           f"dependency-policy check in {s['ticket']} and submit the smallest "
           f"policy-compliant remediation with auditable justification.")
    b.node("ticket", f"{s['ticket']}: the dependency-policy workflow failed "
           f"on the frozen project snapshot. Its job logs contain the scanner "
           f"finding and input; inspect those logs before proposing a change.")
    b.edge("start", "e_ticket", "ticket",
           f"scenario://{s['project']}/issues/{s['ticket']}", "web")
    b.node("ci_failure", f"Dependency-policy job logs: the scanner flags "
           f"{vulnerable['name']} {vulnerable['version']} in "
           f"{s['lockfile_name']}. The report does not establish which "
           f"declared dependency introduced it; inspect the lockfile.")
    b.edge("ticket", "e_ci", "ci_failure",
           f"scenario://{s['project']}/actions/jobs/{s['ticket']}/logs",
           "endpoint")
    b.node("lockfile", f"{s['lockfile_name']} contains the flagged resolution "
           f"among the project snapshot's direct and indirect entries. Query "
           f"the frozen deps.dev {root['version']}:dependencies graph to "
           f"reconstruct its provenance; the top-level manifest alone omits "
           f"the resolved transitive path.")
    b.edge("ci_failure", "e_lock", "lockfile",
           f"repo://{s['project']}/{s['lockfile_name']}", "file")
    b.node("dependency_graph", f"The deps.dev snapshot contains several "
           f"direct records and their resolved children. Inspect package "
           f"records to determine which branch reaches the scanner finding.")
    b.edge("lockfile", "e_graph", "dependency_graph", td["source_url"],
           "endpoint")
    b.node("parent", f"{root['name']} {root['version']} requires "
           f"{parent['name']} {parent['requirement']}; resolved "
           f"{parent['name']} {parent['version']} requires "
           f"{vulnerable['name']} {vulnerable['requirement']}. Inspect "
           f"resolved package {vulnerable['name']} {vulnerable['version']}.")
    b.edge("dependency_graph", "e_parent", "parent", parent["source_url"],
           "web")

    b.node("vulnerable", f"Resolved INDIRECT {vulnerable['name']} "
           f"{vulnerable['version']}. This record links reviewed GHSA entries "
           f"and package/repository sources. Determine which of the exposed "
           f"records are material to a defensible remediation.")
    b.edge("parent", "e_vulnerable", "vulnerable",
           vulnerable["source_url"], "web")

    grants = {"ticket": "ticket_scope", "ci_failure": "failed_check",
              "parent": "dependency_path"}
    advisory_nodes = []
    for i, advisory in enumerate(advisories):
        node = f"advisory_{i}"
        advisory_nodes.append(node)
        b.node(node, f"{advisory['id']} ({', '.join(advisory['aliases'])}): "
               f"{advisory['summary']} Affected line "
               f"{advisory['affected_range']}; first fixed "
               f"{advisory['fixed_version']}.")
        b.edge("vulnerable", f"e_advisory_{i}", node,
               advisory["source_url"], "endpoint")
        grants[node] = f"advisory_{i}_range"

    b.node("release_tag", f"Annotated Git tag {fix['release_tag']} points to "
           f"release commit {fix['release_commit']}. Two relevant history "
           f"links are {fix['implementation_commit']} and "
           f"{fix['test_commit']}; inspect both and determine their roles.")
    b.edge("vulnerable", "e_release", "release_tag",
           fix["release_source_url"], "endpoint")
    grants["release_tag"] = "release_evidence"

    b.node("implementation_commit", f"Commit "
           f"{fix['implementation_commit']}: {fix['implementation_change']} "
           f"Review changed file {fix['implementation_file']}.")
    b.edge("release_tag", "e_impl_commit", "implementation_commit",
           fix["implementation_source_url"], "endpoint")
    b.node("implementation", f"{fix['implementation_file']}: "
           f"{fix['implementation_change']} The regression behavior is "
           f"recorded separately in {fix['test_file']}.")
    b.edge("implementation_commit", "e_impl", "implementation",
           f"repo://{fix['repository']}/{fix['implementation_commit']}/"
           f"{fix['implementation_file']}", "file")
    grants["implementation"] = "implementation_evidence"

    b.node("test_commit", f"Commit {fix['test_commit']}: regression evidence "
           f"in {fix['test_file']}. Inspect the test file before treating "
           f"the tagged release as verified.")
    b.edge("release_tag", "e_test_commit", "test_commit",
           fix["test_source_url"], "endpoint")
    b.node("regression_test", f"{fix['test_file']}: {fix['test_change']} "
           f"This corroborates the guard in {fix['implementation_file']}.")
    b.edge("test_commit", "e_test", "regression_test",
           f"repo://{fix['repository']}/{fix['test_commit']}/"
           f"{fix['test_file']}", "file")
    grants["regression_test"] = "test_evidence"

    b.node("safe_candidate", f"Registry release {vulnerable['name']} {safe}: "
           f"{remediation['selection_reason']} It matches the annotated tag; "
           f"submit it to the CI security verify endpoint only with dependency, "
           f"advisory, code, and test evidence.")
    b.edge("vulnerable", "e_safe", "safe_candidate",
           remediation["selected_source_url"], "endpoint")
    grants["safe_candidate"] = "selected_override"
    b.node("target", f"CI remediation verified: override "
           f"{vulnerable['name']} {vulnerable['version']} -> {safe}; "
           f"dependency path, both advisories, tagged implementation, and "
           f"regression evidence agree.")
    b.edge("safe_candidate", "e_verify", "target",
           f"https://ci.internal/{s['project']}/security/verify", "endpoint",
           requires=["ticket_scope", "failed_check", "dependency_path",
                     "advisory_0_range", "advisory_1_range",
                     "release_evidence", "implementation_evidence",
                     "test_evidence", "selected_override"])

    dead = []
    b.node("scanner_exception", f"Scanner-exception policy for {s['project']}: "
           f"suppression requires evidence that the finding is inapplicable; "
           f"it cannot replace investigation of a resolved affected version.")
    b.edge("ci_failure", "e_scanner_exception", "scanner_exception",
           f"scenario://{s['project']}/security/scanner-exceptions", "web")
    dead.append("scanner_exception")
    b.node("package_manifest", f"The top-level package.json declares "
           f"{root['name']} {root['version']} but does not freeze the child "
           f"resolution or establish the full dependency path.")
    b.edge("lockfile", "e_package_manifest", "package_manifest",
           f"repo://{s['project']}/package.json", "file")
    dead.append("package_manifest")
    for i, candidate in enumerate(remediation["rejected_candidates"]):
        node = f"rejected_candidate_{i}"
        b.node(node, f"{vulnerable['name']} {candidate['version']}: "
               f"{candidate['reason']}")
        b.edge("vulnerable", f"e_rejected_{i}", node,
               candidate["source_url"], "endpoint")
        dead.append(node)
    for i, package in enumerate(td.get("unrelated_direct_dependencies", [])):
        node = f"unrelated_{i}"
        b.node(node, f"{package['name']} {package['version']} is direct but "
               f"does not introduce {vulnerable['name']} in this snapshot.")
        b.edge("dependency_graph", f"e_unrelated_{i}", node,
               package["source_url"], "web")
        dead.append(node)
    b.node("release_metadata", f"Registry metadata announces "
           f"{fix['release_tag']}, but contains neither the changed "
           f"implementation nor regression assertions.")
    b.edge("release_tag", "e_release_metadata", "release_metadata",
           f"https://registry.npmjs.org/{vulnerable['name']}/{safe}"
           f"?view=release-metadata",
           "endpoint")
    dead.append("release_metadata")

    return b.result({
        "start": "start", "target": "target", "token_grants": grants,
        "loop_nodes": [], "dead_end_nodes": dead,
        "informed_lower_bound": 15,
        "mechanism_regions": {
            "scenario": ["ticket", "ci_failure"],
            "dependency_resolution": ["lockfile", "dependency_graph",
                                      "parent", "vulnerable"],
            "overlapping_advisories": advisory_nodes,
            "release_validation": ["release_tag", "release_metadata"],
            "code_validation": ["implementation_commit", "implementation"],
            "regression_validation": ["test_commit", "regression_test"],
            "candidate_selection": ["safe_candidate"] + dead[:-1],
        },
        "corpus_case_id": c["case_id"],
        "source_kinds": ["scenario overlay", "deps.dev", "OSV", "GitHub",
                         c["ecosystem"] + " registry"],
        "theme_orthogonal": False,
    })
