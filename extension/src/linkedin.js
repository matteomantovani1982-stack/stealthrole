// StealthRole LinkedIn content script
(() => {

  // API call: background script first, direct fetch fallback
  function srApiCall(path, options, callback) {
    // Check if extension context is still valid
    if (!chrome.runtime?.id) {
      console.warn("[StealthRole] Extension context lost — using direct API");
      directFetch(path, options).then(callback);
      return;
    }

    try {
      chrome.runtime.sendMessage({ type: "API_REQUEST", path, options }, (res) => {
        if (chrome.runtime.lastError || !res) {
          console.warn("[StealthRole] Background unavailable:", chrome.runtime.lastError?.message || "no response");
          // Fallback: call API directly
          directFetch(path, options).then(callback);
        } else {
          callback(res);
        }
      });
    } catch (e) {
      console.warn("[StealthRole] sendMessage failed:", e.message);
      directFetch(path, options).then(callback);
    }
  }

  async function directFetch(path, options = {}) {
    try {
      // Read token from storage
      const stored = await chrome.storage.local.get("sr_token");
      const token = stored.sr_token;
      if (!token) {
        return { ok: false, error: "Not logged in — open StealthRole popup to log in" };
      }

      const res = await fetch(CONFIG.API_BASE + path, {
        method: options.method || "GET",
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Bearer " + token,
        },
        body: options.body || undefined,
      });

      if (res.status === 401) {
        return { ok: false, error: "Session expired — open StealthRole popup to log in" };
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        return { ok: false, error: body.detail || ("API error " + res.status) };
      }
      const data = await res.json();
      return { ok: true, data };
    } catch (e) {
      return { ok: false, error: "Network error: " + e.message };
    }
  }

  function getPageType() {
    const path = window.location.pathname;
    if (path.includes("/mynetwork/invite-connect/connections")) return "connections";
    if (path.includes("/in/")) return "profile";
    if (path.includes("/messaging")) return "messaging";
    if (path.includes("/search/results/people")) return "search";
    return "other";
  }

  let _lastUrl = window.location.href;
  let _mutualScrapeInProgress = false;

  function initForPage() {
    _mutualScrapeInProgress = false; // Reset on new page navigation
    const pageType = getPageType();
    console.log("[StealthRole] Page init:", pageType, window.location.pathname);
    if (["connections", "profile", "messaging", "search"].includes(pageType)) {
      injectOverlayButton(pageType);
    }

    // ── Auto-sync: if we're on the connections page and background set
    //    sr_sync_task, start the automated scroll+scrape+batch flow.
    if (pageType === "connections") {
      // Auto-diagnose the DOM structure after the page stabilizes — tells
      // us what LinkedIn is actually rendering this week without any user action.
      setTimeout(() => {
        try {
          const links = Array.from(document.querySelectorAll("a[href*='/in/']"))
            .filter((a) => {
              const href = a.href || "";
              return /\/in\/[^\/]+\/?$/.test(href.split("?")[0]);
            })
            .slice(0, 5);
          console.log(`[StealthRole-DIAG] found ${document.querySelectorAll("a[href*='/in/']").length} /in/ links on page`);
          console.log(`[StealthRole-DIAG] probing first ${links.length} unique profile links:`);
          links.forEach((link, idx) => {
            console.log(`[StealthRole-DIAG] === Link ${idx} href=${link.href.split('?')[0]} ===`);
            let el = link;
            for (let i = 0; i < 8; i++) {
              if (!el) break;
              const tag = el.tagName;
              const role = el.getAttribute && el.getAttribute("role");
              const view = el.getAttribute && el.getAttribute("data-view-name");
              const cls = (el.className || "").toString().slice(0, 50);
              const kids = el.children ? el.children.length : 0;
              const txt = (el.innerText || "").replace(/\n+/g, " | ").slice(0, 150);
              console.log(`[StealthRole-DIAG]   L${i} ${tag}${role ? '[role='+role+']' : ''}${view ? '[dv='+view+']' : ''} cls="${cls}" kids=${kids} txt="${txt}"`);
              el = el.parentElement;
            }
          });
        } catch (e) {
          console.warn("[StealthRole-DIAG] probe failed:", e);
        }
      }, 3000);

      try {
        chrome.storage.local.get("sr_sync_task", (data) => {
          const task = data.sr_sync_task;
          console.log("[StealthRole] connections page — sr_sync_task =", JSON.stringify(task));
          if (task && task.type === "connections" && task.status !== "done") {
            console.log("[StealthRole] sr_sync_task detected, starting autoScrapeConnections in 2s");
            chrome.storage.local.set({ sr_sync_task: { ...task, status: "scanning" } });
            setTimeout(() => autoScrapeConnections(), 2000);
          } else {
            console.log("[StealthRole] no active sync task — click the blue 🔄 Sync ALL button to start");
          }
        });
      } catch (e) {
        console.warn("[StealthRole] sr_sync_task check failed:", e);
      }
    }

    // Auto-save profile + scrape mutual connections on profile pages
    if (pageType === "profile") {
      waitForProfileName().then(() => {
        scrapeProfileAsync().then(() => {
          scrapeMutualConnections();
          setTimeout(() => scrapeMutualConnections(), 3000);
        });
      });
    }

    // On search pages — check if we're scraping mutual connections for a target person
    if (pageType === "search") {
      setTimeout(() => scrapeMutualSearchResults(), 2000);
      // Retry after more results load
      setTimeout(() => scrapeMutualSearchResults(), 5000);
    }

    // ── On-demand network scan: web app set sr_scan_target asking us
    //    to scrape this connector's connections list for matches at a
    //    target company ──────────────────────────────────────────────
    try {
      chrome.storage.local.get("sr_scan_target", (data) => {
        const scan = data.sr_scan_target;
        if (!scan || !scan.target_company) return;
        // If we're on the connector's profile page → click through to connections
        if (pageType === "profile") {
          const connectorSlug = (scan.connector_url || "").split("/in/")[1]?.replace(/\/$/, "") || "";
          const currentSlug = window.location.pathname.split("/in/")[1]?.replace(/\/$/, "") || "";
          if (connectorSlug && currentSlug && connectorSlug === currentSlug) {
            updateScanProgress(scan, "Opening connections list...");
            // LinkedIn's "Connections" link on a profile uses /search/results/people/?connectionOf=...
            setTimeout(() => clickConnectionsLink(connectorSlug), 2500);
          }
        }
        // If we're on a search results page with the network scan target set,
        // scrape it for matches at the target company
        if (pageType === "search" && window.location.href.includes("network=") && scan.target_company) {
          setTimeout(() => scrapeNetworkForCompany(scan), 2500);
        }
      });
    } catch (e) {
      console.warn("[StealthRole] sr_scan_target check failed:", e);
    }
  }

  // ── On-demand network scan helpers ───────────────────────────────────
  function updateScanProgress(currentScan, progressText) {
    try {
      const updated = { ...currentScan, status: "scanning", progress: progressText };
      chrome.storage.local.set({ sr_scan_target: updated });
      console.log("[StealthRole] scan progress:", progressText);
    } catch (e) {}
  }

  function clickConnectionsLink(connectorSlug) {
    // Strategy 1: find a link to /search/results/people/?connectionOf=...
    const links = document.querySelectorAll("a[href*='connectionOf'], a[href*='/search/results/people']");
    for (const link of links) {
      if (link.offsetParent === null) continue;
      const text = (link.innerText || link.textContent || "").toLowerCase();
      if (text.includes("connection")) {
        console.log("[StealthRole] clicking connections link:", link.href);
        link.click();
        return;
      }
    }
    // Strategy 2: find any clickable element with text "X connections"
    const all = document.querySelectorAll("a, button, span, div");
    for (const el of all) {
      if (el.offsetParent === null) continue;
      const text = (el.innerText || el.textContent || "").trim().toLowerCase();
      // Match e.g. "500+ connections", "1234 connections"
      if (/^[\d,]+\+?\s+connections?$/i.test(text) || text === "connections") {
        const clickTarget = el.closest("a, button") || el;
        console.log("[StealthRole] clicking text-matched connections el");
        clickTarget.click();
        return;
      }
    }
    console.log("[StealthRole] connections link not found on profile");
  }

  function scrapeNetworkForCompany(scanTarget) {
    if (_mutualScrapeInProgress) return;
    _mutualScrapeInProgress = true;
    const targetCompany = (scanTarget.target_company || "").toLowerCase().trim();
    const matches = [];
    const seen = new Set();
    let totalScraped = 0;
    let currentPage = 1;
    const maxPages = 10;

    function scrapePage() {
      // Scroll to load all results on this page
      let scrollCount = 0;
      function scrollDown() {
        window.scrollTo(0, document.body.scrollHeight);
        scrollCount++;
        setTimeout(() => {
          if (scrollCount < 3) {
            scrollDown();
          } else {
            const pageResults = scrapeSearchResults();
            for (const p of pageResults) {
              if (seen.has(p.name)) continue;
              seen.add(p.name);
              totalScraped++;
              // Check if their headline / snippet mentions the target company
              const blob = ((p.headline || "") + " " + (p.name || "")).toLowerCase();
              if (blob.includes(targetCompany)) {
                matches.push(p);
              }
            }
            updateScanProgress(scanTarget, `Scanning page ${currentPage} — ${totalScraped} connections checked, ${matches.length} matches at ${scanTarget.target_company}`);

            const nextBtn = findNextPageButton();
            if (nextBtn && currentPage < maxPages) {
              currentPage++;
              nextBtn.click();
              setTimeout(scrapePage, 3000);
            } else {
              // Done — POST matches to backend
              finishScan(scanTarget, matches, totalScraped);
            }
          }
        }, 1000);
      }
      scrollDown();
    }

    setTimeout(scrapePage, 1500);
  }

  function finishScan(scanTarget, matches, totalScraped) {
    showToast(`Found ${matches.length} mutual connection${matches.length === 1 ? "" : "s"} at ${scanTarget.target_company}`);
    const payload = {
      connector_url: scanTarget.connector_url,
      connector_name: scanTarget.connector_name,
      target_company: scanTarget.target_company,
      total_scraped: totalScraped,
      matches: matches.map(m => ({
        name: m.name,
        linkedin_url: m.linkedin_url || "",
        headline: m.headline || "",
      })),
    };
    srApiCall("/linkedin/ingest/network-scan", { method: "POST", body: JSON.stringify(payload) }, (res) => {
      console.log("[StealthRole] network-scan save:", res);
      try {
        const final = {
          ...scanTarget,
          status: "complete",
          progress: `Found ${matches.length} mutual${matches.length === 1 ? "" : "s"} at ${scanTarget.target_company}`,
          matches: payload.matches,
          total_scraped: totalScraped,
          finished_at: Date.now(),
        };
        chrome.storage.local.set({ sr_scan_target: final });
        // Auto-clear after 30s
        setTimeout(() => chrome.storage.local.remove("sr_scan_target"), 30000);
      } catch (e) {}
      _mutualScrapeInProgress = false;
    });
  }

  function waitForProfileName(maxWait = 15000) {
    return new Promise((resolve) => {
      const start = Date.now();
      function check() {
        const name = getProfileName();
        if (name) {
          console.log("[StealthRole] Name found after " + (Date.now() - start) + "ms: " + name);
          resolve(name);
          return;
        }
        if (Date.now() - start > maxWait) {
          console.log("[StealthRole] Gave up waiting for name after " + maxWait + "ms");
          resolve(null);
          return;
        }
        setTimeout(check, 500);
      }
      check();
    });
  }

  function getConnectionDegree() {
    // Look for "· 1st", "· 2nd", "· 3rd" in page text
    const bodyText = document.body.innerText || "";
    if (/·\s*1st/.test(bodyText)) return 1;
    if (/·\s*2nd/.test(bodyText)) return 2;
    if (/·\s*3rd\+?/.test(bodyText)) return 3;
    return 0; // unknown
  }

  function getCompanyFromPage() {
    // Strategy 1: company link on the profile (most reliable — always present)
    // LinkedIn shows company logo + name as a link to /company/xxx/
    const companyLinks = document.querySelectorAll("a[href*='/company/']");
    for (const link of companyLinks) {
      const text = (link.innerText || link.textContent || "").trim();
      // Must be a short company name, not a long sentence
      if (text && text.length >= 2 && text.length < 60 && !text.toLowerCase().includes("see all")) {
        console.log("[StealthRole] Company from link:", text);
        return text;
      }
    }

    // Strategy 2: parse from headline "Title at Company"
    const headline = getProfileHeadline();
    if (headline) {
      const atMatch = headline.match(/\bat\s+(.+)/i);
      if (atMatch) {
        console.log("[StealthRole] Company from headline:", atMatch[1].trim());
        return atMatch[1].trim();
      }
    }

    // Strategy 3: parse from page title "Name - Title at Company | LinkedIn"
    const title = document.title || "";
    const atMatch = title.match(/\bat\s+([^|]+)/i);
    if (atMatch) {
      const company = atMatch[1].trim();
      if (company && company.length < 60) {
        console.log("[StealthRole] Company from title:", company);
        return company;
      }
    }

    console.log("[StealthRole] Company: not found");
    return "";
  }

  function getProfileHeadline() {
    // Strategy 1: page title "Name - Headline | LinkedIn"
    const title = document.title || "";
    const dashIdx = title.indexOf(" - ");
    if (dashIdx > 1) {
      const afterName = title.substring(dashIdx + 3);
      const pipeIdx = afterName.lastIndexOf(" | ");
      const headline = pipeIdx > 0 ? afterName.substring(0, pipeIdx).trim() : afterName.trim();
      if (headline && headline.length >= 2 && !headline.toLowerCase().includes("linkedin")) {
        return headline;
      }
    }

    // Strategy 2: scan visible page text for "Title at Company" near the person's name
    const name = getProfileName();
    if (name) {
      const bodyText = document.body.innerText || "";
      const nameIdx = bodyText.indexOf(name);
      if (nameIdx >= 0) {
        // Look at the text right after the name (within next 500 chars)
        const after = bodyText.substring(nameIdx + name.length, nameIdx + name.length + 500);
        // Find a line that looks like a headline (contains "at" or common title words)
        const lines = after.split("\n").map(l => l.trim()).filter(l => l.length > 3 && l.length < 200);
        for (const line of lines) {
          if (/\bat\b/i.test(line) || /founder|ceo|cto|coo|director|manager|engineer|vp|head of|president|partner/i.test(line)) {
            return line;
          }
        }
      }
    }
    return "";
  }

  function getProfileName() {
    // Strategy 1: Parse from page title — most reliable
    // LinkedIn titles are "Firstname Lastname - Headline | LinkedIn"
    const title = document.title || "";
    const dashIdx = title.indexOf(" - ");
    if (dashIdx > 1) {
      const name = title.substring(0, dashIdx).trim();
      if (name.length >= 2 && name.length < 60) {
        return name;
      }
    }
    // Also try "Firstname Lastname | LinkedIn" format
    const pipeIdx = title.indexOf(" | ");
    if (pipeIdx > 1) {
      const name = title.substring(0, pipeIdx).trim();
      if (name.length >= 2 && name.length < 60 && !name.toLowerCase().includes("linkedin")) {
        return name;
      }
    }

    // Strategy 2: DOM selectors (fallback)
    const selectors = ["h1", "h1.text-heading-xlarge", "h1.inline", "main h1"];
    for (const sel of selectors) {
      const els = document.querySelectorAll(sel);
      for (const el of els) {
        const text = (el.innerText || el.textContent || "").trim();
        if (text && text.length >= 2 && text.length < 80 && !text.toLowerCase().includes("linkedin")) {
          return text;
        }
      }
    }
    return "";
  }

  // Run on initial load
  initForPage();

  // LinkedIn is a SPA — watch for URL changes (client-side navigation)
  const _urlObserver = new MutationObserver(() => {
    if (window.location.href !== _lastUrl) {
      _lastUrl = window.location.href;
      console.log("[StealthRole] URL changed:", window.location.pathname);
      // Small delay to let LinkedIn render the new page
      setTimeout(initForPage, 1500);
    }
  });
  _urlObserver.observe(document.body, { childList: true, subtree: true });

  // Also listen to popstate for back/forward navigation
  window.addEventListener("popstate", () => {
    setTimeout(() => {
      if (window.location.href !== _lastUrl) {
        _lastUrl = window.location.href;
        console.log("[StealthRole] popstate navigation:", window.location.pathname);
        setTimeout(initForPage, 1500);
      }
    }, 100);
  });

  // Patch pushState/replaceState to catch SPA navigations the observer might miss
  const _origPushState = history.pushState;
  const _origReplaceState = history.replaceState;
  history.pushState = function(...args) {
    _origPushState.apply(this, args);
    setTimeout(() => {
      if (window.location.href !== _lastUrl) {
        _lastUrl = window.location.href;
        console.log("[StealthRole] pushState navigation:", window.location.pathname);
        setTimeout(initForPage, 1500);
      }
    }, 100);
  };
  history.replaceState = function(...args) {
    _origReplaceState.apply(this, args);
    setTimeout(() => {
      if (window.location.href !== _lastUrl) {
        _lastUrl = window.location.href;
        setTimeout(initForPage, 1500);
      }
    }, 100);
  };

  function injectOverlayButton(type) {
    // Clean up any existing overlay elements first
    document.getElementById("sr-overlay-btn")?.remove();
    document.getElementById("sr-overlay-btn-secondary")?.remove();

    const labels = {
      connections: "Import Connections",
      profile: "Save Profile",
      messaging: "Import Messages",
      search: "Import Results",
    };
    const btn = document.createElement("button");
    btn.id = "sr-overlay-btn";
    btn.className = "sr-overlay-btn";
    btn.innerHTML = '<span class="sr-icon">&#9889;</span> ' + (labels[type] || "StealthRole");
    btn.addEventListener("click", () => handleOverlayClick(type));
    document.body.appendChild(btn);

    // On the connections page, also inject a SECOND button that runs the full
    // auto-scroll sync directly — no need to round-trip through stealthrole.com
    // Settings. This is the preferred way to import all connections.
    if (type === "connections") {
      const syncBtn = document.createElement("button");
      syncBtn.id = "sr-overlay-btn-secondary";
      syncBtn.className = "sr-overlay-btn";
      syncBtn.style.bottom = "70px"; // stack above the Import button
      syncBtn.style.background = "linear-gradient(135deg, #5B6CFF 0%, #7F8CFF 100%)";
      syncBtn.innerHTML = '<span class="sr-icon">&#128260;</span> Sync ALL (auto-scroll)';
      syncBtn.addEventListener("click", async () => {
        syncBtn.disabled = true;
        syncBtn.innerHTML = '<span class="sr-icon">&#9203;</span> Scanning…';
        showToast("Starting full sync — keep this tab open");
        // Mark a synthetic sync task so finishConnectionsSync still fires on completion
        try {
          chrome.storage.local.set({
            sr_sync_task: { type: "connections", status: "scanning", started_at: Date.now(), count: 0 }
          });
        } catch {}
        await autoScrapeConnections();
        syncBtn.disabled = false;
        syncBtn.innerHTML = '<span class="sr-icon">&#9989;</span> Done — sync again';
      });
      document.body.appendChild(syncBtn);
    }
  }

  function showToast(message) {
    let toast = document.getElementById("sr-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "sr-toast";
      toast.className = "sr-toast";
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 4000);
  }

  function handleOverlayClick(type) {
    if (type === "connections") scrapeConnections();
    else if (type === "profile") { scrapeProfile(); scrapeMutualConnections(); }
    else if (type === "messaging") scrapeMessages();
    else if (type === "search") scrapeConnections();
  }

  // ── Collect currently-visible connection cards ──
  //
  // LinkedIn 2026 connections page structure (reverse-engineered from the
  // DOM diagnostic dump run on a real account):
  //
  //   Card container = first div ancestor of a profile link whose innerText
  //   contains " Connected on ". Card innerText follows this exact pattern:
  //
  //     "Name | Headline piece 1 | Headline piece 2 | ... | Connected on DATE | Me"
  //
  //   where "| Me" is the Message button label. No li, no role="listitem",
  //   no data-view-name — all obfuscated divs with generated class names.
  //
  // Examples actually observed:
  //   "Rupert Searle | Adviser to Entrepreneurs | Private Investor | Venture
  //    Capital | Family Office | Connected on April 9, 2026 | Me"
  //   "Chiara Manzini | Management Consultant @ Accenture | Aerospace &
  //    Defence | Ex-Amazon | Connected on April 12, 2026 | Me"
  //
  // We parse by:
  //   1. Splitting innerText on " | "
  //   2. First part = name
  //   3. Finding the "Connected on" index and everything between [1, that) = headline pieces
  //   4. Joining headline pieces with " · "
  //   5. Extracting "Title @ Company" or "Title at Company" from the first piece
  function collectVisibleConnectionCards(existingSeen) {
    const profileLinks = document.querySelectorAll("a[href*='/in/']");
    const seen = existingSeen || new Set();
    const connections = [];

    profileLinks.forEach((link) => {
      const href = (link.href || "").split("?")[0];
      // Must be a real profile link, not /in/me, /in/search, etc.
      if (!/\/in\/[^/]+\/?$/.test(href)) return;
      const linkedinId = href.split("/in/")[1]?.replace(/\/$/, "") || "";
      if (!linkedinId || seen.has(linkedinId)) return;

      // Walk up from the profile link until we find an ancestor whose
      // innerText contains "Connected on" — that's our card boundary.
      // Cap at 600 chars to avoid grabbing the whole list container.
      let card = null;
      let cardText = "";
      let cur = link.parentElement;
      for (let i = 0; cur && i < 10; i++) {
        const t = (cur.innerText || "").replace(/\s+/g, " ").trim();
        if (t && /\|\s*Connected on /i.test(t) && t.length < 700) {
          card = cur;
          cardText = t;
          break;
        }
        cur = cur.parentElement;
      }
      if (!card || !cardText) return;

      // Parse by pipe separator
      const parts = cardText.split(/\s*\|\s*/).map((s) => s.trim()).filter(Boolean);
      if (parts.length < 2) return;

      const fullName = parts[0];
      if (!fullName || fullName.length < 3 || fullName.length > 80) return;

      // Find the "Connected on" index and trailing button labels
      const connectedIdx = parts.findIndex((p) => /^Connected on /i.test(p));
      const headlineEnd = connectedIdx === -1 ? parts.length : connectedIdx;

      const headlineParts = parts.slice(1, headlineEnd);
      const headline = headlineParts.join(" · ");

      // Extract title + company from the first headline piece: "X at Y" or "X @ Y"
      let currentTitle = headlineParts[0] || "";
      let currentCompany = "";
      const firstPiece = headlineParts[0] || "";
      const atMatch = firstPiece.match(/^(.+?)\s+(?:at|@)\s+(.+)$/i);
      if (atMatch) {
        currentTitle = atMatch[1].trim();
        currentCompany = atMatch[2].trim();
      } else if (headlineParts.length >= 2) {
        // Fallback: if first piece has no "at", and there's a second piece,
        // treat first as title and second as company (common LinkedIn layout:
        // "Product Manager | Acme Inc"). Only apply if the "company" candidate
        // looks company-ish (not a buzzword list).
        const maybeCompany = headlineParts[1];
        if (maybeCompany && maybeCompany.length < 60 && !/\s·\s/.test(maybeCompany)) {
          currentCompany = maybeCompany;
        }
      }

      seen.add(linkedinId);
      connections.push({
        linkedin_id: linkedinId,
        linkedin_url: href,
        full_name: fullName,
        headline,
        current_title: currentTitle,
        current_company: currentCompany,
      });
    });

    return connections;
  }

  // ── Manual scrape (triggered from the ⚡ Import Connections overlay button)
  function scrapeConnections() {
    showToast("Scanning connections...");
    const connections = collectVisibleConnectionCards();
    console.log("[StealthRole] scrapeConnections found " + connections.length + " unique profiles");
    if (connections.length === 0) { showToast("No connections found. Scroll down to load more."); return; }
    showToast("Importing " + connections.length + " connections...");
    srApiCall("/linkedin/ingest/connections", { method: "POST", body: JSON.stringify({ connections }) },
      (res) => { if (res?.ok) showToast("Imported " + (res.data?.created || 0) + " connections"); else showToast(res?.error || "Import failed"); });
  }

  // ── Auto scroll helper: scroll to bottom until height stops growing
  async function scrollToBottom(maxDurationMs = 180000) {
    const startedAt = Date.now();
    return new Promise((resolve) => {
      let lastHeight = 0;
      let unchanged = 0;
      const interval = setInterval(() => {
        window.scrollTo(0, document.body.scrollHeight);
        // Some LinkedIn pages use an inner scroll container — also push that
        const scrollers = document.querySelectorAll("[class*='scaffold-finite-scroll']");
        scrollers.forEach((s) => { s.scrollTop = s.scrollHeight; });

        const h = document.body.scrollHeight;
        if (h === lastHeight) {
          unchanged++;
          if (unchanged >= 3) { clearInterval(interval); resolve(); }
        } else {
          unchanged = 0;
          lastHeight = h;
        }
        if (Date.now() - startedAt > maxDurationMs) {
          clearInterval(interval);
          resolve();
        }
      }, 1500);
    });
  }

  // ── Auto-scrape: full sync flow triggered by background on /mynetwork/invite-connect/connections/
  // Scrolls to the bottom loading all connections, then POSTs them to
  // /linkedin/ingest/connections in chunks of 100, reporting PROGRESS between
  // chunks so the popup and Settings page can show a live count.
  //
  // Robustness notes:
  // - LinkedIn's connections list is VIRTUALIZED: only ~40-60 rows live in
  //   the DOM at any time; older rows are removed as you scroll past. We
  //   therefore must call collectNow() between every scroll increment and
  //   accumulate into a persistent Set so we don't lose early batches.
  // - The outer page height doesn't always grow — sometimes an inner
  //   scroller is the one that scrolls. We push both window and any
  //   scaffold-scroll element. We also click any visible "Show more"
  //   button which LinkedIn sometimes renders instead of infinite scroll.
  // - We loop for up to 6 minutes or until 6 consecutive idle ticks
  //   (no new profiles found) — whichever comes first.
  async function autoScrapeConnections() {
    console.log("[StealthRole] autoScrapeConnections starting");
    const sendProgress = (count, status, error) => {
      try {
        chrome.runtime.sendMessage({ type: "PROGRESS", feature: "connections", count, status, error });
      } catch {}
    };
    sendProgress(0, "scanning");

    const seen = new Set();
    const allConnections = [];
    const collectNow = () => {
      const newOnes = collectVisibleConnectionCards(seen);
      for (const c of newOnes) allConnections.push(c);
      return newOnes.length;
    };

    const clickShowMore = () => {
      // Look for any visible "Show more" button in the connections container.
      // LinkedIn rotates between infinite scroll and a Show-more button.
      const buttons = document.querySelectorAll("button, a[role='button']");
      for (const b of buttons) {
        if (!b.offsetParent) continue;
        const t = (b.textContent || "").trim().toLowerCase();
        if (/^show (more|\d+ more)/.test(t) || t === "load more") {
          try { b.click(); return true; } catch {}
        }
      }
      return false;
    };

    try {
      collectNow();
      sendProgress(allConnections.length, "scanning");

      // Log the first 3 parsed records so we can verify the extraction is
      // pulling real names + titles + companies (not just empty strings).
      if (allConnections.length > 0) {
        console.log("[StealthRole] first 3 parsed records:");
        for (const c of allConnections.slice(0, 3)) {
          console.log(`  ${c.full_name} | title="${c.current_title}" | company="${c.current_company}"`);
        }
      }

      // Find every element on the page that is actually a scroll container.
      // LinkedIn has moved containers around across redesigns; instead of
      // pinning a class name, detect ALL scrollable elements at runtime and
      // push every one of them. This catches the real virtual list wherever
      // LinkedIn puts it this week.
      const findScrollers = () => {
        const result = [document.scrollingElement || document.documentElement, document.body];
        const all = document.querySelectorAll("div, main, section, [role='main']");
        for (const el of all) {
          if (!el || !el.clientHeight) continue;
          const style = getComputedStyle(el);
          if ((style.overflowY === "auto" || style.overflowY === "scroll") && el.scrollHeight > el.clientHeight + 50) {
            result.push(el);
          }
        }
        return result;
      };

      const startedAt = Date.now();
      const MAX_MS = 600000; // 10 minute hard cap
      const IDLE_TICKS_LIMIT = 20; // ~60s of idle before giving up
      let idleTicks = 0;
      let tickNo = 0;

      while (Date.now() - startedAt < MAX_MS && idleTicks < IDLE_TICKS_LIMIT) {
        tickNo++;
        const scrollers = findScrollers();

        // Telemetry snapshot of the primary scroller (largest scrollHeight)
        let primary = scrollers[0] || document.documentElement;
        for (const s of scrollers) {
          if ((s.scrollHeight || 0) > (primary.scrollHeight || 0)) primary = s;
        }
        const beforeTop = primary.scrollTop;
        const beforeHeight = primary.scrollHeight;

        for (const s of scrollers) {
          try { s.scrollTop = s.scrollHeight; } catch {}
          try { s.dispatchEvent(new Event("scroll", { bubbles: true })); } catch {}
        }
        try { window.scrollTo(0, document.body.scrollHeight); } catch {}
        try { window.dispatchEvent(new Event("scroll", { bubbles: true })); } catch {}

        // Every 4 idle ticks try tapping the keyboard End key — LinkedIn
        // sometimes only loads more on keyboard-driven scroll events.
        if (idleTicks > 0 && idleTicks % 4 === 0) {
          try {
            window.dispatchEvent(new KeyboardEvent("keydown", { key: "End", code: "End", keyCode: 35, bubbles: true }));
            window.dispatchEvent(new KeyboardEvent("keyup", { key: "End", code: "End", keyCode: 35, bubbles: true }));
          } catch {}
        }

        clickShowMore();

        await new Promise((r) => setTimeout(r, 2500));

        const newCount = collectNow();
        sendProgress(allConnections.length, "scanning");

        const afterTop = primary.scrollTop;
        const afterHeight = primary.scrollHeight;
        const profileLinkCount = document.querySelectorAll("a[href*='/in/']").length;

        console.log(
          `[StealthRole] tick ${tickNo}: +${newCount} new (total ${allConnections.length}), ` +
          `scrollTop ${beforeTop}→${afterTop}, scrollHeight ${beforeHeight}→${afterHeight}, ` +
          `links=${profileLinkCount}, idle=${idleTicks}`
        );

        if (newCount === 0) idleTicks++;
        else idleTicks = 0;
      }
      console.log(`[StealthRole] scroll loop finished after ${tickNo} ticks, ${allConnections.length} total`);

      console.log("[StealthRole] autoScrapeConnections collected " + allConnections.length);
      if (allConnections.length === 0) {
        sendProgress(0, "error", "No connections found — are you on the connections page and logged in?");
        return;
      }

      // POST in chunks of 100
      const CHUNK = 100;
      let posted = 0;
      for (let i = 0; i < allConnections.length; i += CHUNK) {
        const batch = allConnections.slice(i, i + CHUNK);
        await new Promise((resolve) => {
          srApiCall(
            "/linkedin/ingest/connections",
            { method: "POST", body: JSON.stringify({ connections: batch }) },
            (res) => {
              if (!res?.ok) console.warn("[StealthRole] batch import error:", res?.error);
              resolve();
            }
          );
        });
        posted += batch.length;
        sendProgress(posted, "scanning");
      }

      sendProgress(allConnections.length, "done");
    } catch (e) {
      console.error("[StealthRole] autoScrapeConnections error:", e);
      sendProgress(allConnections.length, "error", String(e?.message || e));
    }
  }

  // ── Async version of scrapeProfile (returns promise so mutual scrape waits for save)
  function scrapeProfileAsync() {
    return new Promise((resolve) => {
      const url = window.location.href.split("?")[0];
      const linkedinId = url.split("/in/")[1]?.replace(/\/$/, "") || "";
      const fullName = getProfileName();
      const headline = getProfileHeadline();
      const degree = getConnectionDegree();
      const currentCompany = getCompanyFromPage();
      let currentTitle = headline;
      const atMatch = headline.match(/^(.+?)\s+(?:at|@)\s+(.+)/i);
      if (atMatch) { currentTitle = atMatch[1].trim(); }

      console.log("[StealthRole] scrapeProfileAsync: name='" + fullName + "' title='" + currentTitle + "' company='" + currentCompany + "' degree=" + degree);
      if (!fullName) { resolve(); return; }

      // ALWAYS save the profile as a contact, regardless of degree.
      // Strength reflects how directly we know them.
      const strength = degree === 1 ? "strong" : degree === 2 ? "weak" : degree === 3 ? "discovered" : "visited";
      const payload = {
        linkedin_id: linkedinId,
        linkedin_url: url,
        full_name: fullName,
        headline,
        current_title: currentTitle,
        current_company: currentCompany,
        relationship_strength: strength,
        connection_degree: degree || null,
      };
      srApiCall("/linkedin/ingest/connections", { method: "POST", body: JSON.stringify({ connections: [payload] }) },
        (res) => {
          console.log("[StealthRole] Profile save response:", JSON.stringify(res));
          if (res?.ok) {
            const created = res.data?.created || 0;
            const msg = created > 0 ? "Saved: " + fullName + (currentCompany ? " at " + currentCompany : "") : "Updated: " + fullName;
            showToast(msg);
          } else {
            showToast("Save failed: " + (res?.error || "unknown error"));
          }
          resolve();
        });
    });
  }

  // ── Scrape single profile
  function scrapeProfile() {
    const url = window.location.href.split("?")[0];
    const linkedinId = url.split("/in/")[1]?.replace(/\/$/, "") || "";
    const fullName = getProfileName();
    const headline = getProfileHeadline();
    const degree = getConnectionDegree();
    const currentCompany = getCompanyFromPage();
    let currentTitle = headline;
    const atMatch = headline.match(/^(.+?)\s+(?:at|@)\s+(.+)/i);
    if (atMatch) { currentTitle = atMatch[1].trim(); }

    console.log("[StealthRole] scrapeProfile: name='" + fullName + "' title='" + currentTitle + "' company='" + currentCompany + "' degree=" + degree + " id=" + linkedinId);
    if (!fullName) { console.log("[StealthRole] scrapeProfile: ABORT - no name found"); return; }

    // ALWAYS save the profile, regardless of degree.
    const strength = degree === 1 ? "strong" : degree === 2 ? "weak" : degree === 3 ? "discovered" : "visited";
    showToast("Saving " + fullName + "...");
    const payload = {
      linkedin_id: linkedinId,
      linkedin_url: url,
      full_name: fullName,
      headline,
      current_title: currentTitle,
      current_company: currentCompany,
      relationship_strength: strength,
      connection_degree: degree || null,
    };
    srApiCall("/linkedin/ingest/connections", { method: "POST", body: JSON.stringify({ connections: [payload] }) },
      (res) => {
        console.log("[StealthRole] Profile save response:", JSON.stringify(res));
        if (res?.ok) showToast("Saved: " + fullName + (currentCompany ? " at " + currentCompany : ""));
        else showToast("Save failed: " + (res?.error || "unknown error"));
      });
  }

  // ── MUTUAL CONNECTIONS — the killer feature
  // (_mutualScrapeInProgress declared at the top of the IIFE)

  function scrapeMutualConnections() {
    if (_mutualScrapeInProgress) {
      console.log("[StealthRole] Mutual scrape in progress, will retry in 6s...");
      setTimeout(() => scrapeMutualConnections(), 6000);
      return;
    }
    const url = window.location.href.split("?")[0];
    const linkedinId = url.split("/in/")[1]?.replace(/\/$/, "") || "";
    if (!linkedinId) return;

    const targetName = getProfileName();
    const targetHeadline = getProfileHeadline();
    const targetCompany = getCompanyFromPage();
    let targetTitle = targetHeadline;
    const atMatch = targetHeadline.match(/^(.+?)\s+(?:at|@)\s+(.+)/i);
    if (atMatch) { targetTitle = atMatch[1].trim(); }

    console.log("[StealthRole] scrapeMutualConnections: name='" + targetName + "' company='" + targetCompany + "' id=" + linkedinId);
    if (!targetName) { console.log("[StealthRole] scrapeMutualConnections: ABORT - no name"); return; }

    const targetPerson = { linkedin_id: linkedinId, linkedin_url: url, full_name: targetName, current_title: targetTitle, current_company: targetCompany, headline: targetHeadline };

    // Step 1: Find the mutual connections link and click it
    // This navigates to a search results page showing ALL mutual connections
    const mutualLink = findMutualConnectionsLink();
    if (mutualLink) {
      _mutualScrapeInProgress = true;
      // Save target person info so the search results page can use it
      chrome.storage.local.set({ sr_mutual_target: targetPerson }, () => {
        console.log("[StealthRole] Saved target person, clicking mutual connections link...");
        console.log("[StealthRole] Mutual link href:", mutualLink.href || mutualLink.getAttribute("href") || "no href");

        // Check if it's a link with href (navigates to search page) or a button (opens modal)
        const href = mutualLink.href || mutualLink.getAttribute("href") || "";
        if (href && href.includes("/search/")) {
          // It will navigate — the search page handler will pick it up
          mutualLink.click();
          setTimeout(() => { _mutualScrapeInProgress = false; }, 5000);
        } else {
          // Might open a modal — try clicking and scraping
          mutualLink.click();
          setTimeout(() => scrapeMutualFromPage(targetPerson), 2000);
          setTimeout(() => scrapeMutualFromPage(targetPerson), 4000);
          setTimeout(() => { _mutualScrapeInProgress = false; }, 6000);
        }
      });
      return;
    }

    console.log("[StealthRole] No mutual link found, using fallback text scrape");
    // Step 2: Fallback — scrape the 2-3 visible names from page text
    const mutualNames = scrapeVisibleMutuals();
    let mutualCount = mutualNames.length;
    const bodyText = document.body.innerText || "";
    const countMatch = bodyText.match(/(\d+)\s+(?:other\s+)?mutual\s+connect/);
    if (countMatch) mutualCount = Math.max(mutualCount, parseInt(countMatch[1]) + mutualNames.length);

    console.log("[StealthRole] Mutual scan (text fallback):", { targetName, targetCompany, mutualCount, names: mutualNames.map(m => m.name) });
    if (mutualNames.length === 0 && mutualCount === 0) return;
    sendMutualData(targetPerson, mutualNames, mutualCount);
  }

  function findMutualConnectionsLink() {
    // Strategy 1: find any <a> with href containing mutual/facetConnectionOf/connectionOf
    const hrefLinks = document.querySelectorAll("a[href*='facetConnectionOf'], a[href*='connectionOf'], a[href*='mutualConnections'], a[href*='facetNetwork']");
    for (const el of hrefLinks) {
      // Verify it's visible (LinkedIn sometimes renders hidden duplicates)
      if (el.offsetParent === null) continue;
      console.log("[StealthRole] Found href link:", el.href?.substring(0, 100));
      return el;
    }

    // Strategy 2: find ANY clickable element whose text mentions "mutual connect"
    const allElements = document.querySelectorAll("a, button, span, div");
    for (const el of allElements) {
      if (el.offsetParent === null) continue; // skip hidden
      const text = (el.innerText || el.textContent || "").toLowerCase().trim();
      if ((text.includes("mutual connect") || text.includes("connection in common")) && text.length < 200) {
        const style = window.getComputedStyle(el);
        const isClickable = el.tagName === "A" || el.tagName === "BUTTON" || style.cursor === "pointer";
        const clickableParent = el.closest("a, button, [role='link'], [role='button']");
        if (isClickable || clickableParent) {
          const target = clickableParent || el;
          console.log("[StealthRole] Found mutual link via text:", target.tagName, text.substring(0, 60));
          return target;
        }
      }
    }

    // Strategy 3: Look for the "people in common" section and find its clickable parent
    const peopleInCommon = document.querySelectorAll(
      "[data-view-name='profile-shared-connections'], " +
      "section[aria-label*='common' i], " +
      "section[aria-label*='mutual' i]"
    );
    for (const section of peopleInCommon) {
      const link = section.querySelector("a[href*='/search/']") || section.closest("a[href*='/search/']");
      if (link) {
        console.log("[StealthRole] Found mutual link via section");
        return link;
      }
    }

    console.log("[StealthRole] No mutual connections link found on page");
    return null;
  }

  // Scrape mutual connections from search results page
  // Called when the user navigates to the mutual connections search page
  function scrapeMutualSearchResults() {
    chrome.storage.local.get("sr_mutual_target", (data) => {
      const targetPerson = data.sr_mutual_target;
      if (!targetPerson) return;

      const url = window.location.href;
      if (!url.includes("/search/results/people") && !url.includes("facetConnectionOf") && !url.includes("connectionOf")) return;

      console.log("[StealthRole] On mutual connections search page for:", targetPerson.full_name);
      showToast("Scanning all mutual connections with " + targetPerson.full_name + "...");

      // Scrape all pages — scroll to load, then click Next for pagination
      const allMutuals = [];
      const seenNames = new Set();
      let currentPage = 1;
      const maxPages = 10;

      function scrapePage() {
        console.log("[StealthRole] Scraping page " + currentPage + "...");

        // Scroll down to load all results on this page
        let scrollCount = 0;
        function scrollDown() {
          window.scrollTo(0, document.body.scrollHeight);
          scrollCount++;
          setTimeout(() => {
            if (scrollCount < 3) {
              scrollDown();
            } else {
              // Done scrolling this page — scrape results
              const pageResults = scrapeSearchResults();
              let newCount = 0;
              for (const m of pageResults) {
                if (!seenNames.has(m.name)) {
                  seenNames.add(m.name);
                  allMutuals.push(m);
                  newCount++;
                }
              }
              console.log("[StealthRole] Page " + currentPage + ": " + newCount + " new, " + allMutuals.length + " total");

              // Try to find and click the Next button
              const nextBtn = findNextPageButton();
              if (nextBtn && currentPage < maxPages && newCount > 0) {
                currentPage++;
                nextBtn.click();
                // Wait for next page to load
                setTimeout(scrapePage, 3000);
              } else {
                // Done — send all results
                console.log("[StealthRole] All pages done. Total: " + allMutuals.length + " mutual connections");
                if (allMutuals.length > 0) {
                  sendMutualData(targetPerson, allMutuals, allMutuals.length);
                  showToast("Mapped " + allMutuals.length + " paths to " + targetPerson.full_name + " — go back to StealthRole, it will refresh automatically");
                }
                chrome.storage.local.remove("sr_mutual_target");
                window.scrollTo(0, 0);
              }
            }
          }, 1000);
        }
        scrollDown();
      }

      // Start after initial page load
      setTimeout(scrapePage, 2000);
    });
  }

  function findNextPageButton() {
    // LinkedIn pagination: look for "Next" button or arrow
    const buttons = document.querySelectorAll("button, a");
    for (const btn of buttons) {
      const text = (btn.innerText || btn.textContent || "").trim().toLowerCase();
      const ariaLabel = (btn.getAttribute("aria-label") || "").toLowerCase();
      if (text === "next" || ariaLabel.includes("next")) {
        // Make sure it's not disabled
        if (!btn.disabled && !btn.classList.contains("disabled") && btn.getAttribute("aria-disabled") !== "true") {
          console.log("[StealthRole] Found Next button:", btn.tagName, text || ariaLabel);
          return btn;
        }
      }
    }
    // Also check for pagination arrow (→) button
    const paginationBtns = document.querySelectorAll(".artdeco-pagination__button--next, [aria-label='Next']");
    for (const btn of paginationBtns) {
      if (!btn.disabled && btn.getAttribute("aria-disabled") !== "true") return btn;
    }
    console.log("[StealthRole] No Next button found — last page");
    return null;
  }

  function scrapeSearchResults() {
    const results = [];
    const seen = new Set();

    // LinkedIn search results: each person is in a list item
    const cards = document.querySelectorAll(
      ".reusable-search__result-container, " +
      ".entity-result, " +
      "li.reusable-search__result-container, " +
      "[data-chameleon-result-urn], " +
      ".search-results-container li"
    );

    console.log("[StealthRole] Search result cards found:", cards.length);

    cards.forEach(card => {
      // Try multiple selectors for the name
      const nameEl = card.querySelector(
        "span[aria-hidden='true'], " +
        ".entity-result__title-text a span, " +
        ".app-aware-link span[dir='ltr'] span:first-child"
      );
      const linkEl = card.querySelector("a[href*='/in/']");
      const titleEl = card.querySelector(
        ".entity-result__primary-subtitle, " +
        ".entity-result__summary, " +
        ".linked-area .t-14"
      );

      let name = nameEl?.innerText?.trim() || nameEl?.textContent?.trim() || "";
      // Clean up name — remove "View X's profile" etc
      name = name.split("\n")[0].trim();
      if (!name || name.length < 2 || name.length > 60 || seen.has(name)) return;
      if (name.toLowerCase().includes("linkedin") || name.toLowerCase().includes("view ")) return;
      seen.add(name);

      const linkedinUrl = linkEl?.href?.split("?")[0] || "";
      const lid = linkedinUrl.split("/in/")[1]?.replace(/\/$/, "") || "";
      const headline = titleEl?.innerText?.trim() || titleEl?.textContent?.trim() || "";

      results.push({
        name,
        linkedin_id: lid || name.toLowerCase().replace(/[^a-z0-9]/g, "-"),
        linkedin_url: linkedinUrl,
        headline,
      });
    });

    // Fallback: if no structured results, try getting names from the page
    if (results.length === 0) {
      // Try to get names from any link to /in/ profiles
      document.querySelectorAll("a[href*='/in/']").forEach(link => {
        const text = (link.innerText || link.textContent || "").trim().split("\n")[0].trim();
        if (text && text.length >= 2 && text.length < 60 && !seen.has(text) && !text.toLowerCase().includes("linkedin")) {
          seen.add(text);
          const href = link.href?.split("?")[0] || "";
          const lid = href.split("/in/")[1]?.replace(/\/$/, "") || "";
          results.push({ name: text, linkedin_id: lid, linkedin_url: href });
        }
      });
    }

    return results;
  }

  function scrapeMutualFromPage(targetPerson) {
    // Try to scrape from modal/overlay that might have opened
    const results = scrapeSearchResults();
    console.log("[StealthRole] Mutual scan (modal/page):", { target: targetPerson.full_name, found: results.length });
    if (results.length > 0) {
      sendMutualData(targetPerson, results, results.length);
    }
  }

  function scrapeVisibleMutuals() {
    const mutualNames = [];
    const seen = new Set();
    const bodyText = document.body.innerText || "";

    // Pattern: "Name1, Name2 and N other mutual connections"
    const pattern1 = bodyText.match(/([A-Z][a-zA-Zàèéìòùü'\- ]+(?:,\s*[A-Z][a-zA-Zàèéìòùü'\- ]+)*)\s+and\s+(\d+)\s+other\s+mutual\s+connect/);
    if (pattern1) {
      pattern1[1].split(",").map(n => n.trim()).filter(n => n.length > 1).forEach(name => {
        if (!seen.has(name)) { seen.add(name); mutualNames.push({ name, linkedin_id: name.toLowerCase().replace(/[^a-z0-9]/g, "-"), linkedin_url: "" }); }
      });
    }

    // Pattern: "Name1 and Name2 are mutual connections"
    const pattern3 = bodyText.match(/([A-Z][a-zA-Zàèéìòùü'\- ]+)\s+and\s+([A-Z][a-zA-Zàèéìòùü'\- ]+)\s+are\s+mutual/);
    if (pattern3 && mutualNames.length === 0) {
      [pattern3[1].trim(), pattern3[2].trim()].forEach(name => {
        if (!seen.has(name)) { seen.add(name); mutualNames.push({ name, linkedin_id: "", linkedin_url: "" }); }
      });
    }

    // Image alt texts near mutual mentions
    document.querySelectorAll("img").forEach(img => {
      const alt = (img.getAttribute("alt") || "").trim();
      const parent = img.closest("a, div, span");
      const parentText = parent?.textContent || "";
      if (alt && alt.length > 2 && alt.length < 50 && parentText.includes("mutual") && !seen.has(alt)) {
        seen.add(alt);
        const linkEl = parent?.closest("a[href*='/in/']") || parent?.querySelector("a[href*='/in/']");
        const linkedinUrl = linkEl?.href?.split("?")[0] || "";
        const lid = linkedinUrl.split("/in/")[1]?.replace(/\/$/, "") || "";
        mutualNames.push({ name: alt, linkedin_id: lid || "", linkedin_url: linkedinUrl });
      }
    });

    return mutualNames;
  }

  function sendMutualData(targetPerson, mutualNames, mutualCount) {
    const payload = {
      target_person: targetPerson,
      mutual_connections: mutualNames,
      mutual_count: mutualCount || mutualNames.length,
    };

    console.log("[StealthRole] Sending " + mutualNames.length + " mutuals for " + targetPerson.full_name + " at " + targetPerson.current_company);
    srApiCall("/linkedin/ingest/mutual-connections", { method: "POST", body: JSON.stringify(payload) },
      (res) => {
        console.log("[StealthRole] Mutual save response:", JSON.stringify(res));
        if (res?.ok && res.data?.stored > 0) {
          showToast("Mapped " + res.data.stored + " paths to " + targetPerson.full_name + " — go back to StealthRole");
        } else if (res?.ok && res.data?.stored === 0 && mutualNames.length > 0) {
          showToast("Connections already mapped for " + targetPerson.full_name);
        } else if (!res?.ok) {
          showToast("Failed to save: " + (res?.error || "unknown"));
          console.error("[StealthRole] Mutual save FAILED:", res);
        }
      });
  }

  // ── Scrape messages
  function scrapeMessages() {
    showToast("Scanning messages...");
    const msgEls = document.querySelectorAll(".msg-s-event-listitem, .msg-s-message-list__event");
    const messages = [];
    msgEls.forEach((el) => {
      const senderEl = el.querySelector(".msg-s-event-listitem__link span.t-bold, .msg-s-message-group__name");
      const textEl = el.querySelector(".msg-s-event-listitem__body, .msg-s-event__content");
      const timeEl = el.querySelector("time");
      if (!senderEl || !textEl) return;
      messages.push({ sender_name: senderEl.textContent.trim(), message_text: textEl.textContent.trim().substring(0, 2000), sent_at: timeEl?.getAttribute("datetime") || new Date().toISOString(), direction: "inbound" });
    });
    if (messages.length === 0) { showToast("No messages found. Open a conversation first."); return; }
    srApiCall("/linkedin/ingest/conversations", { method: "POST", body: JSON.stringify({ messages }) },
      (res) => { if (res?.ok) showToast("Imported " + (res.data?.messages_imported || 0) + " messages"); else showToast(res?.error || "Import failed"); });
  }

  // ── Listen for messages from popup
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === "IMPORT_CONNECTIONS") {
      if (getPageType() === "profile") { scrapeProfile(); scrapeMutualConnections(); }
      else scrapeConnections();
      setTimeout(() => sendResponse({ ok: true }), 2000);
      return true;
    }
    if (msg.type === "SCRAPE_MUTUALS") {
      scrapeMutualConnections();
      setTimeout(() => sendResponse({ ok: true }), 2000);
      return true;
    }
  });
})();
