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
    // LinkedIn shows "1st", "2nd", "3rd" in various badge formats
    // Try multiple selector strategies since LinkedIn changes these often
    const degreeSelectors = [
      ".dist-value",
      ".distance-badge",
      "span[class*='degree']",
      // Modern LinkedIn (2025+) uses these
      "span.pv-text-details__separator + span",
      ".pv-top-card--list span",
      "[data-test-distance-badge]",
      ".pvs-profile-actions span",
    ];
    for (const sel of degreeSelectors) {
      for (const el of document.querySelectorAll(sel)) {
        const t = (el.textContent || "").trim();
        if (/^[123](st|nd|rd)$/i.test(t)) return parseInt(t[0], 10);
        const m = t.match(/(\d)\s*(?:st|nd|rd)/i);
        if (m) return parseInt(m[1], 10);
      }
    }
    // Broader scan: any small element containing just "1st", "2nd", "3rd"
    for (const el of document.querySelectorAll("span, div, li")) {
      const t = (el.textContent || "").trim();
      if (t.length > 10) continue; // skip large text blocks
      if (/^[123]\s*(?:st|nd|rd)$/i.test(t)) return parseInt(t[0], 10);
    }
    // Last resort: search aria-labels and title attributes
    for (const el of document.querySelectorAll("[aria-label], [title]")) {
      const label = (el.getAttribute("aria-label") || el.getAttribute("title") || "").toLowerCase();
      if (label.includes("1st degree")) return 1;
      if (label.includes("2nd degree")) return 2;
      if (label.includes("3rd degree")) return 3;
    }
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
      // Expose degree so linkedin-core.js can auto-trigger mutual scraping for 2nd/3rd
      SR._lastScrapedDegree = degree;
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

  /**
   * Resolve the target profile's entity URN.
   * Tries: 1) DOM code blocks, 2) mutual link href, 3) Voyager API (multiple endpoints)
   */
  async function resolveProfileUrn(linkedinId) {
    // ── Source 1: LinkedIn embeds profile data in <code> tags ──
    for (const code of document.querySelectorAll("code")) {
      const text = code.textContent || "";
      // Look for the target's mini profile or fsd_profile URN
      const m = text.match(/"publicIdentifier"\s*:\s*"[^"]*"[^}]*"entityUrn"\s*:\s*"(urn:li:(?:fsd_profile|fs_miniProfile):[^"]+)"/) ||
                text.match(/"entityUrn"\s*:\s*"(urn:li:fsd_profile:[^"]+)"/);
      if (m) {
        console.log("[SR] URN from <code> tag:", m[1]);
        return m[1];
      }
    }

    // ── Source 2: Extract from the mutual connections link href ──
    // LinkedIn links like: /search/results/people/?facetConnectionOf=%5B%22ACoAAxxxxxx%22%5D
    for (const link of document.querySelectorAll("a[href*='facetConnectionOf'], a[href*='connectionOf']")) {
      const href = link.href || "";
      const m = href.match(/(?:facetConnectionOf|connectionOf)=%5B%22([^%"]+)%22%5D/) ||
                href.match(/(?:facetConnectionOf|connectionOf)=\[?"?([A-Za-z0-9_:-]+)"?\]?/);
      if (m) {
        console.log("[SR] URN from mutual link:", m[1]);
        return m[1]; // This is the raw profile ID like "ACoAAAxxxxxx"
      }
    }

    // ── Source 3: Scan page HTML for any fsd_profile URN ──
    const bodyHtml = document.documentElement.innerHTML.slice(0, 500000);
    const allUrns = [...bodyHtml.matchAll(/urn:li:fsd_profile:([A-Za-z0-9_-]+)/g)];
    // The target's URN is usually the most frequent non-self one
    if (allUrns.length > 0) {
      // Find the most common URN (likely the target)
      const counts = {};
      for (const m of allUrns) { counts[m[1]] = (counts[m[1]] || 0) + 1; }
      const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
      if (sorted.length > 0) {
        const urn = `urn:li:fsd_profile:${sorted[0][0]}`;
        console.log("[SR] URN from HTML scan:", urn, `(appeared ${sorted[0][1]}x)`);
        return urn;
      }
    }

    // ── Source 4: Voyager API — try multiple endpoints ──
    const headers = SR.voyagerHeaders();
    if (!headers) return null;

    const apiUrls = [
      `https://www.linkedin.com/voyager/api/identity/profiles/${encodeURIComponent(linkedinId)}/profileView`,
      `https://www.linkedin.com/voyager/api/identity/dash/profiles?q=memberIdentity&memberIdentity=${encodeURIComponent(linkedinId)}&decorationId=com.linkedin.voyager.dash.deco.identity.profile.WebTopCardCore-18`,
      `https://www.linkedin.com/voyager/api/identity/dash/profiles?q=memberIdentity&memberIdentity=${encodeURIComponent(linkedinId)}&decorationId=com.linkedin.voyager.dash.deco.identity.profile.TopCardSupplementary-135`,
      `https://www.linkedin.com/voyager/api/identity/dash/profiles?q=memberIdentity&memberIdentity=${encodeURIComponent(linkedinId)}`,
    ];

    for (const url of apiUrls) {
      try {
        const res = await SR.fetchWithTimeout(url, { headers, credentials: "include" }, 8000);
        if (!res.ok) { console.log(`[SR] URN API ${res.status}: ${url.slice(0, 80)}…`); continue; }
        const data = await res.json();
        // Walk included + elements for profile URN
        for (const item of [...(data.included || []), ...(data.elements || [])]) {
          const urn = item.entityUrn || item["$urn"] || item["*profile"] || "";
          if (typeof urn === "string" && (urn.includes("fsd_profile:") || urn.includes("fs_miniProfile:"))) {
            console.log("[SR] URN from API:", urn);
            return urn;
          }
        }
      } catch (e) {
        console.log("[SR] URN API error:", e.message);
      }
    }

    console.warn("[SR] Could not resolve URN for", linkedinId);
    return null;
  }

  /**
   * Fetch mutual connections via Voyager search API.
   */
  async function fetchMutualsViaVoyager(linkedinId) {
    const headers = SR.voyagerHeaders();
    if (!headers) {
      console.warn("[SR] No CSRF token — can't call Voyager");
      return null;
    }

    SR.showToast("Resolving profile…");
    const profileUrn = await resolveProfileUrn(linkedinId);
    if (!profileUrn) return null;

    // The URN might be a full URN or just the raw ID (from facetConnectionOf link)
    // Make sure we have the raw ID for the search query
    const rawId = profileUrn.replace(/^urn:li:(?:fsd_profile|fs_miniProfile|member):/, "");

    SR.showToast("Searching mutual connections…");

    // Try multiple search URL formats
    const searchUrls = [
      // Use raw ID directly (works when extracted from facetConnectionOf)
      `https://www.linkedin.com/voyager/api/search/dash/clusters?q=all&origin=MEMBER_PROFILE_CANNED_SEARCH&query=(flagshipSearchIntent:SEARCH_SRP,queryParameters:(connectionOf:List(${encodeURIComponent(profileUrn)}),network:List(F),resultType:List(PEOPLE)))&count=49&start=0`,
      // With SHARED_CONNECTIONS origin
      `https://www.linkedin.com/voyager/api/search/dash/clusters?q=all&origin=SHARED_CONNECTIONS_CANNED_SEARCH&query=(flagshipSearchIntent:SEARCH_SRP,queryParameters:(connectionOf:List(${encodeURIComponent(profileUrn)}),network:List(F),resultType:List(PEOPLE)))&count=49&start=0`,
    ];

    for (const searchUrl of searchUrls) {
      try {
        console.log("[SR] Trying Voyager mutual search…");
        const res = await SR.fetchWithTimeout(searchUrl, { headers, credentials: "include" }, 12000);

        if (!res.ok) {
          console.log(`[SR] Voyager search returned ${res.status}`);
          continue;
        }

        const data = await res.json();
        const mutuals = extractMutualsFromVoyagerResponse(data, linkedinId);
        if (mutuals.length > 0) return mutuals;
        console.log("[SR] Voyager search returned OK but 0 mutuals, trying next URL…");
      } catch (e) {
        console.warn("[SR] Voyager search failed:", e.message);
      }
    }
    return null;
  }

  /**
   * Parse mutual connection profiles from a Voyager search response.
   */
  function extractMutualsFromVoyagerResponse(data, excludeId) {
    const mutuals = [];
    const seenIds = new Set();

    // Extract from "included" array (miniProfile entities)
    for (const item of (data.included || [])) {
      const urn = item.entityUrn || item["$urn"] || "";
      if (!urn.includes("miniProfile") && !urn.includes("fsd_profile")) continue;
      const name = [item.firstName, item.lastName].filter(Boolean).join(" ").trim();
      const publicId = item.publicIdentifier || "";
      if (!name || !publicId || publicId === excludeId || seenIds.has(publicId)) continue;
      seenIds.add(publicId);
      mutuals.push({
        name,
        linkedin_id: publicId,
        linkedin_url: `https://www.linkedin.com/in/${publicId}`,
        headline: item.occupation || item.headline || "",
      });
    }

    // Extract from elements/clusters (search result format)
    const elements = data.data?.searchDashClustersByAll?.elements || data.elements || [];
    for (const cluster of elements) {
      for (const item of (cluster.items || [])) {
        const entity = item.item?.entityResult || item.entityResult || {};
        const title = entity.title?.text || "";
        const navUrl = entity.navigationUrl || "";
        const subtitle = entity.primarySubtitle?.text || "";
        if (title && navUrl.includes("/in/")) {
          const pubId = navUrl.split("/in/")[1]?.split("?")[0]?.replace(/\/$/, "") || "";
          if (pubId && pubId !== excludeId && !seenIds.has(pubId)) {
            seenIds.add(pubId);
            mutuals.push({
              name: title,
              linkedin_id: pubId,
              linkedin_url: `https://www.linkedin.com/in/${pubId}`,
              headline: subtitle,
            });
          }
        }
      }
    }

    console.log(`[SR] Parsed ${mutuals.length} mutual profiles from Voyager response`);
    return mutuals;
  }

  /**
   * Wait for the mutual connections section to render, then scrape links from it.
   */
  async function scrapeMutualsFromRenderedDom(linkedinId) {
    // LinkedIn lazy-loads the mutual connections section. Wait for it.
    console.log("[SR] Waiting for mutual section to render…");
    for (let i = 0; i < 12; i++) {
      await new Promise(r => setTimeout(r, 1000));
      // Check for mutual connections link/section
      const mutualLink = findMutualConnectionsLink();
      if (mutualLink) {
        console.log("[SR] Found mutual connections link after", (i + 1), "seconds");
        // Try to extract the URN from the link and do an API call
        const href = mutualLink.href || mutualLink.closest("a")?.href || "";
        const urnMatch = href.match(/(?:facetConnectionOf|connectionOf)=%5B%22([^%"]+)%22%5D/);
        if (urnMatch) {
          console.log("[SR] Extracted URN from mutual link:", urnMatch[1]);
          const headers = SR.voyagerHeaders();
          if (headers) {
            const profileUrn = urnMatch[1];
            const searchUrl = `https://www.linkedin.com/voyager/api/search/dash/clusters?q=all&origin=MEMBER_PROFILE_CANNED_SEARCH&query=(flagshipSearchIntent:SEARCH_SRP,queryParameters:(connectionOf:List(${encodeURIComponent(profileUrn)}),network:List(F),resultType:List(PEOPLE)))&count=49&start=0`;
            try {
              const res = await SR.fetchWithTimeout(searchUrl, { headers, credentials: "include" }, 12000);
              if (res.ok) {
                const data = await res.json();
                const mutuals = extractMutualsFromVoyagerResponse(data, linkedinId);
                if (mutuals.length > 0) return mutuals;
              }
            } catch {}
          }
        }
        break;
      }
      // Also check for visible mutual name text
      const visibleMutuals = scrapeVisibleMutuals();
      if (visibleMutuals.length > 0) return visibleMutuals;
    }

    // Final DOM scrape after waiting
    return scrapeVisibleMutuals();
  }

  SR.scrapeMutualConnections = function () {
    if (SR._mutualScrapeInProgress) {
      console.log("[SR] Mutual scrape already in progress");
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

    SR._mutualScrapeInProgress = true;

    (async () => {
      try {
        // ── Step 1: Wait for the mutual connections section to render ──
        // LinkedIn lazy-loads this section. Wait up to 10s for it.
        SR.showToast("Looking for mutual connections…");
        let mutualLink = null;
        for (let i = 0; i < 10; i++) {
          await new Promise(r => setTimeout(r, 1000));
          mutualLink = findMutualConnectionsLink();
          if (mutualLink) break;
        }

        // ── Step 2: Try Voyager API using URN from the link or page ──
        // This is fast and doesn't navigate away from the page
        try {
          const voyagerMutuals = await fetchMutualsViaVoyager(linkedinId);
          if (voyagerMutuals && voyagerMutuals.length > 0) {
            console.log(`[SR] Voyager: ${voyagerMutuals.length} mutuals`);
            SR.showToast(`Found ${voyagerMutuals.length} mutual connections — syncing`);
            sendMutualData(targetPerson, voyagerMutuals, voyagerMutuals.length);
            return;
          }
        } catch (e) {
          console.log("[SR] Voyager approach failed:", e.message);
        }

        // ── Step 3: Click through to search results (the proven approach) ──
        // This navigates away from the profile page. The search results page
        // will trigger scrapeMutualSearchResults() via initForPage → sr_mutual_target.
        if (mutualLink) {
          SR.showToast("Opening mutual connections list…");
          console.log("[SR] Clicking mutual connections link → search results page");
          chrome.storage.local.set({ sr_mutual_target: targetPerson }, () => {
            mutualLink.click();
          });
          return;
        }

        // ── Step 4: Check visible mutuals from DOM as last resort ──
        const visibleMutuals = scrapeVisibleMutuals();
        if (visibleMutuals.length > 0) {
          SR.showToast(`Found ${visibleMutuals.length} mutual connections — syncing`);
          sendMutualData(targetPerson, visibleMutuals, visibleMutuals.length);
          return;
        }

        console.log("[SR] No mutual connections found");
        SR.showToast("No mutual connections found for " + (targetName || "this profile"));
      } catch (e) {
        console.error("[SR] scrapeMutualConnections error:", e);
      } finally {
        SR._mutualScrapeInProgress = false;
      }
    })();
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

    // Use a broad character class that handles non-Latin scripts (Arabic, Chinese, etc.)
    // \p{L} matches any Unicode letter; also allow hyphens, apostrophes, dots, spaces
    const nameChar = "[\\p{L}\\p{M}'\\-\\.\\s]";
    const nameRe = new RegExp(`([\\p{Lu}\\p{Lo}]${nameChar}{1,50}(?:,\\s*[\\p{Lu}\\p{Lo}]${nameChar}{1,50})*)\\s+and\\s+(\\d+)\\s+other\\s+mutual\\s+connect`, "u");

    // Pattern: "Name1, Name2 and N other mutual connections"
    const pattern1 = bodyText.match(nameRe);
    if (pattern1) {
      for (const name of pattern1[1].split(",").map((n) => n.trim()).filter((n) => n.length > 1)) {
        if (!seen.has(name)) {
          seen.add(name);
          mutualNames.push({ name, linkedin_id: name.toLowerCase().replace(/[^a-z0-9]/g, "-"), linkedin_url: "" });
        }
      }
    }

    // Pattern: "Name1 and Name2 are mutual connections"
    const nameRe2 = new RegExp(`([\\p{Lu}\\p{Lo}]${nameChar}{1,50})\\s+and\\s+([\\p{Lu}\\p{Lo}]${nameChar}{1,50})\\s+are\\s+mutual`, "u");
    const pattern3 = bodyText.match(nameRe2);
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
