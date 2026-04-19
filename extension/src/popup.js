// StealthRole popup script — v2.0.0
// Expanded UI with stats grid, Sync connections orchestration, and live progress.
// Keeps the legacy "Save this job" and "Auto-fill application" flows intact.

const loginView = document.getElementById("login-view");
const mainView  = document.getElementById("main-view");
const loginError = document.getElementById("login-error");
const loginBtn = document.getElementById("login-btn");
const logoutBtn = document.getElementById("btn-logout");

const syncBtn = document.getElementById("btn-sync-connections");
const syncMsgBtn = document.getElementById("btn-sync-messages");
const saveJobBtn = document.getElementById("btn-save-job");
const autofillBtn = document.getElementById("btn-autofill");

const progressWrap = document.getElementById("progress-wrap");
const progressLabel = document.getElementById("progress-label");
const progressCount = document.getElementById("progress-count");
const progressFill = document.getElementById("progress-fill");

// ── Auth state ───────────────────────────────────────────────────────────────
chrome.runtime.sendMessage({ type: "GET_TOKEN" }, async (res) => {
  if (res && res.token) {
    showMainView();
    loadStats();
    restoreSyncStatus();
  } else {
    showLoginView();
  }
});

function showLoginView() { loginView.style.display = "block"; mainView.style.display = "none"; }
function showMainView()  { loginView.style.display = "none";  mainView.style.display = "block"; }

// ── Login / logout ───────────────────────────────────────────────────────────
loginBtn.addEventListener("click", () => {
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;
  if (!email || !password) return;
  loginBtn.textContent = "…";
  loginError.style.display = "none";

  chrome.runtime.sendMessage({ type: "LOGIN", email, password }, (res) => {
    loginBtn.textContent = "Sign in";
    if (res && res.ok) {
      document.getElementById("user-email").textContent = res.user?.email || "Connected";
      showMainView();
      loadStats();
    } else {
      loginError.textContent = (res && res.error) || "Login failed";
      loginError.style.display = "block";
    }
  });
});

logoutBtn.addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "LOGOUT" }, () => showLoginView());
});

// ── Sync connections ─────────────────────────────────────────────────────────
syncBtn.addEventListener("click", () => {
  setProgress({ status: "scanning", count: 0, indet: true, feature: "connections" });
  syncBtn.disabled = true;
  chrome.runtime.sendMessage({ type: "START_CONNECTIONS_SYNC" }, (res) => {
    if (!res || !res.ok) {
      setProgress({ status: "error", count: 0, error: (res && res.error) || "Failed to start" });
      syncBtn.disabled = false;
    }
  });
});

// ── Sync messages ───────────────────────────────────────────────────────────
syncMsgBtn.addEventListener("click", () => {
  setProgress({ status: "scanning", count: 0, indet: true, feature: "messages" });
  syncMsgBtn.disabled = true;
  chrome.runtime.sendMessage({ type: "START_MESSAGES_SYNC" }, (res) => {
    if (!res || !res.ok) {
      setProgress({ status: "error", count: 0, error: (res && res.error) || "Failed to start" });
      syncMsgBtn.disabled = false;
    }
  });
});

// Restore progress UI if a sync is already running when the popup opens
function restoreSyncStatus() {
  chrome.runtime.sendMessage({ type: "GET_SYNC_STATUS" }, (res) => {
    const task = res && res.task;
    if (task && task.status === "scanning") {
      setProgress({ status: "scanning", count: task.count || 0, indet: true, feature: task.type });
      if (task.type === "connections") syncBtn.disabled = true;
      if (task.type === "messages") syncMsgBtn.disabled = true;
    }
  });
}

// Listen for PROGRESS broadcasts from background (connections OR messages)
chrome.runtime.onMessage.addListener((msg) => {
  if (msg?.type !== "PROGRESS") return;
  if (msg.feature !== "connections" && msg.feature !== "messages") return;
  setProgress(msg);
  if (msg.status === "done" || msg.status === "error") {
    syncBtn.disabled = false;
    syncMsgBtn.disabled = false;
    loadStats();
  }
});

