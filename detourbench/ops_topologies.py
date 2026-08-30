#!/usr/bin/env python3
"""Corpus-backed SRE, network, data, and Kubernetes task builders."""

OPS_CORPUS = None


VARIANT_TO_TOPOLOGY = {
    "sre_diagnostic_disambiguation":
        "integrated_sre_disambiguation_case",
    "sre_shared_upstream":
        "integrated_sre_shared_upstream_case",
    "network_source_precedence":
        "integrated_net_precedence_case",
    "data_dual_plan":
        "integrated_data_dual_plan_case",
    "k8s_dual_plan":
        "integrated_k8s_dual_plan_case",
    "sre_hypothesis_prioritization":
        "integrated_sre_hypothesis_case",
    "sre_unequal_plans":
        "integrated_sre_unequal_plan_case",
}


def _case():
    if OPS_CORPUS is None:
        raise RuntimeError("ops topology needs --ops-corpus")
    return OPS_CORPUS


def supported_topologies(corpus):
    topology = VARIANT_TO_TOPOLOGY.get(corpus.get("integrated_variant"))
    return [topology] if topology else []


def _meta(c, grants, dead, regions, informed_lower_bound):
    return {
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
        "source_kinds": ["public documentation", "public incident record",
                         "generated scenario overlay"],
        "theme_orthogonal": False,
    }


def integrated_sre_disambiguation_case(
        b, th, rng, honeypot_depth=5, loop_size=3):
    """Disambiguate slow database execution from pool-acquisition delay."""
    c, s = _case(), _case()["scenario_overlay"]
    observed = c["observed_evidence"]

    b.node("start", f"On-call ticket {s['ticket']} for {s['service']}: "
           f"{s['summary']}. Establish the cause, make the smallest safe "
           "change, and verify recovery.")
    b.node("ticket", f"{s['ticket']} scopes the incident to "
           f"{s['latency_window']}. Inspect the latency slice before "
           "selecting a representative trace.")
    b.edge("start", "e_ticket", "ticket",
           f"scenario://{s['service']}/incidents/{s['ticket']}", "web")

    representative_trace = (
        f"scenario://{s['service']}/traces/{s['ticket']}/representative")
    b.node("latency_slice", "The latency slice isolates checkout requests "
           "whose wall time is attributed to SQL spans. Inspect the linked "
           f"representative trace {representative_trace} to separate database "
           "execution from client-side acquisition time.")
    b.edge("ticket", "e_latency", "latency_slice",
           f"scenario://{s['service']}/metrics/{s['ticket']}/latency-slice",
           "endpoint")

    b.node("trace", f"Representative trace: {s['trace_summary']}. The two "
           "live hypotheses are slow database execution and connection-pool "
           "acquisition delay; compare DB health or pool-wait metrics.")
    b.edge("latency_slice", "e_trace", "trace", representative_trace, "web")

    b.node("database_health", f"Database health for the incident window: "
           f"{s['database_health']}. This rules out slow execution but does "
           "not itself identify the application-side change.")
    b.edge("trace", "e_database_health", "database_health",
           f"scenario://database/health/{s['ticket']}", "endpoint")

    b.node("pool_metrics", f"Connection-pool telemetry: {s['pool_metrics']}. "
           "Public pool-sizing evidence records the same replicas-times-pool "
           f"failure mode ({observed[0]['source_url']}). Inspect the rollout "
           "configuration diff.")
    b.edge("trace", "e_pool", "pool_metrics",
           f"scenario://{s['service']}/metrics/{s['ticket']}/pool-wait",
           "endpoint")

    canary_identifier = (
        f"scenario://{s['service']}/canaries/{s['ticket']}")
    b.node("config_diff", f"Rollout configuration diff: {s['config_diff']}. "
           f"The runbook permits {s['resolution']}; apply it to the canary "
           f"at {canary_identifier} before resolving the incident.")
    b.edge("pool_metrics", "e_config", "config_diff",
           f"scenario://{s['service']}/deployments/{s['ticket']}/config-diff",
           "file")

    b.node("canary", f"Canary verification: {s['canary_result']}. The "
           "incident can now be resolved with the tested pool configuration.")
    b.edge("config_diff", "e_canary", "canary",
           canary_identifier, "endpoint")

    b.node("target", f"Incident resolved: {s['resolution']}; canary latency "
           "and connection-acquisition wait are healthy.")
    b.edge("canary", "e_resolve", "target",
           f"scenario://{s['service']}/incidents/{s['ticket']}/resolve",
           "endpoint",
           requires=["incident_scope", "symptom_window",
                     "pool_saturation_evidence", "config_regression",
                     "canary_pass"])

    dead = ["database_health"]
    distractors = [
        ("cpu_history", "CPU and HPA history are healthy apart from the "
         "intended replica increase; they do not explain SQL-span wait time.",
         "cpu-hpa-history"),
        ("heap_profile", "Heap profile shows no allocation or GC regression "
         "during the latency window.", "heap-profile"),
        ("slow_queries", "The slow-query report contains no query whose "
         "execution time matches the observed request latency.", "slow-queries"),
    ]
    for node, desc, slug in distractors:
        b.node(node, desc)
        b.edge("trace", "e_" + node, node,
               f"scenario://{s['service']}/diagnostics/{s['ticket']}/{slug}",
               "endpoint")
        dead.append(node)

    grants = {
        "ticket": "incident_scope",
        "latency_slice": "symptom_window",
        "pool_metrics": "pool_saturation_evidence",
        "config_diff": "config_regression",
        "canary": "canary_pass",
    }
    return b.result(_meta(c, grants, dead, {
        "incident": ["ticket", "latency_slice", "trace"],
        "competing_hypothesis": ["database_health"],
        "root_cause": ["pool_metrics", "config_diff"],
        "verification": ["canary", "target"],
        "plausible_distractors": [x[0] for x in distractors],
    }, 7))


