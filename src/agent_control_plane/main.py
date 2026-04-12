from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from collections import defaultdict, deque
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .auth import AuthContext, authenticate_demo_user, create_access_token, get_auth_context, require_permission, require_tenant_access
from .db import Base, build_engine, build_session_factory
from .metrics import MetricsRegistry
from .models import ApprovalRequest, IncidentRequest, LaunchRunRequest, OperatorNoteRequest, ReplayRequest
from .repository import DatabaseRepository
from .services import ControlPlaneService
from .settings import Settings, get_settings


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(message)s")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    logger = logging.getLogger(settings.app_name)
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    repository = DatabaseRepository(session_factory)
    service = ControlPlaneService(repository)
    metrics = MetricsRegistry()
    rate_windows: dict[str, deque[float]] = defaultdict(deque)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if settings.app_env == "test" or settings.database_url.startswith("sqlite"):
            Base.metadata.create_all(bind=engine)
        repository.seed_if_empty()
        yield

    app = FastAPI(title="Agent Control Plane", version="0.2.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.repository = repository
    app.state.service = service
    app.state.logger = logger
    app.state.metrics = metrics

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        started = time.perf_counter()
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/"):
            identifier = request.headers.get("Authorization") or request.headers.get("X-Operator-Profile") or request.client.host
            bucket = rate_windows[identifier]
            now = time.time()
            while bucket and now - bucket[0] > 60:
                bucket.popleft()
            if len(bucket) >= settings.rate_limit_per_minute:
                return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
            bucket.append(now)
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info(
                json.dumps(
                    {
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": getattr(response, "status_code", 500),
                        "duration_ms": duration_ms,
                    }
                )
            )
            if response is not None:
                response.headers["X-Request-ID"] = request_id
                metrics.inc(f"http_{response.status_code}")

    def get_service() -> ControlPlaneService:
        return app.state.service

    def scoped_runs(context: AuthContext, service: ControlPlaneService):
        runs = service.list_runs()
        return [run for run in runs if run.tenant in context.profile.tenant_scope]

    def require_run_access(context: AuthContext, service: ControlPlaneService, run_id: str):
        run = service.get_run_detail(run_id).run
        require_tenant_access(context, run.tenant)
        return run

    @app.post("/api/auth/login")
    async def login(payload: dict) -> dict:
        username = payload.get("username")
        password = payload.get("password")
        context = authenticate_demo_user(username, password)
        token = create_access_token(context.username, context.profile.id, settings)
        return {"access_token": token, "token_type": "bearer", "profile_id": context.profile.id}

    @app.get("/health")
    def health(service: ControlPlaneService = Depends(get_service)) -> dict:
        runs = service.list_runs()
        return {
            "service": settings.app_name,
            "environment": settings.app_env,
            "runs": len(runs),
            "pending_approvals": len([run for run in runs if run.status == "approval_required"]),
            "incidents": len(service.list_incidents()),
            "eval_health": service.get_overview().eval_health,
        }

    @app.get("/ready")
    def ready() -> dict:
        return {"status": "ready"}

    @app.get("/metrics")
    def metrics_endpoint(service: ControlPlaneService = Depends(get_service)) -> PlainTextResponse:
        payload = metrics.render_prometheus(service.queue_depth(), len([item for item in service.list_incidents() if item.status == "open"]))
        return PlainTextResponse(payload, media_type="text/plain; version=0.0.4")

    @app.get("/cockpit")
    def cockpit() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/api/overview")
    def overview(service: ControlPlaneService = Depends(get_service)) -> dict:
        return service.get_overview().model_dump()

    @app.get("/api/scenarios")
    def scenarios(service: ControlPlaneService = Depends(get_service)) -> list[dict]:
        return [item.model_dump() for item in service.list_scenarios()]

    @app.get("/api/runs")
    def runs(
        status: str | None = Query(default=None),
        tenant: str | None = Query(default=None),
        context: AuthContext = Depends(get_auth_context),
        service: ControlPlaneService = Depends(get_service),
    ) -> list[dict]:
        items = scoped_runs(context, service)
        if status:
            items = [run for run in items if run.status == status]
        if tenant:
            items = [run for run in items if run.tenant == tenant]
        return [item.model_dump() for item in items]

    @app.get("/api/runs/{run_id}")
    def run_detail(run_id: str, context: AuthContext = Depends(get_auth_context), service: ControlPlaneService = Depends(get_service)) -> dict:
        try:
            require_run_access(context, service, run_id)
            return service.get_run_detail(run_id).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc

    @app.get("/api/runs/{run_id}/timeline")
    def run_timeline(run_id: str, context: AuthContext = Depends(get_auth_context), service: ControlPlaneService = Depends(get_service)) -> list[dict]:
        try:
            require_run_access(context, service, run_id)
            return [step.model_dump() for step in service.get_run_detail(run_id).timeline]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc

    @app.get("/api/runs/{run_id}/compare/{other_run_id}")
    def compare(run_id: str, other_run_id: str, context: AuthContext = Depends(get_auth_context), service: ControlPlaneService = Depends(get_service)) -> dict:
        try:
            require_run_access(context, service, run_id)
            require_run_access(context, service, other_run_id)
            return service.compare_runs(run_id, other_run_id).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc

    @app.get("/api/review-queue")
    def review_queue(context: AuthContext = Depends(get_auth_context), service: ControlPlaneService = Depends(get_service)) -> list[dict]:
        allowed_ids = {run.id for run in scoped_runs(context, service)}
        return [item for item in service.list_review_queue() if item["run_id"] in allowed_ids]

    @app.get("/api/queue-summary")
    def queue_summary(service: ControlPlaneService = Depends(get_service)) -> list[dict]:
        return service.get_queue_summary()

    @app.get("/api/activity-stream")
    def activity_stream(context: AuthContext = Depends(get_auth_context), service: ControlPlaneService = Depends(get_service)) -> list[dict]:
        allowed_ids = {run.id for run in scoped_runs(context, service)}
        return [item for item in service.list_activity() if item["run_id"] in allowed_ids]

    @app.get("/api/audit-events")
    def audit_events(
        run_id: str | None = None,
        action: str | None = None,
        limit: int = Query(default=50, le=200),
        context: AuthContext = Depends(get_auth_context),
        service: ControlPlaneService = Depends(get_service),
    ) -> list[dict]:
        if run_id:
            require_run_access(context, service, run_id)
        items = service.list_audit_events(run_id)
        if action:
            items = [item for item in items if item.action == action]
        allowed_ids = {run.id for run in scoped_runs(context, service)}
        items = [item for item in items if item.run_id in allowed_ids]
        return [item.model_dump() for item in items[:limit]]

    @app.get("/api/runs/{run_id}/notes")
    def run_notes(
        run_id: str,
        limit: int = Query(default=50, le=200),
        context: AuthContext = Depends(get_auth_context),
        service: ControlPlaneService = Depends(get_service),
    ) -> list[dict]:
        require_run_access(context, service, run_id)
        return [item.model_dump() for item in service.list_operator_notes(run_id)[:limit]]

    @app.get("/api/evals")
    def evals(context: AuthContext = Depends(get_auth_context), service: ControlPlaneService = Depends(get_service)) -> list[dict]:
        allowed_ids = {run.id for run in scoped_runs(context, service)}
        return [item for item in service.list_evals() if item["run_id"] in allowed_ids]

    @app.get("/api/incidents")
    def incidents(context: AuthContext = Depends(get_auth_context), service: ControlPlaneService = Depends(get_service)) -> list[dict]:
        allowed_ids = {run.id for run in scoped_runs(context, service)}
        return [item.model_dump() for item in service.list_incidents() if item.run_id in allowed_ids]

    @app.get("/api/operator-context")
    def operator_context(
        context: AuthContext = Depends(get_auth_context),
        service: ControlPlaneService = Depends(get_service),
    ) -> dict:
        payload = service.get_operator_context(context.profile)
        payload["username"] = context.username
        return payload

    @app.get("/api/operator-profiles")
    def operator_profiles(service: ControlPlaneService = Depends(get_service)) -> list[dict]:
        return service.list_operator_profiles()

    @app.get("/api/comparison-matrix")
    def comparison_matrix(context: AuthContext = Depends(get_auth_context), service: ControlPlaneService = Depends(get_service)) -> list[dict]:
        allowed_ids = {run.id for run in scoped_runs(context, service)}
        return [item for item in service.get_comparison_matrix() if item["run_id"] in allowed_ids]

    @app.get("/api/runs/{run_id}/graph")
    def run_graph(run_id: str, context: AuthContext = Depends(get_auth_context), service: ControlPlaneService = Depends(get_service)) -> dict:
        try:
            require_run_access(context, service, run_id)
            return service.get_trace_graph(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc

    @app.get("/api/runs/{run_id}/report.md")
    def run_report_markdown(run_id: str, context: AuthContext = Depends(get_auth_context), service: ControlPlaneService = Depends(get_service)) -> PlainTextResponse:
        try:
            require_run_access(context, service, run_id)
            return PlainTextResponse(service.render_report_markdown(run_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc

    @app.get("/api/runs/{run_id}/incident.md")
    def incident_markdown(run_id: str, context: AuthContext = Depends(get_auth_context), service: ControlPlaneService = Depends(get_service)) -> PlainTextResponse:
        try:
            require_run_access(context, service, run_id)
            return PlainTextResponse(service.render_incident_markdown(run_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Incident not found") from exc

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str, context: AuthContext = Depends(get_auth_context), service: ControlPlaneService = Depends(get_service)) -> dict:
        try:
            job = service.get_job(job_id)
            require_run_access(context, service, job.run_id)
            return job.model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc

    @app.get("/api/jobs")
    def jobs(
        status: str | None = Query(default=None),
        context: AuthContext = Depends(get_auth_context),
        service: ControlPlaneService = Depends(get_service),
    ) -> list[dict]:
        allowed_ids = {run.id for run in scoped_runs(context, service)}
        return [job.model_dump() for job in service.list_jobs(status) if job.run_id in allowed_ids]

    @app.get("/api/admin/tenants")
    def admin_tenants(context: AuthContext = Depends(get_auth_context), service: ControlPlaneService = Depends(get_service)) -> list[dict]:
        require_permission(context, "admin")
        return service.list_tenants()

    @app.get("/api/admin/policies")
    def admin_policies(context: AuthContext = Depends(get_auth_context), service: ControlPlaneService = Depends(get_service)) -> list[dict]:
        require_permission(context, "admin")
        return service.list_policy_bundles()

    @app.get("/api/admin/operators")
    def admin_operators(context: AuthContext = Depends(get_auth_context), service: ControlPlaneService = Depends(get_service)) -> list[dict]:
        require_permission(context, "admin")
        return service.list_operator_profiles()

    @app.post("/api/runs")
    def create_run(
        request: LaunchRunRequest,
        context: AuthContext = Depends(get_auth_context),
        service: ControlPlaneService = Depends(get_service),
    ) -> dict:
        require_permission(context, "review")
        metrics.inc("runs_created")
        return service.launch_run(request.scenario_id).model_dump()

    @app.post("/api/runs/{run_id}/approval")
    def approval(
        run_id: str,
        request: ApprovalRequest,
        context: AuthContext = Depends(get_auth_context),
        service: ControlPlaneService = Depends(get_service),
    ) -> dict:
        require_permission(context, "approve")
        try:
            require_run_access(context, service, run_id)
            metrics.inc(f"approval_{request.action}")
            return service.apply_approval(run_id, request.action).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc

    @app.post("/api/runs/{run_id}/incident")
    def incident(
        run_id: str,
        request: IncidentRequest,
        context: AuthContext = Depends(get_auth_context),
        service: ControlPlaneService = Depends(get_service),
    ) -> dict:
        require_permission(context, "contain_incident")
        require_run_access(context, service, run_id)
        incident_obj = service.update_incident(run_id, request.action, request.owner)
        if incident_obj is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        metrics.inc(f"incident_{request.action}")
        return incident_obj.model_dump()

    @app.post("/api/runs/{run_id}/replay", status_code=202)
    def replay(
        run_id: str,
        request: ReplayRequest,
        context: AuthContext = Depends(get_auth_context),
        service: ControlPlaneService = Depends(get_service),
    ) -> JSONResponse:
        require_permission(context, "replay")
        try:
            require_run_access(context, service, run_id)
            job = service.queue_replay(run_id, request.mode, context.username)
            metrics.inc("replay_jobs_queued")
            return JSONResponse(status_code=202, content={"job": job.model_dump()})
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc

    @app.post("/api/runs/{run_id}/notes")
    def add_note(
        run_id: str,
        request: OperatorNoteRequest,
        context: AuthContext = Depends(get_auth_context),
        service: ControlPlaneService = Depends(get_service),
    ) -> dict:
        require_permission(context, "review")
        try:
            require_run_access(context, service, run_id)
            metrics.inc("operator_notes_created")
            return service.add_operator_note(run_id, context.username, request.body).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc

    return app


app = create_app()
