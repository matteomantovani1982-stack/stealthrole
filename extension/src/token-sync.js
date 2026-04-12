// StealthRole token sync — runs on stealthrole.com
// Syncs the web app's auth token to the extension's chrome.storage
// so the user only needs to log in once on the web app.

(() => {
  // Inject a marker so the web app knows the extension is installed
  const marker = document.createElement("div");
  marker.id = "sr-extension-marker";
  marker.style.display = "none";
  document.body.appendChild(marker);

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
