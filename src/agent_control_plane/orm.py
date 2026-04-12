from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class ScenarioRecord(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    objective: Mapped[str] = mapped_column(Text)
    agent_name: Mapped[str] = mapped_column(String(128))
    risk_score: Mapped[int] = mapped_column(Integer)
    expected_status: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text)


class RunRecord(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant: Mapped[str] = mapped_column(String(128))
    agent_name: Mapped[str] = mapped_column(String(128))
    objective: Mapped[str] = mapped_column(Text)
    scenario: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(64))
    policy_bundle: Mapped[str] = mapped_column(String(64))
    risk_score: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    cost_usd: Mapped[float] = mapped_column(Float)
    latency_ms: Mapped[int] = mapped_column(Integer)
    trust_boundaries: Mapped[list[str]] = mapped_column(JSON)
    pending_reviewer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    incident_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latest_replay_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[str] = mapped_column(String(64))
    eval_quality: Mapped[int] = mapped_column(Integer)
    eval_groundedness: Mapped[int] = mapped_column(Integer)
    eval_tool_safety: Mapped[int] = mapped_column(Integer)
    eval_latency: Mapped[int] = mapped_column(Integer)
    eval_cost_efficiency: Mapped[int] = mapped_column(Integer)

    steps: Mapped[list["StepRecord"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class StepRecord(Base):
    __tablename__ = "steps"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    index: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255))
    actor: Mapped[str] = mapped_column(String(64))
    boundary: Mapped[str] = mapped_column(String(32))
    verdict: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text)
    policy_name: Mapped[str] = mapped_column(String(255))
    policy_reason: Mapped[str] = mapped_column(Text)
    failure_class: Mapped[str | None] = mapped_column(String(128), nullable=True)

    run: Mapped[RunRecord] = relationship(back_populates="steps")


class IncidentRecord(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    owner: Mapped[str] = mapped_column(String(128))
    summary: Mapped[str] = mapped_column(Text)


class ReplayRecord(Base):
    __tablename__ = "replays"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    parent_run_id: Mapped[str] = mapped_column(String(64))
    run_id: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(Text)


class ActivityEventRecord(Base):
    __tablename__ = "activity_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[str] = mapped_column(String(64))


class OperatorNoteRecord(Base):
    __tablename__ = "operator_notes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    author: Mapped[str] = mapped_column(String(128))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64))


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128))
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64))


class ReplayJobRecord(Base):
    __tablename__ = "replay_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(64))
    requested_by: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[str] = mapped_column(String(64))
    result_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    replay_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
