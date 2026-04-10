# Agent Control Plane

> Mission-control product for running, reviewing, and governing AI agents with policy checks, approvals, incidents, replay diffs, and evaluation scorecards.

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
- Browser UI with custom HTML/CSS/JS

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
pip install pytest
uvicorn agent_control_plane.main:app --reload --port 8010
```

Open:

- `http://127.0.0.1:8010/cockpit`
- `http://127.0.0.1:8010/health`

## Key Endpoints

- `GET /health`
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
- `GET /api/evals`
- `GET /api/incidents`
- `GET /api/operator-profiles`
- `GET /api/comparison-matrix`
- `GET /api/runs/{run_id}/report.md`
- `GET /api/runs/{run_id}/incident.md`
- `POST /api/runs`
- `POST /api/runs/{run_id}/approval`
- `POST /api/runs/{run_id}/incident`
- `POST /api/runs/{run_id}/replay`

## Demo Flow

1. Open the cockpit.
2. Launch a seeded scenario.
3. Review the execution timeline.
4. Inspect trace graph and eval scorecards.
5. Approve, reject, or escalate the run.
6. Replay under stricter policy.
7. Compare the original run and replay.

## Proof Assets

- cockpit: [docs/assets/cockpit-home.png](/C:/Users/syfsy/projekty/agent-control-plane/docs/assets/cockpit-home.png)
- run report export: [docs/assets/run-report.png](/C:/Users/syfsy/projekty/agent-control-plane/docs/assets/run-report.png)
- incident bundle export: [docs/assets/incident-bundle.png](/C:/Users/syfsy/projekty/agent-control-plane/docs/assets/incident-bundle.png)

## Interview Framing

This is not another chatbot demo.

It is an operator-facing platform for AI agents: a system that makes multi-step agent behavior reviewable, governable, replayable, and exportable in a production-style workflow.

## Docs

- Architecture: [docs/ARCHITECTURE.md](/C:/Users/syfsy/projekty/agent-control-plane/docs/ARCHITECTURE.md)
- Case study: [docs/CASE_STUDY.md](/C:/Users/syfsy/projekty/agent-control-plane/docs/CASE_STUDY.md)
- Krotka wersja pod rozmowe: [docs/README_SHORT_PL.md](/C:/Users/syfsy/projekty/agent-control-plane/docs/README_SHORT_PL.md)