def integrated_sre_shared_upstream_case(
        b, th, rng, honeypot_depth=5, loop_size=3):
    """Correlate independent service traces to one shared DNS dependency."""
    c, s = _case(), _case()["scenario_overlay"]
    b.node("start", f"Fleet incident {s['ticket']} in {s['cluster']}: "
           f"{s['summary']}. Determine whether the services failed "
           "independently or share one upstream cause, then verify recovery.")
    b.node("ticket", f"{s['ticket']} links a cross-service error dashboard. "
           "Inspect the common time window before opening service traces.")
    b.edge("start", "e_ticket", "ticket",
           f"scenario://{s['cluster']}/incidents/{s['ticket']}", "web")
    trace_links = ", ".join(row["identifier"] for row in s["service_traces"])
    b.node("dashboard", "The dashboard aligns failures from checkout, auth, "
           "and notifications to one minute. Corroborate at least two service "
           f"traces ({trace_links}) before opening the shared dependency map.")
    b.edge("ticket", "e_dashboard", "dashboard",
           f"scenario://{s['cluster']}/dashboards/{s['ticket']}/fleet-errors",
           "endpoint")

    traces = []
    grants = {"ticket": "incident_scope",
              "dashboard": "cross_service_window"}
    for i, row in enumerate(s["service_traces"]):
        node = f"service_trace_{i}"
        traces.append(node)
        b.node(node, f"{row['service']} trace: {row['finding']}. Compare with "
               "another affected service or inspect its local diagnostics.")
        b.edge("dashboard", f"e_trace_{i}", node, row["identifier"], "web")
        grants[node] = f"service_trace_{i}"

    b.node("dependency_map", f"Shared dependency map: {s['dependency_map']}. "
           "Compare node-local resolver health with the shared identity, "
           "proxy, and configuration dependency.")
    b.edge("dashboard", "e_dependency_map", "dependency_map",
           f"scenario://{s['cluster']}/dependencies/shared-upstream",
           "file", requires_visited=traces, requires_visited_n=2)
    b.node("resolver_health", f"Resolver health: {s['resolver_health']}. "
           "Compare this signal with shared proxy and configuration health "
           "before attributing the common failures to DNS.")
    b.edge("dependency_map", "e_resolver_health", "resolver_health",
           f"scenario://{s['cluster']}/kube-system/node-local-dns/health",
           "endpoint")
    b.node("shared_proxy_health", "Shared identity/proxy/configuration health: "
           f"{s['shared_proxy_health']}. Compare this with resolver health "
           "before selecting the shared root cause.")
    b.edge("dependency_map", "e_shared_proxy_health", "shared_proxy_health",
           f"scenario://{s['cluster']}/shared-platform/config-health",
           "endpoint")
    b.node("cause_assessment", f"Shared-cause assessment: "
           f"{s['cause_assessment']}. Inspect the node-local-dns rollout diff.")
    b.edge("dependency_map", "e_cause_assessment", "cause_assessment",
           c["decision_policy"]["source_url"], "file",
           requires_visited=["resolver_health", "shared_proxy_health"],
           requires_visited_n=2)
    b.node("rollout_diff", f"Resolver rollout diff: {s['rollout_diff']}. "
           "The public RKE2 issue documents this exact missing-upstream "
           f"failure class ({c['observed_evidence'][2]['source_url']}). "
           "Roll back the resolver configuration.")
    b.edge("cause_assessment", "e_rollout_diff", "rollout_diff",
           f"scenario://{s['cluster']}/kube-system/node-local-dns/diff",
           "file")
    b.node("rollback", f"Resolver rollback complete: {s['rollback_result']}. "
           "Run fleet verification across affected service classes.")
    b.edge("rollout_diff", "e_rollback", "rollback",
           f"scenario://{s['cluster']}/kube-system/node-local-dns/rollback",
           "endpoint")
    b.node("target", f"Fleet verified: {s['fleet_verification']}.")
    b.edge("rollback", "e_verify", "target",
           f"scenario://{s['cluster']}/incidents/{s['ticket']}/verify",
           "endpoint",
           requires=["incident_scope", "cross_service_window",
                     "shared_dependency", "resolver_regression",
                     "rollback_applied"],
           requires_visited=traces, requires_visited_n=2)

    grants.update({
        "dependency_map": "shared_dependency",
        "cause_assessment": "resolver_regression",
        "rollback": "rollback_applied",
    })
    dead = []
    for i, trace in enumerate(traces):
        for j, branch in enumerate(s["local_branches"][i]):
            node = f"local_diagnostic_{i}_{j}"
            b.node(node, f"Service-local diagnostic: {branch['finding']}. "
                   "This cannot explain synchronized failures in the other "
                   "service classes.")
            b.edge(trace, f"e_local_{i}_{j}", node,
                   f"scenario://{s['cluster']}/services/{i}/diagnostics/"
                   f"{branch['slug']}", "endpoint")
            dead.append(node)
    b.node("provider_status", "External provider status is healthy during "
           "the incident window; provider histories do not share one vendor.")
    b.edge("dashboard", "e_provider_status", "provider_status",
           f"scenario://{s['cluster']}/providers/status", "web")
    dead.append("provider_status")
    return b.result(_meta(c, grants, dead, {
        "incident": ["ticket", "dashboard"],
        "corroboration": traces,
        "shared_candidates": ["dependency_map", "resolver_health",
                              "shared_proxy_health"],
        "shared_root_cause": ["cause_assessment", "rollout_diff"],
        "remediation": ["rollback", "target"],
        "local_diagnostics": dead,
    }, 11))


