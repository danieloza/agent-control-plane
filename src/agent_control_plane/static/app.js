const state = { runs: [], scenarios: [], activeRunId: null, compareRunId: null, profiles: [] };

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Failed to load ${path}`);
  return response.json();
}

function badge(status) {
  return `<span class="badge ${status}">${status.replaceAll("_", " ")}</span>`;
}

function renderOverview(overview) {
  const metrics = [["Active Runs", overview.active_runs], ["Pending Approvals", overview.pending_approvals], ["Open Incidents", overview.open_incidents], ["Blocked Runs", overview.blocked_runs], ["Avg Cost (USD)", overview.avg_cost_usd], ["Eval Health", overview.eval_health]];
  document.getElementById("overview-grid").innerHTML = metrics.map(([label, value]) => `<div class="metric-card"><div class="label">${label}</div><div class="value">${value}</div></div>`).join("");
}

function renderRuns(runs) {
  state.runs = runs;
  document.getElementById("run-count").textContent = runs.length;
  document.getElementById("run-list").innerHTML = runs.map((run) => `
    <button class="run-item ${run.id === state.activeRunId ? "active" : ""}" onclick="selectRun('${run.id}')">
      <div class="row"><span class="title">${run.id}</span>${badge(run.status)}</div>
      <div class="small muted">${run.agent_name}</div>
      <div class="small">${run.objective}</div>
      <div class="row small muted"><span>Risk ${run.risk_score}</span><span>$${run.cost_usd.toFixed(3)} / ${run.latency_ms}ms</span></div>
    </button>
  `).join("");
}

function renderRunDetail(detail) {
  const run = detail.run;
  document.getElementById("active-run-label").textContent = run.id;
  document.getElementById("run-summary").innerHTML = `
    <div class="label">Objective</div>
    <div class="title">${run.objective}</div>
    <div class="row small muted"><span>${run.agent_name}</span><span>${run.policy_bundle}</span></div>
    <div class="row small"><span>Risk ${run.risk_score}</span><span>${badge(run.status)}</span></div>
    <div class="row small muted"><span>Boundaries</span><span>${run.trust_boundaries.join(", ")}</span></div>
    <div class="export-links">
      <a href="/api/runs/${run.id}/report.md" target="_blank" rel="noreferrer">Run report</a>
      <a href="/api/runs/${run.id}/incident.md" target="_blank" rel="noreferrer">Incident bundle</a>
    </div>
  `;
  document.getElementById("timeline").innerHTML = detail.timeline.map((step) => `
    <div class="timeline-item">
      <div class="row"><span class="title">Step ${step.index} | ${step.step_type}</span>${badge(step.verdict)}</div>
      <div class="small">${step.title}</div>
      <div class="small muted">${step.summary}</div>
      <div class="row small"><span class="boundary">${step.boundary}</span><span class="muted">${step.policy_name}</span></div>
      <div class="small muted">${step.policy_reason}</div>
      ${step.failure_class ? `<div class="small" style="color: var(--amber)">Failure class: ${step.failure_class}</div>` : ""}
    </div>
  `).join("");
  const compareCard = document.getElementById("compare-card");
  if (detail.replay) {
    compareCard.classList.add("compare-panel");
    compareCard.innerHTML = `<div class="label">Latest Replay</div><div class="title">${detail.replay.id}</div><div class="small muted">${detail.replay.summary}</div>`;
  } else if (detail.incident) {
    compareCard.innerHTML = `<div class="label">Incident</div><div class="title">${detail.incident.title}</div><div class="small muted">${detail.incident.summary}</div>`;
  } else {
    compareCard.innerHTML = `<div class="label">Control Status</div><div class="small muted">No replay or incident linked to this run yet.</div>`;
  }
  const incidentCard = document.getElementById("incident-card");
  if (detail.incident) {
    incidentCard.innerHTML = `
      <div class="label">Incident Detail</div>
      <div class="title">${detail.incident.title}</div>
      <div class="row small"><span>${detail.incident.owner}</span><span>${detail.incident.status}</span></div>
      <div class="small muted">${detail.incident.summary}</div>
    `;
  } else {
    incidentCard.innerHTML = `<div class="label">Incident Detail</div><div class="small muted">No active incident linked to this run.</div>`;
  }
}

function renderTraceGraph(graph) {
  const items = [];
  graph.nodes.forEach((node, index) => {
    items.push(`
      <div class="graph-node">
        <div class="row"><span class="title">${node.label}</span>${badge(node.verdict)}</div>
        <div class="row small"><span class="boundary">${node.boundary}</span><span class="mono">${node.type}</span></div>
      </div>
    `);
    if (graph.edges[index]) {
      items.push(`<div class="graph-edge">${graph.edges[index].label}</div>`);
    }
  });
  document.getElementById("trace-graph").innerHTML = items.join("");
}

function renderReviewQueue(queue) {
  document.getElementById("review-queue").innerHTML = queue.map((item) => `<div class="queue-item"><div class="row"><span class="title">${item.run_id}</span><span class="badge ${item.priority === "critical" ? "blocked" : item.priority === "high" ? "approval_required" : "allowed"}">${item.priority}</span></div><div class="small">${item.next_action}</div><div class="small muted">Owner: ${item.owner}</div></div>`).join("");
}

function renderActivity(items) {
  document.getElementById("activity-stream").innerHTML = items.map((item) => `<div class="activity-item"><div class="row"><span class="title">${item.label}</span><span class="mono">${item.category}</span></div><div class="small muted">${item.run_id}</div></div>`).join("");
}

function renderEvals(items) {
  document.getElementById("eval-board").innerHTML = items.map((item) => {
    const bars = [["quality", item.quality], ["groundedness", item.groundedness], ["tool_safety", item.tool_safety], ["latency", item.latency], ["cost", item.cost_efficiency]];
    return `<div class="eval-item"><div class="row"><span class="title">${item.run_id}</span><span class="mono">${item.scenario}</span></div>${bars.map(([label, value]) => `<div class="small muted">${label}</div><div class="bar"><span style="width:${value}%"></span></div>`).join("")}</div>`;
  }).join("");
}

function renderQueueSummary(items) {
  document.getElementById("queue-summary").innerHTML = items.map((item) => `
    <div class="queue-item">
      <div class="row"><span class="title">${item.owner}</span><span class="mono">${item.items} items</span></div>
      <div class="row small muted"><span>critical ${item.critical}</span><span>high ${item.high}</span></div>
    </div>
  `).join("");
}

function renderComparisonMatrix(items) {
  document.getElementById("comparison-matrix").innerHTML = items.map((item) => `
    <div class="matrix-item">
      <div class="row"><span class="title">${item.run_id}</span>${badge(item.status)}</div>
      <div class="small muted">${item.scenario}</div>
      <div class="matrix-grid">
        <div class="small">risk ${item.risk_score}</div>
        <div class="small">quality ${item.quality}</div>
        <div class="small">tool safety ${item.tool_safety}</div>
        <div class="small">${item.latency_ms}ms</div>
      </div>
    </div>
  `).join("");
}

function renderProfiles(items) {
  state.profiles = items;
  document.getElementById("profile-select").innerHTML = items.map((item) => `
    <option value="${item.id}">${item.label} | ${item.role}</option>
  `).join("");
}

function renderCompareSelector(runs) {
  const activeRunId = state.activeRunId;
  const options = runs
    .filter((run) => run.id !== activeRunId)
    .map((run) => `<option value="${run.id}">${run.id} | ${run.scenario} | ${run.status}</option>`)
    .join("");
  document.getElementById("compare-run-select").innerHTML = options || `<option value="">No target</option>`;
}

async function loadCompare() {
  const compareRunId = document.getElementById("compare-run-select").value;
  if (!state.activeRunId || !compareRunId) return;
  state.compareRunId = compareRunId;
  const compare = await getJson(`/api/runs/${state.activeRunId}/compare/${compareRunId}`);
  document.getElementById("compare-card").innerHTML = `
    <div class="label">Compare View</div>
    <div class="title">${compare.left_run_id} vs ${compare.right_run_id}</div>
    <div class="small muted">${compare.status_change}</div>
    <div class="matrix-grid">
      <div class="small">risk delta ${compare.risk_delta}</div>
      <div class="small">cost delta ${compare.cost_delta}</div>
      <div class="small">latency delta ${compare.latency_delta}</div>
      <div class="small">${compare.control_delta}</div>
    </div>
  `;
}

async function selectRun(runId) {
  state.activeRunId = runId;
  renderRuns(state.runs);
  renderCompareSelector(state.runs);
  const [detail, graph] = await Promise.all([getJson(`/api/runs/${runId}`), getJson(`/api/runs/${runId}/graph`)]);
  renderRunDetail(detail);
  renderTraceGraph(graph);
}

async function refreshAll(preferredRunId) {
  const [overview, scenarios, runs, queue, queueSummary, activity, evals, matrix, profiles] = await Promise.all([
    getJson("/api/overview"),
    getJson("/api/scenarios"),
    getJson("/api/runs"),
    getJson("/api/review-queue"),
    getJson("/api/queue-summary"),
    getJson("/api/activity-stream"),
    getJson("/api/evals"),
    getJson("/api/comparison-matrix"),
    getJson("/api/operator-profiles"),
  ]);
  state.scenarios = scenarios;
  document.getElementById("scenario-select").innerHTML = scenarios.map((item) => `<option value="${item.id}">${item.name}</option>`).join("");
  renderProfiles(profiles);
  renderOverview(overview);
  renderRuns(runs);
  renderReviewQueue(queue);
  renderQueueSummary(queueSummary);
  renderActivity(activity);
  renderEvals(evals);
  renderComparisonMatrix(matrix);
  const targetRunId = preferredRunId || state.activeRunId || runs[0]?.id;
  if (targetRunId) await selectRun(targetRunId);
}

async function postJson(path, body) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!response.ok) throw new Error(`Failed request ${path}`);
  return response.json();
}

document.getElementById("launch-button").addEventListener("click", async () => {
  const scenarioId = document.getElementById("scenario-select").value;
  const run = await postJson("/api/runs", { scenario_id: scenarioId });
  await refreshAll(run.id);
});

document.querySelectorAll("[data-action]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (!state.activeRunId) return;
    await postJson(`/api/runs/${state.activeRunId}/approval`, { action: button.dataset.action });
    await refreshAll(state.activeRunId);
  });
});

document.querySelectorAll("[data-incident]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (!state.activeRunId) return;
    await postJson(`/api/runs/${state.activeRunId}/incident`, { action: button.dataset.incident });
    await refreshAll(state.activeRunId);
  });
});

document.getElementById("replay-button").addEventListener("click", async () => {
  if (!state.activeRunId) return;
  const result = await postJson(`/api/runs/${state.activeRunId}/replay`, { mode: "stricter_controls" });
  await refreshAll(result.replay.run_id);
});

document.getElementById("compare-button").addEventListener("click", loadCompare);

refreshAll();
