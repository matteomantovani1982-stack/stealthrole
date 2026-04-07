// StealthRole LinkedIn content script
(() => {
  const SR_API = "https://api.stealthrole.com/api/v1";

  // Resilient API call — tries background script first, falls back to direct fetch
  async function srApiCall(path, options, callback) {
    // Try background script first
    try {
      chrome.runtime.sendMessage(
        { type: "API_REQUEST", path, options },
        (res) => {
          if (chrome.runtime.lastError || !res) {
            // Background script is dead — fall back to direct API call
            console.log("[StealthRole] Background dead, using direct API. Error:", chrome.runtime.lastError?.message);
            directApiCall(path, options).then(callback);
          } else {
            callback(res);
          }
        }
      );
    } catch (e) {
      console.log("[StealthRole] sendMessage failed, using direct API:", e.message);
      directApiCall(path, options).then(callback);
    }
  }

  async function directApiCall(path, options = {}) {
    try {
      // Get token from chrome.storage
      const data = await chrome.storage.local.get("sr_token");
      const token = data.sr_token;
      if (!token) {
        console.log("[StealthRole] No token — please log in via the extension popup");
        return { ok: false, error: "Not logged in" };
      }
      const res = await fetch(`${SR_API}${path}`, {
        method: options.method || "GET",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: options.body || undefined,
      });
      if (res.ok) {
        const json = await res.json();
        return { ok: true, data: json };
      }
      return { ok: false, error: `API ${res.status}` };
    } catch (e) {
      console.error("[StealthRole] Direct API call failed:", e);
      return { ok: false, error: e.message };
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

  function initForPage() {
    const pageType = getPageType();
    console.log("[StealthRole] Page init:", pageType, window.location.pathname);
    if (["connections", "profile", "messaging", "search"].includes(pageType)) {
      injectOverlayButton(pageType);
    }

    // Auto-save profile + scrape mutual connections on profile pages
    if (pageType === "profile") {
      waitForProfileName().then(() => {
        scrapeProfile();
        scrapeMutualConnections();
        // Retry mutuals after more content loads
        setTimeout(() => scrapeMutualConnections(), 3000);
      });
    }
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
    // Strategy 1: parse from headline "Title at Company"
    const headline = getProfileHeadline();
    if (headline) {
      const atMatch = headline.match(/\bat\s+(.+)/i);
      if (atMatch) return atMatch[1].trim();
    }
    // Strategy 2: scan page text for "at Company" near the name
    const name = getProfileName();
    const bodyText = document.body.innerText || "";
    if (name) {
      const nameIdx = bodyText.indexOf(name);
      if (nameIdx >= 0) {
        const after = bodyText.substring(nameIdx, nameIdx + 300);
        const atMatch = after.match(/(?:at|@)\s+([A-Z][A-Za-z0-9\s&.'-]{1,40})/);
        if (atMatch) return atMatch[1].trim();
      }
    }
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

  function injectOverlayButton(type) {
    const existing = document.getElementById("sr-overlay-btn");
    if (existing) existing.remove();
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

  // ── Scrape connections list
  function scrapeConnections() {
    showToast("Scanning connections...");
    const cards = document.querySelectorAll(".mn-connection-card, .artdeco-list__item, li.reusable-search__result-container");
    const connections = [];
    cards.forEach((card) => {
      const nameEl = card.querySelector(".mn-connection-card__name, .entity-result__title-text a span[aria-hidden='true'], .app-aware-link span[aria-hidden='true']");
      const titleEl = card.querySelector(".mn-connection-card__occupation, .entity-result__primary-subtitle, .artdeco-entity-lockup__subtitle");
      const linkEl = card.querySelector("a[href*='/in/']");
      if (!nameEl) return;
      const fullName = nameEl.textContent.trim();
      const headline = titleEl?.textContent?.trim() || "";
      const linkedinUrl = linkEl?.href?.split("?")[0] || "";
      const linkedinId = linkedinUrl.split("/in/")[1]?.replace(/\/$/, "") || "";
      let currentTitle = headline, currentCompany = "";
      const atMatch = headline.match(/^(.+?)\s+(?:at|@)\s+(.+)/i);
      if (atMatch) { currentTitle = atMatch[1].trim(); currentCompany = atMatch[2].trim(); }
      connections.push({ linkedin_id: linkedinId, linkedin_url: linkedinUrl, full_name: fullName, headline, current_title: currentTitle, current_company: currentCompany });
    });
    if (connections.length === 0) { showToast("No connections found. Scroll down to load more."); return; }
    srApiCall("/linkedin/ingest/connections", { method: "POST", body: JSON.stringify({ connections }) },
      (res) => { if (res?.ok) showToast("Imported " + (res.data?.created || 0) + " connections"); else showToast(res?.error || "Import failed"); });
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

    // Only save 1st-degree connections as actual connections
    // 2nd/3rd degree profiles are saved via mutual connections, not as direct contacts
    if (degree === 1 || degree === 0) {
      const strength = degree === 1 ? "medium" : "visited";
      showToast("Saving " + fullName + "...");
      srApiCall("/linkedin/ingest/connections", { method: "POST", body: JSON.stringify({ connections: [{ linkedin_id: linkedinId, linkedin_url: url, full_name: fullName, headline, current_title: currentTitle, current_company: currentCompany, relationship_strength: strength }] }) },
        (res) => {
          console.log("[StealthRole] Profile save response:", JSON.stringify(res));
          if (res?.ok) showToast("Saved: " + fullName + (currentCompany ? " at " + currentCompany : ""));
          else showToast("Save failed: " + (res?.error || "unknown error"));
        });
    } else {
      console.log("[StealthRole] " + fullName + " is " + degree + "nd/rd degree — skipping connection save, mutual scrape will handle it");
    }
  }

  // ── MUTUAL CONNECTIONS — the killer feature
  let _mutualScrapeInProgress = false;

  function scrapeMutualConnections() {
    if (_mutualScrapeInProgress) return;
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

    // Step 1: Try to click the mutual connections link to open the full list
    const mutualLink = findMutualConnectionsLink();
    if (mutualLink) {
      _mutualScrapeInProgress = true;
      console.log("[StealthRole] Found mutual link, clicking to expand full list...");
      mutualLink.click();
      // Wait for the modal/overlay to render, then scrape from it
      setTimeout(() => scrapeMutualFromModal(targetPerson), 1500);
      setTimeout(() => scrapeMutualFromModal(targetPerson), 3000);
      setTimeout(() => { _mutualScrapeInProgress = false; }, 4000);
      return;
    }

    // Step 2: Fallback — scrape whatever is visible on the page
    const mutualNames = scrapeVisibleMutuals();
    let mutualCount = mutualNames.length;

    // Also check for a count in page text
    const bodyText = document.body.innerText || "";
    const countMatch = bodyText.match(/(\d+)\s+mutual\s+connect/);
    if (countMatch) mutualCount = Math.max(mutualCount, parseInt(countMatch[1]));

    console.log("[StealthRole] Mutual scan (fallback):", { targetName, targetCompany, mutualCount, mutualNames: mutualNames.map(m => m.name) });

    if (mutualNames.length === 0 && mutualCount === 0) return;
    sendMutualData(targetPerson, mutualNames, mutualCount);
  }

  function findMutualConnectionsLink() {
    // LinkedIn shows "N mutual connections" as a clickable link on profiles
    const candidates = document.querySelectorAll(
      "a[href*='facetConnectionOf'], " +
      "a[href*='mutual'], " +
      "a.link-without-visited-state, " +
      "button.link-without-visited-state, " +
      "span.t-bold + span.t-normal"
    );
    for (const el of candidates) {
      const text = (el.textContent || "").toLowerCase();
      if (text.includes("mutual connect")) return el;
    }
    // Also check for the mutual connections section link
    const allLinks = document.querySelectorAll("a, button");
    for (const el of allLinks) {
      const text = (el.textContent || "").toLowerCase().trim();
      if (/\d+\s+mutual\s+connect/.test(text)) return el;
    }
    return null;
  }

  function scrapeMutualFromModal(targetPerson) {
    // LinkedIn opens either a modal, a search results page, or an overlay
    const mutualNames = [];
    const seen = new Set();

    // Check for modal/overlay with connection cards
    const modalCards = document.querySelectorAll(
      ".artdeco-modal .reusable-search__result-container, " +
      ".artdeco-modal .entity-result, " +
      ".artdeco-modal .mn-connection-card, " +
      "[role='dialog'] .entity-result, " +
      ".scaffold-finite-scroll .entity-result, " +
      ".search-results-container .entity-result"
    );

    modalCards.forEach(card => {
      const nameEl = card.querySelector(
        ".entity-result__title-text a span[aria-hidden='true'], " +
        ".mn-connection-card__name, " +
        ".app-aware-link span[aria-hidden='true'], " +
        "span.t-bold span[aria-hidden='true']"
      );
      const linkEl = card.querySelector("a[href*='/in/']");
      const titleEl = card.querySelector(
        ".entity-result__primary-subtitle, " +
        ".mn-connection-card__occupation, " +
        ".artdeco-entity-lockup__subtitle"
      );

      const name = nameEl?.textContent?.trim();
      if (!name || name.length < 2 || seen.has(name)) return;
      seen.add(name);

      const linkedinUrl = linkEl?.href?.split("?")[0] || "";
      const lid = linkedinUrl.split("/in/")[1]?.replace(/\/$/, "") || "";
      const headline = titleEl?.textContent?.trim() || "";

      mutualNames.push({
        name,
        linkedin_id: lid || name.toLowerCase().replace(/[^a-z0-9]/g, "-"),
        linkedin_url: linkedinUrl,
        headline,
      });
    });

    // If modal didn't yield results, also try the inline list
    if (mutualNames.length === 0) {
      scrapeVisibleMutuals().forEach(m => {
        if (!seen.has(m.name)) { seen.add(m.name); mutualNames.push(m); }
      });
    }

    console.log("[StealthRole] Mutual scan (modal):", { target: targetPerson.full_name, found: mutualNames.length, names: mutualNames.map(m => m.name) });

    if (mutualNames.length > 0) {
      sendMutualData(targetPerson, mutualNames, mutualNames.length);
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

    srApiCall("/linkedin/ingest/mutual-connections", { method: "POST", body: JSON.stringify(payload) },
      (res) => {
        if (res?.ok && res.data?.stored > 0) {
          showToast("Mapped " + res.data.stored + " connections to " + targetPerson.full_name);
        } else if (res?.ok && res.data?.stored === 0 && mutualNames.length > 0) {
          showToast("Connections already mapped for " + targetPerson.full_name);
        } else if (mutualCount > 0 && mutualNames.length === 0) {
          showToast(mutualCount + " mutual connections — click the link to map them");
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
