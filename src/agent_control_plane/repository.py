from __future__ import annotations

from copy import deepcopy

from .models import ActivityEvent, CompareView, EvalScorecard, Incident, Replay, Run, Scenario, Step


class InMemoryRepository:
    def __init__(self) -> None:
        self.scenarios = {
            "support_read_only": Scenario(
                id="support_read_only",
                name="Support Read-Only",
                objective="Summarize a customer escalation after checking internal KB and CRM context.",
                agent_name="support-agent",
                risk_score=38,
                expected_status="completed",
                summary="Safe read-only support workflow.",
            ),
            "customer_update": Scenario(
                id="customer_update",
                name="Customer Update Approval",
                objective="Draft an outbound customer-impact update that should stop for human approval.",
                agent_name="ops-triage-agent",
                risk_score=69,
                expected_status="approval_required",
                summary="Customer-facing workflow held for approval.",
            ),
            "finance_write": Scenario(
                id="finance_write",
                name="Finance Write Block",
                objective="Attempt a sensitive ERP write that should be blocked and escalated.",
                agent_name="finance-ops-agent",
                risk_score=93,
                expected_status="blocked",
                summary="High-risk finance flow with incident escalation.",
            ),
        }

        self.runs = {
            "run_5201": Run(
                id="run_5201",
                tenant="acme-support",
                agent_name="support-agent",
                objective=self.scenarios["support_read_only"].objective,
                scenario="support_read_only",
                model="gpt-5.4",
                policy_bundle="bundle_v8",
                risk_score=38,
                status="completed",
                cost_usd=0.021,
                latency_ms=1680,
                trust_boundaries=["user", "internal", "external"],
                created_at="2026-04-10T08:00:11Z",
                updated_at="2026-04-10T08:00:14Z",
                evals=EvalScorecard(quality=92, groundedness=95, tool_safety=98, latency=87, cost_efficiency=90),
            ),
            "run_5202": Run(
                id="run_5202",
                tenant="acme-ops",
                agent_name="ops-triage-agent",
                objective=self.scenarios["customer_update"].objective,
                scenario="customer_update",
                model="gpt-5.4",
                policy_bundle="bundle_v8",
                risk_score=69,
                status="approval_required",
                cost_usd=0.039,
                latency_ms=2140,
                trust_boundaries=["user", "internal", "external", "sensitive"],
                pending_reviewer="ops-lead",
                created_at="2026-04-10T08:03:11Z",
                updated_at="2026-04-10T08:03:15Z",
                evals=EvalScorecard(quality=86, groundedness=88, tool_safety=74, latency=79, cost_efficiency=78),
            ),
            "run_5203": Run(
                id="run_5203",
                tenant="acme-finance",
                agent_name="finance-ops-agent",
                objective=self.scenarios["finance_write"].objective,
                scenario="finance_write",
                model="gpt-5.4",
                policy_bundle="bundle_v8",
                risk_score=93,
                status="blocked",
                cost_usd=0.057,
                latency_ms=2470,
                trust_boundaries=["user", "internal", "external", "sensitive"],
                incident_id="inc_5203",
                latest_replay_id="rpl_6203",
                created_at="2026-04-10T08:07:11Z",
                updated_at="2026-04-10T08:07:17Z",
                evals=EvalScorecard(quality=64, groundedness=72, tool_safety=28, latency=66, cost_efficiency=71),
            ),
            "run_5204": Run(
                id="run_5204",
                tenant="acme-finance",
                agent_name="finance-ops-agent",
                objective="Replay of the blocked finance write under stricter controls.",
                scenario="finance_write",
                model="gpt-5.4",
                policy_bundle="bundle_v9_strict",
                risk_score=61,
                status="approval_required",
                cost_usd=0.049,
                latency_ms=2360,
                trust_boundaries=["user", "internal", "external", "sensitive"],
                pending_reviewer="security-lead",
                created_at="2026-04-10T08:09:11Z",
                updated_at="2026-04-10T08:09:14Z",
                evals=EvalScorecard(quality=78, groundedness=84, tool_safety=81, latency=70, cost_efficiency=72),
            ),
        }

        self.steps = {
            "run_5201": [
                Step(id="step_1", run_id="run_5201", index=1, step_type="input", title="Customer escalation received", actor="user", boundary="user", verdict="allowed", summary="User requested a summarized response after internal review.", policy_name="Support intake", policy_reason="Read-only support request is permitted."),
                Step(id="step_2", run_id="run_5201", index=2, step_type="planning", title="Read-only support plan selected", actor="assistant", boundary="internal", verdict="allowed", summary="Planner selected KB lookup and CRM read without outbound action.", policy_name="Read-only workflow", policy_reason="No sensitive action in the execution plan."),
                Step(id="step_3", run_id="run_5201", index=3, step_type="retrieval", title="Knowledge base evidence loaded", actor="tool", boundary="external", verdict="allowed", summary="Relevant KB sections and prior support notes were retrieved.", policy_name="Knowledge retrieval", policy_reason="Approved read-only retrieval path."),
                Step(id="step_4", run_id="run_5201", index=4, step_type="response", title="Safe summary returned", actor="assistant", boundary="model", verdict="allowed", summary="Grounded answer returned without write action or outbound release.", policy_name="Read-only completion", policy_reason="The answer stayed within the approved support scope."),
            ],
            "run_5202": [
                Step(id="step_1", run_id="run_5202", index=1, step_type="input", title="Customer-impact task received", actor="user", boundary="user", verdict="allowed", summary="Outbound customer-impact workflow that should stop in approval before release.", policy_name="Support intake", policy_reason="The request is allowed to enter review flow."),
                Step(id="step_2", run_id="run_5202", index=2, step_type="planning", title="Planner selected outbound path", actor="assistant", boundary="internal", verdict="allowed", summary="Planner prepared CRM read plus a draft customer update.", policy_name="Plan outbound response", policy_reason="Planning is allowed before sensitive release."),
                Step(id="step_3", run_id="run_5202", index=3, step_type="tool_call", title="CRM account context loaded", actor="tool", boundary="external", verdict="allowed", summary="Agent pulled account state and prior dispute history before drafting.", policy_name="CRM read scope", policy_reason="Read-only SaaS lookup crossed the external boundary safely."),
                Step(id="step_4", run_id="run_5202", index=4, step_type="approval", title="Outbound update routed to approval", actor="policy", boundary="sensitive", verdict="approval_required", summary="Policy intercepted the release because it could affect the customer experience.", policy_name="Customer-impact approval", policy_reason="Sensitive customer-facing action requires human approval.", failure_class="Policy Drift"),
                Step(id="step_5", run_id="run_5202", index=5, step_type="response", title="Draft held for operator", actor="assistant", boundary="model", verdict="approval_required", summary="A draft exists, but it is withheld until an operator decides how to proceed.", policy_name="Approval hold", policy_reason="Model output cannot be released without human approval."),
            ],
            "run_5203": [
                Step(id="step_1", run_id="run_5203", index=1, step_type="input", title="Refund investigation initiated", actor="user", boundary="user", verdict="allowed", summary="Agent asked to verify a duplicate refund and update ERP state.", policy_name="Finance intake", policy_reason="The request can enter controlled execution."),
                Step(id="step_2", run_id="run_5203", index=2, step_type="planning", title="High-risk write plan generated", actor="assistant", boundary="internal", verdict="allowed", summary="Planner selected refund history lookup plus a production ERP write.", policy_name="Finance planning", policy_reason="Planning allowed, write action still subject to gate."),
                Step(id="step_3", run_id="run_5203", index=3, step_type="tool_call", title="ERP write attempt intercepted", actor="policy", boundary="sensitive", verdict="blocked", summary="Production ERP write was blocked due to prompt injection signal and risk bundle mismatch.", policy_name="Production finance guardrail", policy_reason="Sensitive write is blocked under current bundle.", failure_class="Prompt Injection Risk"),
                Step(id="step_4", run_id="run_5203", index=4, step_type="response", title="Incident opened and run stopped", actor="system", boundary="internal", verdict="blocked", summary="The run was halted and escalated to incident review.", policy_name="Incident escalation", policy_reason="Risk threshold exceeded, manual investigation required."),
            ],
            "run_5204": [
                Step(id="step_1", run_id="run_5204", index=1, step_type="input", title="Finance replay requested", actor="operator", boundary="user", verdict="allowed", summary="Blocked run was replayed under stricter controls and review mode.", policy_name="Replay authorization", policy_reason="Replay is permitted for review and evaluation."),
                Step(id="step_2", run_id="run_5204", index=2, step_type="planning", title="Read-only reconciliation plan selected", actor="assistant", boundary="internal", verdict="allowed", summary="Planner replaced direct write with a staged reconciliation workflow.", policy_name="Safer finance planning", policy_reason="Strict bundle downgraded the action plan."),
                Step(id="step_3", run_id="run_5204", index=3, step_type="approval", title="Staged reconciliation requires approval", actor="policy", boundary="sensitive", verdict="approval_required", summary="Replay no longer hard-blocks but still requires human approval for staged release.", policy_name="Strict finance approval", policy_reason="Write intent transformed into approval-gated staged action."),
            ],
        }

        self.incidents = {
            "inc_5203": Incident(id="inc_5203", run_id="run_5203", title="Finance write blocked after prompt injection signal", severity="critical", status="open", owner="security-lead", summary="Sensitive finance write request crossed the risk threshold and triggered incident review.")
        }

        self.replays = {
            "rpl_6203": Replay(id="rpl_6203", parent_run_id="run_5203", run_id="run_5204", mode="stricter_controls", summary="Strict replay converted block into approval-gated staged action.")
        }

        self.activity = [
            ActivityEvent(id="evt_1", run_id="run_5204", label="Replay completed under strict bundle", category="replay", timestamp="2026-04-10T08:09:14Z"),
            ActivityEvent(id="evt_2", run_id="run_5203", label="Critical incident opened", category="incident", timestamp="2026-04-10T08:07:17Z"),
            ActivityEvent(id="evt_3", run_id="run_5202", label="Approval requested for outbound update", category="approval", timestamp="2026-04-10T08:03:15Z"),
        ]

    def list_runs(self) -> list[Run]:
        return sorted(self.runs.values(), key=lambda run: run.created_at, reverse=True)

    def get_run(self, run_id: str) -> Run:
        return self.runs[run_id]

    def get_steps(self, run_id: str) -> list[Step]:
        return self.steps.get(run_id, [])

    def list_scenarios(self) -> list[Scenario]:
        return list(self.scenarios.values())

    def get_incident_by_run(self, run_id: str) -> Incident | None:
        for incident in self.incidents.values():
            if incident.run_id == run_id:
                return incident
        return None

    def get_replay_for_run(self, run_id: str) -> Replay | None:
        replay_id = self.runs[run_id].latest_replay_id
        return self.replays.get(replay_id) if replay_id else None

    def list_incidents(self) -> list[Incident]:
        return list(self.incidents.values())

    def list_activity(self) -> list[ActivityEvent]:
        return self.activity

    def create_run_from_scenario(self, scenario_id: str) -> Run:
        scenario = self.scenarios[scenario_id]
        next_index = max(int(run_id.split("_")[1]) for run_id in self.runs) + 1
        run_id = f"run_{next_index}"
        seed_map = {"support_read_only": "run_5201", "customer_update": "run_5202", "finance_write": "run_5203"}
        template_run = self.runs[seed_map[scenario_id]]
        run = template_run.model_copy(deep=True)
        run.id = run_id
        run.tenant = "acme-sim"
        run.created_at = "2026-04-10T09:00:00Z"
        run.updated_at = "2026-04-10T09:00:03Z"
        self.runs[run_id] = run
        self.steps[run_id] = deepcopy(self.steps[seed_map[scenario_id]])
        for index, step in enumerate(self.steps[run_id], start=1):
            step.run_id = run_id
            step.id = f"{run_id}_step_{index}"
        self.activity.insert(0, ActivityEvent(id=f"evt_{len(self.activity) + 1}", run_id=run_id, label=f"Scenario launched: {scenario.name}", category="launch", timestamp="2026-04-10T09:00:03Z"))
        return run

    def approve_run(self, run_id: str, action: str) -> Run:
        run = self.runs[run_id]
        if action == "approve":
            run.status = "completed"
            run.pending_reviewer = None
        elif action == "reject":
            run.status = "blocked"
        else:
            run.pending_reviewer = "manager-review"
        run.updated_at = "2026-04-10T09:05:00Z"
        return run

    def update_incident(self, run_id: str, action: str, owner: str | None) -> Incident | None:
        incident = self.get_incident_by_run(run_id)
        if not incident:
            return None
        if action == "contain":
            incident.status = "contained"
        elif action == "mitigate":
            incident.status = "mitigated"
        elif action == "reopen":
            incident.status = "open"
        elif action == "assign_owner" and owner:
            incident.owner = owner
        return incident

    def create_replay(self, run_id: str, mode: str) -> Replay:
        parent = self.runs[run_id]
        next_index = max(int(item.split("_")[1]) for item in self.runs) + 1
        replay_run_id = f"run_{next_index}"
        replay_id = f"rpl_{next_index + 1000}"
        replay_run = parent.model_copy(deep=True)
        replay_run.id = replay_run_id
        replay_run.objective = f"Replay of {parent.objective}"
        replay_run.policy_bundle = f"{parent.policy_bundle}_{mode}"
        replay_run.risk_score = max(parent.risk_score - 14, 30)
        replay_run.status = "approval_required" if parent.status != "completed" else "completed"
        replay_run.cost_usd = max(parent.cost_usd - 0.006, 0.01)
        replay_run.latency_ms = max(parent.latency_ms - 120, 900)
        replay_run.created_at = "2026-04-10T09:10:00Z"
        replay_run.updated_at = "2026-04-10T09:10:04Z"
        replay_run.evals.tool_safety = min(parent.evals.tool_safety + 28, 100)
        replay_run.evals.groundedness = min(parent.evals.groundedness + 5, 100)
        self.runs[replay_run_id] = replay_run
        self.steps[replay_run_id] = deepcopy(self.steps[run_id])
        for index, step in enumerate(self.steps[replay_run_id], start=1):
            step.run_id = replay_run_id
            step.id = f"{replay_run_id}_step_{index}"
            if step.verdict == "blocked":
                step.verdict = "approval_required"
                step.summary = "Strict replay downgraded the hard block into an approval-gated staged action."
        replay = Replay(id=replay_id, parent_run_id=run_id, run_id=replay_run_id, mode=mode, summary="Replay generated with safer controls and improved tool safety.")
        self.replays[replay_id] = replay
        parent.latest_replay_id = replay_id
        return replay

    def compare_runs(self, left_run_id: str, right_run_id: str) -> CompareView:
        left = self.runs[left_run_id]
        right = self.runs[right_run_id]
        return CompareView(
            left_run_id=left_run_id,
            right_run_id=right_run_id,
            status_change=f"{left.status} -> {right.status}",
            risk_delta=right.risk_score - left.risk_score,
            cost_delta=round(right.cost_usd - left.cost_usd, 3),
            latency_delta=right.latency_ms - left.latency_ms,
            control_delta="safer controls" if right.evals.tool_safety > left.evals.tool_safety else "no improvement",
        )
