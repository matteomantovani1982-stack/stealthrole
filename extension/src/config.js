// StealthRole extension configuration
const CONFIG = {
  API_BASE: "https://api.stealthrole.com/api/v1",
  APP_URL: "https://stealthrole.com",
};

// Storage helpers
async function getToken() {
  const data = await chrome.storage.local.get("sr_token");
  return data.sr_token || null;
}

async function setToken(token) {
  await chrome.storage.local.set({ sr_token: token });
}

async function clearToken() {
  await chrome.storage.local.remove("sr_token");
}

async function apiRequest(path, options = {}) {
  const token = await getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${CONFIG.API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    await clearToken();
    throw new Error("Session expired — please log in again");
  }

  if (res.status === 204) return null;

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error ${res.status}`);
  }

  return res.json();
}
