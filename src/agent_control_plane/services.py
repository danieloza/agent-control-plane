from __future__ import annotations

from statistics import mean

from .models import CompareView, Incident, Overview, Run, RunDetail, Scenario
from .repository import InMemoryRepository


class ControlPlaneService:
    def __init__(self, repository: InMemoryRepository) -> None:
        self.repository = repository

    def get_overview(self) -> Overview:
        runs = self.repository.list_runs()
        return Overview(
            active_runs=len([run for run in runs if run.status in {"approval_required", "in_progress"}]),
            pending_approvals=len([run for run in runs if run.status == "approval_required"]),
            open_incidents=len([incident for incident in self.repository.list_incidents() if incident.status == "open"]),
            blocked_runs=len([run for run in runs if run.status == "blocked"]),
            avg_cost_usd=round(mean(run.cost_usd for run in runs), 3),
            avg_latency_ms=round(mean(run.latency_ms for run in runs)),
            eval_health=round(mean(run.evals.quality for run in runs)),
        )

    def list_runs(self) -> list[Run]:
        return self.repository.list_runs()

    def list_scenarios(self) -> list[Scenario]:
        return self.repository.list_scenarios()

    def get_run_detail(self, run_id: str) -> RunDetail:
        return RunDetail(
            run=self.repository.get_run(run_id),
            timeline=self.repository.get_steps(run_id),
            incident=self.repository.get_incident_by_run(run_id),
            replay=self.repository.get_replay_for_run(run_id),
        )

    def compare_runs(self, left_run_id: str, right_run_id: str) -> CompareView:
        return self.repository.compare_runs(left_run_id, right_run_id)

    def list_review_queue(self) -> list[dict]:
        items = []
        for run in self.repository.list_runs():
            if run.status in {"approval_required", "blocked"}:
                items.append(
                    {
                        "run_id": run.id,
                        "priority": "critical" if run.risk_score > 85 else "high" if run.risk_score > 60 else "medium",
                        "next_action": "Investigate incident" if run.status == "blocked" else "Review approval",
                        "owner": run.pending_reviewer or "security-lead",
                        "risk_score": run.risk_score,
                    }
                )
        return items

    def get_queue_summary(self) -> list[dict]:
        ownership: dict[str, dict] = {}
        for item in self.list_review_queue():
            owner = item["owner"] or "unassigned"
            summary = ownership.setdefault(owner, {"owner": owner, "items": 0, "critical": 0, "high": 0})
            summary["items"] += 1
            if item["priority"] == "critical":
                summary["critical"] += 1
            if item["priority"] == "high":
                summary["high"] += 1
        return sorted(ownership.values(), key=lambda item: (-item["critical"], -item["items"], item["owner"]))

    def list_activity(self) -> list[dict]:
        return [item.model_dump() for item in self.repository.list_activity()]

    def list_evals(self) -> list[dict]:
        return [
            {
                "run_id": run.id,
                "scenario": run.scenario,
                "quality": run.evals.quality,
                "groundedness": run.evals.groundedness,
                "tool_safety": run.evals.tool_safety,
                "latency": run.evals.latency,
                "cost_efficiency": run.evals.cost_efficiency,
            }
            for run in self.repository.list_runs()
        ]

    def list_incidents(self) -> list[Incident]:
        return self.repository.list_incidents()

    def get_trace_graph(self, run_id: str) -> dict:
        detail = self.get_run_detail(run_id)
        nodes = []
        edges = []
        for step in detail.timeline:
            nodes.append(
                {
                    "id": step.id,
                    "label": step.title,
                    "type": step.step_type,
                    "boundary": step.boundary,
                    "verdict": step.verdict,
                }
            )
        for left, right in zip(detail.timeline, detail.timeline[1:]):
            edges.append(
                {
                    "from": left.id,
                    "to": right.id,
                    "label": f"{left.step_type} -> {right.step_type}",
                }
            )
        return {"run_id": run_id, "nodes": nodes, "edges": edges}

    def get_comparison_matrix(self) -> list[dict]:
        runs = self.repository.list_runs()
        matrix = []
        for run in runs:
            matrix.append(
                {
                    "run_id": run.id,
                    "scenario": run.scenario,
                    "status": run.status,
                    "risk_score": run.risk_score,
                    "cost_usd": run.cost_usd,
                    "latency_ms": run.latency_ms,
                    "tool_safety": run.evals.tool_safety,
                    "quality": run.evals.quality,
                }
            )
        return matrix

    def get_operator_context(self) -> dict:
        return {
            "active_profile": "ops-supervisor",
            "role": "operator",
            "tenant_scope": ["acme-support", "acme-ops", "acme-finance"],
            "permissions": ["review", "approve", "replay", "contain_incident"],
        }

    def list_operator_profiles(self) -> list[dict]:
        return [
            {
                "id": "ops-supervisor",
                "label": "Ops Supervisor",
                "role": "operator",
                "tenant_scope": ["acme-support", "acme-ops"],
                "permissions": ["review", "approve", "replay"],
            },
            {
                "id": "security-lead",
                "label": "Security Lead",
                "role": "security",
                "tenant_scope": ["acme-finance", "acme-ops"],
                "permissions": ["review", "contain_incident", "replay", "assign_owner"],
            },
            {
                "id": "platform-admin",
                "label": "Platform Admin",
                "role": "admin",
                "tenant_scope": ["acme-support", "acme-ops", "acme-finance"],
                "permissions": ["review", "approve", "replay", "contain_incident", "assign_owner"],
            },
        ]

    def render_report_markdown(self, run_id: str) -> str:
        detail = self.get_run_detail(run_id)
        run = detail.run
        lines = [
            f"# Run Report: {run.id}",
            "",
            f"- Agent: `{run.agent_name}`",
            f"- Scenario: `{run.scenario}`",
            f"- Status: `{run.status}`",
            f"- Risk score: `{run.risk_score}`",
            f"- Cost: `${run.cost_usd:.3f}`",
            f"- Latency: `{run.latency_ms}ms`",
            "",
            "## Objective",
            run.objective,
            "",
            "## Timeline",
        ]
        for step in detail.timeline:
            lines.extend(
                [
                    f"- Step {step.index} `{step.step_type}` | `{step.verdict}`",
                    f"  {step.title}",
                    f"  Policy: {step.policy_name} - {step.policy_reason}",
                ]
            )
        if detail.replay:
            lines.extend(["", "## Replay", detail.replay.summary])
        if detail.incident:
            lines.extend(["", "## Incident", detail.incident.summary])
        return "\n".join(lines)

    def render_incident_markdown(self, run_id: str) -> str:
        incident = self.repository.get_incident_by_run(run_id)
        if not incident:
            raise KeyError(run_id)
        detail = self.get_run_detail(run_id)
        lines = [
            f"# Incident Bundle: {incident.id}",
            "",
            f"- Run: `{incident.run_id}`",
            f"- Severity: `{incident.severity}`",
            f"- Status: `{incident.status}`",
            f"- Owner: `{incident.owner}`",
            "",
            "## Summary",
            incident.summary,
            "",
            "## Trigger Steps",
        ]
        for step in detail.timeline:
            if step.verdict == "blocked" or step.failure_class:
                lines.extend(
                    [
                        f"- Step {step.index}: {step.title}",
                        f"  Verdict: {step.verdict}",
                        f"  Failure class: {step.failure_class or 'n/a'}",
                    ]
                )
        return "\n".join(lines)

    def launch_run(self, scenario_id: str) -> Run:
        return self.repository.create_run_from_scenario(scenario_id)

    def apply_approval(self, run_id: str, action: str) -> Run:
        return self.repository.approve_run(run_id, action)

    def update_incident(self, run_id: str, action: str, owner: str | None) -> Incident | None:
        return self.repository.update_incident(run_id, action, owner)

    def create_replay(self, run_id: str, mode: str) -> dict:
        replay = self.repository.create_replay(run_id, mode)
        compare = self.repository.compare_runs(run_id, replay.run_id)
        return {"replay": replay, "compare": compare}
