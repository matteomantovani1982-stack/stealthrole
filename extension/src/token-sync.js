// StealthRole token sync — runs on stealthrole.com
// Syncs the web app's auth token to the extension's chrome.storage
// so the user only needs to log in once on the web app.
// Also bridges web app → extension messaging via window.postMessage.

(() => {
  // Inject a marker so the web app knows the extension is installed.
  // Set data-version so the web app can detect old extension versions.
  const marker = document.createElement("div");
  marker.id = "sr-extension-marker";
  marker.dataset.version = "1.0.0";
  marker.style.display = "none";
  document.body.appendChild(marker);

  // ── Bridge: web app → extension messaging ──────────────────────────
  // The web app cannot directly send messages to the extension's content
  // script on linkedin.com (security model). It posts a message to its
  // own window which we (running in the same page context) catch and
  // forward to chrome.storage / chrome.runtime.
  window.addEventListener("message", (event) => {
    if (event.source !== window || !event.data || typeof event.data !== "object") return;
    const msg = event.data;

    // Trigger an on-demand network scan: open a connector's connections list
    // in a new tab and ask the linkedin.js content script to scrape it.
    if (msg.type === "SR_SCAN_NETWORK") {
      const payload = {
        connector_url: msg.connectorUrl || "",
        connector_name: msg.connectorName || "",
        target_company: msg.targetCompany || "",
        started_at: Date.now(),
        status: "queued",
        progress: "Opening connector's profile...",
        matches: [],
      };
      try {
        chrome.storage.local.set({ sr_scan_target: payload }, () => {
          console.log("[StealthRole] sr_scan_target set:", payload);
          // Open the connector's connections list. LinkedIn URL pattern:
          //   /search/results/people/?network=%5B%22F%22%5D&connectionOf=%5B%22<id>%22%5D
          // But we don't have the LinkedIn numeric ID, only the public URL.
          // Open the connector's profile — the linkedin.js content script
          // will detect sr_scan_target and click through to connections.
          const url = msg.connectorUrl || "";
          if (url) window.open(url, "_blank");
          // Reply to the page so the UI can show "scanning..."
          window.postMessage({ type: "SR_SCAN_NETWORK_ACK", ok: true }, "*");
        });
      } catch (e) {
        window.postMessage({ type: "SR_SCAN_NETWORK_ACK", ok: false, error: String(e) }, "*");
      }
    }

    // Cancel an in-flight scan
    if (msg.type === "SR_CANCEL_SCAN") {
      try {
        chrome.storage.local.remove("sr_scan_target");
      } catch {}
    }

    // Trigger the automated connections sync (opens a LinkedIn tab, scrolls,
    // scrapes, batches to backend). Fired by the Settings page "Sync now via
    // extension" button.
    if (msg.type === "SR_START_CONNECTIONS_SYNC") {
      try {
        chrome.runtime.sendMessage({ type: "START_CONNECTIONS_SYNC" }, (res) => {
          window.postMessage({ type: "SR_SYNC_STARTED", ok: !!(res && res.ok), error: res && res.error }, "*");
        });
      } catch (e) {
        window.postMessage({ type: "SR_SYNC_STARTED", ok: false, error: String(e) }, "*");
      }
    }
  });

  // Forward PROGRESS broadcasts from the background service worker back to
  // the page so Settings can render a live count during sync.
  try {
    chrome.runtime.onMessage.addListener((msg) => {
      if (msg && msg.type === "PROGRESS") {
        window.postMessage({ type: "SR_SYNC_PROGRESS", payload: msg }, "*");
      }
    });
  } catch {}

  // Forward storage updates back to the page so it can show progress
  try {
    chrome.storage.onChanged.addListener((changes, areaName) => {
      if (areaName !== "local") return;
      if (changes.sr_scan_target) {
        const newVal = changes.sr_scan_target.newValue;
        window.postMessage({ type: "SR_SCAN_NETWORK_PROGRESS", payload: newVal }, "*");
      }
    });
  } catch {}

  // Listen for token sync events from the web app
  window.addEventListener("sr-token-sync", (e) => {
    const token = e.detail?.token;
    if (token) {
      chrome.storage.local.set({ sr_token: token }, () => {
        console.log("[StealthRole] Token synced from web app to extension");
      });
    }
  });

  // Also read the token from localStorage directly on page load
  // (in case the event hasn't fired yet)
  try {
    const token = localStorage.getItem("sr_token");
    if (token) {
      chrome.storage.local.set({ sr_token: token }, () => {
        console.log("[StealthRole] Token synced on page load");
      });
    }
  } catch (e) {
    // localStorage might not be accessible
  }

  // Watch for localStorage changes (login/logout on the web app)
  window.addEventListener("storage", (e) => {
    if (e.key === "sr_token") {
      if (e.newValue) {
        chrome.storage.local.set({ sr_token: e.newValue });
        console.log("[StealthRole] Token updated via storage event");
      } else {
        chrome.storage.local.remove("sr_token");
        console.log("[StealthRole] Token cleared via storage event");
      }
    }
  });
})();
