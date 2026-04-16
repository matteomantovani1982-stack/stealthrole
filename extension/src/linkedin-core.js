// StealthRole LinkedIn — shared core (v2.0.0)
// All modules extend the SR namespace created here.
// Loaded first via manifest; config.js provides CONFIG global.

window.SR = window.SR || {};

(() => {
  "use strict";
  const SR = window.SR;

  console.log("%c[StealthRole v2.0.0] core loaded", "color: #7F8CFF; font-weight: bold");

  // ── API call: background service-worker first, direct fetch fallback ──

  SR.apiCall = function (path, options, callback) {
    if (!chrome.runtime?.id) {
      console.warn("[SR] Extension context lost — using direct API");
      SR.directFetch(path, options).then(callback);
      return;
    }
    try {
      chrome.runtime.sendMessage({ type: "API_REQUEST", path, options }, (res) => {
        if (chrome.runtime.lastError || !res) {
          console.warn("[SR] Background unavailable:", chrome.runtime.lastError?.message || "no response");
          SR.directFetch(path, options).then(callback);
        } else {
          callback(res);
        }
      });
    } catch (e) {
      console.warn("[SR] sendMessage failed:", e.message);
      SR.directFetch(path, options).then(callback);
    }
  };

  SR.directFetch = async function (path, options = {}) {
    try {
      const stored = await chrome.storage.local.get("sr_token");
      const token = stored.sr_token;
      if (!token) return { ok: false, error: "Not logged in — open StealthRole popup to log in" };
      const res = await fetch(CONFIG.API_BASE + path, {
        method: options.method || "GET",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
        body: options.body || undefined,
      });
      if (res.status === 401) return { ok: false, error: "Session expired — open StealthRole popup to log in" };
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        return { ok: false, error: body.detail || "API error " + res.status };
      }
      return { ok: true, data: await res.json() };
    } catch (e) {
      return { ok: false, error: "Network error: " + e.message };
    }
  };

  /** POST a JSON payload to a StealthRole API path, returning a promise. */
  SR.apiPost = function (path, payload) {
    return new Promise((resolve) => {
      SR.apiCall(path, { method: "POST", body: JSON.stringify(payload) }, resolve);
    });
  };

  // ── Page detection ──

  SR.getPageType = function () {
    const path = window.location.pathname;
    if (path.includes("/mynetwork/invite-connect/connections")) return "connections";
    if (path.includes("/jobs/view/") || path.includes("/jobs/collections/")) return "job";
    if (path.includes("/jobs/search/")) return "job-search";
    if (path.includes("/company/") && !path.includes("/jobs/")) return "company";
    if (path.includes("/in/")) return "profile";
    if (path.includes("/messaging")) return "messaging";
    if (path.includes("/search/results/people")) return "search";
    return "other";
  };

  // ── LinkedIn CSRF token ──

  SR.getCsrfToken = function () {
    const match = document.cookie.match(/JSESSIONID="?(ajax:[^";]+)"?/);
    return match ? match[1] : null;
  };

  SR.voyagerHeaders = function () {
    const csrf = SR.getCsrfToken();
    if (!csrf) return null;
    return {
      "csrf-token": csrf,
      "x-restli-protocol-version": "2.0.0",
      accept: "application/vnd.linkedin.normalized+json+2.1",
      "x-li-lang": "en_US",
    };
  };

  // ── Current user identity (for message is_mine detection) ──

  SR._myProfileUrn = null;
  SR._myPublicId = null;

  SR.fetchMyProfile = async function () {
    if (SR._myProfileUrn) return SR._myProfileUrn;
    const headers = SR.voyagerHeaders();
    if (!headers) return null;
    try {
      const res = await fetch("https://www.linkedin.com/voyager/api/me", {
        headers,
        credentials: "include",
      });
      if (!res.ok) return null;
      const data = await res.json();
      const walk = (obj) => {
        if (!obj || typeof obj !== "object") return;
        if (Array.isArray(obj)) { for (const x of obj) walk(x); return; }
        if (obj.publicIdentifier && !SR._myPublicId) SR._myPublicId = obj.publicIdentifier;
        const urn = obj.entityUrn || obj["$urn"] || "";
        if (typeof urn === "string" && /urn:li:(fs_miniProfile|fsd_profile|member):/i.test(urn) && !SR._myProfileUrn) {
          SR._myProfileUrn = urn;
        }
        for (const k in obj) { if (obj[k] && typeof obj[k] === "object") walk(obj[k]); }
      };
      walk(data);
      if (SR._myProfileUrn) console.log("[SR] My profile URN:", SR._myProfileUrn);
      if (SR._myPublicId) console.log("[SR] My public ID:", SR._myPublicId);
      return SR._myProfileUrn;
    } catch (e) {
      console.warn("[SR] fetchMyProfile failed:", e.message);
      return null;
    }
  };

  // ── Progress reporting → background → popup ──

  SR.sendProgress = function (feature, count, status, error) {
    try {
      chrome.runtime.sendMessage({ type: "PROGRESS", feature, count, status, error });
    } catch {}
  };

  // ── Toast notification ──

  SR.showToast = function (message) {
    let t = document.getElementById("sr-toast");
    if (!t) {
      t = document.createElement("div");
      t.id = "sr-toast";
      t.className = "sr-toast";
      document.body.appendChild(t);
    }
    t.textContent = message;
    t.classList.add("sr-toast-visible");
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.remove("sr-toast-visible"), 4000);
  };

  // ── Overlay sync button ──

  SR.injectOverlayButton = function (type) {
    if (document.getElementById("sr-overlay-btn")) return;
    const btn = document.createElement("button");
    btn.id = "sr-overlay-btn";
    btn.className = "sr-overlay-btn";
    const labels = {
      connections: "Sync Connections",
      profile: "Save Contact",
      messaging: "Import Messages",
      search: "Save Results",
      job: "⚡ Analyze Job",
      "job-search": "Save Jobs",
      company: "🔍 Company Intel",
    };
    btn.textContent = labels[type] || "StealthRole";
    btn.addEventListener("click", () => SR.handleOverlayClick(type));
    document.body.appendChild(btn);

    if (type === "connections" || type === "messaging") {
      const syncBtn = document.createElement("button");
      syncBtn.id = "sr-sync-btn";
      syncBtn.className = "sr-overlay-btn sr-sync-btn";
      syncBtn.textContent = "⟳ Full Sync";
      syncBtn.addEventListener("click", async () => {
        syncBtn.disabled = true;
        syncBtn.textContent = "Starting…";
        const msgType = type === "connections" ? "START_CONNECTIONS_SYNC" : "START_MESSAGES_SYNC";
        chrome.runtime.sendMessage({ type: msgType }, (res) => {
          if (res?.ok) {
            syncBtn.textContent = "Syncing…";
          } else {
            syncBtn.textContent = res?.error || "Failed";
            setTimeout(() => { syncBtn.textContent = "⟳ Full Sync"; syncBtn.disabled = false; }, 3000);
          }
        });
      });
      document.body.appendChild(syncBtn);
    }
  };

  SR.handleOverlayClick = function (type) {
    if (type === "connections") SR.scrapeConnectionsManual?.();
    else if (type === "profile") { SR.scrapeProfile?.(); SR.scrapeMutualConnections?.(); }
    else if (type === "messaging") SR.autoScrapeMessages?.();
    else if (type === "search") SR.handleSearchScrape?.();
    else if (type === "job") SR.captureJob?.();
    else if (type === "job-search") SR.captureJobSearchResults?.();
    else if (type === "company") SR.captureCompanyIntel?.();
  };

  // ── PerformanceObserver — passive endpoint discovery ──
  // Installed on messaging pages. Captures the real voyager URLs that
  // LinkedIn's own React app fetches, so autoScrapeMessages can try them
  // first instead of guessing with hardcoded endpoints.

  SR._discoveredMsgEndpoints = [];

  SR.installNetworkObserver = function () {
    try {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          const url = entry.name || "";
          if (!url.includes("voyager")) continue;
          if (!(url.includes("essag") || url.includes("onvers") || url.includes("inbox") || url.includes("thread"))) continue;
          if (SR._discoveredMsgEndpoints.includes(url)) continue;
          console.log("[SR-NET] Captured:", url.slice(0, 200));
          SR._discoveredMsgEndpoints.push(url);
        }
      });
      observer.observe({ type: "resource", buffered: true });
      console.log("[SR-NET] Observer installed — capturing LinkedIn messaging API calls");
    } catch (e) {
      console.warn("[SR-NET] Observer failed:", e);
    }
  };

  // ── State flags ──

  SR._autoScrapeInProgress = false;
  SR._autoMessagesInProgress = false;
  SR._mutualScrapeInProgress = false;
  SR._lastUrl = window.location.href;

  // ── Page init routing ──

  SR.initForPage = function () {
    SR._mutualScrapeInProgress = false;
    const pageType = SR.getPageType();
    console.log("[SR] Page init:", pageType, window.location.pathname);

    if (["connections", "profile", "messaging", "search", "job", "job-search", "company"].includes(pageType)) {
      SR.injectOverlayButton(pageType);
    }

    // Auto-sync: if background set sr_sync_task, start the right flow
    try {
      chrome.storage.local.get("sr_sync_task", (data) => {
        const task = data.sr_sync_task;
        if (!task || task.status === "done") return;
        if (pageType === "connections" && task.type === "connections") {
          console.log("[SR] sr_sync_task=connections, auto-sync in 2 s");
          chrome.storage.local.set({ sr_sync_task: { ...task, status: "scanning" } });
          setTimeout(() => SR.autoScrapeConnections?.(), 2000);
        }
        if (pageType === "messaging" && task.type === "messages") {
          console.log("[SR] sr_sync_task=messages, auto-sync in 2 s");
          chrome.storage.local.set({ sr_sync_task: { ...task, status: "scanning" } });
          setTimeout(() => SR.autoScrapeMessages?.(), 2000);
        }
      });
    } catch {}

    // Messaging: install network observer so we discover endpoints early
    if (pageType === "messaging") {
      SR.installNetworkObserver();
      // Auto-classify visible conversations
      setTimeout(() => SR.classifyVisibleConversations?.(), 3000);
    }

    // Job page: auto-capture after a short delay for page to render
    if (pageType === "job") {
      setTimeout(() => SR.captureJob?.(), 2000);
    }

    // Company page: auto-capture company intel
    if (pageType === "company") {
      setTimeout(() => SR.captureCompanyIntel?.(), 2000);
    }

    // Profile: auto-scrape + check for pending scan
    if (pageType === "profile") {
      SR.waitForProfileName?.().then(() => {
        SR.scrapeProfile?.().then(() => {
          try {
            chrome.storage.local.get("sr_scan_target", (data) => {
              if (!data.sr_scan_target) return;
              const scan = data.sr_scan_target;
              const connectorSlug = (scan.connector_url || "").split("/in/")[1]?.replace(/\/$/, "") || "";
              const currentSlug = window.location.pathname.split("/in/")[1]?.replace(/\/$/, "") || "";
              if (connectorSlug && connectorSlug === currentSlug) {
                SR.scrapeMutualConnections?.();
              }
            });
          } catch {}
        });
      });
    }
  };

  // ── SPA navigation detection ──

  const urlObserver = new MutationObserver(() => {
    if (window.location.href !== SR._lastUrl) {
      SR._lastUrl = window.location.href;
      document.getElementById("sr-overlay-btn")?.remove();
      document.getElementById("sr-sync-btn")?.remove();
      setTimeout(() => SR.initForPage(), 1500);
    }
  });
  urlObserver.observe(document.body, { childList: true, subtree: true });

  window.addEventListener("popstate", () => {
    setTimeout(() => {
      if (window.location.href !== SR._lastUrl) {
        SR._lastUrl = window.location.href;
        setTimeout(() => SR.initForPage(), 1500);
      }
    }, 500);
  });

  // ── Message listener from popup / background ──

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === "IMPORT_CONNECTIONS") {
      if (SR.getPageType() === "profile") {
        SR.scrapeProfile?.();
        SR.scrapeMutualConnections?.();
      } else {
        SR.scrapeConnectionsManual?.();
      }
      setTimeout(() => sendResponse({ ok: true }), 2000);
      return true;
    }
    if (msg.type === "SCRAPE_MUTUALS") {
      SR.scrapeMutualConnections?.();
      setTimeout(() => sendResponse({ ok: true }), 2000);
      return true;
    }
  });

  // ── Intelligence side-panel ──
  // A persistent panel injected into LinkedIn pages that shows StealthRole
  // intelligence: way-in paths, signals, who-you-know, recruiter flags.

  SR.showIntelPanel = function (title, sections) {
    let panel = document.getElementById("sr-intel-panel");
    if (!panel) {
      panel = document.createElement("div");
      panel.id = "sr-intel-panel";
      panel.className = "sr-intel-panel";
      document.body.appendChild(panel);
    }
    let html = `<div class="sr-intel-header">
      <span class="sr-intel-logo">⚡</span>
      <span class="sr-intel-title">${title}</span>
      <button class="sr-intel-close" onclick="document.getElementById('sr-intel-panel').style.display='none'">&times;</button>
    </div>`;

    for (const section of sections) {
      html += `<div class="sr-intel-section">`;
      if (section.heading) html += `<div class="sr-intel-heading">${section.heading}</div>`;
      if (section.badge) html += `<span class="sr-intel-badge sr-intel-badge--${section.badgeType || 'info'}">${section.badge}</span>`;
      if (section.items && section.items.length > 0) {
        html += `<ul class="sr-intel-list">`;
        for (const item of section.items) {
          html += `<li class="sr-intel-item">`;
          if (item.icon) html += `<span class="sr-intel-icon">${item.icon}</span>`;
          html += `<span class="sr-intel-text">${item.text}</span>`;
          if (item.sub) html += `<span class="sr-intel-sub">${item.sub}</span>`;
          if (item.action) html += `<button class="sr-intel-action" onclick="${item.action.onclick}">${item.action.label}</button>`;
          html += `</li>`;
        }
        html += `</ul>`;
      }
      if (section.empty) html += `<div class="sr-intel-empty">${section.empty}</div>`;
      if (section.html) html += section.html;
      html += `</div>`;
    }
    panel.innerHTML = html;
    panel.style.display = "block";
  };

  SR.hideIntelPanel = function () {
    const panel = document.getElementById("sr-intel-panel");
    if (panel) panel.style.display = "none";
  };

  // ── Boot ──
  setTimeout(() => SR.initForPage(), 800);
  setTimeout(() => SR.initForPage(), 3000);
})();
