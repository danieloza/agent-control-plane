# Reliability Notes

This repository is still a portfolio product slice, but it is shaped to communicate a production mindset.

## Reliability assumptions

- replay work is separated from the API process through a worker boundary
- mutating actions are role-gated and tenant-aware
- review history is persisted through notes and audit events
- health, readiness, and metrics endpoints exist for runtime visibility
- the API stays thin enough that operational logic can evolve in services without rewriting transport code

## Threat model summary

The most relevant risks are not model quality alone. They are operational risks around who can trigger actions, who can review them, and whether risky flows leave enough evidence behind.

Primary concerns:

- unauthorized approvals or incident actions
- replay abuse that re-runs sensitive flows without the right operator context
- cross-tenant visibility leakage in review surfaces
- missing evidence after risky or blocked runs
- queue or worker failures that make the system look healthy while replay work stalls

## Current mitigations

- operator profiles and demo auth gate approvals, incidents, and replay actions
- tenant-aware RBAC narrows access by role and scope
- replay is persisted as a job with explicit status transitions
- audit events and operator notes preserve review history
- readiness and metrics surfaces expose operational state beyond "HTTP 200"

## Known limitations

- auth is still demo-grade, not full enterprise SSO
- replay jobs use a simple worker model, not a hardened queueing stack
- there is no immutable audit store or external event sink yet
- metrics are useful but still shallow compared with a full tracing setup

## Next reliability upgrades

- OpenTelemetry traces and richer metrics
- retry policy and dead-letter handling for replay jobs
- stronger secret handling and externalized auth
- explicit retention and archival strategy for notes, incidents, and exports
