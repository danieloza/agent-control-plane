from fastapi.testclient import TestClient

from agent_control_plane.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "agent-control-plane"
    assert data["runs"] >= 4


def test_runs() -> None:
    response = client.get("/api/runs")
    assert response.status_code == 200
    data = response.json()
    assert any(run["id"] == "run_5203" for run in data)


def test_run_detail() -> None:
    response = client.get("/api/runs/run_5202")
    assert response.status_code == 200
    data = response.json()
    assert data["run"]["status"] == "approval_required"
    assert len(data["timeline"]) >= 4


def test_launch_and_replay() -> None:
    create_response = client.post("/api/runs", json={"scenario_id": "customer_update"})
    assert create_response.status_code == 200
    run_id = create_response.json()["id"]

    replay_response = client.post(f"/api/runs/{run_id}/replay", json={"mode": "stricter_controls"})
    assert replay_response.status_code == 200
    data = replay_response.json()
    assert data["replay"]["run_id"].startswith("run_")
    assert "status_change" in data["compare"]


def test_approval_changes_status() -> None:
    response = client.post("/api/runs/run_5202/approval", json={"action": "approve"})
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_graph_and_markdown_exports() -> None:
    graph_response = client.get("/api/runs/run_5203/graph")
    assert graph_response.status_code == 200
    graph = graph_response.json()
    assert len(graph["nodes"]) >= 3

    report_response = client.get("/api/runs/run_5202/report.md")
    assert report_response.status_code == 200
    assert "Run Report: run_5202" in report_response.text

    incident_response = client.get("/api/runs/run_5203/incident.md")
    assert incident_response.status_code == 200
    assert "Incident Bundle: inc_5203" in incident_response.text


def test_queue_summary_and_matrix() -> None:
    queue_response = client.get("/api/queue-summary")
    assert queue_response.status_code == 200
    assert len(queue_response.json()) >= 1

    matrix_response = client.get("/api/comparison-matrix")
    assert matrix_response.status_code == 200
    assert any(item["run_id"] == "run_5203" for item in matrix_response.json())


def test_operator_profiles() -> None:
    response = client.get("/api/operator-profiles")
    assert response.status_code == 200
    data = response.json()
    assert any(item["id"] == "ops-supervisor" for item in data)
