// StealthRole extension configuration
const CONFIG = {
  API_BASE: "https://api.stealthrole.com/api/v1",
  APP_URL: "https://stealthrole.com",
};

// Storage helpers
async function getToken() {
  // Prefer a token captured for the *current* API base (e.g. local token for
  // localhost:8000, prod token for api.stealthrole.com). Falls back to the
  // generic sr_token for backwards-compat if the per-base map isn't populated.
  try {
    const data = await chrome.storage.local.get(["sr_token", "sr_tokens_by_base"]);
    const base = await getApiBase();
    if (data.sr_tokens_by_base && typeof data.sr_tokens_by_base === "object") {
      const t = data.sr_tokens_by_base[base];
      if (t) return t;
    }
    return data.sr_token || null;
  } catch {
    const data = await chrome.storage.local.get("sr_token");
    return data.sr_token || null;
  }
}

async function setToken(token) {
  await chrome.storage.local.set({ sr_token: token });
}

async function clearToken() {
  await chrome.storage.local.remove("sr_token");
}

// Read the API base last set by token-sync.js (matches whichever SR site
// the user signed into — prod or localhost). If sr_api_base is missing but
// sr_tokens_by_base still has entries (e.g. storage event quirks), infer the
// base so localhost dev does not silently fall back to prod and write data
// to the wrong backend.
async function getApiBase() {
  try {
    const data = await chrome.storage.local.get(["sr_api_base", "sr_tokens_by_base"]);
    if (data && typeof data.sr_api_base === "string" && data.sr_api_base) {
      return data.sr_api_base;
    }
    const map = data.sr_tokens_by_base;
    if (map && typeof map === "object") {
      const keys = Object.keys(map).filter((k) => map[k]);
      const local = keys.find((k) => /localhost|127\.0\.0\.1/i.test(k));
      if (local) return local;
      if (keys.length === 1) return keys[0];
    }
  } catch {}
  return CONFIG.API_BASE;
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

  const apiBase = await getApiBase();
  const url = `${apiBase}${path}`;
  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    // Visible diagnostic so we can tell *which* base + token combo got rejected.
    // Helps catch the "extension cached prod token but now talks to localhost"
    // foot-gun where the prod JWT is signed with a different secret.
    console.warn(
      `[StealthRole] 401 from ${apiBase}${path}  token_prefix=${(token || "").slice(0, 16)}…  ` +
      `(if base=localhost but token=prod, reload localhost:3000 to capture local token)`,
    );
    // DON'T clear the token — it may still work for other endpoints
    // or the user might just need to retry. Clearing causes a cascade
    // where ALL subsequent calls fail.
    throw new Error("Session expired — please log in again");
  }

  if (res.status === 204) return null;

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error ${res.status}`);
  }

  return res.json();
}
