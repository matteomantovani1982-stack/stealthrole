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
      const testUrl = build(0, 10);
      try {
        const res = await fetch(testUrl, { headers, credentials: "include" });
        console.log(`[SR] conn probe ${i}:`, testUrl.slice(0, 110), "→", res.status);
        if (!res.ok) continue;
        const data = await res.json();
        const topKeys = Object.keys(data || {});
        console.log(`[SR] conn probe ${i}: keys =`, topKeys.join(", "));
        if (data.paging) console.log(`[SR] conn probe ${i}: paging =`, JSON.stringify(data.paging));
        if (data.elements?.[0]) console.log(`[SR] conn probe ${i}: elements[0] =`, JSON.stringify(data.elements[0]).slice(0, 400));
        if (data.included?.[0]) console.log(`[SR] conn probe ${i}: included[0] =`, JSON.stringify(data.included[0]).slice(0, 400));

        const extracted = extractVoyagerRecords(data);
        console.log(`[SR] conn probe ${i}: extracted`, extracted.length, "records");
        if (extracted.length === 0) continue;
        return await paginateVoyager(build, headers, data);
      } catch (e) {
        console.warn(`[SR] conn probe ${i} failed:`, e.message);
      }
    }
    console.warn("[SR] voyager connections: no endpoint worked");
    return null;
  }

  async function paginateVoyager(build, headers, firstPageData) {
    const all = [];
    const BATCH = 40;
    const MAX_TOTAL = 10000;
    const seenIds = new Set();

    let extracted = extractVoyagerRecords(firstPageData);
    for (const c of extracted) {
      if (!seenIds.has(c.linkedin_id)) { seenIds.add(c.linkedin_id); all.push(c); }
    }
    console.log(`[SR] voyager conn: page 0 → ${extracted.length} records`);

    let start = BATCH;
    while (start < MAX_TOTAL) {
      const url = build(start, BATCH);
      try {
        const res = await fetch(url, { headers, credentials: "include" });
        if (!res.ok) { console.warn("[SR] voyager conn page", start, "→", res.status); break; }
        const data = await res.json();
        extracted = extractVoyagerRecords(data);
        if (extracted.length === 0) { console.log("[SR] voyager conn: end at start=", start); break; }
        let added = 0;
        for (const c of extracted) {
          if (!seenIds.has(c.linkedin_id)) { seenIds.add(c.linkedin_id); all.push(c); added++; }
        }
        console.log(`[SR] voyager conn: page ${start / BATCH} → ${extracted.length} records (${added} new, total ${all.length})`);
        if (extracted.length < BATCH) break;
        start += BATCH;
        await new Promise((r) => setTimeout(r, 400));
      } catch (e) {
        console.warn("[SR] voyager conn page", start, "error:", e.message);
        break;
      }
    }
    return all;
  }

  // ── Extract connection records from voyager response ──
  // Recursively scans for known profile field patterns.

  function extractVoyagerRecords(data) {
    const results = [];
    const seen = new Set();

    const addResult = (slug, first, last, headline) => {
      if (!slug || seen.has(slug)) return;
      seen.add(slug);
      const fullName = [first, last].filter(Boolean).join(" ").trim();
      if (!fullName) return;
      const hl = headline || "";
      let currentTitle = hl;
      let currentCompany = "";
      const m = hl.match(/^(.+?)\s+(?:at|@)\s+(.+)$/i);
      if (m) { currentTitle = m[1].trim(); currentCompany = m[2].trim(); }
      results.push({
        linkedin_id: slug,
        linkedin_url: `https://www.linkedin.com/in/${slug}/`,
        full_name: fullName,
        headline: hl,
        current_title: currentTitle,
        current_company: currentCompany,
      });
    };

    const visit = (obj) => {
      if (!obj || typeof obj !== "object") return;
      // Direct profile
      if (obj.publicIdentifier && (obj.firstName || obj.lastName)) {
        addResult(obj.publicIdentifier, obj.firstName, obj.lastName, obj.headline || obj.occupation || "");
      }
      // miniProfile nested
      if (obj.miniProfile?.publicIdentifier) {
        addResult(obj.miniProfile.publicIdentifier, obj.miniProfile.firstName, obj.miniProfile.lastName, obj.miniProfile.occupation || obj.headline || "");
      }
      // profile nested
      if (obj.profile?.publicIdentifier) {
        addResult(obj.profile.publicIdentifier, obj.profile.firstName, obj.profile.lastName, obj.profile.headline || obj.profile.occupation || "");
      }
      // connectedMember (dash model)
      if (obj.connectedMember?.publicIdentifier) {
        addResult(obj.connectedMember.publicIdentifier, obj.connectedMember.firstName, obj.connectedMember.lastName, obj.connectedMember.headline || "");
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

  // ── scrollToBottom helper ──

  async function scrollToBottom(maxDurationMs = 180000) {
    return new Promise((resolve) => {
      const started = Date.now();
      const interval = setInterval(() => {
        if (Date.now() - started > maxDurationMs) { clearInterval(interval); resolve(); return; }
        const scrollers = [document.scrollingElement || document.documentElement, document.body];
        scrollers.forEach((s) => { try { s.scrollTop = s.scrollHeight; } catch {} });
        try { window.scrollTo(0, document.body.scrollHeight); } catch {}
      }, 2500);
    });
  }

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

    try {
      console.log("[SR] attempting Voyager API…");
      const voyagerRecords = await fetchAllConnectionsViaVoyager();
      if (voyagerRecords && voyagerRecords.length > 0) {
        console.log(`[SR] Voyager returned ${voyagerRecords.length} — skipping DOM scroll`);
        progress(voyagerRecords.length, "scanning");
        const CHUNK = 100;
        let posted = 0;
        for (let i = 0; i < voyagerRecords.length; i += CHUNK) {
          const batch = voyagerRecords.slice(i, i + CHUNK);
          const res = await SR.apiPost("/linkedin/ingest/connections", { connections: batch });
          if (!res?.ok) console.warn("[SR] voyager batch error:", res?.error);
          posted += batch.length;
          progress(posted, "scanning");
        }
        progress(voyagerRecords.length, "done");
        SR._autoScrapeInProgress = false;
        return;
      }
      console.warn("[SR] Voyager did not return data — falling back to DOM scroll");
    } catch (e) {
      console.error("[SR] Voyager attempt errored:", e);
    }

    // ── DOM scroll fallback ──

    console.log("[SR] starting DOM scroll fallback");
    progress(0, "scanning");

    const seen = new Set();
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

      // POST in chunks
      const CHUNK = 100;
      let posted = 0;
      for (let i = 0; i < allConnections.length; i += CHUNK) {
        const batch = allConnections.slice(i, i + CHUNK);
        const res = await SR.apiPost("/linkedin/ingest/connections", { connections: batch });
        if (!res?.ok) console.warn("[SR] batch import error:", res?.error);
        posted += batch.length;
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
