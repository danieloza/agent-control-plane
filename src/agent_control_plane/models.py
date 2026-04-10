from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RunStatus = Literal["completed", "approval_required", "blocked", "in_progress"]
StepType = Literal["input", "planning", "retrieval", "tool_call", "approval", "response"]
BoundaryType = Literal["user", "internal", "external", "sensitive", "model"]
VerdictType = Literal["allowed", "approval_required", "blocked"]
SeverityType = Literal["low", "medium", "high", "critical"]
ReplayMode = Literal["stricter_controls", "read_only", "staging_only"]
ApprovalAction = Literal["approve", "reject", "escalate"]
IncidentAction = Literal["contain", "mitigate", "reopen", "assign_owner"]


class Step(BaseModel):
    id: str
    run_id: str
    index: int
    step_type: StepType
    title: str
    actor: str
    boundary: BoundaryType
    verdict: VerdictType
    summary: str
    policy_name: str
    policy_reason: str
    failure_class: str | None = None


class EvalScorecard(BaseModel):
    quality: int = Field(ge=0, le=100)
    groundedness: int = Field(ge=0, le=100)
    tool_safety: int = Field(ge=0, le=100)
    latency: int = Field(ge=0, le=100)
    cost_efficiency: int = Field(ge=0, le=100)


class Incident(BaseModel):
    id: str
    run_id: str
    title: str
    severity: SeverityType
    status: Literal["open", "contained", "mitigated"]
    owner: str
    summary: str


class Replay(BaseModel):
    id: str
    parent_run_id: str
    run_id: str
    mode: ReplayMode
    summary: str


class Run(BaseModel):
    id: str
    tenant: str
    agent_name: str
    objective: str
    scenario: str
    model: str
    policy_bundle: str
    risk_score: int
    status: RunStatus
    cost_usd: float
    latency_ms: int
    trust_boundaries: list[BoundaryType]
    pending_reviewer: str | None = None
    incident_id: str | None = None
    latest_replay_id: str | None = None
    created_at: str
    updated_at: str
    evals: EvalScorecard


class Scenario(BaseModel):
    id: str
    name: str
    objective: str
    agent_name: str
    risk_score: int
    expected_status: RunStatus
    summary: str


class ActivityEvent(BaseModel):
    id: str
    run_id: str
    label: str
    category: str
    timestamp: str


class Overview(BaseModel):
    active_runs: int
    pending_approvals: int
    open_incidents: int
    blocked_runs: int
    avg_cost_usd: float
    avg_latency_ms: int
    eval_health: int


class RunDetail(BaseModel):
    run: Run
    timeline: list[Step]
    incident: Incident | None
    replay: Replay | None


class CompareView(BaseModel):
    left_run_id: str
    right_run_id: str
    status_change: str
    risk_delta: int
    cost_delta: float
    latency_delta: int
    control_delta: str


class LaunchRunRequest(BaseModel):
    scenario_id: str


class ApprovalRequest(BaseModel):
    action: ApprovalAction


class IncidentRequest(BaseModel):
    action: IncidentAction
    owner: str | None = None


class ReplayRequest(BaseModel):
    mode: ReplayMode
