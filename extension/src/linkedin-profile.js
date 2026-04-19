// StealthRole LinkedIn — Profile + Mutual Connections (v2.0.0)
// Merged scrapeProfile/scrapeProfileAsync into one promise-based function.
// Mutual connections flow: save target profile → navigate to mutual search
// → scrape results → POST to backend.

(() => {
  "use strict";
  const SR = window.SR;

  // ── DOM helpers for profile pages ──

  SR.waitForProfileName = function (maxWait = 15000) {
    return new Promise((resolve) => {
      const deadline = Date.now() + maxWait;
      function check() {
        const name = getProfileName();
        if (name) { resolve(name); return; }
        if (Date.now() > deadline) { resolve(null); return; }
        setTimeout(check, 500);
      }
      check();
    });
  };

  function getProfileName() {
    // Primary: h1 on profile page
    const h1 = document.querySelector("h1");
    if (h1) {
      const name = h1.textContent.trim();
      if (name.length > 1 && name.length < 80) return name;
    }
    // Fallback: main content name
    for (const el of document.querySelectorAll(".text-heading-xlarge, .pv-text-details__left-panel h1, [data-generated-suggestion-target]")) {
      const text = (el.innerText || el.textContent || "").trim();
      if (text.length > 1 && text.length < 80) return text;
    }
    return "";
  }

  function getProfileHeadline() {
    // .text-body-medium is LinkedIn's headline class
    const el = document.querySelector(".text-body-medium, .pv-text-details__left-panel .text-body-medium");
    if (el) {
      const text = el.textContent.trim().replace(/\s+/g, " ");
      if (text.length > 1) return text;
    }
    // Fallback: meta description
    const meta = document.querySelector('meta[name="description"]');
    if (meta) return (meta.getAttribute("content") || "").trim().slice(0, 200);
    return "";
  }

  function getConnectionDegree() {
    // LinkedIn shows "1st", "2nd", "3rd" in a badge
    for (const el of document.querySelectorAll(".dist-value, .distance-badge, span[class*='degree']")) {
      const t = (el.textContent || "").trim();
      const m = t.match(/(\d)/);
      if (m) return parseInt(m[1], 10);
    }
    const bodyText = document.body.innerText || "";
    if (/\b1st\b/.test(bodyText)) return 1;
    if (/\b2nd\b/.test(bodyText)) return 2;
    if (/\b3rd\b/.test(bodyText)) return 3;
    return null;
  }

  function getCompanyFromPage() {
    // Experience section: first company link
    for (const link of document.querySelectorAll("a[href*='/company/']")) {
      const text = (link.innerText || link.textContent || "").trim();
      if (text.length > 1 && text.length < 60 && !/follow/i.test(text) && !/linkedin/i.test(text)) {
        return text;
      }
    }
    return "";
  }

  // ── Unified profile scraper (returns Promise) ──

  SR.scrapeProfile = function () {
    return new Promise((resolve) => {
      const url = window.location.href.split("?")[0];
      const linkedinId = url.split("/in/")[1]?.replace(/\/$/, "") || "";
      const fullName = getProfileName();
      const headline = getProfileHeadline();
      const degree = getConnectionDegree();
      const currentCompany = getCompanyFromPage();

      let currentTitle = headline;
      const atMatch = headline.match(/^(.+?)\s+(?:at|@)\s+(.+)/i);
      if (atMatch) currentTitle = atMatch[1].trim();

      console.log(`[SR] scrapeProfile: name='${fullName}' title='${currentTitle}' company='${currentCompany}' degree=${degree}`);
      if (!fullName) { resolve(); return; }

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

      // Enrich with full experience/education/skills if available
      const enriched = SR.enrichProfile?.() || {};
      if (enriched.experience?.length) payload.experience = enriched.experience;
      if (enriched.education?.length) payload.education = enriched.education;
      if (enriched.skills?.length) payload.skills = enriched.skills;
      if (enriched.about) payload.about = enriched.about;

      SR.apiCall(
        "/linkedin/ingest/connections",
        { method: "POST", body: JSON.stringify({ connections: [payload] }) },
        (res) => {
          console.log("[SR] Profile save:", JSON.stringify(res));
          if (res?.ok) {
            const created = res.data?.created || 0;
            const msg = created > 0
              ? "Saved: " + fullName + (currentCompany ? " at " + currentCompany : "")
              : "Updated: " + fullName;
            SR.showToast(msg);
          } else {
            SR.showToast("Save failed: " + (res?.error || "unknown error"));
          }
          // Show profile intel panel
          showProfileIntel(payload, enriched);
          resolve();
        }
      );
    });
  };

  // ── Profile intelligence panel ──

  async function showProfileIntel(profileData, enriched) {
    if (!profileData.current_company) return; // can't do company intel without a company

    // Ask backend: who else do I know at this person's company?
    let networkData = null;
    try {
      const res = await SR.apiPost("/linkedin/analyze-network", { company_name: profileData.current_company });
      if (res?.ok) networkData = res.data;
    } catch {}

    const sections = [];

    // Profile summary
    const profileItems = [
      { icon: profileData.connection_degree === 1 ? "🟢" : profileData.connection_degree === 2 ? "🟡" : "⚪", text: profileData.full_name, sub: profileData.current_title },
      profileData.current_company ? { icon: "🏢", text: profileData.current_company } : null,
    ].filter(Boolean);
    sections.push({ heading: "👤 Contact", items: profileItems });

    // Enriched data
    if (enriched.experience?.length > 0) {
      sections.push({
        heading: "💼 Experience",
        items: enriched.experience.slice(0, 3).map((e) => ({
          icon: "•",
          text: e.title,
          sub: e.company + (e.duration ? " · " + e.duration : ""),
        })),
      });
    }

    // Network intel
    if (networkData) {
      const connections = networkData.connections || [];
      if (connections.length > 1) { // > 1 because current profile is one of them
        sections.push({
          heading: "🤝 Others at " + profileData.current_company,
          badge: `${connections.length}`,
          badgeType: "success",
          items: connections.filter((c) => c.linkedin_id !== profileData.linkedin_id).slice(0, 4).map((c) => ({
            icon: c.is_recruiter ? "🎯" : "👤",
            text: c.full_name,
            sub: c.current_title || "",
          })),
        });
      }
    }

    if (sections.length > 1) { // Only show if we have more than just the profile summary
      SR.showIntelPanel(profileData.full_name, sections);
    }
  }

  // ── Mutual connections ──

  SR.scrapeMutualConnections = function () {
    if (SR._mutualScrapeInProgress) {
      console.log("[SR] Mutual scrape in progress, retrying in 6 s…");
      setTimeout(() => SR.scrapeMutualConnections(), 6000);
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
    if (atMatch) targetTitle = atMatch[1].trim();

    console.log(`[SR] scrapeMutualConnections: name='${targetName}' company='${targetCompany}' id=${linkedinId}`);

    const targetPerson = {
      linkedin_id: linkedinId,
      linkedin_url: url,
      full_name: targetName,
      headline: targetHeadline,
      current_title: targetTitle,
      current_company: targetCompany,
    };

    // First try: scrape visible mutuals from current page
    const visibleMutuals = scrapeVisibleMutuals();
    if (visibleMutuals.length > 0) {
      console.log("[SR] Found", visibleMutuals.length, "visible mutuals");
      sendMutualData(targetPerson, visibleMutuals, visibleMutuals.length);
      return;
    }

    // Try clicking the mutual connections link
    const mutualLink = findMutualConnectionsLink();
    if (!mutualLink) {
      console.log("[SR] No mutual connections link found");
      return;
    }

    SR._mutualScrapeInProgress = true;
    chrome.storage.local.set({ sr_mutual_target: targetPerson }, () => {
      try {
        mutualLink.click();
        console.log("[SR] Clicked mutual connections link");
        // The navigation will trigger scrapeMutualSearchResults on the new page
        setTimeout(() => { SR._mutualScrapeInProgress = false; }, 5000);
      } catch (e) {
        console.warn("[SR] Failed to click mutual link:", e);
        setTimeout(() => { SR._mutualScrapeInProgress = false; }, 6000);
      }
    });
  };

  function findMutualConnectionsLink() {
    // Look for link containing "mutual" and "connection"
    const allLinks = document.querySelectorAll("a[href*='facetConnectionOf'], a[href*='mutual'], a[href*='shared']");
    for (const link of allLinks) {
      if (link.offsetParent !== null) return link;
    }
    // Fallback: text-based search
    for (const el of document.querySelectorAll("a, button, span[role='link']")) {
      const text = (el.innerText || el.textContent || "").toLowerCase().trim();
      if (text.includes("mutual") && text.includes("connection") && el.offsetParent !== null) {
        return el;
      }
    }
    return null;
  }

  // ── Scrape mutual search results page ──

  SR.scrapeMutualSearchResults = function () {
    chrome.storage.local.get("sr_mutual_target", (data) => {
      const targetPerson = data.sr_mutual_target;
      if (!targetPerson) {
        console.log("[SR] No sr_mutual_target — not a mutual scrape page");
        return;
      }
      console.log("[SR] scrapeMutualSearchResults for:", targetPerson.full_name);
      chrome.storage.local.remove("sr_mutual_target");

      function scrapePage() {
        const results = SR.scrapeSearchResultCards?.() || [];
        console.log("[SR] Mutual search page:", results.length, "results");

        // Auto-scroll to load more
        function scrollDown() {
          try { window.scrollTo(0, document.body.scrollHeight); } catch {}
          setTimeout(() => {
            const moreResults = SR.scrapeSearchResultCards?.() || [];
            if (moreResults.length > results.length) {
              // Found more, send all
              sendMutualData(targetPerson, moreResults, moreResults.length);
            } else if (results.length > 0) {
              sendMutualData(targetPerson, results, results.length);
            }
            // Check for next page
            const nextBtn = findNextPageButton();
            if (nextBtn && results.length < 100) {
              try { nextBtn.click(); setTimeout(scrapePage, 3000); } catch {}
            }
          }, 2000);
        }
        scrollDown();
      }
      setTimeout(scrapePage, 2000);
    });
  };

  // Use shared SR.findNextPageButton from linkedin-core.js
  const findNextPageButton = () => SR.findNextPageButton();

  // ── Scrape visible mutual names from profile page ──

  function scrapeVisibleMutuals() {
    const mutualNames = [];
    const seen = new Set();
    const bodyText = document.body.innerText || "";

    // Pattern: "Name1, Name2 and N other mutual connections"
    const pattern1 = bodyText.match(/([A-Z][a-zA-Zàèéìòùü'\- ]+(?:,\s*[A-Z][a-zA-Zàèéìòùü'\- ]+)*)\s+and\s+(\d+)\s+other\s+mutual\s+connect/);
    if (pattern1) {
      for (const name of pattern1[1].split(",").map((n) => n.trim()).filter((n) => n.length > 1)) {
        if (!seen.has(name)) {
          seen.add(name);
          mutualNames.push({ name, linkedin_id: name.toLowerCase().replace(/[^a-z0-9]/g, "-"), linkedin_url: "" });
        }
      }
    }

    // Pattern: "Name1 and Name2 are mutual connections"
    const pattern3 = bodyText.match(/([A-Z][a-zA-Zàèéìòùü'\- ]+)\s+and\s+([A-Z][a-zA-Zàèéìòùü'\- ]+)\s+are\s+mutual/);
    if (pattern3 && mutualNames.length === 0) {
      for (const name of [pattern3[1].trim(), pattern3[2].trim()]) {
        if (!seen.has(name)) {
          seen.add(name);
          mutualNames.push({ name, linkedin_id: "", linkedin_url: "" });
        }
      }
    }

    // Image alt texts near mutual mentions
    for (const img of document.querySelectorAll("img")) {
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
    }

    return mutualNames;
  }

  // ── Send mutual data to backend ──

  function sendMutualData(targetPerson, mutualNames, mutualCount) {
    const payload = {
      target_person: targetPerson,
      mutual_connections: mutualNames,
      mutual_count: mutualCount || mutualNames.length,
    };
    console.log("[SR] Sending", mutualNames.length, "mutuals for", targetPerson.full_name);
    SR.apiCall("/linkedin/ingest/mutual-connections", { method: "POST", body: JSON.stringify(payload) }, (res) => {
      console.log("[SR] Mutual save:", JSON.stringify(res));
      if (res?.ok && res.data?.stored > 0) {
        SR.showToast("Mapped " + res.data.stored + " paths to " + targetPerson.full_name + " — go back to StealthRole");
      } else if (res?.ok && res.data?.stored === 0 && mutualNames.length > 0) {
        SR.showToast("Connections already mapped for " + targetPerson.full_name);
      } else if (!res?.ok) {
        SR.showToast("Failed to save: " + (res?.error || "unknown"));
        console.error("[SR] Mutual save FAILED:", res);
      }
    });
  }
})();
