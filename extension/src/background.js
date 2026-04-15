// StealthRole background service worker
// Handles messages between popup, content scripts, and API
// and orchestrates long-running sync tasks (connections for now, messages later).

importScripts("config.js");

// Keep service worker alive — Manifest V3 kills it after 30s of inactivity
const KEEPALIVE_INTERVAL = 25000;
setInterval(() => { chrome.storage.local.get("sr_keepalive"); }, KEEPALIVE_INTERVAL);

// ── Install / update ─────────────────────────────────────────────────────────
chrome.runtime.onInstalled.addListener(() => {
  console.log("[StealthRole] Extension installed/updated");
  // Recurring 6-hour connections sync. The alarm only fires — the sync
  // itself still requires an authenticated token, so first-time installs
  // won't do anything until the user has logged in to stealthrole.com.
  try {
    chrome.alarms.create("sr-sync-connections", { periodInMinutes: 360 });
  } catch (e) {
    console.warn("[StealthRole] Could not create alarm:", e);
  }
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== "sr-sync-connections") return;
  const token = await getToken();
  if (!token) return; // silent no-op until user is logged in
  console.log("[StealthRole] Recurring connections sync firing");
  startConnectionsSync({ silent: true });
});

// ── Sync orchestration ───────────────────────────────────────────────────────
// Opens LinkedIn connections page in a new tab and seeds chrome.storage with
// sr_sync_task so the content script (linkedin.js) knows to auto-scrape on load.
// The content script reports PROGRESS back to this worker, we fan out to the
// popup and clean up the tab on completion.

const CONNECTIONS_URL = "https://www.linkedin.com/mynetwork/invite-connect/connections/?sortType=RECENTLY_ADDED";

async function startConnectionsSync({ silent = false } = {}) {
  const existing = await chrome.storage.local.get("sr_sync_task");
  if (existing.sr_sync_task && existing.sr_sync_task.status === "scanning") {
    console.log("[StealthRole] Connections sync already running, ignoring");
    return { ok: false, error: "Already running" };
  }
  const task = {
    type: "connections",
    status: "opening",
    started_at: Date.now(),
    count: 0,
    silent,
  };
  await chrome.storage.local.set({ sr_sync_task: task });
  const tab = await chrome.tabs.create({ url: CONNECTIONS_URL, active: !silent });
  await chrome.storage.local.set({ sr_sync_task: { ...task, tab_id: tab.id } });
  return { ok: true, tab_id: tab.id };
}

async function finishConnectionsSync({ count, error } = {}) {
  const { sr_sync_task } = await chrome.storage.local.get("sr_sync_task");
  if (!sr_sync_task) return;
  const tabId = sr_sync_task.tab_id;
  await chrome.storage.local.remove("sr_sync_task");
  // Fan out final PROGRESS so popup / Settings page updates
  broadcast({ type: "PROGRESS", feature: "connections", count: count ?? 0, status: error ? "error" : "done", error });
  // Close the tab (silent mode: always; visible: only if no error so user can see what happened)
  if (tabId) {
    try { await chrome.tabs.remove(tabId); } catch {}
  }
  // User-facing notification
  if (error) {
    try {
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/icon128.png",
        title: "StealthRole sync failed",
        message: String(error).slice(0, 200),
      });
    } catch {}
  } else {
    try {
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/icon128.png",
        title: "StealthRole",
        message: `Synced ${count ?? 0} LinkedIn connections`,
      });
    } catch {}
  }
}

// Broadcast to all extension contexts (popup). Content scripts reach the page
// directly via window.postMessage from linkedin.js / token-sync.js.
function broadcast(msg) {
  try { chrome.runtime.sendMessage(msg, () => void chrome.runtime.lastError); } catch {}
}

// ── Message router ───────────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "API_REQUEST") {
    apiRequest(msg.path, msg.options)
      .then((data) => sendResponse({ ok: true, data }))
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true; // async response
  }

  if (msg.type === "GET_TOKEN") {
    getToken().then((token) => sendResponse({ token }));
    return true;
  }

  if (msg.type === "LOGIN") {
    apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: msg.email, password: msg.password }),
    })
      .then(async (data) => {
        await setToken(data.access_token);
        const user = await apiRequest("/auth/me");
        sendResponse({ ok: true, user });
      })
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true;
  }

  if (msg.type === "LOGOUT") {
    clearToken().then(() => sendResponse({ ok: true }));
    return true;
  }

  // ── Sync triggers ──
  if (msg.type === "START_CONNECTIONS_SYNC") {
    startConnectionsSync({ silent: !!msg.silent })
      .then((r) => sendResponse(r))
      .catch((e) => sendResponse({ ok: false, error: e.message }));
    return true;
  }

  if (msg.type === "GET_SYNC_STATUS") {
    chrome.storage.local.get("sr_sync_task").then(({ sr_sync_task }) => {
      sendResponse({ task: sr_sync_task || null });
    });
    return true;
  }

  // ── Progress reports from content script → fan out to popup ──
  if (msg.type === "PROGRESS") {
    // Update stored task count so popup can show the latest number on re-open
    chrome.storage.local.get("sr_sync_task").then(({ sr_sync_task }) => {
      if (sr_sync_task) {
        chrome.storage.local.set({
          sr_sync_task: { ...sr_sync_task, count: msg.count, status: msg.status },
        });
      }
    });
    broadcast(msg);
    if (msg.status === "done" || msg.status === "error") {
      finishConnectionsSync({ count: msg.count, error: msg.error });
    }
    // No sendResponse — fire and forget
    return false;
  }
});
