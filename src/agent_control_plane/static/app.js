sessionStorage.removeItem("acp.accessToken");

const state = {
  runs: [],
  scenarios: [],
  activeRunId: null,
  compareRunId: null,
  profiles: [],
  currentProfileId: sessionStorage.getItem("acp.profileId") || "ops-supervisor",
  authContext: null,
  currentRunFilter: "",
  accessToken: "",
  loadingDepth: 0,
  backgroundRefreshHandle: null,
};

const DEMO_CREDENTIALS = {
  "ops.demo": { username: "ops.demo", password: "ops-demo" },
  "security.demo": { username: "security.demo", password: "security-demo" },
  "admin.demo": { username: "admin.demo", password: "admin-demo" },
};

const ONBOARDING_STEPS = [
  {
    selector: "#runs-header",
    title: "Start with the queue",
    body: "Scan Runs first. This is the operator queue showing which runs are healthy, waiting for approval, or blocked.",
  },
  {
    selector: "#brief-header",
    title: "Read the brief before the logs",
    body: "Operator Brief compresses the current run into one recommendation, one impact statement, and one policy explanation.",
  },
  {
    selector: "#action-console-header",
    title: "Make the decision here",
    body: "Use the Action Console for approvals, escalations, incident handling, or replay under stricter controls.",
  },
  {
    selector: "#diagnostics-header",
    title: "Diagnostics are second-level",
    body: "Only open Diagnostics when you need deeper investigation, comparison, replay analysis, or model-quality evidence.",
  },
];

function buildHeaders(extra = {}) {
  const headers = { "X-Operator-Profile": state.currentProfileId, ...extra };
  if (state.accessToken) {
    headers.Authorization = `Bearer ${state.accessToken}`;
  }
  return headers;
}

function setLoading(active) {
  state.loadingDepth = Math.max(0, state.loadingDepth + (active ? 1 : -1));
  const isActive = state.loadingDepth > 0;
  document.getElementById("loading-bar").classList.toggle("active", isActive);
  document.getElementById("loading-overlay").classList.toggle("is-hidden", !isActive);
}

function showToast(message, tone = "info") {
  const toast = document.createElement("div");
  toast.className = `toast ${tone}`;
  toast.innerHTML = `<div class="title">${tone === "error" ? "Request failed" : tone === "success" ? "Updated" : "Status"}</div><div class="small muted">${message}</div>`;
  const region = document.getElementById("toast-region");
  region.appendChild(toast);
  window.setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(-4px)";
  }, 2600);
  window.setTimeout(() => toast.remove(), 3000);
}

function updateAuthPill() {
  const pill = document.getElementById("auth-pill");
  const username = state.authContext?.username || "Profile mode";
  const role = state.authContext?.role || state.currentProfileId;
  pill.textContent = state.accessToken ? `${username} | ${role}` : `Profile mode | ${role}`;
}

function resetAccessToken() {
  state.accessToken = "";
  persistSession();
  updateAuthPill();
}

function clearTourHighlight() {
  document.querySelectorAll(".tour-target").forEach((node) => node.classList.remove("tour-target"));
}

function showOnboardingStep(index) {
  const step = ONBOARDING_STEPS[index];
  if (!step) return;
  const target = document.querySelector(step.selector);
  clearTourHighlight();
  if (target) target.classList.add("tour-target");
  document.getElementById("onboarding-title").textContent = step.title;
  document.getElementById("onboarding-body").textContent = step.body;
  document.getElementById("onboarding-step").textContent = `${index + 1}/${ONBOARDING_STEPS.length}`;
  document.getElementById("onboarding-card").classList.remove("is-hidden");
  document.getElementById("onboarding-next").textContent = index === ONBOARDING_STEPS.length - 1 ? "Finish" : "Next";
  state.onboardingIndex = index;
}

function hideOnboarding(markSeen = false) {
  document.getElementById("onboarding-card").classList.add("is-hidden");
  clearTourHighlight();
  if (markSeen) {
    localStorage.setItem("acp.onboardingSeen", "1");
  }
}

function showHelp() {
  document.getElementById("help-card").classList.remove("is-hidden");
}

function hideHelp() {
  document.getElementById("help-card").classList.add("is-hidden");
}

function maybeStartOnboarding() {
  if (localStorage.getItem("acp.onboardingSeen") === "1") return;
  showOnboardingStep(0);
}

function restartOnboarding() {
  hideHelp();
  localStorage.removeItem("acp.onboardingSeen");
  showOnboardingStep(0);
}

