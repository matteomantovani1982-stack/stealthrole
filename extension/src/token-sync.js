// StealthRole token sync — runs on stealthrole.com
// Syncs the web app's auth token to the extension's chrome.storage
// so the user only needs to log in once on the web app.
// Also bridges web app → extension messaging via window.postMessage.

(() => {
  // Inject a marker so the web app knows the extension is installed.
  // Set data-version so the web app can detect old extension versions.
  const marker = document.createElement("div");
  marker.id = "sr-extension-marker";
  marker.dataset.version = "2.0.0";
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
    // in a new tab and ask the content scripts to scrape it.
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

    // Send a message via LinkedIn — pre-fill draft in LinkedIn's composer
    if (msg.type === "SR_SEND_LINKEDIN_MESSAGE") {
      try {
        chrome.runtime.sendMessage({
          type: "SEND_LINKEDIN_MESSAGE",
          conversationUrn: msg.conversationUrn || null,
          linkedinUrl: msg.linkedinUrl || null,
          draftText: msg.draftText,
        }, (res) => {
          window.postMessage({
            type: "SR_SEND_LINKEDIN_MESSAGE_RESULT",
            ok: !!(res && res.ok),
            error: res && res.error,
          }, "*");
        });
      } catch (e) {
        window.postMessage({ type: "SR_SEND_LINKEDIN_MESSAGE_RESULT", ok: false, error: String(e) }, "*");
      }
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

  // Derive the API base URL from the page origin. This lets the extension
  // talk to the SAME backend the user is currently signed into:
  //   localhost:3000 → http://localhost:8000/api/v1   (dev)
  //   stealthrole.com → https://api.stealthrole.com/api/v1   (prod)
  // Without this, the extension writes data to prod even when you're
  // testing locally, so localhost UIs look empty.
  function deriveApiBase() {
    try {
      const origin = window.location.origin;
      if (/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(origin)) {
        return "http://localhost:8000/api/v1";
      }
      if (/stealthrole\.com$/i.test(window.location.hostname)) {
        return "https://api.stealthrole.com/api/v1";
      }
    } catch {}
    return null;
  }

  /** Avoid repeated chrome.storage writes + console spam when the same JWT is synced many times */
  let _lastPersistedJwt = "";

  function persistTokenAndBase(token, source) {
    const apiBase = deriveApiBase();
    if (token === _lastPersistedJwt) {
      return;
    }
    _lastPersistedJwt = token;
    // Keep a per-base map so prod and local tokens don't trample each other
    // (each tab's token-sync ran on a different origin → each has its own JWT).
    chrome.storage.local.get("sr_tokens_by_base", (cur) => {
      const tokens = (cur && cur.sr_tokens_by_base && typeof cur.sr_tokens_by_base === "object")
        ? { ...cur.sr_tokens_by_base }
        : {};
      if (apiBase) tokens[apiBase] = token;
      const payload = { sr_token: token, sr_tokens_by_base: tokens };
      if (apiBase) payload.sr_api_base = apiBase;
      chrome.storage.local.set(payload, () => {
        console.log(
          `[StealthRole] Token synced (${source}) → API base = ${apiBase || "unknown"} (token_prefix=${token.slice(0, 16)}…, bases stored=${Object.keys(tokens).length})`,
        );
      });
    });
  }

  // Listen for token sync events from the web app (login, refresh) and clears (logout).
  window.addEventListener("sr-token-sync", (e) => {
    const token = e.detail?.token;
    if (!token) {
      try {
        _lastPersistedJwt = "";
        chrome.storage.local.remove(["sr_token", "sr_api_base", "sr_tokens_by_base"], () => {
          console.log("[StealthRole] Extension storage cleared (logout / token reset)");
        });
      } catch (err) {
        console.warn("[StealthRole] Could not clear extension storage:", err);
      }
      return;
    }
    persistTokenAndBase(token, "sr-token-sync event");
  });

  // Also read the token from localStorage directly on page load
  // (in case the event hasn't fired yet)
  try {
    const token = localStorage.getItem("sr_token");
    if (token) persistTokenAndBase(token, "page load");
  } catch (e) {
    // localStorage might not be accessible
  }

  // Watch for localStorage changes (login/logout on the web app)
  window.addEventListener("storage", (e) => {
    if (e.key === "sr_token") {
      if (e.newValue) {
        persistTokenAndBase(e.newValue, "storage event");
      } else {
        chrome.storage.local.remove(["sr_token", "sr_api_base"]);
        console.log("[StealthRole] Token cleared via storage event");
      }
    }
  });
})();