def integrated_net_precedence_case(
        b, th, rng, honeypot_depth=5, loop_size=3):
    """Resolve a route conflict using freshness and source precedence."""
    c, s = _case(), _case()["scenario_overlay"]
    b.node("start", f"Routing incident {s['ticket']} on {s['edge']}: "
           f"{s['summary']}. Establish the authoritative current route "
           "state, remove the stale approved local-preference statement, "
           "and verify convergence. The sandbox change is in scope; no human "
           "confirmation is available or required.")
    b.node("ticket", f"{s['ticket']} concerns {s['prefix']}. Inspect the "
           "edge Loc-RIB, which exposes both current and snapshot evidence.")
    b.edge("start", "e_ticket", "ticket",
           f"scenario://network/incidents/{s['ticket']}", "web")
    b.node("edge_rib", f"Edge Loc-RIB: {s['edge_rib']}. Compare the current "
           "BMP record and cached looking-glass snapshot, then consult the "
           "routing-data authority note.")
    b.edge("ticket", "e_edge_rib", "edge_rib",
           f"scenario://network/routers/{s['edge']}/loc-rib/{s['prefix']}",
           "endpoint")
    b.node("cached_snapshot", f"Cached looking glass: "
           f"{s['cached_looking_glass']}. Its route is plausible but its "
           "freshness must be evaluated against policy.")
    b.edge("edge_rib", "e_cached", "cached_snapshot",
           f"scenario://network/looking-glass/cache/{s['prefix']}", "web")
    b.node("current_bmp", f"Current BMP Loc-RIB: {s['current_bmp']}. Review "
           "the routing-data authority note before acting on the conflict.")
    b.edge("edge_rib", "e_bmp", "current_bmp",
           f"scenario://network/bmp/current/{s['edge']}/{s['prefix']}",
           "endpoint")
    b.node("authority_note", f"Routing-data authority: {s['authority_note']}. "
           "Use the current BMP state and inspect the approved maintenance "
           "record for the stale preference.")
    b.edge("edge_rib", "e_authority", "authority_note",
           c["decision_policy"]["source_url"], "file",
           requires_visited=["cached_snapshot", "current_bmp"],
           requires_visited_n=2)
    b.node("maintenance", f"Maintenance record: {s['maintenance_record']}. "
           "Inspect the edge policy diff for the incomplete rollback.")
    b.edge("authority_note", "e_maintenance", "maintenance",
           f"scenario://network/changes/{s['ticket']}/maintenance",
           "web", requires="current_route_state")
    b.node("policy_diff", f"Policy diff: {s['policy_diff']}. Withdraw the "
           "stale local-preference statement.")
    b.edge("maintenance", "e_policy_diff", "policy_diff",
           f"scenario://network/routers/{s['edge']}/policy/diff", "file")
    b.node("withdrawal", "The temporary local-preference statement has been "
           "removed. Verify convergence in both BMP and the edge Loc-RIB.")
    b.edge("policy_diff", "e_withdraw", "withdrawal",
           f"scenario://network/routers/{s['edge']}/policy/withdraw",
           "endpoint")
    b.node("target", f"Routing converged: {s['verification']}.")
    b.edge("withdrawal", "e_verify", "target",
           f"scenario://network/incidents/{s['ticket']}/verify", "endpoint",
           requires=["incident_scope", "current_route_state",
                     "source_precedence", "maintenance_context",
                     "policy_fault", "withdrawal_applied"])
    grants = {
        "ticket": "incident_scope",
        "current_bmp": "current_route_state",
        "authority_note": "source_precedence",
        "maintenance": "maintenance_context",
        "policy_diff": "policy_fault",
        "withdrawal": "withdrawal_applied",
        "cached_snapshot": "stale_snapshot",
    }
    dead = []
    for node, label in (
            ("rpki", "RPKI origin validation is valid for both paths; it "
             "cannot explain local preference selection."),
            ("optics", "Interface optical levels and error counters are "
             "healthy throughout the incident."),
            ("bfd", "BFD sessions remain established with no flap in the "
             "maintenance window.")):
        b.node(node, label)
        b.edge("edge_rib", "e_" + node, node,
               f"scenario://network/diagnostics/{s['ticket']}/{node}",
               "endpoint")
        dead.append(node)
    return b.result(_meta(c, grants, dead, {
        "incident": ["ticket", "edge_rib"],
        "conflicting_sources": ["cached_snapshot", "current_bmp"],
        "precedence": ["authority_note"],
        "change_context": ["maintenance", "policy_diff"],
        "remediation": ["withdrawal", "target"],
        "plausible_distractors": dead,
    }, 9))


