// StealthRole background service worker
// Handles messages between popup, content scripts, and API

importScripts("config.js");

// Keep service worker alive — Manifest V3 kills it after 30s of inactivity
const KEEPALIVE_INTERVAL = 25000;
setInterval(() => { chrome.storage.local.get("sr_keepalive"); }, KEEPALIVE_INTERVAL);

// Re-register on install/update to avoid stale worker
chrome.runtime.onInstalled.addListener(() => {
  console.log("[StealthRole] Extension installed/updated");
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "API_REQUEST") {
    apiRequest(msg.path, msg.options)
      .then((data) => sendResponse({ ok: true, data }))
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true; // Keep channel open for async response
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
        // Fetch user info
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
});