function updateActionHints(run, recommendation) {
  const actionTooltips = {
    approve: run.status === "approval_required"
      ? "Approve this run and allow the held result to proceed."
      : "Use when you want to explicitly allow the current run state to proceed.",
    reject: run.status === "approval_required"
      ? "Reject the held run because the output or action should not be released."
      : "Reject the current run if it should not be allowed to continue.",
    escalate: "Escalate this run when the decision should move to a higher-review path.",
  };
  const incidentTooltips = {
    contain: run.status === "blocked"
      ? "Contain the blocked run and keep the incident isolated while it is under investigation."
      : "Use containment when the active run represents an ongoing operational risk.",
    mitigate: "Record that mitigating action has been taken for the related incident.",
    reopen: "Reopen the incident if the issue is still active or unresolved.",
  };
  document.querySelectorAll("[data-action]").forEach((button) => {
    button.setAttribute("data-tooltip", actionTooltips[button.dataset.action] || "Run-level decision action.");
  });
  document.querySelectorAll("[data-incident]").forEach((button) => {
    button.setAttribute("data-tooltip", incidentTooltips[button.dataset.incident] || "Incident-level response action.");
  });
  document.getElementById("replay-button").setAttribute(
    "data-tooltip",
    run.status === "completed"
      ? "Replay this completed run under stricter controls to validate that it stays safe under tighter policy."
      : `Replay this ${run.status.replaceAll("_", " ")} run under stricter controls to compare outcomes and risk.`
  );
  document.getElementById("compare-button").setAttribute(
    "data-tooltip",
    `Load a compact comparison between the active run and another run. Current recommendation: ${recommendation.short}.`
  );
}

async function withUiState(action, { loading = false, successMessage = "", suppressErrorToast = false } = {}) {
  if (loading) setLoading(true);
  try {
    const result = await action();
    if (successMessage) showToast(successMessage, "success");
    return result;
  } catch (error) {
    if (!suppressErrorToast) {
      showToast(error.message || "Unexpected request failure.", "error");
    }
    throw error;
  } finally {
    if (loading) setLoading(false);
  }
}

async function getJson(path) {
  let response = await fetch(path, { headers: buildHeaders() });
  if (response.status === 401 && state.accessToken) {
    resetAccessToken();
    response = await fetch(path, { headers: buildHeaders() });
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail || `Failed to load ${path}`);
  }
  return response.json();
}

function badge(status) {
  return `<span class="badge ${status}">${status.replaceAll("_", " ")}</span>`;
}

function statusGlyph(status) {
  if (status === "blocked") return "!";
  if (status === "approval_required") return "?";
  return "+";
}

function deriveRecommendation(run) {
  if (run.status === "approval_required") {
    return {
      action: "Review and decide",
      impact: "This run crossed a sensitive boundary and is waiting for a human decision before release.",
      next: "Use Approve, Reject, or Escalate in the Action Console.",
      tone: "approval_required",
      short: "Review before release",
    };
  }
  if (run.status === "blocked") {
    return {
      action: "Investigate incident",
      impact: "A policy blocked the run before completion because the requested action was considered unsafe.",
      next: "Check the timeline, then use Contain, Mitigate, or Reopen.",
      tone: "blocked",
      short: "Investigate and contain",
    };
  }
  return {
    action: "No action required",
    impact: "The run completed successfully under the current policy bundle without requiring intervention.",
    next: "Review the timeline only if you need context or want to compare it against a stricter replay.",
    tone: "allowed",
    short: "No action required",
  };
}

function renderOperatorBrief(detail) {
  const run = detail.run;
  const recommendation = deriveRecommendation(run);
  const lastStep = detail.timeline[detail.timeline.length - 1];
  const why = lastStep?.policy_reason || "No exceptional policy intervention was recorded for this run.";
  document.getElementById("operator-brief").innerHTML = `
    <div class="brief-callout ${recommendation.tone}" data-tooltip="This line tells the operator the primary recommended decision for the active run.">
      <div class="label">Recommended next step</div>
      <div class="title">${recommendation.action}</div>
      <div class="small muted">${recommendation.next}</div>
    </div>
    <div class="label">What happened</div>
    <div class="title">${run.objective}</div>
    <div class="small muted">${run.agent_name} crossed ${run.trust_boundaries.join(", ")} boundaries under ${run.policy_bundle}.</div>
    <div class="operator-brief-grid">
      <div class="operator-brief-card">
        <div class="label">Status</div>
        <div class="title">${run.status.replaceAll("_", " ")}</div>
        <div class="small muted">Risk ${run.risk_score} · ${run.latency_ms}ms · $${run.cost_usd.toFixed(3)}</div>
      </div>
      <div class="operator-brief-card">
        <div class="label">Why It Matters</div>
        <div class="small">${recommendation.impact}</div>
      </div>
      <div class="operator-brief-card">
        <div class="label">Policy Readout</div>
        <div class="small">${why}</div>
      </div>
    </div>
  `;
}

