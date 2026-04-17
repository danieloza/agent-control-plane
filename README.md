# Agent Control Plane

> Mission-control product for running, reviewing, and governing AI agents with policy checks, approvals, incidents, replay diffs, and evaluation scorecards.

![Demo walkthrough](C:/Users/syfsy/projekty/agent-control-plane/docs/assets/demo-walkthrough.gif)

## Demo Walkthrough

1. Launch a seeded scenario and inspect the run queue from the cockpit.
2. Export the run as a report artifact for async review.
3. Export the incident bundle to show how risky runs move into evidence-driven follow-up.

## Product Thesis

Most agent demos stop at "the model called a tool."

Real teams need more:

- what happened step by step
- which policy allowed, flagged, or blocked the action
- where trust boundaries were crossed
- which actions require human approval
- what changed after replaying under stricter controls
- which runs are risky, expensive, slow, or degraded

Agent Control Plane models that missing operational layer.

## Why This Matters In Production

Production AI systems need more than a successful model call.

- operators need to know what happened and why
- risky write actions need approval paths and auditability
- incidents need evidence, ownership, and mitigation state
- replay needs to be safer than the original run, not just repeat it
- engineering teams need persistence, auth, metrics, and a worker boundary to debug failures under load

This repository is designed to show that operational layer, not just another agent UI.

## What It Shows

- operator command view for active runs, incidents, approvals, and eval health
- structured execution timelines across input, planning, retrieval, tool use, approvals, and outcomes
- policy verdicts with reasons and trust-boundary markers
- replay compare for safer re-runs under stricter bundles
- incident review with evidence, owner, and mitigation state
- eval scorecards for quality, groundedness, cost, latency, and tool safety
- review queue, ownership summary, trace graph, and comparison matrix

## Stack

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL-first runtime via `DATABASE_URL`
- Browser UI with custom HTML/CSS/JS

## Production Slice Upgrade

This repository now includes a first production-oriented slice:

- SQLAlchemy persistence instead of in-memory state
- startup seeding into a real database
- operator auth context via `X-Operator-Profile`
- RBAC checks for approvals, incidents, and replay actions
- structured request logging with request IDs
- replay execution through a separate worker with job-status polling
- operator notes and audit trail events for review history
- Alembic migration scaffolding for schema evolution
- Dockerfile, `docker-compose.yml`, `.env.example`, and runbook
- Postgres-backed docker profile for a more realistic local stack
- demo JWT auth, tenant-aware RBAC, and basic rate limiting on mutating API calls
- Prometheus-style metrics surface and admin registry views

## Architecture Diagram

```mermaid
flowchart LR
    O["Operator / Reviewer"] --> UI["Cockpit UI"]
    UI --> API["FastAPI API"]
    API --> SVC["Services Layer"]
    SVC --> REPO["SQLAlchemy Repository"]
    REPO --> DB["Postgres / SQLite"]
    API --> AUTH["Auth / RBAC"]
    API --> MET["Metrics / Health"]
    SVC --> JOB["Replay Job Queue"]
    JOB --> WORKER["Replay Worker"]
    WORKER --> REPO
    SVC --> EXP["Markdown Exports"]
```

## Architecture Decisions

- `FastAPI + custom UI` keeps the system API-first while still providing an operator-facing surface for demos and review flows.
- `Repository/service split` keeps persistence and runtime logic separate enough to evolve toward a larger platform without turning handlers into business logic blobs.
- `Replay worker` keeps heavier replay operations outside the request/response lifecycle and makes the reliability story more believable than inline replay.
- `Tenant-aware RBAC` lets the same control surface model operator boundaries instead of pretending all reviewers are equivalent.
- `Markdown exports` make run and incident reviews portable for async review, handoff, and documentation workflows.

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
pip install pytest
alembic upgrade head
uvicorn agent_control_plane.main:app --reload --port 8010
agent-control-plane-worker
```

Open:

- `http://127.0.0.1:8010/cockpit`
- `http://127.0.0.1:8010/health`
- `http://127.0.0.1:8010/ready`
- `http://127.0.0.1:8010/metrics`

### Docker

```bash
docker compose up --build
```

## Key Endpoints

- `GET /health`
- `GET /ready`
- `GET /metrics`
- `GET /cockpit`
- `GET /api/overview`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/timeline`
- `GET /api/runs/{run_id}/graph`
- `GET /api/runs/{run_id}/compare/{other_run_id}`
- `GET /api/review-queue`
- `GET /api/queue-summary`
- `GET /api/activity-stream`
- `GET /api/audit-events`
- `GET /api/evals`
- `GET /api/incidents`
- `GET /api/jobs`
- `GET /api/operator-profiles`
- `GET /api/comparison-matrix`
- `GET /api/admin/tenants`
- `GET /api/admin/policies`
- `GET /api/admin/operators`
- `GET /api/runs/{run_id}/notes`
- `GET /api/runs/{run_id}/report.md`
- `GET /api/runs/{run_id}/incident.md`
- `GET /api/jobs/{job_id}`
- `POST /api/auth/login`
- `POST /api/runs`
- `POST /api/runs/{run_id}/approval`
- `POST /api/runs/{run_id}/incident`
- `POST /api/runs/{run_id}/replay`
- `POST /api/runs/{run_id}/notes`

## Demo Flow

1. Open the cockpit.
2. Launch a seeded scenario.
3. Review the execution timeline.
4. Inspect trace graph and eval scorecards.
5. Approve, reject, or escalate the run.
6. Replay under stricter policy.
7. Compare the original run and replay.

## Demo Auth

Demo users:

- `ops.demo` / `ops-demo`
- `security.demo` / `security-demo`
- `admin.demo` / `admin-demo`

## Proof Assets

- cockpit overview: [docs/assets/cockpit-home.png](/C:/Users/syfsy/projekty/agent-control-plane/docs/assets/cockpit-home.png)
  shows the operator-first layout with run queue, recommendation layer, and action console
- run report export: [docs/assets/run-report.png](/C:/Users/syfsy/projekty/agent-control-plane/docs/assets/run-report.png)
  shows how a single run can be exported into a review artifact outside the live UI
- incident bundle export: [docs/assets/incident-bundle.png](/C:/Users/syfsy/projekty/agent-control-plane/docs/assets/incident-bundle.png)
  shows how blocked or risky runs can be packaged for incident handling and audit follow-up

## Interview Framing

This is not another chatbot demo.

It is an operator-facing platform for AI agents: a system that makes multi-step agent behavior reviewable, governable, replayable, and exportable in a production-style workflow with persistence, auth context, and safer replay handling.

## Docs

- Architecture: [docs/ARCHITECTURE.md](/C:/Users/syfsy/projekty/agent-control-plane/docs/ARCHITECTURE.md)
- Case study: [docs/CASE_STUDY.md](/C:/Users/syfsy/projekty/agent-control-plane/docs/CASE_STUDY.md)
- Runbook: [docs/RUNBOOK.md](/C:/Users/syfsy/projekty/agent-control-plane/docs/RUNBOOK.md)
- Reliability / threat notes: [docs/RELIABILITY_NOTES.md](/C:/Users/syfsy/projekty/agent-control-plane/docs/RELIABILITY_NOTES.md)

## Migrations

```bash
alembic upgrade head
```
