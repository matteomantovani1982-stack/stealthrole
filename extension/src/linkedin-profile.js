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
    // Strategy 1: CSS selectors (LinkedIn changes these frequently)
    const selectors = [
      "h1.text-heading-xlarge",
      ".pv-text-details__left-panel h1",
      "h1.break-words",
      ".text-heading-xlarge",
      "[data-generated-suggestion-target]",
      "main h1",
      "h1",
      ".artdeco-entity-lockup__title",
      "[aria-label*='profile'] h1",
    ];
    for (const sel of selectors) {
      try {
        const el = document.querySelector(sel);
        if (el) {
          const name = (el.innerText || el.textContent || "").trim().split("\n")[0].trim();
          if (name.length > 1 && name.length < 80 && !/linkedin/i.test(name)) return name;
        }
      } catch {}
    }
    // Strategy 2: og:title meta tag
    const ogTitle = document.querySelector('meta[property="og:title"]');
    if (ogTitle) {
      const content = ogTitle.getAttribute("content") || "";
      const dashIdx = content.indexOf(" - ");
      const name = dashIdx > 0 ? content.substring(0, dashIdx).trim() : content.replace(/\s*\|.*$/, "").trim();
      if (name.length > 1 && name.length < 80 && !/linkedin/i.test(name)) return name;
    }
    // Strategy 3: document.title — handles both "Name - Title | LinkedIn" and "Name | LinkedIn"
    const title = document.title || "";
    if (title.includes("LinkedIn")) {
      // Try "Name - Title | LinkedIn" first
      const dashIdx = title.indexOf(" - ");
      if (dashIdx > 0) {
        const name = title.substring(0, dashIdx).trim();
        if (name.length > 1 && name.length < 80 && !/linkedin/i.test(name)) return name;
      }
      // Try "Name | LinkedIn" format
      const pipeIdx = title.indexOf(" | ");
      if (pipeIdx > 0) {
        const name = title.substring(0, pipeIdx).trim();
        if (name.length > 1 && name.length < 80 && !/linkedin/i.test(name)) return name;
      }
    }
    // Strategy 4: Parse from <main> textContent — LinkedIn 2025+ renders name as first text
    // Pattern: "  Name· 1st· 2nd..." or "  Name· 2nd..."
    const mainEl = document.querySelector("main");
    if (mainEl) {
      const mainText = (mainEl.textContent || "").trim();
      // Name is the first text before "·" or degree marker
      const dotMatch = mainText.match(/^(.+?)(?:\s*·|\s*(?:1st|2nd|3rd)\b)/);
      if (dotMatch) {
        const name = dotMatch[1].trim();
        if (name.length > 1 && name.length < 80 && !/linkedin/i.test(name)) {
          console.log(`[SR] getProfileName: extracted from <main> text: '${name}'`);
          return name;
        }
      }
    }
    console.log("[SR] getProfileName: ALL methods failed");
    return "";
  }

  function getProfileHeadline() {
    // Strategy 1: CSS selectors. Use innerText (not textContent) so that
    // separate DOM elements aren't fused into a single string. textContent
    // turns "Director of Operations" + "NEOM" into "Director of OperationsNEOM"
    // which then breaks downstream company extraction.
    const selectors = [
      // Modern LinkedIn 2024-2025 — headline lives in the top-card lockup
      ".pv-text-details__left-panel .text-body-medium.break-words",
      ".pv-text-details__left-panel .text-body-medium",
      ".artdeco-entity-lockup__subtitle",
      ".text-body-medium.break-words",
      ".text-body-medium",
      "[data-generated-suggestion-target] + div",
    ];
    for (const sel of selectors) {
      try {
        const el = document.querySelector(sel);
        if (el) {
          // innerText preserves layout-induced whitespace between block-level
          // descendants, which textContent does not.
          const raw = (el.innerText || el.textContent || "").trim();
          const text = raw.replace(/\s+/g, " ");
          if (text.length > 1 && text.length < 300 && !/^\d+\s+(?:connections?|followers?)/i.test(text)) {
            return text;
          }
        }
      } catch {}
    }
    // Strategy 2: og:title meta → "Name - Headline | LinkedIn"
    const ogTitle = document.querySelector('meta[property="og:title"]');
    if (ogTitle) {
      const content = ogTitle.getAttribute("content") || "";
      const dashIdx = content.indexOf(" - ");
      if (dashIdx > 0) {
        const headline = content.substring(dashIdx + 3).replace(/\s*\|.*$/, "").trim();
        if (headline.length > 1) return headline;
      }
    }
    // Strategy 3: document.title → "Name - Headline | LinkedIn"
    const title = document.title || "";
    const titleDash = title.indexOf(" - ");
    if (titleDash > 0) {
      const headline = title.substring(titleDash + 3).replace(/\s*\|.*$/, "").trim();
      if (headline.length > 1 && !/linkedin/i.test(headline)) return headline;
    }
    // Strategy 4: Parse from <main>. Use innerText so that separate
    // experience-row elements get a newline between them — that's what lets
    // us isolate the headline from the company/school/location lines below.
    const mainEl = document.querySelector("main");
    if (mainEl) {
      const mainTextRaw = (mainEl.innerText || mainEl.textContent || "").trim();
      // The headline is on its own line, right after the degree marker line.
      const lines = mainTextRaw
        .split(/\n+/)
        .map((s) => s.trim())
        .filter((s) => s.length > 0);
      // Find the first line that contains "1st"/"2nd"/"3rd" — the headline
      // line is usually 1–3 lines after it (skipping pronouns / "She/Her" etc).
      const degreeIdx = lines.findIndex((l) => /\b(?:1st|2nd|3rd)\b/i.test(l));
      if (degreeIdx >= 0) {
        for (let i = degreeIdx + 1; i < Math.min(degreeIdx + 6, lines.length); i++) {
          const candidate = lines[i].replace(/\s+/g, " ").trim();
          if (candidate.length < 4 || candidate.length > 300) continue;
          // Skip lines that look like pronouns, location, follower count, contact info
          if (/^\(?(?:she|he|they)\/(?:her|him|them)\)?$/i.test(candidate)) continue;
          if (/^\d{1,3}(?:,\d{3})*\s+(?:followers?|connections?|mutual)/i.test(candidate)) continue;
          if (/^contact info$/i.test(candidate)) continue;
          if (/^(?:university|school|college|institute)/i.test(candidate)) continue;
          if (/^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s+[A-Z]/.test(candidate) && !/[|·•]/.test(candidate)) {
            // Looks like "City, Country, Region" line
            continue;
          }
          console.log(`[SR] getProfileHeadline: extracted from <main> innerText: '${candidate}'`);
          return candidate;
        }
      }
      // Last-ditch fallback: the OLD broken text-scan, kept only because some
      // exotic profiles render entirely without newlines. Mark it clearly.
      const mainText = (mainEl.textContent || "").trim();
      const degreeMatch = mainText.match(/(?:1st|2nd|3rd)\s*(?:·\s*(?:1st|2nd|3rd)\s*)*(.+?)(?:(?:University|School|College|Institute|\d{1,3}(?:,\d{3})*\s*followers|Contact info|·\s*Contact))/i);
      if (degreeMatch) {
        const headline = degreeMatch[1].trim();
        if (headline.length > 3 && headline.length < 300) {
          console.log(`[SR] getProfileHeadline: FALLBACK textContent (may be fused): '${headline}'`);
          return headline;
        }
      }
    }
    // Strategy 5: meta description
    const meta = document.querySelector('meta[name="description"]');
    if (meta) {
      const desc = (meta.getAttribute("content") || "").trim().slice(0, 200);
      if (desc.length > 1) return desc;
    }
    return "";
  }

  /** True when LinkedIn lists shared connections (often still shows a misleading "3rd" badge). */
  function pageShowsMutualConnectionsHint() {
    try {
      const main = document.querySelector("main");
      if (!main) return false;
      const t = (main.innerText || main.textContent || "").toLowerCase();
      if (/\band\s+\d+\s+other\s+mutual\s+connections?\b/.test(t)) return true;
      if (/\d+\s+other\s+mutual\s+connections?\b/.test(t)) return true;
      if (/\bmutual\s+connections?\b/.test(t)) {
        if (main.querySelector('a[href*="mutual"], a[href*="Mutual"], a[href*="sharedConnections"]'))
          return true;
      }
    } catch {}
    return false;
  }

  function withMutualConnectionsDegreeFix(degree) {
    if (degree === 1) return 1;
    if ((degree === 3 || degree === null) && pageShowsMutualConnectionsHint()) {
      console.log("[SR] degree: mutual connections visible on page → 2nd");
      return 2;
    }
    return degree;
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
        if (/^[123](st|nd|rd)$/i.test(t)) return withMutualConnectionsDegreeFix(parseInt(t[0], 10));
        const m = t.match(/(\d)\s*(?:st|nd|rd)/i);
        if (m) return withMutualConnectionsDegreeFix(parseInt(m[1], 10));
      }
    }
    // Broader scan: any small element containing just "1st", "2nd", "3rd"
    for (const el of document.querySelectorAll("span, div, li")) {
      const t = (el.textContent || "").trim();
      if (t.length > 10) continue; // skip large text blocks
      if (/^[123]\s*(?:st|nd|rd)$/i.test(t)) return withMutualConnectionsDegreeFix(parseInt(t[0], 10));
    }
    // Last resort: search aria-labels and title attributes
    for (const el of document.querySelectorAll("[aria-label], [title]")) {
      const label = (el.getAttribute("aria-label") || el.getAttribute("title") || "").toLowerCase();
      if (label.includes("1st degree")) return withMutualConnectionsDegreeFix(1);
      if (label.includes("2nd degree")) return withMutualConnectionsDegreeFix(2);
      if (label.includes("3rd degree")) return withMutualConnectionsDegreeFix(3);
    }
    // Fallback: parse from <main> text — LinkedIn 2025+ embeds "· 1st" / "· 2nd" in text
    const mainEl = document.querySelector("main");
    if (mainEl) {
      const mainText = (mainEl.textContent || "").substring(0, 300);
      if (/·\s*1st\b/i.test(mainText)) return withMutualConnectionsDegreeFix(1);
      if (/·\s*2nd\b/i.test(mainText)) return withMutualConnectionsDegreeFix(2);
      if (/·\s*3rd\b/i.test(mainText)) return withMutualConnectionsDegreeFix(3);
    }
    return withMutualConnectionsDegreeFix(null);
  }

  function getCompanyFromPage() {
    const SCHOOL_RE = /\b(university|college|institute|school|academy|polytechnic|heriot[- ]watt|insead|wharton|kellogg|cambridge|oxford)\b/i;
    const TITLE_WORDS_RE = /\b(manager|director|vp|ceo|coo|cfo|cto|head|lead|senior|specialist|analyst|engineer|consultant|partner|founder|president|architect|designer|advisor|principal|operations|strategy)\b/i;
    const NOISE_RE = /^(?:follow|see all|see more|see less|connect|message|premium|sponsored)$|people you may|jobs you may|recommended for you/i;

    function _isPlausibleCompany(text) {
      if (!text || text.length < 2 || text.length > 60) return false;
      if (NOISE_RE.test(text)) return false;
      if (SCHOOL_RE.test(text)) return false;
      if (/\d+[dwmhys]\s*[·•]/.test(text)) return false;
      if (text.includes("\n")) return false;
      return true;
    }

    // 0. PRIMARY: schema.org structured data (`worksFor.name`).
    //    LinkedIn embeds an <script type="application/ld+json"> blob that has
    //    the canonical "Person" graph for the profile, including jobTitle and
    //    worksFor — this is the most reliable signal because it's machine-
    //    readable and not affected by lazy-loading the experience section.
    //    We try this BEFORE any DOM scraping because it works even when the
    //    user hasn't scrolled past the top card.
    for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const json = JSON.parse(script.textContent || "");
        // The blob may be a single Person object, an array of objects, or
        // an @graph wrapper.
        const candidates = Array.isArray(json) ? json : json["@graph"] || [json];
        for (const obj of candidates) {
          if (!obj || obj["@type"] !== "Person") continue;
          const wf = obj.worksFor;
          // worksFor can be an Organization object or an array of them.
          const orgs = Array.isArray(wf) ? wf : (wf ? [wf] : []);
          for (const org of orgs) {
            const name = (org?.name || "").trim();
            if (_isPlausibleCompany(name)) {
              console.log(`[SR] getCompanyFromPage: from ld+json worksFor: '${name}'`);
              return name;
            }
          }
        }
      } catch {}
    }

    // 0b. <code> JSON blocks. LinkedIn embeds normalized voyager models in
    //     <code> tags. The target's Position entries carry a "companyName"
    //     field. Find one whose surrounding entity references the target's
    //     publicIdentifier (URL slug) and return its companyName.
    const targetSlug = ((window.location.pathname.match(/\/in\/([^/?#]+)/) || [])[1] || "").toLowerCase();
    if (targetSlug) {
      for (const code of document.querySelectorAll("code")) {
        const text = code.textContent || "";
        if (!text || text.length < 200) continue;
        if (!text.includes(targetSlug)) continue;
        // Look for a "companyName":"X" field inside this block. Prefer the
        // FIRST occurrence — LinkedIn orders positions by recency, so the
        // first companyName near the profile entity is the current employer.
        const m = text.match(/"companyName"\s*:\s*"([^"]{2,60})"/);
        if (m && _isPlausibleCompany(m[1])) {
          console.log(`[SR] getCompanyFromPage: from <code> companyName: '${m[1]}'`);
          return m[1];
        }
      }
    }

    // Find the actual Experience section by anchor (modern LinkedIn pattern:
    // <div id="experience"> followed by the section). This is much tighter
    // than ".closest('section')" which would also match sidebar / sponsored
    // / "People also viewed" / "Cityscape Global" ad blocks.
    function _findExperienceSection() {
      const anchor = document.getElementById("experience");
      if (anchor) {
        // The experience content is the next <section> sibling (or its closest
        // ancestor section that contains the anchor).
        let el = anchor.nextElementSibling;
        while (el && el.tagName && el.tagName.toLowerCase() !== "section") {
          el = el.nextElementSibling;
        }
        if (el) return el;
        return anchor.parentElement?.closest("section") || null;
      }
      // Fallback: find a section whose first heading text equals "Experience".
      for (const section of document.querySelectorAll("section")) {
        const heading = section.querySelector("h2, .pvs-header__title, [class*='header__title']");
        const txt = (heading?.innerText || heading?.textContent || "").trim().toLowerCase();
        if (txt === "experience" || txt.startsWith("experience")) return section;
      }
      return null;
    }

    // 1. PREFERRED: /company/<slug>/ link inside the actual Experience section
    //    (anchored by the #experience div). The CURRENT job is always the
    //    FIRST entry in the section, so we take the first plausible link.
    const expSection = _findExperienceSection();
    if (expSection) {
      for (const link of expSection.querySelectorAll("a[href*='/company/']")) {
        const text = (link.innerText || link.textContent || "").trim().split("\n")[0].trim();
        if (_isPlausibleCompany(text)) return text;
      }
    }

    // 2. Headline parse — when the experience section can't give us a clean
    //    answer, fall back to the headline. Modern LinkedIn 2024-2025
    //    headlines use "Title | Company | Location" or "Title at Company".
    //    Some profiles use "<Title> of <Company>" (e.g. "Sport Director of
    //    Neom SC") — we handle that via a brand-like-noun heuristic too.
    const headline = getProfileHeadline();
    if (headline) {
      // 2a. "Title at Company" pattern
      const atMatch = headline.match(/\bat\s+(.+?)(?:\s*[|·•,]|$)/i);
      if (atMatch) {
        const company = atMatch[1].trim();
        if (_isPlausibleCompany(company)) return company;
      }
      // 2b. Pipe-separated: "Title | Company | Location"
      const segments = headline.split(/[|·•]/).map((s) => s.trim()).filter((s) => s.length > 1);
      if (segments.length >= 2) {
        for (let i = 1; i < segments.length; i++) {
          const seg = segments[i];
          if (TITLE_WORDS_RE.test(seg)) continue;
          if (!_isPlausibleCompany(seg)) continue;
          if (/^\d/.test(seg)) continue;
          return seg;
        }
      }
      // 2c. "<Title-like prefix> of <Brand>" — e.g. "Sport Director of Neom SC"
      //     Only accept when the right-hand side is short, capitalized, and
      //     doesn't look like a generic role descriptor ("of Marketing" is
      //     a title fragment, "of Neom SC" is a company).
      const firstSeg = segments[0] || headline;
      const ofMatch = firstSeg.match(/\bof\s+([A-Z][A-Za-z0-9&.'\-\s]{1,40})$/);
      if (ofMatch) {
        const candidate = ofMatch[1].trim();
        const looksLikeRole = /\b(marketing|sales|engineering|operations|product|finance|hr|people|growth|design|strategy|technology|business|content)\b/i.test(candidate);
        if (!looksLikeRole && _isPlausibleCompany(candidate)) {
          return candidate;
        }
      }
    }

    // 3. og:title / document.title — multiple LinkedIn formats:
    //    "Name - Title at Company | LinkedIn"
    //    "Name - Title - Company | LinkedIn"        (dash separator)
    //    "Name | LinkedIn"                          (no company info)
    function _companyFromTitle(content) {
      if (!content) return "";
      // Strip the trailing " | LinkedIn"
      const head = content.replace(/\s*\|\s*LinkedIn\s*$/i, "").trim();
      // Pattern A: "...at Company"
      const atMatch = head.match(/\bat\s+(.+?)$/i);
      if (atMatch) {
        const company = atMatch[1].replace(/\s*\|.*$/, "").trim();
        if (_isPlausibleCompany(company)) return company;
      }
      // Pattern B: "Name - Title - Company"   (last dash-segment is the company)
      //   Some profiles render with " - " separator and the company is the
      //   final segment. Take the LAST segment if it looks like a company.
      const dashSegments = head.split(/\s+[-–—]\s+/).map((s) => s.trim()).filter(Boolean);
      if (dashSegments.length >= 3) {
        const last = dashSegments[dashSegments.length - 1];
        if (_isPlausibleCompany(last) && !TITLE_WORDS_RE.test(last)) return last;
      }
      // Pattern C: "Name | Company | Location" — pipe separator inside title
      const pipeSegments = head.split(/\s*\|\s*/).map((s) => s.trim()).filter(Boolean);
      if (pipeSegments.length >= 2) {
        for (let i = 1; i < pipeSegments.length; i++) {
          const seg = pipeSegments[i];
          if (TITLE_WORDS_RE.test(seg)) continue;
          if (_isPlausibleCompany(seg)) return seg;
        }
      }
      return "";
    }

    const ogTitleEl = document.querySelector('meta[property="og:title"]');
    const ogTitle = ogTitleEl?.getAttribute("content") || "";
    const fromOg = _companyFromTitle(ogTitle);
    if (fromOg) return fromOg;
    const fromDoc = _companyFromTitle(document.title || "");
    if (fromDoc) return fromDoc;

    // 4. Last-ditch: any /company/ link, but only inside the main profile
    //    column — never the right rail / "People also viewed" sidebar where
    //    sponsored ads bleed in.
    const mainColumn = document.querySelector("main") || document.body;
    for (const link of mainColumn.querySelectorAll("a[href*='/company/']")) {
      if (link.closest("aside, [class*='sponsored'], [class*='right-rail'], [class*='also-viewed']")) {
        continue;
      }
      const text = (link.innerText || link.textContent || "").trim().split("\n")[0].trim();
      if (_isPlausibleCompany(text)) return text;
    }

    return "";
  }

  // ── Unified profile scraper (returns Promise) ──

  // LinkedIn's experience section is lazy-loaded — it's not in the DOM on
  // first paint. If we extract company before scrolling, getCompanyFromPage()
  // returns "" and the connection is saved without its current employer,
  // which then breaks Way In matching ("Terry doesn't appear at NEOM"
  // because his connection row has company=""). Scroll once before reading.
  async function _ensureExperienceLoaded() {
    if (document.getElementById("experience")) return;
    try {
      const before = window.scrollY;
      window.scrollTo(0, Math.min(document.body.scrollHeight, 1200));
      // Wait for lazy section to mount
      for (let i = 0; i < 6; i++) {
        await new Promise((r) => setTimeout(r, 250));
        if (document.getElementById("experience")) break;
      }
      try { window.scrollTo(0, before); } catch {}
    } catch {}
  }

  SR.scrapeProfile = function () {
    return new Promise(async (resolve) => {
      const url = window.location.href.split("?")[0];
      const linkedinId = (url.match(/\/in\/([^/?#]+)/) || [])[1]?.replace(/\/$/, "") || "";
      const fullName = getProfileName();
      const headline = getProfileHeadline();
      const degree = getConnectionDegree();
      let currentCompany = getCompanyFromPage();

      // If we couldn't extract a company on first try, the experience section
      // is probably still being lazy-loaded. Force-scroll once and re-extract.
      if (!currentCompany) {
        await _ensureExperienceLoaded();
        currentCompany = getCompanyFromPage();
        if (currentCompany) {
          console.log(`[SR] scrapeProfile: recovered company after lazy-load: '${currentCompany}'`);
        }
      }

      let currentTitle = headline;
      const atMatch = headline.match(/^(.+?)\s+(?:at|@)\s+(.+)/i);
      if (atMatch) currentTitle = atMatch[1].trim();

      console.log(`[SR] scrapeProfile: name='${fullName}' title='${currentTitle}' company='${currentCompany}' degree=${degree}`);
      SR._lastScrapedProfile = { linkedinId, fullName, headline, currentTitle, currentCompany, url };
      SR._lastScrapedDegree = degree;
      if (!fullName || !linkedinId) { console.warn("[SR] scrapeProfile: missing name or ID, skipping API call"); resolve(); return; }

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
   *
   * IMPORTANT: A profile page contains BOTH the target's URN (in the top card,
   * profile JSON) AND the visiting user's OWN URN (in nav, messaging widget,
   * notifications, recent posts). The viewer's URN often appears MORE often
   * than the target's. Naively picking the most-common URN therefore returns
   * the SELF URN — and the Voyager mutual search becomes "your connections of
   * yourself" which is empty. That's the root cause of "scrapes 0 mutuals".
   *
   * Resolution order:
   *   1. <code> JSON entry whose publicIdentifier == the URL slug (target only)
   *   2. mutual-connections link href (always a target-specific URN)
   *   3. HTML scan with self URN excluded
   *   4. Voyager identity API
   */
  async function resolveProfileUrn(linkedinId) {
    const myUrnSuffix = (SR._myProfileUrn || "").split(":").pop() || "";
    const myPublicId = (SR._myPublicId || "").toLowerCase();
    const targetSlug = (linkedinId || "").toLowerCase();

    // ── Source 1: <code> tag JSON whose publicIdentifier matches the URL slug ──
    // LinkedIn embeds normalized models in <code> tags. The TARGET's entry has
    // publicIdentifier == the slug from /in/<slug>. Anchor on that to skip
    // the viewer's own profile JSON which is also embedded.
    for (const code of document.querySelectorAll("code")) {
      const text = code.textContent || "";
      if (!text || text.length < 100) continue;

      // Match a JSON object that contains BOTH publicIdentifier=<slug> AND
      // an entityUrn for that same record. \s\S* allows other fields between.
      const slugRe = new RegExp(
        `"publicIdentifier"\\s*:\\s*"${targetSlug.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")}"[\\s\\S]{0,2000}?"entityUrn"\\s*:\\s*"(urn:li:(?:fsd_profile|fs_miniProfile):[^"]+)"`,
        "i",
      );
      const slugMatch = text.match(slugRe);
      if (slugMatch && !slugMatch[1].endsWith(myUrnSuffix)) {
        console.log("[SR] URN from <code> publicIdentifier match:", slugMatch[1]);
        return slugMatch[1];
      }

      // Reverse order: entityUrn before publicIdentifier
      const slugReRev = new RegExp(
        `"entityUrn"\\s*:\\s*"(urn:li:(?:fsd_profile|fs_miniProfile):[^"]+)"[\\s\\S]{0,2000}?"publicIdentifier"\\s*:\\s*"${targetSlug.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")}"`,
        "i",
      );
      const slugMatchRev = text.match(slugReRev);
      if (slugMatchRev && !slugMatchRev[1].endsWith(myUrnSuffix)) {
        console.log("[SR] URN from <code> publicIdentifier match (reverse):", slugMatchRev[1]);
        return slugMatchRev[1];
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
        return m[1]; // raw profile ID like "ACoAAAxxxxxx"
      }
    }

    // ── Source 3: HTML scan with self URN excluded ──
    const bodyHtml = document.documentElement.innerHTML.slice(0, 500000);
    const allUrns = [...bodyHtml.matchAll(/urn:li:fsd_profile:([A-Za-z0-9_-]+)/g)];
    if (allUrns.length > 0) {
      const counts = {};
      for (const m of allUrns) {
        if (myUrnSuffix && m[1] === myUrnSuffix) continue; // skip self
        counts[m[1]] = (counts[m[1]] || 0) + 1;
      }
      const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
      if (sorted.length > 0) {
        const urn = `urn:li:fsd_profile:${sorted[0][0]}`;
        console.log(`[SR] URN from HTML scan (self excluded): ${urn} (appeared ${sorted[0][1]}x, ${sorted.length} candidates)`);
        return urn;
      }
      console.warn("[SR] HTML scan: only self URN found, no candidates");
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

    // CRITICAL: ensure SR._myProfileUrn is populated before resolving.
    // Otherwise resolveProfileUrn can't exclude the visiting user's own URN
    // and may return self → Voyager search returns nothing useful.
    if (!SR._myProfileUrn && SR.fetchMyProfile) {
      try { await SR.fetchMyProfile(); } catch {}
    }

    SR.showToast("Resolving profile…");
    const profileUrn = await resolveProfileUrn(linkedinId);
    if (!profileUrn) {
      console.warn("[SR mutuals] resolveProfileUrn returned null for", linkedinId);
      return null;
    }
    console.log("[SR mutuals] Resolved target URN:", profileUrn, "(self URN:", SR._myProfileUrn || "unknown", ")");

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
    const linkedinId = (url.match(/\/in\/([^/?#]+)/) || [])[1]?.replace(/\/$/, "") || "";
    if (!linkedinId) return;

    // Use cached profile data from scrapeProfile (DOM may have changed since then)
    const cached = SR._lastScrapedProfile || {};
    const isSameProfile = linkedinId && cached.linkedinId && cached.linkedinId === linkedinId;
    const targetName = isSameProfile && cached.fullName ? cached.fullName : getProfileName();
    const targetHeadline = isSameProfile && cached.headline ? cached.headline : getProfileHeadline();
    const targetCompany = isSameProfile && cached.currentCompany ? cached.currentCompany : getCompanyFromPage();
    let targetTitle = isSameProfile && cached.currentTitle ? cached.currentTitle : targetHeadline;
    if (!isSameProfile || !cached.currentTitle) {
      const atMatch = targetHeadline.match(/^(.+?)\s+(?:at|@)\s+(.+)/i);
      if (atMatch) targetTitle = atMatch[1].trim();
    }

    console.log(`[SR] scrapeMutualConnections: name='${targetName}' company='${targetCompany}' id=${linkedinId} (cached=${isSameProfile})`);

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
      const t0 = Date.now();
      const trace = (...args) => console.log(`[SR mutuals +${Date.now() - t0}ms]`, ...args);
      try {
        // ── Step 0: Force-load the lazy section ──
        // The "X mutual connections" link is in the right rail (or under "About")
        // and LinkedIn doesn't render it until you scroll past the top card.
        // Without this, findMutualConnectionsLink() polls a non-existent link
        // for 10s and gives up. Scroll once, wait, scroll back.
        trace("step 0: scrolling to surface lazy-loaded mutual section");
        try {
          window.scrollTo({ top: Math.floor(document.body.scrollHeight * 0.4), behavior: "instant" });
          await new Promise(r => setTimeout(r, 800));
          window.scrollTo({ top: Math.floor(document.body.scrollHeight * 0.7), behavior: "instant" });
          await new Promise(r => setTimeout(r, 800));
          window.scrollTo({ top: 0, behavior: "instant" });
        } catch {}

        // ── Step 1: Wait for the mutual connections section to render ──
        SR.showToast("Looking for mutual connections…");
        let mutualLink = null;
        for (let i = 0; i < 10; i++) {
          await new Promise(r => setTimeout(r, 1000));
          mutualLink = findMutualConnectionsLink();
          if (mutualLink) {
            trace(`step 1: mutual link found after ${i + 1}s →`, mutualLink.href?.substring(0, 80));
            break;
          }
        }
        if (!mutualLink) trace("step 1: NO mutual link found after 10s polling");

        // ── Step 2: Try Voyager API using URN from the link or page ──
        // Fast and doesn't navigate. Will try multiple URN sources internally.
        trace("step 2: trying Voyager API");
        try {
          const voyagerMutuals = await fetchMutualsViaVoyager(linkedinId);
          if (voyagerMutuals && voyagerMutuals.length > 0) {
            trace(`step 2: Voyager returned ${voyagerMutuals.length} mutuals`);
            SR.showToast(`Found ${voyagerMutuals.length} mutual connections — syncing`);
            sendMutualData(targetPerson, voyagerMutuals, voyagerMutuals.length);
            return;
          }
          trace("step 2: Voyager returned 0 mutuals");
        } catch (e) {
          trace("step 2: Voyager threw:", e.message);
        }

        // ── Step 3: Click through to search results ──
        // Navigates away. The search results page triggers scrapeMutualSearchResults()
        // via initForPage → sr_mutual_target. We attach the expected count and
        // visible names parsed from the profile link text so the search-results
        // scraper can cap output at the real mutual count instead of including
        // "People you may also know" recommendations from below the fold.
        if (mutualLink) {
          const linkText = (mutualLink.innerText || mutualLink.textContent || "").trim();
          const meta = parseMutualLinkMeta(linkText);
          targetPerson.expected_mutual_count = meta.expectedCount;
          targetPerson.visible_mutual_names = meta.visibleNames;
          trace(`step 3: clicking mutual link → expected_count=${meta.expectedCount} visible=${meta.visibleNames.join(", ") || "(none)"}`);
          SR.showToast("Opening mutual connections list…");
          // storage.local.set is async — wait for the callback before navigating.
          chrome.storage.local.set({ sr_mutual_target: targetPerson }, () => {
            trace("step 3: sr_mutual_target saved, clicking link in 200ms");
            setTimeout(() => {
              chrome.storage.local.get("sr_mutual_target", (check) => {
                if (check.sr_mutual_target) {
                  trace("step 3: verified sr_mutual_target in storage, navigating");
                } else {
                  console.warn("[SR mutuals] sr_mutual_target NOT in storage after set — retrying once");
                  chrome.storage.local.set({ sr_mutual_target: targetPerson });
                }
                mutualLink.click();
              });
            }, 200);
          });
          return;
        }

        // ── Step 4: Visible mutuals from DOM as last resort ──
        const visibleMutuals = scrapeVisibleMutuals();
        if (visibleMutuals.length > 0) {
          trace(`step 4: scraped ${visibleMutuals.length} visible mutual names from DOM`);
          SR.showToast(`Found ${visibleMutuals.length} mutual connections — syncing`);
          sendMutualData(targetPerson, visibleMutuals, visibleMutuals.length);
          return;
        }

        trace("ALL strategies failed → 0 mutuals");
        console.warn(
          "[SR mutuals] Diagnosis: profile=", targetName,
          " | link found=", !!mutualLink,
          " | self URN known=", !!SR._myProfileUrn,
          " | visible mutual text patterns=", scrapeVisibleMutuals().length,
          " — if you see this often, paste this whole log block to the dev",
        );
        SR.showToast("No mutual connections found for " + (targetName || "this profile"));
      } catch (e) {
        console.error("[SR mutuals] uncaught error:", e);
      } finally {
        SR._mutualScrapeInProgress = false;
      }
    })();
  };

  /**
   * Parse "Foo, Bar and N other mutual connections" or
   * "Foo and Bar are mutual connections" into a structured count + name list.
   * The count from this text is the GROUND TRUTH for how many mutuals exist —
   * the search-results page that opens when you click the link almost always
   * pads the list with "People you may also know" recommendations underneath
   * the actual mutuals (LinkedIn 2024-2025 change). Without the count, we
   * over-collect those recommendations as fake mutual rows.
   */
  function parseMutualLinkMeta(text) {
    if (!text) return { expectedCount: 0, visibleNames: [] };
    const t = text.trim();
    // "Foo, Bar and N other mutual connection(s)"
    const mOther = t.match(/^(.+?)\s+and\s+(\d+)\s+other\s+mutual\s+connect/i);
    if (mOther) {
      const named = mOther[1].split(/\s*,\s*|\s+and\s+/).map((s) => s.trim()).filter(Boolean);
      return { expectedCount: named.length + parseInt(mOther[2], 10), visibleNames: named };
    }
    // "Foo and Bar are mutual connections"
    const mAre = t.match(/^(.+?)\s+(?:and|,)\s+(.+?)\s+are\s+mutual/i);
    if (mAre) {
      return { expectedCount: 2, visibleNames: [mAre[1].trim(), mAre[2].trim()] };
    }
    // "Foo is a mutual connection"
    const mIs = t.match(/^(.+?)\s+is\s+a?\s*mutual/i);
    if (mIs) {
      return { expectedCount: 1, visibleNames: [mIs[1].trim()] };
    }
    // "N mutual connections" with no names
    const mN = t.match(/^(\d+)\s+mutual\s+connect/i);
    if (mN) {
      return { expectedCount: parseInt(mN[1], 10), visibleNames: [] };
    }
    return { expectedCount: 0, visibleNames: [] };
  }
  // Expose for the search-results scraper.
  SR.parseMutualLinkMeta = parseMutualLinkMeta;

  function findMutualConnectionsLink() {
    // 1. Best: href-based selectors (most reliable)
    const hrefSelectors = [
      "a[href*='facetConnectionOf']",
      "a[href*='facetNetwork'][href*='F']",  // LinkedIn sometimes uses network facet
      "a[href*='mutual']",
      "a[href*='shared']",
    ];
    for (const sel of hrefSelectors) {
      const links = document.querySelectorAll(sel);
      for (const link of links) {
        if (link.offsetParent !== null) {
          console.log("[SR] Found mutual link via href:", link.href?.substring(0, 80));
          return link;
        }
      }
    }
    // 2. Text-based search — broader patterns
    for (const el of document.querySelectorAll("a, button, span[role='link']")) {
      const text = (el.innerText || el.textContent || "").toLowerCase().trim();
      if (el.offsetParent === null) continue;
      if (
        (text.includes("mutual") && (text.includes("connection") || text.includes("contact"))) ||
        (text.includes("who you") && text.includes("know")) ||
        /\d+\s+(?:other\s+)?mutual/.test(text)
      ) {
        console.log("[SR] Found mutual link via text:", text.substring(0, 60));
        return el;
      }
    }
    console.log("[SR] No mutual connections link found");
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

      let retryCount = 0;
      const MAX_RETRIES = 5;
      const expectedCount = Number(targetPerson.expected_mutual_count) || 0;
      const visibleNames = (targetPerson.visible_mutual_names || []).map((n) => n.toLowerCase().trim()).filter(Boolean);

      // Cap output at the actual mutual count from the profile-page link text.
      // Without this cap LinkedIn's "People you may also know" recommendations
      // (rendered below the real mutuals on the search page) get scraped too
      // and saved as fake MutualConnection rows. The link-text count is
      // authoritative ("Filip, Nadeer and 1 other mutual connection" → 3),
      // so we cap at exactly that — no buffer, no floor.
      function applyMutualCap(rawResults) {
        if (!rawResults?.length) return [];
        // Always trust visible-name matches first — those are confirmed mutuals
        // from the profile page. Then fill remaining slots from the search list.
        const out = [];
        const seen = new Set();
        const matchesVisible = (name) => {
          if (!visibleNames.length) return false;
          const lower = (name || "").toLowerCase();
          return visibleNames.some((v) => lower.includes(v) || lower.startsWith(v.split(" ")[0] || ""));
        };
        for (const r of rawResults) {
          if (!matchesVisible(r.name)) continue;
          const key = (r.linkedin_id || r.name || "").toLowerCase();
          if (seen.has(key)) continue;
          seen.add(key);
          out.push(r);
        }
        const cap = expectedCount > 0 ? expectedCount : rawResults.length;
        for (const r of rawResults) {
          if (out.length >= cap) break;
          const key = (r.linkedin_id || r.name || "").toLowerCase();
          if (seen.has(key)) continue;
          seen.add(key);
          out.push(r);
        }
        return out;
      }

      function scrapePage() {
        const rawResults = SR.scrapeSearchResultCards?.() || [];
        const results = applyMutualCap(rawResults);
        console.log(
          "[SR] Mutual search page:", rawResults.length, "raw →", results.length,
          "kept (expected:", expectedCount, ", retry", retryCount + ")"
        );

        if (rawResults.length === 0 && retryCount < MAX_RETRIES) {
          retryCount++;
          console.log("[SR] No results yet, retrying in 2s (attempt", retryCount, "of", MAX_RETRIES + ")");
          setTimeout(scrapePage, 2000);
          return;
        }

        if (results.length === 0) {
          console.warn("[SR] No mutual search results found after", MAX_RETRIES, "retries");
          SR.showToast("Could not find mutual connections on this page");
          return;
        }

        function scrollDown() {
          try { window.scrollTo(0, document.body.scrollHeight); } catch {}
          setTimeout(() => {
            const moreRaw = SR.scrapeSearchResultCards?.() || [];
            const more = applyMutualCap(moreRaw);
            const finalResults = more.length > results.length ? more : results;
            sendMutualData(targetPerson, finalResults, finalResults.length);
            // Pagination only matters if we still have headroom under the cap.
            const cap = expectedCount > 0 ? expectedCount : 100;
            const nextBtn = findNextPageButton();
            if (nextBtn && finalResults.length < cap && finalResults.length < 100) {
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