function renderOverview(overview) {
  const metrics = [["Active Runs", overview.active_runs], ["Pending Approvals", overview.pending_approvals], ["Open Incidents", overview.open_incidents], ["Blocked Runs", overview.blocked_runs], ["Avg Cost (USD)", overview.avg_cost_usd], ["Eval Health", overview.eval_health]];
  document.getElementById("overview-grid").innerHTML = metrics.map(([label, value]) => `<div class="metric-card"><div class="label">${label}</div><div class="value">${value}</div></div>`).join("");
}

function renderRuns(runs) {
  state.runs = runs;
  document.getElementById("run-count").textContent = runs.length;
  document.getElementById("run-list").innerHTML = runs.map((run) => {
    const recommendation = deriveRecommendation(run);
    return `
      <button class="run-item ${run.id === state.activeRunId ? "active" : ""}" onclick="selectRun('${run.id}')" data-tooltip="Open this run to see what happened, why the policy produced this outcome, and which action to take next.">
        <div class="run-status-row">
          <span class="run-glyph ${run.status}" aria-hidden="true">${statusGlyph(run.status)}</span>
          <div class="run-status-copy">
            <div class="row"><span class="title">${run.id}</span>${badge(run.status)}</div>
            <div class="small muted">${run.agent_name}</div>
          </div>
        </div>
        <div class="small run-snippet">${run.objective}</div>
        <div class="queue-hint ${recommendation.tone}" data-tooltip="Short recommendation for how this run should be handled in the queue.">${recommendation.short}</div>
        <div class="row small muted"><span>Risk ${run.risk_score}</span><span>${run.latency_ms}ms</span></div>
      </button>
    `;
  }).join("");
}

