// StealthRole LinkedIn — Company Intelligence + Profile Enrichment (v2.0.0)
//
// EARS: passive intelligence layer that enriches every page you visit.
//
// Company pages: captures headcount, industry, specialties, recent hires,
//   and cross-references with hidden market signals.
//
// Profile pages: enriches contacts with full experience/education/skills
//   (beyond the basic headline scrape), detects recruiter/hiring manager.
//
// Messaging page: classifies visible conversations as recruiter/opportunity
//   and badges them in the sidebar.

(() => {
  "use strict";
  const SR = window.SR;

  // ══════════════════════════════════════════════════════════════════════
  // Company page intelligence
  // ══════════════════════════════════════════════════════════════════════

  SR.captureCompanyIntel = async function () {
    const data = extractCompanyFromPage();
    if (!data.name) {
      console.log("[SR] captureCompanyIntel: no company data found");
      return;
    }
    console.log(`[SR] captureCompanyIntel: "${data.name}"`);
    SR.showToast(`Analyzing ${data.name}…`);

    // Push company data to backend
    const saveRes = await SR.apiPost("/linkedin/ingest/company", {
      company: data,
      source_url: window.location.href,
    });

    // Fetch intelligence: who do I know, signals, open jobs
    let networkData = null;
    try {
      const intelRes = await SR.apiPost("/linkedin/analyze-network", { company_name: data.name });
      if (intelRes?.ok) networkData = intelRes.data;
    } catch {}

    showCompanyIntelPanel(data, networkData);
  };

  function extractCompanyFromPage() {
    const result = {
      name: "",
      linkedin_url: window.location.href.split("?")[0],
      tagline: "",
      industry: "",
      headcount: "",
      specialties: "",
      website: "",
      headquarters: "",
      founded: "",
      type: "",
      about: "",
    };

    // Company name
    const nameEl = document.querySelector(
      "h1.org-top-card-summary__title, " +
      "h1.top-card-layout__title, " +
      "h1 span[dir='ltr']"
    );
    if (nameEl) result.name = nameEl.textContent.trim();
    if (!result.name) {
      const h1 = document.querySelector("h1");
      if (h1) result.name = h1.textContent.trim();
    }

    // Tagline
    const taglineEl = document.querySelector(
      ".org-top-card-summary__tagline, " +
      ".top-card-layout__headline"
    );
    if (taglineEl) result.tagline = taglineEl.textContent.trim();

    // About section
    const aboutEl = document.querySelector(
      ".org-about-company-module__description, " +
      ".org-page-details-module__card-description, " +
      "section.org-about-module p"
    );
    if (aboutEl) result.about = aboutEl.innerText.trim().slice(0, 3000);

    // Info items (industry, headcount, website, etc.)
    const infoItems = document.querySelectorAll(
      ".org-about-company-module__company-size-definition-text, " +
      ".org-page-details__definition-text, " +
      "dd.org-about-company-module__company-size-definition-text"
    );

    // More robust: look for dl/dt/dd pairs
    const dtElements = document.querySelectorAll("dt");
    for (const dt of dtElements) {
      const label = (dt.textContent || "").trim().toLowerCase();
      const dd = dt.nextElementSibling;
      if (!dd) continue;
      const value = (dd.textContent || "").trim();
      if (label.includes("industr")) result.industry = value;
      else if (label.includes("size") || label.includes("employee")) result.headcount = value;
      else if (label.includes("website")) result.website = value;
      else if (label.includes("headquarter")) result.headquarters = value;
      else if (label.includes("founded")) result.founded = value;
      else if (label.includes("type")) result.type = value;
      else if (label.includes("specialt") || label.includes("specializ")) result.specialties = value;
    }

    // Fallback: scan body text for employee count
    if (!result.headcount) {
      const bodyText = document.body.innerText || "";
      const sizeMatch = bodyText.match(/(\d[\d,]+)\s*(?:employee|people|associate)/i);
      if (sizeMatch) result.headcount = sizeMatch[0];
    }

    return result;
  }

  function showCompanyIntelPanel(companyData, networkData) {
    const sections = [];

    // Company snapshot
    const companyItems = [
      companyData.industry ? { icon: "🏢", text: companyData.industry } : null,
      companyData.headcount ? { icon: "👥", text: companyData.headcount + " employees" } : null,
      companyData.headquarters ? { icon: "📍", text: companyData.headquarters } : null,
      companyData.founded ? { icon: "📅", text: "Founded " + companyData.founded } : null,
    ].filter(Boolean);

    if (companyItems.length > 0) {
      sections.push({ heading: "🏢 Company Snapshot", items: companyItems });
    }

    // Network intelligence
    if (networkData) {
      const connections = networkData.connections || [];
      const wayIn = networkData.way_in_paths || [];
      const signals = networkData.signals || [];
      const recruiters = connections.filter((c) => c.is_recruiter);
      const nonRecruiters = connections.filter((c) => !c.is_recruiter);

      if (recruiters.length > 0) {
        sections.push({
          heading: "🎯 Recruiters / Hiring Managers",
          badge: `${recruiters.length}`,
          badgeType: "highlight",
          items: recruiters.slice(0, 5).map((c) => ({
            icon: "🎯",
            text: c.full_name,
            sub: c.current_title || "",
          })),
        });
      }

      if (nonRecruiters.length > 0) {
        sections.push({
          heading: "🤝 Your Connections Here",
          badge: `${nonRecruiters.length}`,
          badgeType: "success",
          items: nonRecruiters.slice(0, 5).map((c) => ({
            icon: "👤",
            text: c.full_name,
            sub: c.current_title || "",
          })),
        });
      }

      if (wayIn.length > 0) {
        sections.push({
          heading: "🚪 Way In (2nd Degree)",
          badge: `${wayIn.length} paths`,
          badgeType: "highlight",
          items: wayIn.slice(0, 5).map((w) => ({
            icon: "→",
            text: `${w.connector_name} → ${w.target_name}`,
            sub: w.connector_title || "",
          })),
        });
      }

      if (signals.length > 0) {
        sections.push({
          heading: "📡 Market Signals",
          items: signals.slice(0, 5).map((s) => ({
            icon: s.category === "money" ? "💰" : s.category === "growth" ? "📈" : "⚡",
            text: s.headline || s.summary,
          })),
        });
      }

      if (connections.length === 0 && wayIn.length === 0) {
        sections.push({
          heading: "🤝 Network",
          empty: "No connections at " + companyData.name + " yet.",
        });
      }
    }

    SR.showIntelPanel(companyData.name, sections);
  }

  // ══════════════════════════════════════════════════════════════════════
  // Profile page enrichment
  // ══════════════════════════════════════════════════════════════════════
  // Goes beyond the basic headline scrape to extract full experience,
  // education, and skills sections.

  SR.enrichProfile = function () {
    const enriched = {
      experience: extractExperience(),
      education: extractEducation(),
      skills: extractSkills(),
      about: extractAbout(),
    };
    console.log(`[SR] enrichProfile: ${enriched.experience.length} roles, ${enriched.education.length} schools, ${enriched.skills.length} skills`);
    return enriched;
  };

  function extractExperience() {
    const roles = [];
    // LinkedIn puts experience in a section with id="experience"
    const expSection = document.getElementById("experience") || document.querySelector("section[id*='experience']");
    if (!expSection) return roles;

    const container = expSection.closest("section") || expSection.parentElement;
    if (!container) return roles;

    const items = container.querySelectorAll("li.artdeco-list__item, li[class*='experience'], div[data-view-name*='experience']");
    for (const item of items) {
      const titleEl = item.querySelector("span[aria-hidden='true'] t-bold, .t-bold span, span.mr1 span");
      const companyEl = item.querySelector(".t-normal span, .t-14.t-normal span");
      const durationEl = item.querySelector(".t-black--light span, .pvs-entity__caption-wrapper span");

      const title = titleEl?.textContent?.trim() || "";
      const company = companyEl?.textContent?.trim() || "";
      const duration = durationEl?.textContent?.trim() || "";

      if (title || company) {
        roles.push({ title, company, duration });
      }
    }

    // Fallback: just scan for experience text blocks
    if (roles.length === 0) {
      const allText = container.innerText || "";
      const lines = allText.split("\n").map((l) => l.trim()).filter(Boolean);
      for (let i = 0; i < lines.length - 1; i++) {
        if (lines[i].length > 5 && lines[i].length < 80 && /\bat\b|·/i.test(lines[i + 1] || "")) {
          roles.push({ title: lines[i], company: lines[i + 1], duration: "" });
        }
      }
    }
    return roles;
  }

  function extractEducation() {
    const schools = [];
    const eduSection = document.getElementById("education") || document.querySelector("section[id*='education']");
    if (!eduSection) return schools;

    const container = eduSection.closest("section") || eduSection.parentElement;
    if (!container) return schools;

    const items = container.querySelectorAll("li.artdeco-list__item, li[class*='education']");
    for (const item of items) {
      const schoolEl = item.querySelector("span[aria-hidden='true'], .t-bold span");
      const degreeEl = item.querySelector(".t-normal span, .t-14 span");
      const school = schoolEl?.textContent?.trim() || "";
      const degree = degreeEl?.textContent?.trim() || "";
      if (school) schools.push({ school, degree });
    }
    return schools;
  }

  function extractSkills() {
    const skills = [];
    const skillSection = document.getElementById("skills") || document.querySelector("section[id*='skills']");
    if (!skillSection) return skills;

    const container = skillSection.closest("section") || skillSection.parentElement;
    if (!container) return skills;

    const items = container.querySelectorAll("span[aria-hidden='true'], .t-bold span");
    const seen = new Set();
    for (const item of items) {
      const text = item.textContent.trim();
      if (text && text.length > 1 && text.length < 60 && !seen.has(text)) {
        seen.add(text);
        skills.push(text);
      }
    }
    return skills;
  }

  function extractAbout() {
    const aboutSection = document.getElementById("about") || document.querySelector("section[id*='about']");
    if (!aboutSection) return "";
    const container = aboutSection.closest("section") || aboutSection.parentElement;
    if (!container) return "";
    // Find the main text span (LinkedIn hides it behind a "see more" sometimes)
    const textEl = container.querySelector(".pv-about__summary-text span, .inline-show-more-text span, span[aria-hidden='true']");
    return textEl?.textContent?.trim()?.slice(0, 2000) || container.innerText?.trim()?.slice(0, 2000) || "";
  }

  // ══════════════════════════════════════════════════════════════════════
  // Messaging sidebar conversation classification
  // ══════════════════════════════════════════════════════════════════════
  // Scans visible conversation items and badges them as:
  //   🎯 Recruiter — sender title contains recruit/talent/hiring/sourcing
  //   💼 Opportunity — message preview mentions opportunity/role/position
  //   🤝 Connection — mutual interest (mentioned company or referral)

  SR.classifyVisibleConversations = function () {
    const threadLinks = document.querySelectorAll("a[href*='/messaging/thread/']");
    let classified = 0;

    for (const link of threadLinks) {
      // Already badged?
      if (link.closest("[data-sr-classified]")) continue;

      let container = link;
      for (let i = 0; i < 6; i++) {
        if (!container.parentElement) break;
        container = container.parentElement;
        if ((container.innerText || "").trim().length > 10) break;
      }

      const text = (container.innerText || "").toLowerCase();
      let badge = null;

      if (/\brecruit|talent\s*acqu|hiring\s*manag|sourcing|headhunt/i.test(text)) {
        badge = createBadge("🎯", "Recruiter", "#e74c3c");
      } else if (/\bopportunity|position|role|opening|career|we.re\s*hiring|interested\s*in/i.test(text)) {
        badge = createBadge("💼", "Opportunity", "#f39c12");
      } else if (/\breferr|introduct|mutual|connection|recommend/i.test(text)) {
        badge = createBadge("🤝", "Network", "#27ae60");
      }

      if (badge) {
        container.style.position = "relative";
        container.appendChild(badge);
        container.setAttribute("data-sr-classified", "true");
        classified++;
      }
    }

    if (classified > 0) console.log(`[SR] Classified ${classified} conversations`);
  };

  function createBadge(icon, label, color) {
    const badge = document.createElement("span");
    badge.className = "sr-msg-badge";
    badge.style.cssText = `position:absolute;top:4px;right:4px;background:${color};color:#fff;font-size:10px;padding:2px 6px;border-radius:8px;z-index:10;pointer-events:none;`;
    badge.textContent = `${icon} ${label}`;
    return badge;
  }

  // Re-classify when new messages appear (messaging is a SPA)
  if (SR.getPageType() === "messaging") {
    const msgObserver = new MutationObserver(() => {
      SR.classifyVisibleConversations?.();
    });
    // Delay to ensure DOM is ready
    setTimeout(() => {
      const sidebar = document.querySelector(".msg-conversations-container__conversations-list, [class*='conversations-list']");
      if (sidebar) {
        msgObserver.observe(sidebar, { childList: true, subtree: true });
        console.log("[SR] Messaging sidebar observer installed");
      }
    }, 3000);
  }
})();