def integrated_data_dual_plan_case(
        b, th, rng, honeypot_depth=5, loop_size=3):
    """Restore a public data contract by either of two valid plans."""
    c, s = _case(), _case()["scenario_overlay"]
    b.node("start", f"Data incident {s['ticket']} in {s['project']}: "
           f"{s['summary']}. Acquire consumer and replay constraints before "
           "choosing the minimum-scope, least-disruptive safe recovery plan.")
    b.node("ticket", f"{s['ticket']} links the failed pipeline run. Inspect "
           "the contract failure before changing consumers or data.")
    b.edge("start", "e_ticket", "ticket",
           f"scenario://{s['project']}/incidents/{s['ticket']}", "web")
    b.node("failed_run", f"Failed run: {s['failed_run']}. Inspect the source "
           "schema diff.")
    b.edge("ticket", "e_failed_run", "failed_run",
           f"scenario://{s['project']}/runs/{s['ticket']}", "endpoint")
    b.node("schema_diff", f"Schema diff: {s['schema_diff']}. Before planning, "
           "inspect the recovery SLA, current freshness, active consumer "
           "compatibility, and replay or rollback window at "
           f"scenario://{s['project']}/slas/{s['ticket']}, "
           f"scenario://{s['project']}/freshness/{s['ticket']}, "
           f"scenario://{s['project']}/lineage/dim-customer/consumers, and "
           f"scenario://{s['project']}/retention/replay-window.")
    b.edge("failed_run", "e_schema_diff", "schema_diff",
           f"scenario://{s['project']}/schemas/{s['ticket']}/diff", "file")
    b.node("recovery_sla", f"Recovery SLA: {s['recovery_sla']}. Include it "
           "in the multi-factor plan assessment.")
    b.edge("schema_diff", "e_recovery_sla", "recovery_sla",
           f"scenario://{s['project']}/slas/{s['ticket']}", "file")
    b.node("freshness_state", f"Freshness state: {s['freshness_state']}. "
           "Include it in the multi-factor plan assessment.")
    b.edge("schema_diff", "e_freshness_state", "freshness_state",
           f"scenario://{s['project']}/freshness/{s['ticket']}", "endpoint")
    b.node("consumers", f"Consumer compatibility: "
           f"{s['consumer_inventory']}. Include it in the multi-factor plan "
           "assessment.")
    b.edge("schema_diff", "e_consumers", "consumers",
           f"scenario://{s['project']}/lineage/dim-customer/consumers",
           "endpoint")
    b.node("replay_window", f"Replay and rollback window: "
           f"{s['replay_window']}. Include it in the multi-factor plan "
           "assessment.")
    b.edge("schema_diff", "e_replay_window", "replay_window",
           f"scenario://{s['project']}/retention/replay-window", "file")
    b.node("plan_assessment", f"Plan assessment: {s['plan_assessment']}. "
           f"Policy states: {c['decision_policy']['rule']}")
    b.edge("schema_diff", "e_plan_assessment", "plan_assessment",
           c["decision_policy"]["source_url"], "file",
           requires_visited=["recovery_sla", "freshness_state", "consumers",
                             "replay_window"],
           requires_visited_n=4)

    b.node("compat_view", f"Compatibility plan applied: "
           f"{s['compatibility_plan']}. Run the public v1 contract test.")
    b.edge("plan_assessment", "e_compat_view", "compat_view",
           f"scenario://{s['project']}/changes/{s['ticket']}/compat-view",
           "endpoint")
    b.node("compat_test", f"Compatibility verification: "
           f"{s['compatibility_test']}. Restore the public model.")
    b.edge("compat_view", "e_compat_test", "compat_test",
           f"scenario://{s['project']}/tests/{s['ticket']}/v1-contract",
           "endpoint")

    b.node("replay", f"Replay plan started: {s['replay_plan']}. Monitor the "
           "affected partition backfill.")
    b.edge("plan_assessment", "e_replay", "replay",
           f"scenario://{s['project']}/replays/{s['ticket']}", "endpoint")
    b.node("replay_monitor", f"Replay monitor: {s['replay_monitor']}. Run row "
           "validation before consumer tests.")
    b.edge("replay", "e_replay_monitor", "replay_monitor",
           f"scenario://{s['project']}/replays/{s['ticket']}/status",
           "endpoint")
    b.node("row_validation", f"Row validation: {s['row_validation']}. Run the "
           "consumer contract suite.")
    b.edge("replay_monitor", "e_row_validation", "row_validation",
           f"scenario://{s['project']}/tests/{s['ticket']}/row-validation",
           "endpoint")
    b.node("consumer_test", f"Consumer verification: {s['consumer_test']}. "
           "Restore the public model.")
    b.edge("row_validation", "e_consumer_test", "consumer_test",
           f"scenario://{s['project']}/tests/{s['ticket']}/consumers",
           "endpoint")

    b.node("target", "Public dim_customer v1 contract restored; active "
           "consumers are healthy and the selected remediation is verified.")
    common = ["incident_scope", "contract_failure", "schema_change",
              "sla_constraints", "freshness_constraints",
              "consumer_constraints", "replay_constraints", "plan_context"]
    b.edge("compat_test", "e_restore_compat", "target",
           f"scenario://{s['project']}/incidents/{s['ticket']}/restore"
           "?plan=compatibility", "endpoint",
           requires=common + ["compatibility_verified"])
    b.edge("consumer_test", "e_restore_replay", "target",
           f"scenario://{s['project']}/incidents/{s['ticket']}/restore"
           "?plan=replay", "endpoint",
           requires=common + ["replay_verified"])
    grants = {
        "ticket": "incident_scope",
        "failed_run": "contract_failure",
        "schema_diff": "schema_change",
        "recovery_sla": "sla_constraints",
        "freshness_state": "freshness_constraints",
        "consumers": "consumer_constraints",
        "replay_window": "replay_constraints",
        "plan_assessment": "plan_context",
        "compat_test": "compatibility_verified",
        "consumer_test": "replay_verified",
    }
    dead = []
    for node, desc in (
            ("consumer_patches", "Per-consumer patches would duplicate the "
             "same alias across clients and are not the minimum shared fix."),
            ("full_refresh", "A full-history refresh is valid operationally "
             "but exceeds the six-partition affected window."),
            ("nullable_change", "Making the field nullable does not restore "
             "the required public column name.")):
        b.node(node, desc)
        b.edge("schema_diff", "e_" + node, node,
               f"scenario://{s['project']}/proposals/{s['ticket']}/{node}",
               "web")
        dead.append(node)
    return b.result(_meta(c, grants, dead, {
        "incident": ["ticket", "failed_run", "schema_diff"],
        "information_acquisition": ["recovery_sla", "freshness_state",
                                    "consumers", "replay_window",
                                    "plan_assessment"],
        "short_plan": ["compat_view", "compat_test"],
        "long_plan": ["replay", "replay_monitor", "row_validation",
                      "consumer_test"],
        "plausible_distractors": dead,
    }, 11))