function renderRunDetail(detail) {
  const run = detail.run;
  const recommendation = deriveRecommendation(run);
  document.getElementById("active-run-label").textContent = run.id;
  document.getElementById("run-summary").innerHTML = `
    <div class="label" data-tooltip="The current operator decision surface for the active run.">Current decision</div>
    <div class="title">${recommendation.action}</div>
    <div class="row small"><span>${badge(run.status)}</span><span>Risk ${run.risk_score}</span></div>
    <div class="small muted">${recommendation.next}</div>
    <div class="row small muted"><span>${run.agent_name}</span><span>${run.policy_bundle}</span></div>
    <div class="export-links">
      <a href="/api/runs/${run.id}/report.md" target="_blank" rel="noreferrer">Run report</a>
      <a href="/api/runs/${run.id}/incident.md" target="_blank" rel="noreferrer">Incident bundle</a>
    </div>
  `;
  renderOperatorBrief(detail);
  updateActionHints(run, recommendation);
  document.getElementById("timeline").innerHTML = detail.timeline.map((step) => `
    <div class="timeline-item" data-tooltip="A single execution step with its policy verdict, trust boundary, and reasoning.">
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
      <div class="graph-node" data-tooltip="A visualized node from the run trace graph. Useful for deeper investigation, not first-line triage.">
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
  document.getElementById("review-queue").innerHTML = queue.map((item) => `<div class="queue-item" data-tooltip="A shared team queue item showing who owns the next action on a run."><div class="row"><span class="title">${item.run_id}</span><span class="badge ${item.priority === "critical" ? "blocked" : item.priority === "high" ? "approval_required" : "allowed"}">${item.priority}</span></div><div class="small">${item.next_action}</div><div class="small muted">Owner: ${item.owner}</div></div>`).join("");
}

function renderActivity(items) {
  document.getElementById("activity-stream").innerHTML = items.map((item) => `<div class="activity-item" data-tooltip="Recent operator or system activity related to the current queue."><div class="row"><span class="title">${item.label}</span><span class="mono">${item.category}</span></div><div class="small muted">${item.run_id}</div></div>`).join("");
}

function renderEvals(items) {
  document.getElementById("eval-board").innerHTML = items.map((item) => {
    const bars = [["quality", item.quality], ["groundedness", item.groundedness], ["tool_safety", item.tool_safety], ["latency", item.latency], ["cost", item.cost_efficiency]];
    return `<div class="eval-item" data-tooltip="Model quality and safety scorecards for diagnosing how well runs performed."><div class="row"><span class="title">${item.run_id}</span><span class="mono">${item.scenario}</span></div>${bars.map(([label, value]) => `<div class="small muted">${label}</div><div class="bar"><span style="width:${value}%"></span></div>`).join("")}</div>`;
  }).join("");
}

function renderQueueSummary(items) {
  document.getElementById("queue-summary").innerHTML = items.map((item) => `
    <div class="queue-item" data-tooltip="Shows how queue load is distributed across owners.">
      <div class="row"><span class="title">${item.owner}</span><span class="mono">${item.items} items</span></div>
      <div class="row small muted"><span>critical ${item.critical}</span><span>high ${item.high}</span></div>
    </div>
  `).join("");
}

function renderComparisonMatrix(items) {
  document.getElementById("comparison-matrix").innerHTML = items.map((item) => `
    <div class="matrix-item" data-tooltip="Compact comparison of risk, quality, and tool safety across runs.">
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
    <option value="${item.id}" ${item.id === state.currentProfileId ? "selected" : ""}>${item.label} | ${item.role}</option>
  `).join("");
}

function renderJobs(items) {
  document.getElementById("jobs-list").innerHTML = items.map((job) => `
    <div class="queue-item" data-tooltip="Queued and completed replay jobs processed by the background worker.">
      <div class="row"><span class="title">${job.id}</span>${badge(job.status === "queued" || job.status === "processing" ? "approval_required" : job.status === "failed" ? "blocked" : "allowed")}</div>
      <div class="small muted">${job.run_id} | ${job.mode}</div>
      <div class="row small"><span>attempts ${job.attempts}/${job.max_attempts}</span><span>${job.result_run_id || "pending"}</span></div>
      ${job.error ? `<div class="small muted">${job.error}</div>` : ""}
    </div>
  `).join("");
}

function renderNotes(items) {
  document.getElementById("notes-list").innerHTML = items.map((note) => `
    <div class="activity-item" data-tooltip="Operator-authored context attached to the active run for handoff or later review.">
      <div class="row"><span class="title">${note.author}</span><span class="mono">${note.created_at}</span></div>
      <div class="small muted">${note.body}</div>
    </div>
  `).join("") || `<div class="activity-item"><div class="small muted">No operator notes yet.</div></div>`;
}

function renderAudit(items) {
  document.getElementById("audit-list").innerHTML = items.map((item) => `
    <div class="activity-item" data-tooltip="Immutable-looking trail of decisions and state transitions recorded for the active run.">
      <div class="row"><span class="title">${item.action}</span><span class="mono">${item.created_at}</span></div>
      <div class="small muted">${item.actor}</div>
      <div class="small">${item.summary}</div>
    </div>
  `).join("") || `<div class="activity-item"><div class="small muted">No audit events visible.</div></div>`;
}

function renderTenants(items) {
  document.getElementById("tenant-list").innerHTML = items.map((tenant) => `
    <div class="queue-item" data-tooltip="Registered tenant or operating domain available to the control plane.">
      <div class="row"><span class="title">${tenant.label}</span><span class="mono">${tenant.region}</span></div>
      <div class="small muted">${tenant.id}</div>
      <div class="small">${tenant.tier}</div>
    </div>
  `).join("");
}

function renderPolicies(items) {
  document.getElementById("policy-list").innerHTML = items.map((policy) => `
    <div class="queue-item" data-tooltip="Policy bundles define the guardrails and decision logic used during run execution.">
      <div class="row"><span class="title">${policy.label}</span><span class="mono">${policy.mode}</span></div>
      <div class="small muted">${policy.id}</div>
      <div class="small">${policy.controls.join(", ")}</div>
    </div>
  `).join("");
}

function renderPlatformSignals(overview, jobs, context) {
  const signals = [
    { label: "Operator", value: context?.username || "unknown" },
    { label: "Role", value: context?.role || "unknown" },
    { label: "Queue Depth", value: jobs.filter((job) => job.status === "queued").length },
    { label: "Open Incidents", value: overview.open_incidents },
    { label: "Pending Approvals", value: overview.pending_approvals },
  ];
  document.getElementById("platform-signals").innerHTML = signals.map((item) => `
    <div class="queue-item" data-tooltip="Live operational signal derived from the current control plane state.">
      <div class="label">${item.label}</div>
      <div class="title">${item.value}</div>
    </div>
  `).join("");
}

function toggleAdminPanels(isAdmin) {
  document.querySelectorAll(".admin-panel").forEach((panel) => panel.classList.toggle("is-hidden", !isAdmin));
}

function persistSession() {
  sessionStorage.setItem("acp.profileId", state.currentProfileId);
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
  const [detail, graph, notes, audit] = await Promise.all([
    getJson(`/api/runs/${runId}`),
    getJson(`/api/runs/${runId}/graph`),
    getJson(`/api/runs/${runId}/notes`),
    getJson(`/api/audit-events?run_id=${runId}&limit=25`),
  ]);
  renderRunDetail(detail);
  renderTraceGraph(graph);
  renderNotes(notes);
  renderAudit(audit);
}

async function refreshAll(preferredRunId) {
  const params = new URLSearchParams();
  if (state.currentRunFilter) params.set("status", state.currentRunFilter);
  const runsPath = params.size ? `/api/runs?${params.toString()}` : "/api/runs";
  const [overview, scenarios, runs, queue, queueSummary, activity, evals, matrix, profiles, jobs, context] = await Promise.all([
    getJson("/api/overview"),
    getJson("/api/scenarios"),
    getJson(runsPath),
    getJson("/api/review-queue"),
    getJson("/api/queue-summary"),
    getJson("/api/activity-stream"),
    getJson("/api/evals"),
    getJson("/api/comparison-matrix"),
    getJson("/api/operator-profiles"),
    getJson("/api/jobs"),
    getJson("/api/operator-context"),
  ]);
  state.authContext = context;
  state.currentProfileId = context.profile_id || state.currentProfileId;
  persistSession();
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
  renderJobs(jobs);
  renderPlatformSignals(overview, jobs, context);
  document.getElementById("profile-select").value = state.currentProfileId;
  document.getElementById("run-filter").value = state.currentRunFilter;
  toggleAdminPanels(context.role === "admin");
  updateAuthPill();
  if (context.role === "admin") {
    try {
      const [tenants, policies] = await Promise.all([getJson("/api/admin/tenants"), getJson("/api/admin/policies")]);
      renderTenants(tenants);
      renderPolicies(policies);
    } catch {
      renderTenants([]);
      renderPolicies([]);
    }
  } else {
    renderTenants([]);
    renderPolicies([]);
  }
  const targetRunId = preferredRunId || state.activeRunId || runs[0]?.id;
  if (targetRunId) await selectRun(targetRunId);
}

async function postJson(path, body) {
  let response = await fetch(path, { method: "POST", headers: buildHeaders({ "Content-Type": "application/json" }), body: JSON.stringify(body) });
  if (response.status === 401 && state.accessToken) {
    resetAccessToken();
    response = await fetch(path, { method: "POST", headers: buildHeaders({ "Content-Type": "application/json" }), body: JSON.stringify(body) });
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail || `Failed request ${path}`);
  }
  return response.json();
}

async function waitForJob(jobId, attempts = 30) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const job = await getJson(`/api/jobs/${jobId}`);
    if (job.status === "completed") return job;
    if (job.status === "failed") throw new Error(job.error || "Replay job failed");
    await new Promise((resolve) => setTimeout(resolve, 700));
  }
  throw new Error("Replay job is still queued. Check whether the worker process is running.");
}

async function loginAs(username) {
  const credentials = DEMO_CREDENTIALS[username];
  if (!credentials) throw new Error(`Unsupported demo login: ${username}`);
  const auth = await postJson("/api/auth/login", credentials);
  state.accessToken = auth.access_token;
  state.currentProfileId = auth.profile_id;
  persistSession();
  await refreshAll();
  showToast(`Authenticated as ${username}.`, "success");
}

function startBackgroundRefresh() {
  if (state.backgroundRefreshHandle) {
    window.clearInterval(state.backgroundRefreshHandle);
  }
  state.backgroundRefreshHandle = window.setInterval(async () => {
    if (state.loadingDepth > 0) return;
    try {
      await refreshAll(state.activeRunId);
    } catch {
      // Keep the polling loop silent; foreground actions surface errors explicitly.
    }
  }, 12000);
}

document.querySelectorAll("[data-login]").forEach((button) => {
  button.addEventListener("click", async () => {
    await withUiState(() => loginAs(button.dataset.login), { loading: true, suppressErrorToast: false });
  });
});

document.getElementById("launch-button").addEventListener("click", async () => {
  await withUiState(async () => {
    const scenarioId = document.getElementById("scenario-select").value;
    const run = await postJson("/api/runs", { scenario_id: scenarioId });
    await refreshAll(run.id);
  }, { loading: true, successMessage: "Scenario launched." });
});

document.querySelectorAll("[data-action]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (!state.activeRunId) return;
    await withUiState(async () => {
      await postJson(`/api/runs/${state.activeRunId}/approval`, { action: button.dataset.action });
      await refreshAll(state.activeRunId);
    }, { successMessage: `Approval action "${button.dataset.action}" applied.` });
  });
});

document.querySelectorAll("[data-incident]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (!state.activeRunId) return;
    await withUiState(async () => {
      await postJson(`/api/runs/${state.activeRunId}/incident`, { action: button.dataset.incident });
      await refreshAll(state.activeRunId);
    }, { successMessage: `Incident action "${button.dataset.incident}" applied.` });
  });
});

document.getElementById("replay-button").addEventListener("click", async () => {
  if (!state.activeRunId) return;
  const compareCard = document.getElementById("compare-card");
  compareCard.innerHTML = `<div class="label">Replay Job</div><div class="small muted">Queued replay job. Waiting for worker completion...</div>`;
  try {
    await withUiState(async () => {
      const result = await postJson(`/api/runs/${state.activeRunId}/replay`, { mode: "stricter_controls" });
      showToast(`Replay job ${result.job.id} queued.`, "info");
      const job = await waitForJob(result.job.id);
      await refreshAll(job.result_run_id);
    }, { loading: true, successMessage: "Replay completed under stricter controls.", suppressErrorToast: true });
  } catch (error) {
    compareCard.innerHTML = `<div class="label">Replay Job</div><div class="small muted">${error.message}</div>`;
    showToast(error.message, "error");
  }
});

document.getElementById("compare-button").addEventListener("click", async () => {
  await withUiState(loadCompare, { successMessage: "Compare view loaded." });
});

document.getElementById("profile-select").addEventListener("change", async (event) => {
  state.currentProfileId = event.target.value;
  state.accessToken = "";
  persistSession();
  await withUiState(() => refreshAll(state.activeRunId), { loading: true, successMessage: `Switched to ${state.currentProfileId}.` });
});

document.getElementById("run-filter").addEventListener("change", async (event) => {
  state.currentRunFilter = event.target.value;
  state.activeRunId = null;
  await withUiState(() => refreshAll(), { successMessage: "Run filter updated." });
});

document.getElementById("note-button").addEventListener("click", async () => {
  if (!state.activeRunId) return;
  const input = document.getElementById("note-input");
  const body = input.value.trim();
  if (!body) return;
  await withUiState(async () => {
    await postJson(`/api/runs/${state.activeRunId}/notes`, { body });
    input.value = "";
    await selectRun(state.activeRunId);
  }, { successMessage: "Operator note added." });
});

document.getElementById("onboarding-next").addEventListener("click", () => {
  const nextIndex = (state.onboardingIndex || 0) + 1;
  if (nextIndex >= ONBOARDING_STEPS.length) {
    hideOnboarding(true);
    return;
  }
  showOnboardingStep(nextIndex);
});

document.getElementById("onboarding-skip").addEventListener("click", () => {
  hideOnboarding(true);
});

document.getElementById("help-close").addEventListener("click", () => {
  hideHelp();
});

document.getElementById("help-trigger").addEventListener("click", () => {
  showHelp();
});

document.getElementById("help-tour").addEventListener("click", () => {
  restartOnboarding();
});

document.addEventListener("keydown", (event) => {
  const activeTag = document.activeElement?.tagName;
  const isEditable = activeTag === "INPUT" || activeTag === "TEXTAREA" || activeTag === "SELECT";
  if ((event.key === "?" || (event.key === "/" && event.shiftKey)) && !isEditable) {
    event.preventDefault();
    showHelp();
    return;
  }
  if (event.key === "Escape") {
    hideHelp();
    hideOnboarding(true);
    if (document.activeElement && typeof document.activeElement.blur === "function") {
      document.activeElement.blur();
    }
  }
});

window.addEventListener("focus", async () => {
  if (state.loadingDepth === 0) {
    try {
      await refreshAll(state.activeRunId);
    } catch {
      // Ignore background refresh failures here.
    }
  }
});

withUiState(async () => {
  await refreshAll();
  maybeStartOnboarding();
}, { loading: true, suppressErrorToast: false });
startBackgroundRefresh();
