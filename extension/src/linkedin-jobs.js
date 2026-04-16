// StealthRole LinkedIn — Job Capture + Intelligence (v2.0.0)
//
// EYES: auto-captures job postings when user views them on LinkedIn.
// Extracts structured data (title, company, location, description, salary,
// seniority, employment type) and pushes to backend for:
//   - Auto-saving to saved jobs
//   - Intelligence Pack generation (CV tailoring)
//   - Signal cross-referencing (is this company in our hidden market radar?)
//   - Way-in detection (do I know someone here?)
//
// Also handles job search results pages (bulk capture).

(() => {
  "use strict";
  const SR = window.SR;

  // ── Single job page capture ──

  SR.captureJob = async function () {
    const jobData = extractJobFromPage();
    if (!jobData || !jobData.title) {
      console.log("[SR] captureJob: no job data found on page");
      return;
    }
    console.log(`[SR] captureJob: "${jobData.title}" at ${jobData.company}`);
    SR.showToast(`Analyzing: ${jobData.title}`);

    // 1. Save job to backend
    const saveRes = await SR.apiPost("/linkedin/ingest/job", {
      job: jobData,
      source_url: window.location.href,
    });

    if (saveRes?.ok) {
      console.log("[SR] Job saved:", JSON.stringify(saveRes.data).slice(0, 200));
    } else {
      console.warn("[SR] Job save failed:", saveRes?.error);
    }

    // 2. Check who we know at this company
    const company = jobData.company;
    if (company) {
      try {
        const intelRes = await SR.apiPost("/linkedin/analyze-network", { company_name: company });
        if (intelRes?.ok && intelRes.data) {
          showJobIntelPanel(jobData, intelRes.data);
        } else {
          showJobIntelPanel(jobData, null);
        }
      } catch (e) {
        console.warn("[SR] Company intel failed:", e);
        showJobIntelPanel(jobData, null);
      }
    } else {
      showJobIntelPanel(jobData, null);
    }
  };

  // ── Extract structured job data from LinkedIn job detail page ──

  function extractJobFromPage() {
    const result = {
      title: "",
      company: "",
      company_linkedin_url: "",
      location: "",
      description: "",
      salary: "",
      employment_type: "",
      seniority_level: "",
      industry: "",
      job_function: "",
      posted_at: "",
      applicant_count: "",
      linkedin_job_id: "",
      linkedin_url: window.location.href.split("?")[0],
    };

    // Job ID from URL
    const jobIdMatch = window.location.pathname.match(/\/jobs\/view\/(\d+)/);
    if (jobIdMatch) result.linkedin_job_id = jobIdMatch[1];

    // Title — primary heading
    const titleEl = document.querySelector(
      ".job-details-jobs-unified-top-card__job-title h1, " +
      ".jobs-unified-top-card__job-title, " +
      ".t-24.t-bold, " +
      "h1.topcard__title, " +
      "h1"
    );
    if (titleEl) result.title = titleEl.textContent.trim();

    // Company name + URL
    const companyLink = document.querySelector(
      ".job-details-jobs-unified-top-card__company-name a, " +
      ".jobs-unified-top-card__company-name a, " +
      "a[href*='/company/'].topcard__org-name-link, " +
      "a[data-tracking-control-name='public_jobs_topcard-org-name']"
    );
    if (companyLink) {
      result.company = companyLink.textContent.trim();
      result.company_linkedin_url = (companyLink.href || "").split("?")[0];
    }
    if (!result.company) {
      // Fallback: span without link
      const companySpan = document.querySelector(
        ".job-details-jobs-unified-top-card__company-name, " +
        ".jobs-unified-top-card__company-name"
      );
      if (companySpan) result.company = companySpan.textContent.trim();
    }

    // Location
    const locationEl = document.querySelector(
      ".job-details-jobs-unified-top-card__bullet, " +
      ".jobs-unified-top-card__bullet, " +
      ".topcard__flavor--bullet"
    );
    if (locationEl) result.location = locationEl.textContent.trim();

    // Description — the main JD text
    const descEl = document.querySelector(
      ".jobs-description__content, " +
      ".jobs-box__html-content, " +
      "#job-details, " +
      ".description__text"
    );
    if (descEl) result.description = descEl.innerText.trim().slice(0, 10000);

    // Salary (if shown)
    const salaryEl = document.querySelector(
      ".salary-main-rail__data-body, " +
      ".job-details-jobs-unified-top-card__job-insight span, " +
      "[class*='salary']"
    );
    if (salaryEl) {
      const salaryText = salaryEl.textContent.trim();
      if (/\$|£|€|salary|yr|hour|annual/i.test(salaryText)) result.salary = salaryText;
    }

    // Job criteria list (seniority, type, function, industry)
    const criteriaItems = document.querySelectorAll(
      ".jobs-description-details__list-item, " +
      ".description__job-criteria-item, " +
      ".job-details-jobs-unified-top-card__job-insight"
    );
    for (const item of criteriaItems) {
      const label = (item.querySelector("h3, .description__job-criteria-subheader")?.textContent || "").trim().toLowerCase();
      const value = (item.querySelector("span:last-child, .description__job-criteria-text")?.textContent || item.textContent || "").trim();
      if (label.includes("seniority")) result.seniority_level = value;
      else if (label.includes("employment")) result.employment_type = value;
      else if (label.includes("function")) result.job_function = value;
      else if (label.includes("industr")) result.industry = value;
    }

    // Posted time
    const timeEl = document.querySelector(
      ".jobs-unified-top-card__posted-date, " +
      "time, " +
      "[class*='posted-time']"
    );
    if (timeEl) result.posted_at = timeEl.textContent.trim();

    // Applicant count
    const applicantEl = document.querySelector(
      ".jobs-unified-top-card__applicant-count, " +
      "[class*='num-applicants'], " +
      "[class*='applicant-count']"
    );
    if (applicantEl) result.applicant_count = applicantEl.textContent.trim();

    return result;
  }

  // ── Job search results page (bulk capture) ──

  SR.captureJobSearchResults = function () {
    const jobs = extractJobSearchResults();
    console.log("[SR] captureJobSearchResults:", jobs.length, "jobs");
    if (jobs.length === 0) { SR.showToast("No job results found on this page."); return; }

    SR.showToast(`Saving ${jobs.length} jobs…`);
    SR.apiCall("/linkedin/ingest/jobs-bulk", { method: "POST", body: JSON.stringify({ jobs }) }, (res) => {
      if (res?.ok) SR.showToast(`Saved ${res.data?.saved || jobs.length} jobs`);
      else SR.showToast(res?.error || "Save failed");
    });
  };

  function extractJobSearchResults() {
    const results = [];
    const seen = new Set();

    // Job cards in search results or collections
    const cards = document.querySelectorAll(
      ".jobs-search-results__list-item, " +
      ".job-card-container, " +
      ".scaffold-layout__list-item, " +
      "[data-job-id]"
    );

    for (const card of cards) {
      const titleEl = card.querySelector(
        ".job-card-list__title, " +
        ".artdeco-entity-lockup__title, " +
        "a[class*='job-card'] strong, " +
        ".job-card-container__link strong"
      );
      const companyEl = card.querySelector(
        ".artdeco-entity-lockup__subtitle, " +
        ".job-card-container__primary-description, " +
        ".job-card-container__company-name"
      );
      const locationEl = card.querySelector(
        ".artdeco-entity-lockup__caption, " +
        ".job-card-container__metadata-wrapper, " +
        ".job-card-container__metadata-item"
      );
      const linkEl = card.querySelector("a[href*='/jobs/view/']");

      const title = titleEl?.textContent?.trim() || "";
      const company = companyEl?.textContent?.trim() || "";
      if (!title || seen.has(title + company)) continue;
      seen.add(title + company);

      const href = linkEl?.href?.split("?")[0] || "";
      const jobIdMatch = href.match(/\/jobs\/view\/(\d+)/);

      results.push({
        title,
        company,
        location: locationEl?.textContent?.trim() || "",
        linkedin_url: href,
        linkedin_job_id: jobIdMatch ? jobIdMatch[1] : "",
      });
    }
    return results;
  }

  // ── Intelligence panel for job pages ──

  function showJobIntelPanel(jobData, networkData) {
    const sections = [];

    // Job summary
    sections.push({
      heading: "📋 Job Captured",
      items: [
        { icon: "💼", text: jobData.title, sub: jobData.company },
        jobData.location ? { icon: "📍", text: jobData.location } : null,
        jobData.salary ? { icon: "💰", text: jobData.salary } : null,
        jobData.seniority_level ? { icon: "📊", text: jobData.seniority_level } : null,
        jobData.applicant_count ? { icon: "👥", text: jobData.applicant_count } : null,
      ].filter(Boolean),
    });

    // Network intelligence
    if (networkData) {
      const connections = networkData.connections || [];
      const wayIn = networkData.way_in_paths || [];
      const signals = networkData.signals || [];

      if (connections.length > 0) {
        sections.push({
          heading: "🤝 People You Know Here",
          badge: `${connections.length}`,
          badgeType: "success",
          items: connections.slice(0, 5).map((c) => ({
            icon: c.is_recruiter ? "🎯" : "👤",
            text: c.full_name,
            sub: c.current_title || c.headline || "",
          })),
        });
      }

      if (wayIn.length > 0) {
        sections.push({
          heading: "🚪 Way In",
          badge: `${wayIn.length} paths`,
          badgeType: "highlight",
          items: wayIn.slice(0, 3).map((w) => ({
            icon: "→",
            text: `${w.connector_name} → ${w.target_name}`,
            sub: w.connector_title || "",
          })),
        });
      }

      if (signals.length > 0) {
        sections.push({
          heading: "📡 Market Signals",
          items: signals.slice(0, 3).map((s) => ({
            icon: s.category === "money" ? "💰" : s.category === "growth" ? "📈" : s.category === "leadership" ? "👔" : "⚡",
            text: s.headline || s.summary,
            sub: s.source || "",
          })),
        });
      }

      if (connections.length === 0 && wayIn.length === 0) {
        sections.push({
          heading: "🤝 Network",
          empty: "No connections at " + jobData.company + " yet. Sync your LinkedIn connections to find paths in.",
        });
      }
    }

    // Action buttons
    sections.push({
      html: `<div class="sr-intel-actions">
        <button class="sr-intel-btn sr-intel-btn--primary" onclick="window.SR.generateIntelPack?.()">⚡ Generate Intelligence Pack</button>
        <button class="sr-intel-btn" onclick="window.SR.generateOutreach?.()">✉️ Draft Outreach</button>
      </div>`,
    });

    SR.showIntelPanel(`${jobData.company} — ${jobData.title}`, sections);
  }

  // ── Trigger Intelligence Pack generation ──

  SR.generateIntelPack = async function () {
    const jobData = extractJobFromPage();
    if (!jobData?.title) { SR.showToast("No job data on this page"); return; }
    SR.showToast("Generating Intelligence Pack…");
    const res = await SR.apiPost("/jobs", {
      job_url: window.location.href,
      job_title: jobData.title,
      company: jobData.company,
      description: jobData.description?.slice(0, 5000),
    });
    if (res?.ok) {
      SR.showToast("Pack generating — check StealthRole dashboard");
    } else {
      SR.showToast(res?.error || "Failed to start pack");
    }
  };

  // ── Trigger outreach generation ──

  SR.generateOutreach = async function () {
    const jobData = extractJobFromPage();
    if (!jobData?.title) return;
    SR.showToast("Drafting outreach…");
    const res = await SR.apiPost("/outreach/generate", {
      job_title: jobData.title,
      company: jobData.company,
      job_url: window.location.href,
      type: "linkedin_note",
    });
    if (res?.ok && res.data?.message) {
      // Copy to clipboard
      try {
        await navigator.clipboard.writeText(res.data.message);
        SR.showToast("Outreach copied to clipboard!");
      } catch {
        SR.showToast("Outreach ready — check StealthRole");
      }
    } else {
      SR.showToast(res?.error || "Outreach generation failed");
    }
  };
})();
