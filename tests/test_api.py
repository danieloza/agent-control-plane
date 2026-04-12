from pathlib import Path

from fastapi.testclient import TestClient

from agent_control_plane.main import create_app
from agent_control_plane.settings import Settings
from agent_control_plane.worker import process_next_job


def build_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.db"
    settings = Settings(database_url=f"sqlite:///{db_path}", app_env="test")
    app = create_app(settings)
    return TestClient(app)


def test_health(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "agent-control-plane"
        assert data["runs"] >= 4


def test_runs(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        response = client.get("/api/runs")
        assert response.status_code == 200
        data = response.json()
        assert any(run["id"] == "run_5202" for run in data)


def test_run_detail(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        response = client.get("/api/runs/run_5202")
        assert response.status_code == 200
        data = response.json()
        assert data["run"]["status"] == "approval_required"
        assert len(data["timeline"]) >= 4


def test_launch_and_replay_job(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        create_response = client.post("/api/runs", json={"scenario_id": "customer_update"})
        assert create_response.status_code == 200
        run_id = create_response.json()["id"]

        replay_response = client.post(f"/api/runs/{run_id}/replay", json={"mode": "stricter_controls"})
        assert replay_response.status_code == 202
        job_id = replay_response.json()["job"]["id"]

        job_response = client.get(f"/api/jobs/{job_id}")
        assert job_response.status_code == 200
        assert job_response.json()["status"] == "queued"

        settings = Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", app_env="test")
        assert process_next_job(settings) is True

        job_response = client.get(f"/api/jobs/{job_id}")
        assert job_response.status_code == 200
        job = job_response.json()
        assert job["status"] == "completed"
        assert job["result_run_id"].startswith("run_")


def test_approval_changes_status(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        response = client.post("/api/runs/run_5202/approval", json={"action": "approve"})
        assert response.status_code == 200
        assert response.json()["status"] == "completed"


def test_incident_requires_permission(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        forbidden = client.post("/api/runs/run_5203/incident", json={"action": "contain"})
        assert forbidden.status_code == 403

        allowed = client.post("/api/runs/run_5203/incident", json={"action": "contain"}, headers={"X-Operator-Profile": "security-lead"})
        assert allowed.status_code == 200
        assert allowed.json()["status"] == "contained"


def test_graph_and_markdown_exports(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        graph_response = client.get("/api/runs/run_5203/graph", headers={"X-Operator-Profile": "platform-admin"})
        assert graph_response.status_code == 200
        graph = graph_response.json()
        assert len(graph["nodes"]) >= 3

        report_response = client.get("/api/runs/run_5202/report.md")
        assert report_response.status_code == 200
        assert "Run Report: run_5202" in report_response.text

        incident_response = client.get("/api/runs/run_5203/incident.md", headers={"X-Operator-Profile": "platform-admin"})
        assert incident_response.status_code == 200
        assert "Incident Bundle: inc_5203" in incident_response.text


def test_queue_summary_and_matrix(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        queue_response = client.get("/api/queue-summary")
        assert queue_response.status_code == 200
        assert len(queue_response.json()) >= 1

        matrix_response = client.get("/api/comparison-matrix", headers={"X-Operator-Profile": "platform-admin"})
        assert matrix_response.status_code == 200
        assert any(item["run_id"] == "run_5203" for item in matrix_response.json())


def test_operator_profiles_and_context(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        response = client.get("/api/operator-profiles")
        assert response.status_code == 200
        data = response.json()
        assert any(item["id"] == "ops-supervisor" for item in data)

        context = client.get("/api/operator-context", headers={"X-Operator-Profile": "platform-admin"})
        assert context.status_code == 200
        assert context.json()["active_profile"] == "platform-admin"


def test_notes_and_audit_events(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        note_response = client.post(
            "/api/runs/run_5202/notes",
            json={"body": "Outbound customer message needs legal review."},
            headers={"X-Operator-Profile": "ops-supervisor"},
        )
        assert note_response.status_code == 200
        assert note_response.json()["author"] == "ops-supervisor"

        notes = client.get("/api/runs/run_5202/notes")
        assert notes.status_code == 200
        assert any("legal review" in item["body"] for item in notes.json())

        audit = client.get("/api/audit-events", params={"run_id": "run_5202"})
        assert audit.status_code == 200
        assert any(item["action"] == "operator_note_added" for item in audit.json())