function setProgress({ status, count, error, indet, feature }) {
  if (!status) { progressWrap.classList.remove("active"); return; }
  progressWrap.classList.add("active");
  progressWrap.classList.toggle("progress-indet", !!indet);

  const label = feature === "messages" ? "Scanning messages…" : "Scanning connections…";
  if (status === "scanning") {
    progressLabel.textContent = label;
    progressCount.textContent = String(count || 0);
    progressFill.style.width = indet ? "40%" : Math.min(100, ((count || 0) / 5)) + "%";
  } else if (status === "done") {
    progressLabel.textContent = "✓ Done";
    progressCount.textContent = String(count || 0);
    progressFill.style.width = "100%";
    progressWrap.classList.remove("progress-indet");
    setTimeout(() => progressWrap.classList.remove("active"), 3000);
  } else if (status === "error") {
    progressLabel.textContent = "⚠ " + (error || "Error");
    progressCount.textContent = "";
    progressFill.style.width = "0%";
    progressWrap.classList.remove("progress-indet");
  }
}

// ── Save current tab as a job (legacy flow — preserved) ─────────────────────
saveJobBtn.addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  chrome.tabs.sendMessage(tab.id, { type: "SAVE_JOB" }, (res) => {
    if (chrome.runtime.lastError) { saveJobFromTab(tab); return; }
    if (res?.ok) alert(`Saved: ${res.company} — ${res.role}`);
    else saveJobFromTab(tab);
  });
});

async function saveJobFromTab(tab) {
  const title = tab.title || "";
  const url = tab.url || "";
  let company = "", role = "";
  const atMatch = title.match(/^(.+?)\s+(?:at|@)\s+(.+?)(?:\s*[-|]|$)/i);
  const dashMatch = title.match(/^(.+?)\s*[-|]\s*(.+?)(?:\s*[-|]|$)/);
  if (atMatch) { role = atMatch[1].trim(); company = atMatch[2].trim(); }
  else if (dashMatch) { company = dashMatch[1].trim(); role = dashMatch[2].trim(); }
  else { company = title.substring(0, 100); role = "Unknown Role"; }

  chrome.runtime.sendMessage(
    {
      type: "API_REQUEST",
      path: "/applications",
      options: {
        method: "POST",
        body: JSON.stringify({
          company, role,
          date_applied: new Date().toISOString(),
          source_channel: "job_board",
          url,
        }),
      },
    },
    (res) => {
      if (res?.ok) { alert(`Saved: ${company} — ${role}`); loadStats(); }
      else alert(res?.error || "Failed to save");
    }
  );
}

// ── Auto-fill (legacy flow — preserved) ─────────────────────────────────────
autofillBtn.addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const atsUrls = ["greenhouse.io", "lever.co", "workable.com", "ashbyhq.com"];
  if (!atsUrls.some((u) => tab?.url?.includes(u))) {
    alert("Navigate to a Greenhouse, Lever, Workable, or Ashby application form first.");
    return;
  }
  autofillBtn.textContent = "Filling…";
  chrome.tabs.sendMessage(tab.id, { type: "AUTOFILL" }, (res) => {
    autofillBtn.textContent = "⚡ Auto-fill application";
    if (res?.ok) alert("Form filled! Review and submit.");
    else alert(res?.error || "Auto-fill failed — the form may not be detected");
  });
});

// ── Stats ────────────────────────────────────────────────────────────────────
function loadStats() {
  chrome.runtime.sendMessage({ type: "API_REQUEST", path: "/linkedin/stats", options: {} }, (res) => {
    if (res?.ok && res.data) {
      document.getElementById("stat-connections").textContent = res.data.total_connections ?? 0;
      const connSub = document.getElementById("stat-connections-sub");
      if (res.data.total_connections) connSub.textContent = `${res.data.recruiters || 0} recruiters`;

      // Message stats (same endpoint)
      const msgEl = document.getElementById("stat-messages");
      const msgSub = document.getElementById("stat-messages-sub");
      if (res.data.total_conversations != null) {
        msgEl.textContent = res.data.total_conversations;
        if (res.data.unread_conversations) msgSub.textContent = `${res.data.unread_conversations} unread`;
        else msgSub.textContent = "synced";
      }

      // Intro paths
      const pathEl = document.getElementById("stat-paths");
      const pathSub = document.getElementById("stat-paths-sub");
      if (res.data.intro_paths != null) {
        pathEl.textContent = res.data.intro_paths;
        pathSub.textContent = "available";
      }
    }
  });
  chrome.runtime.sendMessage({ type: "API_REQUEST", path: "/applications/analytics", options: {} }, (res) => {
    if (res?.ok && res.data) {
      document.getElementById("stat-apps").textContent = res.data.total_applications ?? 0;
    }
  });
  chrome.runtime.sendMessage({ type: "API_REQUEST", path: "/auth/me", options: {} }, (res) => {
    if (res?.ok && res.data) {
      document.getElementById("user-email").textContent = res.data.email;
    }
  });
}