def integrated_k8s_dual_plan_case(
        b, th, rng, honeypot_depth=5, loop_size=3):
    """Resolve topology-spread scheduling with either safe remediation."""
    c, s = _case(), _case()["scenario_overlay"]
    base = f"scenario://{s['cluster']}/namespaces/{s['namespace']}"
    b.node("start", f"Kubernetes incident {s['ticket']} for "
           f"{s['namespace']}/{s['workload']}: {s['summary']}. Diagnose the "
           "scheduler decision and choose the minimum-scope, least-disruptive "
           "safe remediation.")
    deployment_identifier = f"{base}/deployments/{s['workload']}"
    b.node("ticket", f"{s['ticket']} links the {s['workload']} Deployment "
           f"spec at {deployment_identifier}. Inspect it before reading "
           "scheduler events.")
    b.edge("start", "e_ticket", "ticket",
           f"{base}/incidents/{s['ticket']}", "web")
    b.node("deployment", f"Deployment spec: {s['deployment_spec']}. Inspect "
           "the Pending pod scheduler events.")
    b.edge("ticket", "e_deployment", "deployment",
           deployment_identifier, "file")
    b.node("scheduler_events", f"Scheduler events: {s['scheduler_events']}. "
           "Inspect current node and zone topology.")
    b.edge("deployment", "e_scheduler_events", "scheduler_events",
           f"{base}/pods/{s['workload']}/events", "endpoint")
    b.node("topology_state", f"Topology state: {s['topology_state']}. Consult "
           "the remaining drain duration, autoscaler readiness, and capacity "
           "ETA before consulting remediation policy.")
    b.edge("scheduler_events", "e_topology_state", "topology_state",
           f"scenario://{s['cluster']}/nodes/topology", "endpoint")
    b.node("drain_duration", f"Drain duration: {s['drain_duration']}. Include "
           "it in the remediation-policy decision.")
    b.edge("topology_state", "e_drain_duration", "drain_duration",
           f"scenario://{s['cluster']}/maintenance/drain-window", "web")
    b.node("autoscaler_readiness", f"Autoscaler readiness: "
           f"{s['autoscaler_readiness']}. Include it in the "
           "remediation-policy decision.")
    b.edge("topology_state", "e_autoscaler_readiness",
           "autoscaler_readiness",
           f"scenario://{s['cluster']}/node-groups/eu-west-1c/autoscaler",
           "endpoint")
    b.node("capacity_eta", f"Capacity ETA: {s['capacity_eta']}. Include it in "
           "the remediation-policy decision.")
    b.edge("topology_state", "e_capacity_eta", "capacity_eta",
           f"scenario://{s['cluster']}/node-groups/eu-west-1c/capacity-eta",
           "endpoint")
    b.node("change_policy", f"Change context: {s['change_policy']}. "
           f"Remediation policy: {c['decision_policy']['rule']}")
    b.edge("topology_state", "e_change_policy", "change_policy",
           c["decision_policy"]["source_url"], "file",
           requires_visited=["drain_duration", "autoscaler_readiness",
                             "capacity_eta"],
           requires_visited_n=3)

    b.node("scoped_patch", f"Scoped patch applied: {s['patch_plan']}. Verify "
           "one rollout canary before completing remediation.")
    b.edge("change_policy", "e_scoped_patch", "scoped_patch",
           f"{base}/deployments/{s['workload']}/topology-patch", "endpoint")
    b.node("patch_canary", f"Patch canary: {s['patch_canary']}. Complete the "
           "incident with the verified temporary plan.")
    b.edge("scoped_patch", "e_patch_canary", "patch_canary",
           f"{base}/deployments/{s['workload']}/canary", "endpoint")

    b.node("capacity_scale", f"Capacity plan started: {s['capacity_plan']}. "
           "Wait for missing-zone node readiness.")
    b.edge("change_policy", "e_capacity_scale", "capacity_scale",
           f"scenario://{s['cluster']}/node-groups/eu-west-1c/scale",
           "endpoint")
    b.node("node_readiness", f"Node readiness: {s['node_readiness']}. Run the "
           "full rollout verification.")
    b.edge("capacity_scale", "e_node_readiness", "node_readiness",
           f"scenario://{s['cluster']}/node-groups/eu-west-1c/readiness",
           "endpoint")
    b.node("rollout_verify", f"Rollout verification: "
           f"{s['rollout_verification']}. Complete the incident with the "
           "capacity plan.")
    b.edge("node_readiness", "e_rollout_verify", "rollout_verify",
           f"{base}/deployments/{s['workload']}/verify", "endpoint")

    b.node("target", f"{s['namespace']}/{s['workload']} restored with a "
           "policy-compliant topology remediation and passing smoke tests.")
    common = ["incident_scope", "deployment_constraints",
              "scheduler_diagnosis", "current_zone_capacity",
              "drain_context", "autoscaler_context", "capacity_timing",
              "approved_remediation_policy"]
    b.edge("patch_canary", "e_complete_patch", "target",
           f"{base}/incidents/{s['ticket']}/complete?plan=scoped-patch",
           "endpoint", requires=common + ["patch_verified"])
    b.edge("rollout_verify", "e_complete_capacity", "target",
           f"{base}/incidents/{s['ticket']}/complete?plan=capacity",
           "endpoint", requires=common + ["capacity_verified"])
    grants = {
        "ticket": "incident_scope",
        "deployment": "deployment_constraints",
        "scheduler_events": "scheduler_diagnosis",
        "topology_state": "current_zone_capacity",
        "drain_duration": "drain_context",
        "autoscaler_readiness": "autoscaler_context",
        "capacity_eta": "capacity_timing",
        "change_policy": "approved_remediation_policy",
        "patch_canary": "patch_verified",
        "rollout_verify": "capacity_verified",
    }
    dead = []
    for node, desc in (
            ("pdb", "The PodDisruptionBudget allows the rollout; no eviction "
             "is blocked."),
            ("registry", "The image is already present and pull credentials "
             "are valid."),
            ("cni", "CNI health is normal on every eligible node."),
            ("kubelet", "Ready nodes have no memory, disk, or PID pressure.")):
        b.node(node, desc)
        b.edge("scheduler_events", "e_" + node, node,
               f"{base}/diagnostics/{s['ticket']}/{node}", "endpoint")
        dead.append(node)
    return b.result(_meta(c, grants, dead, {
        "incident": ["ticket", "deployment", "scheduler_events"],
        "information_acquisition": ["topology_state", "drain_duration",
                                    "autoscaler_readiness", "capacity_eta",
                                    "change_policy"],
        "short_plan": ["scoped_patch", "patch_canary"],
        "long_plan": ["capacity_scale", "node_readiness", "rollout_verify"],
        "plausible_distractors": dead,
    }, 11))


