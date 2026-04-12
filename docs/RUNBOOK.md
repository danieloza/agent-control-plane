# Runbook

## Local Development

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
alembic upgrade head
uvicorn agent_control_plane.main:app --reload --port 8010
agent-control-plane-worker
```

## Docker

```bash
docker compose up --build
```

This starts:

- `postgres` on `5432`
- `agent-control-plane` on `8010`
- dedicated replay worker

## Health Checks

- `GET /health`
- `GET /ready`
- `GET /metrics`

## Operator Profiles

Send `X-Operator-Profile` to simulate RBAC:

- `ops-supervisor`
- `security-lead`
- `platform-admin`

Demo JWT auth:

```bash
curl -X POST http://127.0.0.1:8010/api/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"admin.demo\",\"password\":\"admin-demo\"}"
```

## Replay Jobs

Replay requests are queued and completed as background jobs.

1. `POST /api/runs/{run_id}/replay`
2. Poll `GET /api/jobs/{job_id}`
3. Refresh the cockpit with `result_run_id`

## Audit Trail

- operator notes are stored in `operator_notes`
- action history is stored in `audit_events`
- replay queue and outcome state is stored in `replay_jobs`

## Admin Surfaces

- `/api/admin/tenants`
- `/api/admin/policies`
- `/api/admin/operators`
