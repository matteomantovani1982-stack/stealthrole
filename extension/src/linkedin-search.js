// StealthRole LinkedIn — Search results + Network scan (v2.0.0)
// Handles search result scraping, company network scan, and the
// handleSearchScrape click handler.

(() => {
  "use strict";
  const SR = window.SR;

  // ── Search result card scraping ──

  SR.scrapeSearchResultCards = function () {
    const results = [];
    const seen = new Set();

    const cards = document.querySelectorAll(
      ".reusable-search__result-container, " +
      ".entity-result, " +
      "li.reusable-search__result-container, " +
      "[data-chameleon-result-urn], " +
      ".search-results-container li"
    );

    console.log("[SR] Search cards found:", cards.length);

    cards.forEach((card) => {
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

    // Fallback: get names from profile links — but ONLY if those links are
    // inside the search-results container. Without that scope we sweep up
    // "People you may know", "Recent searches", header widgets, footer
    // suggestions, and button text like "Connect" / "Open" / "View profile".
    // Those then get stored as MutualConnection rows and pollute Way In.
    if (results.length === 0) {
      const resultsContainer = document.querySelector(
        ".search-results-container, " +
        ".reusable-search__entity-result-list, " +
        "[role='main'] .scaffold-finite-scroll, " +
        "main"
      );
      const scope = resultsContainer || document;

      // Heuristic: a real person name is 2+ words OR contains an uppercase letter
      // and isn't an obvious UI string. This filters "Open" / "Connect" / "View".
      const looksLikeName = (s) => {
        if (!s) return false;
        const t = s.trim();
        if (t.length < 3 || t.length > 60) return false;
        const lower = t.toLowerCase();
        // UI strings to reject
        const uiNoise = [
          "linkedin", "view profile", "view all", "see all", "connect", "follow",
          "message", "open", "more", "contact info", "send inmail", "premium",
          "show more", "show less", "people you may know", "recent searches",
        ];
        if (uiNoise.some((bad) => lower === bad || lower.startsWith(bad + " "))) return false;
        // Must contain at least one uppercase letter (real names are capitalized)
        if (!/[A-Z\u00C0-\u024F\u0400-\u04FF\u0530-\u058F\u0590-\u05FF\u0600-\u06FF\u4E00-\u9FFF]/.test(t)) return false;
        return true;
      };

      scope.querySelectorAll("a[href*='/in/']").forEach((link) => {
        const text = (link.innerText || link.textContent || "").trim().split("\n")[0].trim();
        if (!looksLikeName(text) || seen.has(text)) return;
        seen.add(text);
        const href = link.href?.split("?")[0] || "";
        const lid = href.split("/in/")[1]?.replace(/\/$/, "") || "";
        if (!lid) return; // require a real linkedin_id slug
        results.push({ name: text, linkedin_id: lid, linkedin_url: href });
      });
    }

    return results;
  };

  // ── Handle search scrape button click ──

  SR.handleSearchScrape = function () {
    const results = SR.scrapeSearchResultCards();
    console.log("[SR] handleSearchScrape:", results.length, "results");
    if (results.length === 0) { SR.showToast("No search results found."); return; }

    // Convert to connections format
    const connections = results.map((r) => ({
      linkedin_id: r.linkedin_id,
      linkedin_url: r.linkedin_url,
      full_name: r.name,
      headline: r.headline || "",
      current_title: r.headline || "",
      current_company: "",
      relationship_strength: "discovered",
    }));

    SR.apiCall("/linkedin/ingest/connections", { method: "POST", body: JSON.stringify({ connections }) }, (res) => {
      if (res?.ok) SR.showToast("Saved " + (res.data?.created || 0) + " people from search");
      else SR.showToast(res?.error || "Import failed");
    });
  };

  // ── Network scan for company ──
  // Triggered from the web app when user initiates a scan targeting a
  // specific company. Scrolls through search/connections pages, filtering
  // for profiles matching the target company.

  SR.scrapeNetworkForCompany = function (scanTarget) {
    console.log("[SR] Network scan for company:", scanTarget.target_company);
    const targetCompany = (scanTarget.target_company || "").toLowerCase().trim();
    if (!targetCompany) return;

    const matches = [];
    let totalScraped = 0;

    function updateScanProgress(progressText) {
      try {
        chrome.runtime.sendMessage({
          type: "SCAN_PROGRESS",
          scan_id: scanTarget.id,
          text: progressText,
        });
      } catch {}
    }

    function scrapePage() {
      updateScanProgress(`Scanning page… (${matches.length} matches so far)`);

      function scrollDown() {
        try { window.scrollTo(0, document.body.scrollHeight); } catch {}
        setTimeout(() => {
          const results = SR.scrapeSearchResultCards?.() || [];
          totalScraped += results.length;

          for (const p of results) {
            const blob = ((p.headline || "") + " " + (p.name || "")).toLowerCase();
            if (blob.includes(targetCompany)) {
              matches.push(p);
            }
          }

          updateScanProgress(`Scanned ${totalScraped} profiles, ${matches.length} matches`);

          if (totalScraped < 500) {
            // Try next page
            const nextBtn = findNextPageButton();
            if (nextBtn) {
              try { nextBtn.click(); setTimeout(scrapePage, 3000); return; } catch {}
            }
          }

          // Done
          finishScan(scanTarget, matches, totalScraped);
        }, 2000);
      }
      scrollDown();
    }
    scrapePage();
  };

  // Use shared SR.findNextPageButton from linkedin-core.js
  const findNextPageButton = () => SR.findNextPageButton();

  function finishScan(scanTarget, matches, totalScraped) {
    const payload = {
      scan_id: scanTarget.id,
      target_company: scanTarget.target_company,
      matches: matches.map((m) => ({
        name: m.name,
        linkedin_id: m.linkedin_id,
        linkedin_url: m.linkedin_url,
        headline: m.headline || "",
      })),
      total_scanned: totalScraped,
    };
    console.log("[SR] Scan complete:", matches.length, "matches from", totalScraped, "profiles");
    SR.apiCall("/linkedin/ingest/network-scan", { method: "POST", body: JSON.stringify(payload) }, (res) => {
      console.log("[SR] Scan save:", JSON.stringify(res));
      if (res?.ok) SR.showToast("Scan complete: " + matches.length + " matches at " + scanTarget.target_company);
      else SR.showToast("Scan failed: " + (res?.error || "unknown"));
    });
  }

  // ── Click handler for "connections" link on profile page ──
  // Used by network scan to navigate to a specific person's connections.

  SR.clickConnectionsLink = function (connectorSlug) {
    const links = document.querySelectorAll("a[href*='/in/']");
    for (const link of links) {
      const text = (link.innerText || link.textContent || "").toLowerCase();
      if (text.includes("connection") && link.href.includes(connectorSlug)) {
        try { link.click(); return true; } catch {}
      }
    }
    // Broader: any link/button mentioning connections
    for (const el of document.querySelectorAll("a, button")) {
      const text = (el.innerText || el.textContent || "").trim().toLowerCase();
      if (text.includes("connection") && text.includes("mutual")) {
        try { el.click(); return true; } catch {}
      }
    }
    return false;
  };
})();
