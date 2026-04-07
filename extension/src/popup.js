// StealthRole popup script

const loginView = document.getElementById("login-view");
const mainView = document.getElementById("main-view");
const loginError = document.getElementById("login-error");
const loginBtn = document.getElementById("login-btn");
const logoutBtn = document.getElementById("btn-logout");
const importBtn = document.getElementById("btn-import");
const saveJobBtn = document.getElementById("btn-save-job");
const autofillBtn = document.getElementById("btn-autofill");

// Check login state on popup open
chrome.runtime.sendMessage({ type: "GET_TOKEN" }, async (res) => {
  if (res.token) {
    showMainView();
    loadStats();
  } else {
    showLoginView();
  }
});

function showLoginView() {
  loginView.style.display = "block";
  mainView.style.display = "none";
}

function showMainView() {
  loginView.style.display = "none";
  mainView.style.display = "block";
}

// Login
loginBtn.addEventListener("click", () => {
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;
  if (!email || !password) return;

  loginBtn.textContent = "...";
  loginError.style.display = "none";

  chrome.runtime.sendMessage(
    { type: "LOGIN", email, password },
    (res) => {
      loginBtn.textContent = "Sign in";
      if (res.ok) {
        document.getElementById("user-email").textContent = res.user?.email || "Connected";
        showMainView();
        loadStats();
      } else {
        loginError.textContent = res.error || "Login failed";
        loginError.style.display = "block";
      }
    }
  );
});

// Logout
logoutBtn.addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "LOGOUT" }, () => {
    showLoginView();
  });
});

// Import LinkedIn — send message to content script
importBtn.addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.url?.includes("linkedin.com")) {
    alert("Navigate to LinkedIn first, then click Import.");
    return;
  }
  // Detect page type and run appropriate action
  const isProfile = tab.url.includes("/in/");
  importBtn.textContent = isProfile ? "Saving profile..." : "Importing...";

  const msgType = isProfile ? "IMPORT_CONNECTIONS" : "IMPORT_CONNECTIONS";
  chrome.tabs.sendMessage(tab.id, { type: msgType }, (res) => {
    importBtn.textContent = "Import LinkedIn Page";
    if (isProfile) {
      // Also trigger mutual connection scrape
      chrome.tabs.sendMessage(tab.id, { type: "SCRAPE_MUTUALS" });
    }
    if (chrome.runtime.lastError) {
      alert("Extension not loaded on this page. Refresh the LinkedIn page and try again.");
      return;
    }
    if (res?.ok) {
      loadStats();
    }
  });
});

// Save job — send message to content script
saveJobBtn.addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  chrome.tabs.sendMessage(tab.id, { type: "SAVE_JOB" }, (res) => {
    if (chrome.runtime.lastError) {
      // No content script on this page — capture from tab info
      saveJobFromTab(tab);
      return;
    }
    if (res?.ok) {
      alert(`Saved: ${res.company} — ${res.role}`);
    } else {
      saveJobFromTab(tab);
    }
  });
});

async function saveJobFromTab(tab) {
  // Fallback: use page title + URL
  const title = tab.title || "";
  const url = tab.url || "";

  // Try to extract company and role from page title
  // Common patterns: "Role at Company" or "Company - Role"
  let company = "";
  let role = "";
  const atMatch = title.match(/^(.+?)\s+(?:at|@)\s+(.+?)(?:\s*[-|]|$)/i);
  const dashMatch = title.match(/^(.+?)\s*[-|]\s*(.+?)(?:\s*[-|]|$)/);

  if (atMatch) {
    role = atMatch[1].trim();
    company = atMatch[2].trim();
  } else if (dashMatch) {
    company = dashMatch[1].trim();
    role = dashMatch[2].trim();
  } else {
    company = title.substring(0, 100);
    role = "Unknown Role";
  }

  chrome.runtime.sendMessage(
    {
      type: "API_REQUEST",
      path: "/applications",
      options: {
        method: "POST",
        body: JSON.stringify({
          company,
          role,
          date_applied: new Date().toISOString(),
          source_channel: "job_board",
          url,
        }),
      },
    },
    (res) => {
      if (res.ok) {
        alert(`Saved: ${company} — ${role}`);
        loadStats();
      } else {
        alert(res.error || "Failed to save");
      }
    }
  );
}

// Auto-fill — send message to content script
autofillBtn.addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const atsUrls = ["greenhouse.io", "lever.co", "workable.com", "ashbyhq.com"];
  if (!atsUrls.some((u) => tab?.url?.includes(u))) {
    alert("Navigate to a Greenhouse, Lever, Workable, or Ashby application form first.");
    return;
  }
  autofillBtn.textContent = "Filling...";
  chrome.tabs.sendMessage(tab.id, { type: "AUTOFILL" }, (res) => {
    autofillBtn.textContent = "Auto-Fill Application";
    if (res?.ok) {
      alert("Form filled! Review and submit.");
    } else {
      alert(res?.error || "Auto-fill failed — the form may not be detected");
    }
  });
});

// Load stats
function loadStats() {
  chrome.runtime.sendMessage(
    { type: "API_REQUEST", path: "/linkedin/stats", options: {} },
    (res) => {
      if (res?.ok && res.data) {
        document.getElementById("stat-connections").textContent = res.data.total_connections || 0;
      }
    }
  );
  chrome.runtime.sendMessage(
    { type: "API_REQUEST", path: "/applications/analytics", options: {} },
    (res) => {
      if (res?.ok && res.data) {
        document.getElementById("stat-apps").textContent = res.data.total_applications || 0;
      }
    }
  );
  // Show user email
  chrome.runtime.sendMessage(
    { type: "API_REQUEST", path: "/auth/me", options: {} },
    (res) => {
      if (res?.ok && res.data) {
        document.getElementById("user-email").textContent = res.data.email;
      }
    }
  );
}
