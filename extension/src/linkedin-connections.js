// StealthRole LinkedIn — Connections sync (v2.0.0)
// Voyager API pagination + DOM scroll fallback.
// Cleaned up: single progress helper, tighter idle detection, removed
// redundant scroll strategies.

(() => {
  "use strict";
  const SR = window.SR;

  // ── Voyager endpoint probing + pagination ──

  const DECORATIONS = [
    "com.linkedin.voyager.dash.deco.web.mynetwork.ConnectionListWithProfile-18",
    "com.linkedin.voyager.dash.deco.web.mynetwork.ConnectionListWithProfile-17",
    "com.linkedin.voyager.dash.deco.web.mynetwork.ConnectionListWithProfile-16",
    "com.linkedin.voyager.dash.deco.web.mynetwork.ConnectionListWithProfile-15",
  ];

  function connectionEndpointBuilders() {
    const builders = [];
    for (const deco of DECORATIONS) {
      builders.push((start, count) =>
        `https://www.linkedin.com/voyager/api/relationships/dash/connections?decorationId=${deco}&count=${count}&q=search&sortType=RECENTLY_ADDED&start=${start}`
      );
    }
    // Fallback without decoration
    builders.push((start, count) =>
      `https://www.linkedin.com/voyager/api/relationships/dash/connections?count=${count}&q=search&sortType=RECENTLY_ADDED&start=${start}`
    );
    // Legacy non-dash endpoint
    builders.push((start, count) =>
      `https://www.linkedin.com/voyager/api/relationships/connections?count=${count}&start=${start}`
    );
    return builders;
  }

  const BATCH = 40; // moved to module scope so probe and paginator share it

  async function fetchAllConnectionsViaVoyager() {
    const headers = SR.voyagerHeaders();
    if (!headers) {
      console.warn("[SR] voyager connections: no CSRF token");
      return null;
    }
    console.log("[SR] voyager connections: CSRF ok, probing endpoints…");

    const builders = connectionEndpointBuilders();
    for (let i = 0; i < builders.length; i++) {
      const build = builders[i];
      // CRITICAL: probe with full BATCH size so firstPageData has all records
      // for page 0. Previously probed with 10 and started pagination at 40,
      // silently skipping records 10–39 (30 connections lost every sync).
      const testUrl = build(0, BATCH);
      try {
        const res = await SR.fetchWithTimeout(testUrl, { headers, credentials: "include" }, 15000);
        console.log(`[SR] conn probe ${i}:`, testUrl.slice(0, 110), "→", res.status);
        if (!res.ok) continue;
        const data = await res.json();
        const topKeys = Object.keys(data || {});
        console.log(`[SR] conn probe ${i}: keys =`, topKeys.join(", "));
        if (data.paging) console.log(`[SR] conn probe ${i}: paging =`, JSON.stringify(data.paging));
        if (data.elements?.[0]) console.log(`[SR] conn probe ${i}: elements[0] =`, JSON.stringify(data.elements[0]).slice(0, 400));
        if (data.included?.[0]) console.log(`[SR] conn probe ${i}: included[0] =`, JSON.stringify(data.included[0]).slice(0, 400));

        const extracted = extractVoyagerRecords(data);
        console.log(`[SR] conn probe ${i}: extracted ${extracted.length} records from ${(data.elements||[]).length} elements + ${(data.included||[]).length} included`);
        if (extracted.length === 0) continue;
        return await paginateVoyager(build, headers, data);
      } catch (e) {
        console.warn(`[SR] conn probe ${i} failed:`, e.message);
      }
    }
    console.warn("[SR] voyager connections: no endpoint worked");
    return null;
  }

  // ── Connection prioritization ──
  // Sorts connections by relevance to job search: recruiters and hiring managers
  // first, then people at target companies, then everyone else by recency.

  const RECRUITER_KEYWORDS = /\b(recruit|talent\s*acqui|sourcer|head\s*hunt|staffing|hiring\s*partner|people\s*ops|hr\s*business\s*partner|ta\s*lead|ta\s*manager)\b/i;
  const HM_KEYWORDS = /\b(hiring\s*manager|engineering\s*manager|vp\s*of\s*eng|director\s*of\s*eng|cto|head\s*of\s*product|head\s*of\s*eng|head\s*of\s*design|team\s*lead)\b/i;

  function prioritizeConnections(connections) {
    // Score each connection: lower = higher priority
    const scored = connections.map((c) => {
      const title = (c.current_title || c.headline || "").toLowerCase();
      let score = 3; // default: regular connection
      if (RECRUITER_KEYWORDS.test(title)) score = 0;        // recruiters first
      else if (HM_KEYWORDS.test(title)) score = 1;          // hiring managers second
      // Connections at common tech/target companies get a slight bump
      else if (/\b(engineer|developer|designer|product\s*manager|data\s*scientist)\b/i.test(title)) score = 2;
      return { ...c, _score: score };
    });
    scored.sort((a, b) => a._score - b._score);
    // Strip internal score before returning
    return scored.map(({ _score, ...rest }) => rest);
  }

  async function paginateVoyager(build, headers, firstPageData) {
    const all = [];
    const MAX_TOTAL = 15000;
    const seenIds = new Set();

    // Extract total from paging metadata so we know when we're truly done.
    // IMPORTANT: paging.count is USUALLY the page size (~40), not total.
    // But some endpoints put the total in paging.count when paging.total is absent.
    let pagingTotal = firstPageData?.paging?.total
      || firstPageData?.metadata?.totalResultCount
      || 0;
    // Heuristic: if paging.count > 100 and there's no paging.total, it's likely the real total
    const pagingCount = firstPageData?.paging?.count || 0;
    if (!pagingTotal && pagingCount > 100) {
      console.log(`[SR] voyager conn: paging.count=${pagingCount} looks like total (no paging.total found) — using it`);
      pagingTotal = pagingCount;
    }
    console.log(`[SR] voyager conn: paging.total = ${pagingTotal}, paging.count = ${pagingCount || "?"}, paging.start = ${firstPageData?.paging?.start || "?"}`);

    let extracted = extractVoyagerRecords(firstPageData);
    for (const c of extracted) {
      if (!seenIds.has(c.linkedin_id)) { seenIds.add(c.linkedin_id); all.push(c); }
    }
    console.log(`[SR] voyager conn: page 0 → ${extracted.length} records (${all.length} unique)`);

    // Start from the API's actual page boundary, NOT extracted record count.
    // extracted.length can be LESS than elements.length due to dedup, but the
    // API paginates by element index, not by unique records.
    const firstPageElements = firstPageData?.elements?.length || BATCH;
    let start = firstPageElements;
    let rateLimitRetries = 0;
    let consecutiveEmpty = 0;
    const MAX_EMPTY = 5; // allow up to 5 empty pages before giving up (LinkedIn skips sometimes)

    while (start < MAX_TOTAL) {
      // If we know the total and we've got them all, stop
      if (pagingTotal > 0 && all.length >= pagingTotal) {
        console.log(`[SR] voyager conn: reached paging.total (${all.length} >= ${pagingTotal})`);
        break;
      }

      const url = build(start, BATCH);
      try {
        const res = await SR.fetchWithRetry(url, { headers, credentials: "include" }, { retries: 2, backoffMs: 2000 });
        if (res.status === 429 || res.status === 503) {
          rateLimitRetries++;
          if (rateLimitRetries > 8) { console.warn("[SR] voyager conn: too many rate limits, stopping"); break; }
          const retryAfter = parseInt(res.headers?.get?.("retry-after") || "15", 10);
          console.warn(`[SR] voyager conn page ${start}: rate-limited (${res.status}), waiting ${retryAfter}s`);
          await new Promise((r) => setTimeout(r, retryAfter * 1000));
          continue; // retry same page
        }
        if (!res.ok) { console.warn("[SR] voyager conn page", start, "→", res.status); break; }
        rateLimitRetries = 0;
        const data = await res.json();
        extracted = extractVoyagerRecords(data);

        if (extracted.length === 0) {
          consecutiveEmpty++;
          console.log(`[SR] voyager conn: empty page at start=${start} (consecutive: ${consecutiveEmpty}/${MAX_EMPTY})`);
          if (consecutiveEmpty >= MAX_EMPTY) {
            console.log("[SR] voyager conn: too many consecutive empty pages, stopping");
            break;
          }
          // Skip ahead and try next page — LinkedIn sometimes has gaps
          start += BATCH;
          await new Promise((r) => setTimeout(r, 800));
          continue;
        }

        consecutiveEmpty = 0; // reset on successful extraction
        let added = 0;
        for (const c of extracted) {
          if (!seenIds.has(c.linkedin_id)) { seenIds.add(c.linkedin_id); all.push(c); added++; }
        }
        console.log(`[SR] voyager conn: page ${Math.floor(start / BATCH)} → ${extracted.length} records (${added} new, total ${all.length}${pagingTotal ? ` / ${pagingTotal}` : ""})`);

        // Only stop on short page if we DON'T know the total, or we've reached it
        if (extracted.length < BATCH && (!pagingTotal || all.length >= pagingTotal)) break;

        start += BATCH;
        // Slow down slightly after 1000 to avoid rate limits
        const delay = all.length > 1000 ? 600 : 400;
        await new Promise((r) => setTimeout(r, delay));
      } catch (e) {
        console.warn("[SR] voyager conn page", start, "error:", e.message);
        // Don't give up on one error — skip and try next page
        consecutiveEmpty++;
        if (consecutiveEmpty >= MAX_EMPTY) break;
        start += BATCH;
        await new Promise((r) => setTimeout(r, 1000));
      }
    }

    console.log(`[SR] voyager conn: pagination complete — ${all.length} total records${pagingTotal ? ` (expected ${pagingTotal})` : ""}`);
    return { records: all, expectedTotal: pagingTotal };
  }

  // ── Extract connection records from voyager response ──
  // Recursively scans for known profile field patterns.

  function extractVoyagerRecords(data) {
    const results = [];
    const seen = new Set();

    // LinkedIn GraphQL wraps strings as {text:"value"} — unwrap them
    const str = (v) => {
      if (typeof v === "string") return v;
      if (v && typeof v === "object" && typeof v.text === "string") return v.text;
      return "";
    };

    // Try every available source for a profile slug/ID.
    // Priority: publicIdentifier → profileUrl slug → entityUrn member ID
    const extractSlug = (obj) => {
      if (!obj || typeof obj !== "object") return "";
      // 1. publicIdentifier (most common)
      const pubId = str(obj.publicIdentifier);
      if (pubId) return pubId;
      // 2. profileUrl slug (e.g. "https://www.linkedin.com/in/john-doe")
      const urlSlug = str(obj.profileUrl).match(/\/in\/([A-Za-z0-9_-]+)/);
      if (urlSlug) return urlSlug[1];
      // 3. entityUrn — extract member ID from URNs like:
      //    urn:li:fsd_profile:ACoAAEOBz6gB...
      //    urn:li:fs_miniProfile:ACoAAEOBz6gB...
      //    urn:li:member:123456789
      const urn = str(obj.entityUrn) || str(obj["*connectedMember"]) || str(obj.$id) || "";
      const urnMatch = urn.match(/urn:li:(?:fsd_profile|fs_miniProfile|member):([A-Za-z0-9_-]+)/);
      if (urnMatch) return `member_${urnMatch[1]}`; // prefix to distinguish from vanity slugs
      return "";
    };

    const addResult = (slug, first, last, headline) => {
      const cleanSlug = str(slug);
      if (!cleanSlug || seen.has(cleanSlug)) return;
      seen.add(cleanSlug);
      const fullName = [str(first), str(last)].filter(Boolean).join(" ").trim();
      if (!fullName) return;
      const hl = str(headline) || "";
      let currentTitle = hl;
      let currentCompany = "";
      const m = hl.match(/^(.+?)\s+(?:at|@)\s+(.+)$/i);
      if (m) { currentTitle = m[1].trim(); currentCompany = m[2].trim(); }
      // For entityUrn-based IDs, we can't build a profile URL
      const isVanitySlug = !cleanSlug.startsWith("member_");
      results.push({
        linkedin_id: cleanSlug,
        linkedin_url: isVanitySlug ? `https://www.linkedin.com/in/${cleanSlug}/` : "",
        full_name: fullName,
        headline: hl,
        current_title: currentTitle,
        current_company: currentCompany,
      });
    };

    // Try to extract a connection from a profile-like object using all slug sources
    const tryExtractProfile = (obj, fallbackHeadline) => {
      if (!obj || typeof obj !== "object") return;
      const slug = extractSlug(obj);
      if (slug && (obj.firstName || obj.lastName)) {
        addResult(slug, obj.firstName, obj.lastName, obj.headline || obj.occupation || fallbackHeadline || "");
      }
    };

    const visit = (obj) => {
      if (!obj || typeof obj !== "object") return;

      // Direct profile — object itself has name fields
      tryExtractProfile(obj, "");

      // miniProfile nested
      if (obj.miniProfile && typeof obj.miniProfile === "object") {
        tryExtractProfile(obj.miniProfile, obj.headline || obj.occupation || "");
      }
      // profile nested
      if (obj.profile && typeof obj.profile === "object") {
        tryExtractProfile(obj.profile, "");
      }
      // connectedMember (dash model)
      if (obj.connectedMember && typeof obj.connectedMember === "object") {
        tryExtractProfile(obj.connectedMember, "");
      }
      // connectedMemberResolutionResult (newer dash model)
      if (obj.connectedMemberResolutionResult && typeof obj.connectedMemberResolutionResult === "object") {
        tryExtractProfile(obj.connectedMemberResolutionResult, "");
      }

      // Recurse
      if (Array.isArray(obj)) { for (const item of obj) visit(item); }
      else { for (const key in obj) { if (obj[key] && typeof obj[key] === "object") visit(obj[key]); } }
    };

    visit(data);
    return results;
  }

  // ── DOM card parsing ──

  function parseCardText(text) {
    const parts = text.split(/\s*\|\s*/).map((s) => s.trim()).filter(Boolean);
    if (parts.length < 2) return null;
    const fullName = parts[0];
    if (!fullName || fullName.length < 3 || fullName.length > 80) return null;

    const connectedIdx = parts.findIndex((p) => /^Connected on /i.test(p));
    const headlineEnd = connectedIdx === -1 ? parts.length : connectedIdx;
    const headlineParts = parts.slice(1, headlineEnd);
    const headline = headlineParts.join(" · ");

    let currentTitle = headlineParts[0] || "";
    let currentCompany = "";
    const atMatch = (headlineParts[0] || "").match(/^(.+?)\s+(?:at|@)\s+(.+)$/i);
    if (atMatch) { currentTitle = atMatch[1].trim(); currentCompany = atMatch[2].trim(); }
    else if (headlineParts.length >= 2 && headlineParts[1].length < 60) { currentCompany = headlineParts[1]; }
    return { fullName, headline, currentTitle, currentCompany };
  }

  function collectVisibleConnectionCards(seen, debug) {
    const connections = [];
    const stats = { links: 0, validHref: 0, hasName: 0, hasHeadline: 0, parsed: 0, deduped: 0, skipped: 0 };
    const profileLinks = document.querySelectorAll("a[href*='/in/']");
    stats.links = profileLinks.length;

    for (const link of profileLinks) {
      const href = (link.href || "").split("?")[0];
      if (!/\/in\/[^/]+\/?$/.test(href)) { stats.skipped++; continue; }
      stats.validHref++;
      const linkedinId = href.split("/in/")[1]?.replace(/\/$/, "") || "";
      if (!linkedinId) { stats.skipped++; continue; }
      if (seen.has(linkedinId)) { stats.deduped++; continue; }

      // Name: aria-label → img alt → parent img alt → link text
      let fullName = link.getAttribute("aria-label") || "";
      if (!fullName) { const img = link.querySelector("img[alt]"); if (img) fullName = img.alt || ""; }
      if (!fullName) { const img = link.parentElement?.querySelector("img[alt]"); if (img) fullName = img.alt || ""; }
      if (!fullName) fullName = (link.textContent || "").trim().replace(/\s+/g, " ");
      fullName = fullName.replace(/^View\s+/i, "").replace(/[''']s\s*profile.*$/i, "").replace(/[''']s$/i, "").trim();

      if (!fullName || fullName.length < 3 || fullName.length > 100) { stats.skipped++; continue; }
      if (/^(message|connect|follow|view|pending|share|like)$/i.test(fullName)) { stats.skipped++; continue; }
      stats.hasName++;

      // Headline: walk up to find "Connected on" container
      let headline = "", currentTitle = "", currentCompany = "";
      let cur = link.parentElement;
      for (let i = 0; cur && i < 8; i++) {
        const t = (cur.innerText || "").replace(/\s+/g, " ").trim();
        if (t && t.length > 30 && t.length < 1500 && /Connected on/i.test(t)) {
          headline = t;
          stats.hasHeadline++;
          const parsed = parseCardText(t);
          if (parsed) {
            stats.parsed++;
            if (parsed.fullName && parsed.fullName.length > 2) fullName = parsed.fullName;
            currentTitle = parsed.currentTitle;
            currentCompany = parsed.currentCompany;
            headline = parsed.headline || headline;
          }
          break;
        }
        cur = cur.parentElement;
      }

      seen.add(linkedinId);
      connections.push({ linkedin_id: linkedinId, linkedin_url: href, full_name: fullName, headline, current_title: currentTitle, current_company: currentCompany });
    }

    if (debug) console.log("[SR] collect stats:", JSON.stringify(stats), "returned:", connections.length);
    return connections;
  }

  // ── Manual one-shot import (overlay button) ──

  SR.scrapeConnectionsManual = function () {
    SR.showToast("Scanning connections…");
    const connections = collectVisibleConnectionCards(new Set(), true);
    console.log("[SR] scrapeConnections:", connections.length, "profiles");
    if (connections.length === 0) { SR.showToast("No connections found on this page."); return; }
    if (connections.length > 0) {
      console.log("[SR] first 3:");
      for (const c of connections.slice(0, 3)) console.log(`  ${c.full_name} | "${c.current_title}" | "${c.current_company}"`);
    }
    SR.apiCall("/linkedin/ingest/connections", { method: "POST", body: JSON.stringify({ connections }) }, (res) => {
      if (res?.ok) SR.showToast("Imported " + (res.data?.created || 0) + " connections");
      else SR.showToast(res?.error || "Import failed");
    });
  };

  // ── Auto-scrape: full sync triggered by background ──

  SR.autoScrapeConnections = async function () {
    if (SR._autoScrapeInProgress) {
      console.warn("[SR] autoScrapeConnections already running");
      return;
    }
    SR._autoScrapeInProgress = true;
    console.log("[SR] autoScrapeConnections starting");

    const progress = (count, status, error) => SR.sendProgress("connections", count, status, error);
    progress(0, "scanning");

    // ── Try Voyager API first ──

    let voyagerSeenIds = new Set();
    let voyagerCount = 0;
    let voyagerExpected = 0;

    try {
      console.log("[SR] attempting Voyager API…");
      const voyagerResult = await fetchAllConnectionsViaVoyager();
      const voyagerRecords = voyagerResult?.records || voyagerResult;
      voyagerExpected = voyagerResult?.expectedTotal || 0;
      if (voyagerRecords && voyagerRecords.length > 0) {
        console.log(`[SR] Voyager returned ${voyagerRecords.length}${voyagerExpected ? ` (expected ${voyagerExpected})` : ""} — prioritizing by job relevance`);
        const sorted = prioritizeConnections(Array.isArray(voyagerRecords) ? voyagerRecords : []);
        progress(sorted.length, "scanning");
        const CHUNK = 100;
        const MAX_RETRIES = 2;
        let posted = 0;
        let batchFails = 0;
        for (let i = 0; i < sorted.length; i += CHUNK) {
          const batch = sorted.slice(i, i + CHUNK);
          let ok = false;
          for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
            const res = await SR.apiPost("/linkedin/ingest/connections", { connections: batch });
            if (res?.ok) {
              ok = true;
              // Use server's actual count, not batch.length
              const serverProcessed = res.data?.total_processed || batch.length;
              posted += serverProcessed;
              if (res.data?.skipped > 0) {
                console.log(`[SR] voyager batch at ${i}: server skipped ${res.data.skipped} records`);
              }
              break;
            }
            console.warn(`[SR] voyager batch error (attempt ${attempt + 1}):`, res?.error);
            if (attempt < MAX_RETRIES) await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
          }
          if (!ok) {
            console.error("[SR] voyager batch failed after retries, skipping chunk at", i);
            batchFails++;
          }
          progress(posted, "scanning");
        }
        voyagerCount = sorted.length;
        for (const c of sorted) voyagerSeenIds.add(c.linkedin_id);
        if (batchFails > 0) console.warn(`[SR] voyager POST: ${batchFails} batch(es) failed out of ${Math.ceil(sorted.length / CHUNK)}`);

        // Check if we got everything — if not, fall through to DOM scroll.
        // Only skip DOM if we got ALL connections (no tolerance — exact match).
        if (voyagerExpected > 0 && voyagerCount >= voyagerExpected) {
          console.log(`[SR] Voyager got ${voyagerCount} / ${voyagerExpected} — complete, skipping DOM`);
          progress(posted, "done");
          SR._autoScrapeInProgress = false;
          return;
        }
        // Always fall through to DOM if we don't have everything
        const missingPercent = voyagerExpected > 0 ? (1 - voyagerCount / voyagerExpected) * 100 : 0;
        console.log(`[SR] Voyager got ${voyagerCount}${voyagerExpected ? ` / ${voyagerExpected} (${missingPercent.toFixed(1)}% missing)` : ""} — supplementing with DOM scroll`);
      } else {
        console.warn("[SR] Voyager did not return data — falling back to DOM scroll");
      }
    } catch (e) {
      console.error("[SR] Voyager attempt errored:", e);
    }

    // ── DOM scroll fallback ──

    console.log(`[SR] starting DOM scroll ${voyagerCount > 0 ? "supplement" : "fallback"} (already have ${voyagerCount} from Voyager)`);
    progress(voyagerCount, "scanning");

    const seen = new Set(voyagerSeenIds);
    const allConnections = [];
    let tickCounter = 0;

    const collectNow = () => {
      tickCounter++;
      const newOnes = collectVisibleConnectionCards(seen, tickCounter === 1);
      for (const c of newOnes) allConnections.push(c);
      return newOnes.length;
    };

    const clickShowMore = () => {
      for (const b of document.querySelectorAll("button, a[role='button']")) {
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
      progress(allConnections.length, "scanning");
      if (allConnections.length > 0) {
        console.log("[SR] first 3 parsed:");
        for (const c of allConnections.slice(0, 3)) console.log(`  ${c.full_name} | "${c.current_title}" | "${c.current_company}"`);
      }

      // Find all scrollable containers on the page
      const findScrollers = () => {
        const result = [document.scrollingElement || document.documentElement, document.body];
        for (const el of document.querySelectorAll("div, main, section, [role='main']")) {
          if (!el?.clientHeight) continue;
          const style = getComputedStyle(el);
          if ((style.overflowY === "auto" || style.overflowY === "scroll") && el.scrollHeight > el.clientHeight + 50) {
            result.push(el);
          }
        }
        return result;
      };

      const startedAt = Date.now();
      const MAX_MS = 1200000;      // 20 min hard cap
      const IDLE_LIMIT = 40;        // ~3 min of idle
      let idleTicks = 0;
      let tickNo = 0;

      const pushScroll = () => {
        const scrollers = findScrollers();
        for (const s of scrollers) {
          try { s.scrollTop = s.scrollHeight; } catch {}
          try { s.dispatchEvent(new Event("scroll", { bubbles: true })); } catch {}
        }
        try { window.scrollTo(0, document.body.scrollHeight); } catch {}
        try { window.dispatchEvent(new Event("scroll", { bubbles: true })); } catch {}
        // Wheel event — some React virtual list libs only respond to this
        try {
          (document.scrollingElement || document.documentElement).dispatchEvent(
            new WheelEvent("wheel", { deltaY: 2000, deltaMode: 0, bubbles: true, cancelable: true })
          );
        } catch {}
        // Scroll last profile link into view to force virtualization render
        try {
          const links = document.querySelectorAll("a[href*='/in/']");
          if (links.length) links[links.length - 1].scrollIntoView({ block: "end", behavior: "instant" });
        } catch {}
        // PageDown key
        try {
          window.dispatchEvent(new KeyboardEvent("keydown", { key: "PageDown", code: "PageDown", keyCode: 34, bubbles: true }));
          window.dispatchEvent(new KeyboardEvent("keyup", { key: "PageDown", code: "PageDown", keyCode: 34, bubbles: true }));
        } catch {}
      };

      while (Date.now() - startedAt < MAX_MS && idleTicks < IDLE_LIMIT) {
        tickNo++;
        const scrollers = findScrollers();
        let primary = scrollers[0] || document.documentElement;
        for (const s of scrollers) { if ((s.scrollHeight || 0) > (primary.scrollHeight || 0)) primary = s; }
        const beforeTop = primary.scrollTop;
        const beforeHeight = primary.scrollHeight;

        pushScroll();
        clickShowMore();

        // Hard nudge when stuck: scroll up then back down
        if (idleTicks >= 8 && idleTicks % 4 === 0) {
          try { primary.scrollTop = Math.max(0, primary.scrollTop - 1500); } catch {}
          await new Promise((r) => setTimeout(r, 500));
          try { primary.scrollTop = primary.scrollHeight; } catch {}
        }

        await new Promise((r) => setTimeout(r, 4000));

        const newCount = collectNow();
        progress(allConnections.length, "scanning");

        console.log(
          `[SR] tick ${tickNo}: +${newCount} (total ${allConnections.length}), ` +
          `scroll ${beforeTop}→${primary.scrollTop}, height ${beforeHeight}→${primary.scrollHeight}, ` +
          `links=${document.querySelectorAll("a[href*='/in/']").length}, idle=${idleTicks}`
        );

        if (newCount === 0) idleTicks++;
        else idleTicks = 0;
      }
      console.log(`[SR] scroll done: ${tickNo} ticks, ${allConnections.length} total`);

      if (allConnections.length === 0) {
        progress(0, "error", "No connections found — are you on the connections page and logged in?");
        return;
      }

      // POST in chunks with retry
      const CHUNK = 100;
      const MAX_RETRIES = 2;
      let posted = 0;
      for (let i = 0; i < allConnections.length; i += CHUNK) {
        const batch = allConnections.slice(i, i + CHUNK);
        let ok = false;
        for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
          const res = await SR.apiPost("/linkedin/ingest/connections", { connections: batch });
          if (res?.ok) {
            ok = true;
            posted += res.data?.total_processed || batch.length;
            break;
          }
          console.warn(`[SR] batch import error (attempt ${attempt + 1}):`, res?.error);
          if (attempt < MAX_RETRIES) await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
        }
        if (!ok) console.error("[SR] DOM batch failed after retries, skipping chunk at", i);
        progress(posted, "scanning");
      }
      progress(allConnections.length, "done");
    } catch (e) {
      console.error("[SR] autoScrapeConnections error:", e);
      progress(allConnections.length, "error", String(e?.message || e));
    } finally {
      SR._autoScrapeInProgress = false;
    }
  };
})();