def integrated_sre_hypothesis_case(
        b, th, rng, honeypot_depth=5, loop_size=3):
    """Prioritize a high-value wait-class observation among plausible causes."""
    c, s = _case(), _case()["scenario_overlay"]
    observed = c["observed_evidence"]
    svc, ticket = s["service"], s["ticket"]
    dash = f"scenario://{svc}/metrics/{ticket}"
    tr = f"scenario://{svc}/traces/{ticket}"
    dashboard_id = f"{dash}/fleet-latency"
    trace_id = f"{tr}/representative"
    sql_id = f"{tr}/sql-exec"
    pool_id = f"{tr}/pool-acquire"
    redis_id = f"{tr}/redis-get"
    inv_id = f"{tr}/inventory-http"
    slow_id = f"{tr}/slow-log"
    gc_id = f"{tr}/gc-pause"
    dns_id = f"{tr}/dns-lookup"
    wait_id = f"{tr}/worker-queue"
    cpu_id = f"{dash}/cpu-throttling"
    workers_id = f"scenario://{svc}/metrics/{ticket}/tomcat-workers"
    scale_id = f"scenario://{svc}/changes/{ticket}/scale-maxthreads"
    diff_id = f"scenario://{svc}/deployments/{ticket}/inventory-client-diff"
    rollback_id = f"scenario://{svc}/changes/{ticket}/rollback-inventory-client"
    canary_id = f"scenario://{svc}/canaries/{ticket}"

    b.node("start", f"On-call ticket {ticket} for {svc}: {s['summary']}. "
           "Restore checkout p99 below 300 ms. Open the incident ticket at "
           f"scenario://{svc}/incidents/{ticket}.")
    b.node("ticket", f"{ticket} is scoped to {svc} between "
           f"{s['latency_window']}, coinciding with inventory-client 4.2.0. "
           f"Inspect the fleet latency dashboard at {dashboard_id}.")
    b.edge("start", "e_ticket", "ticket",
           f"scenario://{svc}/incidents/{ticket}", "web")
    b.node("dashboard", f"Fleet latency: {s['dashboard_summary']}. "
           f"CPU throttling history is at {cpu_id}. A representative trace "
           f"is at {trace_id}.")
    b.edge("ticket", "e_dashboard", "dashboard", dashboard_id, "endpoint")
    b.node("cpu_throttling", f"CPU throttling: {s['cpu_throttling']}.")
    b.edge("dashboard", "e_cpu_throttling", "cpu_throttling", cpu_id,
           "endpoint")
    b.node("trace", f"Representative trace: {s['trace_summary']}. Downstream "
           "status codes are 200 when they arrive. Span timing records: "
           f"{sql_id}, {pool_id}, {redis_id}, {inv_id}, {slow_id}, {gc_id}, "
           f"{dns_id}, and {wait_id}.")
    b.edge("dashboard", "e_trace", "trace", trace_id, "web")

    hypotheses = [
        ("db_health", s["db_health"], sql_id, "sql.exec 14 ms on this "
         "request; executor health for the window is below."),
        ("pool_metrics", s["pool_metrics"], pool_id,
         "hikari.acquire 3 ms on this request; pool telemetry is below."),
        ("redis_latency", s["redis_latency"], redis_id,
         "redis.get 2 ms on this request; cache telemetry is below."),
        ("inventory_http", s["inventory_http"], inv_id,
         "inventory.http is the last span before the request returns."),
        ("slow_queries", s["slow_queries"], slow_id,
         "slow-query log for the same window:"),
        ("gc_pauses", s["gc_pauses"], gc_id,
         "gc.pause is listed on the process, not as the request's last span."),
        ("dns_health", s["dns_health"], dns_id,
         "dns.lookup 1 ms on this request; resolver health is below."),
    ]
    dead = ["cpu_throttling"]
    for node, finding, ident, lead in hypotheses:
        b.node(node, f"{lead} {finding}.")
        b.edge("trace", "e_" + node, node, ident, "endpoint")
        dead.append(node)

    b.node("wait_class", f"Wait-class breakdown for the same request: "
           f"{s['wait_class']}. Tomcat connector thread-pool behavior is "
           f"documented at {observed[0]['source_url']}. Connector worker "
           f"telemetry is at {workers_id}.")
    b.edge("trace", "e_wait_class", "wait_class", wait_id, "endpoint")
    b.node("thread_pool", f"Tomcat workers: {s['thread_pool']}. Linked "
           f"changes: {scale_id} and {diff_id}.")
    b.edge("wait_class", "e_thread_pool", "thread_pool", workers_id, "endpoint")
    b.node("scale_workers", "maxThreads raised from 50 to 200. The acceptor "
           "queue does not drain because existing workers remain blocked in "
           "the inventory-client call.")
    b.edge("thread_pool", "e_scale", "scale_workers", scale_id, "endpoint")
    dead.append("scale_workers")
    b.node("config_diff", f"Deployment diff: {s['config_diff']}. Blocking "
           f"RestTemplate on a request thread is the client model in "
           f"{observed[1]['source_url']}. The runbook allows "
           f"{s['resolution']}. Apply it at {rollback_id}.")
    b.edge("thread_pool", "e_config", "config_diff", diff_id, "file")
    b.node("rollback", f"Client rollback applied: {s['resolution']}. Worker "
           f"queue depth is falling. Run the checkout canary at {canary_id}.")
    b.edge("config_diff", "e_rollback", "rollback", rollback_id, "endpoint")
    b.node("canary", f"Canary: {s['canary_result']}. Complete the incident at "
           f"scenario://{svc}/incidents/{ticket}/resolve.")
    b.edge("rollback", "e_canary", "canary", canary_id, "endpoint")
    b.node("target", f"Incident resolved: {s['resolution']}; canary latency "
           "and worker queueing are healthy. Task complete.")
    b.edge("canary", "e_resolve", "target",
           f"scenario://{svc}/incidents/{ticket}/resolve", "endpoint",
           requires=["incident_scope", "symptom_window", "wait_attribution",
                     "worker_saturation", "change_evidence", "canary_pass"])

    grants = {
        "ticket": "incident_scope",
        "dashboard": "symptom_window",
        "wait_class": "wait_attribution",
        "thread_pool": "worker_saturation",
        "config_diff": "change_evidence",
        "canary": "canary_pass",
    }
    return b.result(_meta(c, grants, dead, {
        "incident": ["ticket", "dashboard", "trace"],
        "mandatory_information": ["wait_class"],
        "root_cause": ["thread_pool", "config_diff"],
        "plausible_hypotheses": dead,
        "remediation": ["rollback"],
        "verification": ["canary", "target"],
    }, 9))


