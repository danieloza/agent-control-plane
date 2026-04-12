from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from .models import ActivityEvent, AuditEvent, CompareView, EvalScorecard, Incident, OperatorNote, Replay, ReplayJob, Run, Scenario, Step
from .orm import ActivityEventRecord, AuditEventRecord, IncidentRecord, OperatorNoteRecord, ReplayJobRecord, ReplayRecord, RunRecord, ScenarioRecord, StepRecord
from .seed_data import SEED_DATA


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class DatabaseRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def seed_if_empty(self) -> None:
        with self.session_factory() as session:
            if session.scalar(select(func.count()).select_from(RunRecord)):
                return
            session.add_all(ScenarioRecord(**item) for item in SEED_DATA["scenarios"])
            session.add_all(RunRecord(**item) for item in SEED_DATA["runs"])
            session.add_all(StepRecord(**item) for item in SEED_DATA["steps"])
            session.add_all(IncidentRecord(**item) for item in SEED_DATA["incidents"])
            session.add_all(ReplayRecord(**item) for item in SEED_DATA["replays"])
            session.add_all(ActivityEventRecord(**item) for item in SEED_DATA["activity"])
            session.add_all(OperatorNoteRecord(**item) for item in SEED_DATA["operator_notes"])
            session.add_all(AuditEventRecord(**item) for item in SEED_DATA["audit_events"])
            session.commit()

    def list_runs(self) -> list[Run]:
        with self.session_factory() as session:
            rows = session.scalars(select(RunRecord).order_by(RunRecord.created_at.desc())).all()
            return [self._to_run(row) for row in rows]

    def get_run(self, run_id: str) -> Run:
        with self.session_factory() as session:
            row = session.get(RunRecord, run_id)
            if row is None:
                raise KeyError(run_id)
            return self._to_run(row)

    def get_steps(self, run_id: str) -> list[Step]:
        with self.session_factory() as session:
            rows = session.scalars(select(StepRecord).where(StepRecord.run_id == run_id).order_by(StepRecord.index.asc())).all()
            return [self._to_step(row) for row in rows]

    def list_scenarios(self) -> list[Scenario]:
        with self.session_factory() as session:
            rows = session.scalars(select(ScenarioRecord).order_by(ScenarioRecord.id.asc())).all()
            return [self._to_scenario(row) for row in rows]

    def get_incident_by_run(self, run_id: str) -> Incident | None:
        with self.session_factory() as session:
            row = session.scalar(select(IncidentRecord).where(IncidentRecord.run_id == run_id))
            return self._to_incident(row) if row else None

    def get_replay_for_run(self, run_id: str) -> Replay | None:
        with self.session_factory() as session:
            run = session.get(RunRecord, run_id)
            if not run or not run.latest_replay_id:
                return None
            replay = session.get(ReplayRecord, run.latest_replay_id)
            return self._to_replay(replay) if replay else None

    def list_incidents(self) -> list[Incident]:
        with self.session_factory() as session:
            rows = session.scalars(select(IncidentRecord).order_by(IncidentRecord.id.asc())).all()
            return [self._to_incident(row) for row in rows]

    def list_activity(self) -> list[ActivityEvent]:
        with self.session_factory() as session:
            rows = session.scalars(select(ActivityEventRecord).order_by(ActivityEventRecord.timestamp.desc())).all()
            return [self._to_activity(row) for row in rows]

    def list_jobs(self, status: str | None = None) -> list[ReplayJob]:
        with self.session_factory() as session:
            stmt = select(ReplayJobRecord)
            if status:
                stmt = stmt.where(ReplayJobRecord.status == status)
            rows = session.scalars(stmt.order_by(ReplayJobRecord.created_at.desc())).all()
            return [self._to_job(row) for row in rows]

    def queue_depth(self) -> int:
        with self.session_factory() as session:
            return int(session.scalar(select(func.count()).select_from(ReplayJobRecord).where(ReplayJobRecord.status == "queued")) or 0)

    def list_operator_notes(self, run_id: str) -> list[OperatorNote]:
        with self.session_factory() as session:
            rows = session.scalars(select(OperatorNoteRecord).where(OperatorNoteRecord.run_id == run_id).order_by(OperatorNoteRecord.created_at.desc())).all()
            return [self._to_note(row) for row in rows]

    def add_operator_note(self, run_id: str, author: str, body: str) -> OperatorNote:
        with self.session_factory() as session:
            run = session.get(RunRecord, run_id)
            if run is None:
                raise KeyError(run_id)
            note = OperatorNoteRecord(
                id=f"note_{self._next_numeric_id(session, OperatorNoteRecord, 'note_')}",
                run_id=run_id,
                author=author,
                body=body,
                created_at=utc_now(),
            )
            session.add(note)
            self._append_audit_event(session, run_id, author, "operator_note_added", "Operator note attached to run review.")
            session.commit()
            return self._to_note(note)

    def list_audit_events(self, run_id: str | None = None) -> list[AuditEvent]:
        with self.session_factory() as session:
            stmt = select(AuditEventRecord)
            if run_id:
                stmt = stmt.where(AuditEventRecord.run_id == run_id)
            rows = session.scalars(stmt.order_by(AuditEventRecord.created_at.desc())).all()
            return [self._to_audit(row) for row in rows]

    def create_run_from_scenario(self, scenario_id: str) -> Run:
        seed_map = {"support_read_only": "run_5201", "customer_update": "run_5202", "finance_write": "run_5203"}
        template_id = seed_map[scenario_id]
        with self.session_factory() as session:
            template = session.get(RunRecord, template_id)
            if template is None:
                raise KeyError(scenario_id)
            next_run_number = self._next_numeric_id(session, RunRecord, "run_")
            run_id = f"run_{next_run_number}"
            now = utc_now()
            run = RunRecord(
                **{
                    column.name: getattr(template, column.name)
                    for column in RunRecord.__table__.columns
                    if column.name not in {"id", "created_at", "updated_at"}
                },
                id=run_id,
                created_at=now,
                updated_at=now,
            )
            session.add(run)
            self._clone_steps(session, template_id, run_id)
            session.add(
                ActivityEventRecord(
                    id=f"evt_{self._next_numeric_id(session, ActivityEventRecord, 'evt_')}",
                    run_id=run_id,
                    label=f"Scenario launched: {scenario_id}",
                    category="launch",
                    timestamp=now,
                )
            )
            session.commit()
            return self._to_run(run)

    def approve_run(self, run_id: str, action: str) -> Run:
        with self.session_factory() as session:
            run = session.get(RunRecord, run_id)
            if run is None:
                raise KeyError(run_id)
            if action == "approve":
                run.status = "completed"
                run.pending_reviewer = None
            elif action == "reject":
                run.status = "blocked"
            else:
                run.pending_reviewer = "manager-review"
            run.updated_at = utc_now()
            self._append_audit_event(session, run_id, "operator", f"approval_{action}", f"Run moved through approval action '{action}'.")
            session.commit()
            return self._to_run(run)

    def update_incident(self, run_id: str, action: str, owner: str | None) -> Incident | None:
        with self.session_factory() as session:
            incident = session.scalar(select(IncidentRecord).where(IncidentRecord.run_id == run_id))
            if incident is None:
                return None
            if action == "contain":
                incident.status = "contained"
            elif action == "mitigate":
                incident.status = "mitigated"
            elif action == "reopen":
                incident.status = "open"
            elif action == "assign_owner" and owner:
                incident.owner = owner
            self._append_audit_event(session, run_id, "operator", f"incident_{action}", f"Incident action '{action}' applied.")
            session.commit()
            return self._to_incident(incident)

    def create_replay_job(self, run_id: str, mode: str, requested_by: str) -> ReplayJob:
        with self.session_factory() as session:
            run = session.get(RunRecord, run_id)
            if run is None:
                raise KeyError(run_id)
            job = ReplayJobRecord(
                id=f"job_{self._next_numeric_id(session, ReplayJobRecord, 'job_')}",
                run_id=run_id,
                mode=mode,
                requested_by=requested_by,
                status="queued",
                created_at=utc_now(),
                updated_at=utc_now(),
                result_run_id=None,
                replay_id=None,
                error=None,
                attempts=0,
                max_attempts=3,
            )
            session.add(job)
            self._append_audit_event(session, run_id, requested_by, "replay_queued", f"Replay queued under mode '{mode}'.")
            session.commit()
            return self._to_job(job)

    def get_job(self, job_id: str) -> ReplayJob:
        with self.session_factory() as session:
            job = session.get(ReplayJobRecord, job_id)
            if job is None:
                raise KeyError(job_id)
            return self._to_job(job)

    def claim_next_replay_job(self) -> ReplayJob | None:
        with self.session_factory() as session:
            job = session.scalar(
                select(ReplayJobRecord)
                .where(ReplayJobRecord.status == "queued")
                .order_by(ReplayJobRecord.created_at.asc())
            )
            if job is None:
                return None
            job.status = "processing"
            job.updated_at = utc_now()
            job.attempts += 1
            session.commit()
            return self._to_job(job)

    def create_replay(self, run_id: str, mode: str, job_id: str | None = None) -> Replay:
        with self.session_factory() as session:
            parent = session.get(RunRecord, run_id)
            if parent is None:
                raise KeyError(run_id)
            next_run_number = self._next_numeric_id(session, RunRecord, "run_")
            replay_run_id = f"run_{next_run_number}"
            replay_id = f"rpl_{next_run_number + 1000}"
            now = utc_now()
            replay_run = RunRecord(
                **{
                    column.name: getattr(parent, column.name)
                    for column in RunRecord.__table__.columns
                    if column.name not in {"id", "objective", "policy_bundle", "risk_score", "status", "cost_usd", "latency_ms", "created_at", "updated_at", "eval_tool_safety", "eval_groundedness"}
                },
                id=replay_run_id,
                objective=f"Replay of {parent.objective}",
                policy_bundle=f"{parent.policy_bundle}_{mode}",
                risk_score=max(parent.risk_score - 14, 30),
                status="approval_required" if parent.status != "completed" else "completed",
                cost_usd=max(parent.cost_usd - 0.006, 0.01),
                latency_ms=max(parent.latency_ms - 120, 900),
                created_at=now,
                updated_at=now,
                eval_tool_safety=min(parent.eval_tool_safety + 28, 100),
                eval_groundedness=min(parent.eval_groundedness + 5, 100),
            )
            session.add(replay_run)

            source_steps = session.scalars(select(StepRecord).where(StepRecord.run_id == run_id).order_by(StepRecord.index.asc())).all()
            for index, step in enumerate(source_steps, start=1):
                verdict = "approval_required" if step.verdict == "blocked" else step.verdict
                summary = "Strict replay downgraded the hard block into an approval-gated staged action." if step.verdict == "blocked" else step.summary
                session.add(
                    StepRecord(
                        id=f"{replay_run_id}_step_{index}",
                        run_id=replay_run_id,
                        index=step.index,
                        step_type=step.step_type,
                        title=step.title,
                        actor=step.actor,
                        boundary=step.boundary,
                        verdict=verdict,
                        summary=summary,
                        policy_name=step.policy_name,
                        policy_reason=step.policy_reason,
                        failure_class=step.failure_class,
                    )
                )

            replay = ReplayRecord(
                id=replay_id,
                parent_run_id=run_id,
                run_id=replay_run_id,
                mode=mode,
                summary="Replay generated with safer controls and improved tool safety.",
            )
            session.add(replay)
            parent.latest_replay_id = replay_id
            session.add(
                ActivityEventRecord(
                    id=f"evt_{self._next_numeric_id(session, ActivityEventRecord, 'evt_')}",
                    run_id=replay_run_id,
                    label="Replay completed under stricter controls",
                    category="replay",
                    timestamp=now,
                )
            )
            self._append_audit_event(session, run_id, "worker", "replay_completed", f"Replay job produced sibling run '{replay_run_id}'.")
            if job_id:
                job = session.get(ReplayJobRecord, job_id)
                if job:
                    job.status = "completed"
                    job.updated_at = now
                    job.result_run_id = replay_run_id
                    job.replay_id = replay_id
                    job.error = None
            session.commit()
            return self._to_replay(replay)

    def fail_job(self, job_id: str, error: str) -> None:
        with self.session_factory() as session:
            job = session.get(ReplayJobRecord, job_id)
            if job:
                job.status = "queued" if job.attempts < job.max_attempts else "failed"
                job.updated_at = utc_now()
                job.error = error
                action = "replay_requeued" if job.status == "queued" else "replay_failed"
                self._append_audit_event(session, job.run_id, "worker", action, error)
                session.commit()

    def compare_runs(self, left_run_id: str, right_run_id: str) -> CompareView:
        with self.session_factory() as session:
            left = session.get(RunRecord, left_run_id)
            right = session.get(RunRecord, right_run_id)
            if left is None or right is None:
                raise KeyError(left_run_id if left is None else right_run_id)
            return CompareView(
                left_run_id=left_run_id,
                right_run_id=right_run_id,
                status_change=f"{left.status} -> {right.status}",
                risk_delta=right.risk_score - left.risk_score,
                cost_delta=round(right.cost_usd - left.cost_usd, 3),
                latency_delta=right.latency_ms - left.latency_ms,
                control_delta="safer controls" if right.eval_tool_safety > left.eval_tool_safety else "no improvement",
            )

    def _clone_steps(self, session: Session, from_run_id: str, to_run_id: str) -> None:
        source_steps = session.scalars(select(StepRecord).where(StepRecord.run_id == from_run_id).order_by(StepRecord.index.asc())).all()
        for index, step in enumerate(source_steps, start=1):
            session.add(
                StepRecord(
                    id=f"{to_run_id}_step_{index}",
                    run_id=to_run_id,
                    index=step.index,
                    step_type=step.step_type,
                    title=step.title,
                    actor=step.actor,
                    boundary=step.boundary,
                    verdict=step.verdict,
                    summary=step.summary,
                    policy_name=step.policy_name,
                    policy_reason=step.policy_reason,
                    failure_class=step.failure_class,
                )
            )

    def _next_numeric_id(self, session: Session, model, prefix: str) -> int:
        ids = session.scalars(select(model.id)).all()
        numbers = [int(item.split("_")[1]) for item in ids if item.startswith(prefix)]
        return max(numbers, default=0) + 1

    def _append_audit_event(self, session: Session, run_id: str, actor: str, action: str, summary: str) -> None:
        session.add(
            AuditEventRecord(
                id=f"audit_{self._next_numeric_id(session, AuditEventRecord, 'audit_')}",
                run_id=run_id,
                actor=actor,
                action=action,
                summary=summary,
                created_at=utc_now(),
            )
        )

    def _to_scenario(self, row: ScenarioRecord) -> Scenario:
        return Scenario.model_validate({column.name: getattr(row, column.name) for column in ScenarioRecord.__table__.columns})

    def _to_run(self, row: RunRecord) -> Run:
        return Run(
            id=row.id,
            tenant=row.tenant,
            agent_name=row.agent_name,
            objective=row.objective,
            scenario=row.scenario,
            model=row.model,
            policy_bundle=row.policy_bundle,
            risk_score=row.risk_score,
            status=row.status,
            cost_usd=row.cost_usd,
            latency_ms=row.latency_ms,
            trust_boundaries=deepcopy(row.trust_boundaries),
            pending_reviewer=row.pending_reviewer,
            incident_id=row.incident_id,
            latest_replay_id=row.latest_replay_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            evals=EvalScorecard(
                quality=row.eval_quality,
                groundedness=row.eval_groundedness,
                tool_safety=row.eval_tool_safety,
                latency=row.eval_latency,
                cost_efficiency=row.eval_cost_efficiency,
            ),
        )

    def _to_step(self, row: StepRecord) -> Step:
        return Step.model_validate({column.name: getattr(row, column.name) for column in StepRecord.__table__.columns})

    def _to_incident(self, row: IncidentRecord) -> Incident:
        return Incident.model_validate({column.name: getattr(row, column.name) for column in IncidentRecord.__table__.columns})

    def _to_replay(self, row: ReplayRecord) -> Replay:
        return Replay.model_validate({column.name: getattr(row, column.name) for column in ReplayRecord.__table__.columns})

    def _to_activity(self, row: ActivityEventRecord) -> ActivityEvent:
        return ActivityEvent.model_validate({column.name: getattr(row, column.name) for column in ActivityEventRecord.__table__.columns})

    def _to_job(self, row: ReplayJobRecord) -> ReplayJob:
        return ReplayJob.model_validate({column.name: getattr(row, column.name) for column in ReplayJobRecord.__table__.columns})

    def _to_note(self, row: OperatorNoteRecord) -> OperatorNote:
        return OperatorNote.model_validate({column.name: getattr(row, column.name) for column in OperatorNoteRecord.__table__.columns})

    def _to_audit(self, row: AuditEventRecord) -> AuditEvent:
        return AuditEvent.model_validate({column.name: getattr(row, column.name) for column in AuditEventRecord.__table__.columns})
