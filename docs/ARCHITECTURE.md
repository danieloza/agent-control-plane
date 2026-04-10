# Architecture

Agent Control Plane is split into four simple layers:

- `repository.py`
  stores seeded runtime data for runs, steps, incidents, replays, review queue, and evaluation scorecards
- `services.py`
  exposes operational logic, command-view metrics, replay creation, and action handling
- `main.py`
  exposes the FastAPI API and serves the cockpit UI
- `static/`
  contains the browser cockpit

## Main Flow

1. A run exists or is launched from a scenario.
2. The operator inspects timeline, policy verdicts, boundaries, and eval signals.
3. The operator can approve, reject, escalate, contain, or replay the run.
4. Replay creates a safer sibling run with a stricter bundle.
5. Compare view shows drift in risk, latency, cost, and control outcomes.

## Current product surfaces

- command cockpit
- execution timeline
- trace graph
- review queue
- ownership summary
- comparison matrix
- replay compare
- markdown exports for run and incident review

## Why the architecture is shaped this way

The goal is to keep the system easy to evolve:

- seeded runtime data lives in `repository.py`
- operator logic stays in `services.py`
- HTTP surface stays thin in `main.py`
- the cockpit only consumes the same API that external automation could consume later

## Next meaningful upgrades

- Postgres-backed state
- role-aware auth
- external event ingestion
- background replay jobs
- OpenTelemetry traces