def integrated_sre_unequal_plan_case(
        b, th, rng, honeypot_depth=5, loop_size=3):
    """Two valid remediations with a large interaction-cost gap."""
    c, s = _case(), _case()["scenario_overlay"]
    cluster, svc, ticket = s["cluster"], s["service"], s["ticket"]
    base = f"scenario://{cluster}"
    dash_id = f"{base}/dashboards/{ticket}/checkout-success"
    redis_id = f"{base}/redis/checkout-cache/health"
    maint_id = f"{base}/changes/CHG-9102"
    slo_id = f"{base}/slos/checkout-success"
    fallback_id = f"{base}/{svc}/flags/local-cache"
    eta_id = f"{base}/redis/checkout-cache-b/eta"
    constraints_id = c["decision_policy"]["source_url"]
    enable_id = f"{base}/{svc}/flags/local-cache/enable"
    canary_id = f"{base}/canaries/{ticket}/checkout"
    quota_id = f"{base}/quota/redis-checkout-cache-b"
    failover_id = f"{base}/runbooks/redis-primary-failover"

    b.node("start", f"Incident {ticket}: {s['summary']}. Recover checkout "
           f"success. Open {base}/incidents/{ticket}.")
    b.node("ticket", f"{ticket} links a checkout error dashboard. Inspect "
           f"{dash_id}.")
    b.edge("start", "e_ticket", "ticket", f"{base}/incidents/{ticket}", "web")
    b.node("dashboard", f"Checkout dashboard: {s['dashboard_summary']}. "
           f"Inspect Redis health at {redis_id}. TLS and CDN diagnostics "
           f"are at {base}/diagnostics/{ticket}/tls and "
           f"{base}/diagnostics/{ticket}/cdn.")
    b.edge("ticket", "e_dashboard", "dashboard", dash_id, "endpoint")
    b.node("redis_health", f"Redis health: {s['redis_health']}. Linked "
           f"records: {failover_id}, {maint_id}, {slo_id}, {fallback_id}, "
           f"{eta_id}, and {constraints_id}.")
    b.edge("dashboard", "e_redis", "redis_health", redis_id, "endpoint")
    b.node("failover_runbook", f"Failover runbook: {s['failover_runbook']}. "
           f"Inspect replica lag at {base}/redis/checkout-cache/replica.")
    b.edge("redis_health", "e_failover", "failover_runbook", failover_id,
           "file")
    b.node("replica_status", f"Replica status: {s['replica_status']}. "
           f"Attempt promotion at {base}/redis/checkout-cache/promote.")
    b.edge("failover_runbook", "e_replica_status", "replica_status",
           f"{base}/redis/checkout-cache/replica", "endpoint")
    b.node("failover_blocked", f"{s['failover_blocked']}.")
    b.edge("replica_status", "e_failover_blocked", "failover_blocked",
           f"{base}/redis/checkout-cache/promote", "endpoint")
    b.node("maintenance", f"Maintenance window: {s['maintenance']}. Include "
           "the remaining window in the incident constraints.")
    b.edge("redis_health", "e_maintenance", "maintenance", maint_id, "web")
    b.node("slo", f"SLO: {s['slo']}. Include the recovery target in the "
           "incident constraints.")
    b.edge("redis_health", "e_slo", "slo", slo_id, "file")
    b.node("fallback_inventory", f"Application fallback: "
           f"{s['fallback_inventory']}. Include it in the incident "
           "constraints.")
    b.edge("redis_health", "e_fallback", "fallback_inventory",
           fallback_id, "file")
    b.node("replica_eta", f"Replacement-cluster ETA: {s['replica_eta']}. "
           "Include capacity timing in the incident constraints.")
    b.edge("redis_health", "e_eta", "replica_eta", eta_id, "endpoint")
    b.node("constraints", f"Incident constraints: {s['constraints_text']}. "
           f"Policy states: {c['decision_policy']['rule']} "
           f"Remediation entrypoints: {quota_id} and {enable_id}.")
    b.edge("redis_health", "e_constraints", "constraints", constraints_id,
           "file",
           requires_visited=["maintenance", "slo", "fallback_inventory",
                             "replica_eta"],
           requires_visited_n=4)

    b.node("quota_request", f"Quota: {s['quota']}. Provision the cluster at "
           f"{base}/redis/checkout-cache-b/provision.")
    b.edge("constraints", "e_quota", "quota_request", quota_id, "endpoint")
    b.node("enable_flag", f"Scoped fallback applied: {s['flag_plan']}. Run "
           f"the checkout canary at {canary_id}.")
    b.edge("constraints", "e_enable_flag", "enable_flag", enable_id, "endpoint")
    b.node("flag_canary", f"Fallback canary: {s['flag_canary']}. Complete "
           f"with {base}/incidents/{ticket}/complete?plan=local-cache.")
    b.edge("enable_flag", "e_flag_canary", "flag_canary", canary_id, "endpoint")
    b.node("provision", f"Provision: {s['provision']}. Wait for replica sync "
           f"at {base}/redis/checkout-cache-b/sync.")
    b.edge("quota_request", "e_provision", "provision",
           f"{base}/redis/checkout-cache-b/provision", "endpoint")
    b.node("replica_sync", f"Replica sync: {s['replica_sync']}. Inspect "
           f"network ACL at {base}/redis/checkout-cache-b/acl.")
    b.edge("provision", "e_sync", "replica_sync",
           f"{base}/redis/checkout-cache-b/sync", "endpoint")
    b.node("network_acl", f"Network ACL: {s['network_acl']}. Configure DNS "
           f"cutover at {base}/dns/checkout-cache.")
    b.edge("replica_sync", "e_acl", "network_acl",
           f"{base}/redis/checkout-cache-b/acl", "endpoint")
    b.node("dns_cutover", f"DNS cutover: {s['dns_cutover']}. Inspect cluster "
           f"readiness at {base}/redis/checkout-cache-b/readiness.")
    b.edge("network_acl", "e_dns", "dns_cutover",
           f"{base}/dns/checkout-cache", "file")
    b.node("cluster_ready", f"Cluster readiness: {s['cluster_ready']}. Run "
           f"cluster health at {base}/redis/checkout-cache-b/health.")
    b.edge("dns_cutover", "e_ready", "cluster_ready",
           f"{base}/redis/checkout-cache-b/readiness", "endpoint")
    b.node("cluster_health", f"Cluster health: {s['cluster_health']}. Run "
           f"checkout verification at {base}/verifications/{ticket}/"
           "checkout-after-cutover.")
    b.edge("cluster_ready", "e_cluster_health", "cluster_health",
           f"{base}/redis/checkout-cache-b/health", "endpoint")
    b.node("cutover_verify", f"Cutover verification: {s['cutover_verify']}. "
           f"Complete with {base}/incidents/{ticket}/complete?plan=new-cluster.")
    b.edge("cluster_health", "e_cutover_verify", "cutover_verify",
           f"{base}/verifications/{ticket}/checkout-after-cutover", "endpoint")

    b.node("target", "Checkout availability restored with a verified "
           "remediation. Task complete.")
    common = ["incident_scope", "redis_degraded", "window_context",
              "slo_deadline", "fallback_available", "capacity_timing",
              "constraints_ack"]
    b.edge("flag_canary", "e_complete_flag", "target",
           f"{base}/incidents/{ticket}/complete?plan=local-cache",
           "endpoint", requires=common + ["scoped_verified"])
    b.edge("cutover_verify", "e_complete_cluster", "target",
           f"{base}/incidents/{ticket}/complete?plan=new-cluster",
           "endpoint", requires=common + ["capacity_verified"])

    grants = {
        "ticket": "incident_scope",
        "redis_health": "redis_degraded",
        "maintenance": "window_context",
        "slo": "slo_deadline",
        "fallback_inventory": "fallback_available",
        "replica_eta": "capacity_timing",
        "constraints": "constraints_ack",
        "flag_canary": "scoped_verified",
        "cutover_verify": "capacity_verified",
    }
    dead = ["failover_runbook", "replica_status", "failover_blocked"]
    for node, desc, slug in (
            ("tls_certs", "checkout-api TLS certificates expire in 46 days "
             "and did not rotate in this window.", "tls"),
            ("cdn_status", "The public CDN is healthy; checkout HTML/JS are "
             "not on the Redis path.", "cdn")):
        b.node(node, desc)
        b.edge("dashboard", "e_" + node, node,
               f"{base}/diagnostics/{ticket}/{slug}", "endpoint")
        dead.append(node)
    return b.result(_meta(c, grants, dead, {
        "incident": ["ticket", "dashboard", "redis_health"],
        "mandatory_information": ["maintenance", "slo", "fallback_inventory",
                                  "replica_eta", "constraints"],
        "short_plan": ["enable_flag", "flag_canary"],
        "long_plan": ["quota_request", "provision", "replica_sync",
                      "network_acl", "dns_cutover", "cluster_ready",
                      "cluster_health", "cutover_verify"],
        "plausible_distractors": dead,
    }, 11))
