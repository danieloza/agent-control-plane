from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .models import ApprovalRequest, IncidentRequest, LaunchRunRequest, ReplayRequest
from .repository import InMemoryRepository
from .services import ControlPlaneService


app = FastAPI(title="Agent Control Plane", version="0.1.0")

static_dir = Path(__file__).parent / "static"
repository = InMemoryRepository()
service = ControlPlaneService(repository)

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/health")
def health() -> dict:
    runs = service.list_runs()
    return {
        "service": "agent-control-plane",
        "runs": len(runs),
        "pending_approvals": len([run for run in runs if run.status == "approval_required"]),
        "incidents": len(service.list_incidents()),
        "eval_health": service.get_overview().eval_health,
    }


@app.get("/cockpit")
def cockpit() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/api/overview")
def overview() -> dict:
    return service.get_overview().model_dump()


@app.get("/api/scenarios")
def scenarios() -> list[dict]:
    return [item.model_dump() for item in service.list_scenarios()]


@app.get("/api/runs")
def runs() -> list[dict]:
    return [item.model_dump() for item in service.list_runs()]


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict:
    try:
        return service.get_run_detail(run_id).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc


@app.get("/api/runs/{run_id}/timeline")
def run_timeline(run_id: str) -> list[dict]:
    try:
        return [step.model_dump() for step in service.get_run_detail(run_id).timeline]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc


@app.get("/api/runs/{run_id}/compare/{other_run_id}")
def compare(run_id: str, other_run_id: str) -> dict:
    try:
        return service.compare_runs(run_id, other_run_id).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc


@app.get("/api/review-queue")
def review_queue() -> list[dict]:
    return service.list_review_queue()


@app.get("/api/queue-summary")
def queue_summary() -> list[dict]:
    return service.get_queue_summary()


@app.get("/api/activity-stream")
def activity_stream() -> list[dict]:
    return service.list_activity()


@app.get("/api/evals")
def evals() -> list[dict]:
    return service.list_evals()


@app.get("/api/incidents")
def incidents() -> list[dict]:
    return [item.model_dump() for item in service.list_incidents()]


@app.get("/api/operator-context")
def operator_context() -> dict:
    return service.get_operator_context()


@app.get("/api/operator-profiles")
def operator_profiles() -> list[dict]:
    return service.list_operator_profiles()


@app.get("/api/comparison-matrix")
def comparison_matrix() -> list[dict]:
    return service.get_comparison_matrix()


@app.get("/api/runs/{run_id}/graph")
def run_graph(run_id: str) -> dict:
    try:
        return service.get_trace_graph(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc


@app.get("/api/runs/{run_id}/report.md")
def run_report_markdown(run_id: str) -> PlainTextResponse:
    try:
        return PlainTextResponse(service.render_report_markdown(run_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc


@app.get("/api/runs/{run_id}/incident.md")
def incident_markdown(run_id: str) -> PlainTextResponse:
    try:
        return PlainTextResponse(service.render_incident_markdown(run_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Incident not found") from exc


@app.post("/api/runs")
def create_run(request: LaunchRunRequest) -> dict:
    return service.launch_run(request.scenario_id).model_dump()


@app.post("/api/runs/{run_id}/approval")
def approval(run_id: str, request: ApprovalRequest) -> dict:
    try:
        return service.apply_approval(run_id, request.action).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc


@app.post("/api/runs/{run_id}/incident")
def incident(run_id: str, request: IncidentRequest) -> dict:
    incident_obj = service.update_incident(run_id, request.action, request.owner)
    if incident_obj is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident_obj.model_dump()


@app.post("/api/runs/{run_id}/replay")
def replay(run_id: str, request: ReplayRequest) -> dict:
    try:
        result = service.create_replay(run_id, request.mode)
        return {
            "replay": result["replay"].model_dump(),
            "compare": result["compare"].model_dump(),
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
