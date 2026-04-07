// StealthRole ATS auto-fill content script
// Runs on Greenhouse, Lever, Workable, Ashby application forms

(() => {
  // ── Detect ATS platform ──────────────────────────────────────────────
  function detectPlatform() {
    const url = window.location.href;
    if (url.includes("greenhouse.io")) return "greenhouse";
    if (url.includes("lever.co")) return "lever";
    if (url.includes("workable.com")) return "workable";
    if (url.includes("ashbyhq.com")) return "ashby";
    return "other";
  }

  // ── Extract job info from the page ───────────────────────────────────
  function extractJobInfo() {
    const platform = detectPlatform();
    let company = "";
    let role = "";

    if (platform === "greenhouse") {
      role = document.querySelector(".app-title, h1.heading")?.textContent?.trim() || "";
      company = document.querySelector(".company-name, .logo-container")?.textContent?.trim() || "";
    } else if (platform === "lever") {
      role = document.querySelector(".posting-headline h2, .section-header")?.textContent?.trim() || "";
      company = document.querySelector(".main-footer-text a, .posting-categories .location")?.textContent?.trim() || "";
    } else if (platform === "workable") {
      role = document.querySelector("h1[data-ui='job-title'], .job-title")?.textContent?.trim() || "";
      company = document.querySelector(".company-name, [data-ui='company-name']")?.textContent?.trim() || "";
    } else {
      role = document.querySelector("h1")?.textContent?.trim() || "";
      company = document.title.split("|")[0]?.trim() || "";
    }

    return { company, role, platform, url: window.location.href };
  }

  // ── Fill form fields ─────────────────────────────────────────────────
  function fillField(selector, value) {
    if (!value) return false;
    const el = document.querySelector(selector);
    if (!el) return false;

    // React-compatible input filling
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype, "value"
    )?.set;
    const nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype, "value"
    )?.set;

    if (el.tagName === "TEXTAREA" && nativeTextAreaValueSetter) {
      nativeTextAreaValueSetter.call(el, value);
    } else if (nativeInputValueSetter) {
      nativeInputValueSetter.call(el, value);
    } else {
      el.value = value;
    }

    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function fillByLabel(labelText, value) {
    if (!value) return false;
    const labels = document.querySelectorAll("label");
    for (const label of labels) {
      if (label.textContent.toLowerCase().includes(labelText.toLowerCase())) {
        const forId = label.getAttribute("for");
        if (forId) {
          const input = document.getElementById(forId);
          if (input) {
            input.value = value;
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.dispatchEvent(new Event("change", { bubbles: true }));
            return true;
          }
        }
        // Try next sibling
        const sibling = label.nextElementSibling;
        if (sibling && (sibling.tagName === "INPUT" || sibling.tagName === "TEXTAREA")) {
          sibling.value = value;
          sibling.dispatchEvent(new Event("input", { bubbles: true }));
          return true;
        }
      }
    }
    return false;
  }

  // ── Platform-specific fillers ────────────────────────────────────────
  function fillGreenhouse(payload) {
    fillField('#first_name, input[name="job_application[first_name]"]', payload.first_name);
    fillField('#last_name, input[name="job_application[last_name]"]', payload.last_name);
    fillField('#email, input[name="job_application[email]"]', payload.email);
    fillField('#phone, input[name="job_application[phone]"]', payload.phone);
    fillField('input[name="job_application[location]"]', payload.location);
    fillByLabel("linkedin", payload.linkedin_profile_url);
    fillByLabel("website", payload.website_url);
    // Cover letter
    const coverEl = document.querySelector('#cover_letter, textarea[name*="cover_letter"]');
    if (coverEl && payload.cover_letter) {
      coverEl.value = payload.cover_letter;
      coverEl.dispatchEvent(new Event("input", { bubbles: true }));
    }
  }

  function fillLever(payload) {
    fillField('input[name="name"]', payload.name);
    fillField('input[name="email"]', payload.email);
    fillField('input[name="phone"]', payload.phone);
    fillField('input[name="org"]', payload.org);
    fillByLabel("linkedin", payload["urls[LinkedIn]"]);
    fillByLabel("portfolio", payload["urls[Portfolio]"]);
    const commentEl = document.querySelector('textarea[name="comments"]');
    if (commentEl && payload.comments) {
      commentEl.value = payload.comments;
      commentEl.dispatchEvent(new Event("input", { bubbles: true }));
    }
  }

  function fillWorkable(payload) {
    fillField('input[name="firstname"], input[data-ui="firstname"]', payload.firstname);
    fillField('input[name="lastname"], input[data-ui="lastname"]', payload.lastname);
    fillField('input[name="email"], input[data-ui="email"]', payload.email);
    fillField('input[name="phone"], input[data-ui="phone"]', payload.phone);
    fillByLabel("address", payload.address);
    fillByLabel("linkedin", payload.linkedin);
    fillByLabel("website", payload.website);
  }

  function fillGeneric(payload) {
    // Try common field names/labels
    const fieldMap = [
      ["first_name", payload.first_name],
      ["last_name", payload.last_name],
      ["full_name", payload.full_name],
      ["name", payload.full_name],
      ["email", payload.email],
      ["phone", payload.phone],
      ["location", payload.location],
      ["linkedin", payload.linkedin_url],
      ["website", payload.website],
    ];
    let filled = 0;
    for (const [label, value] of fieldMap) {
      if (fillByLabel(label, value)) filled++;
      else if (fillField(`input[name*="${label}"]`, value)) filled++;
    }
    return filled;
  }

  // ── Main auto-fill flow ──────────────────────────────────────────────
  async function runAutofill() {
    const jobInfo = extractJobInfo();
    showToast("Preparing auto-fill...");

    // Ask backend for form payload
    chrome.runtime.sendMessage(
      {
        type: "API_REQUEST",
        path: "/auto-apply/prepare",
        options: {
          method: "POST",
          body: JSON.stringify({
            company: jobInfo.company || "Unknown",
            role: jobInfo.role || "Unknown",
            apply_url: jobInfo.url,
          }),
        },
      },
      (res) => {
        if (!res?.ok) {
          showToast(res?.error || "Failed to prepare form data");
          return;
        }

        const payload = res.data.form_payload;
        const submissionId = res.data.id;

        // Fill based on platform
        try {
          if (jobInfo.platform === "greenhouse") fillGreenhouse(payload);
          else if (jobInfo.platform === "lever") fillLever(payload);
          else if (jobInfo.platform === "workable") fillWorkable(payload);
          else fillGeneric(payload);

          showToast("Form filled! Review and submit manually.");

          // Report success back (but don't mark as submitted — user does that)
        } catch (err) {
          showToast("Auto-fill error: " + err.message);
          // Report failure
          chrome.runtime.sendMessage({
            type: "API_REQUEST",
            path: "/auto-apply/report-failed",
            options: {
              method: "POST",
              body: JSON.stringify({ submission_id: submissionId, error: err.message }),
            },
          });
        }
      }
    );
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
    setTimeout(() => toast.classList.remove("show"), 3000);
  }

  // ── Show floating button on ATS pages ────────────────────────────────
  const platform = detectPlatform();
  if (platform !== "other") {
    const btn = document.createElement("button");
    btn.className = "sr-overlay-btn";
    btn.innerHTML = `<span class="sr-icon">&#9889;</span> Auto-Fill with StealthRole`;
    btn.addEventListener("click", runAutofill);
    document.body.appendChild(btn);
  }

  // ── Listen for messages from popup ───────────────────────────────────
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === "AUTOFILL") {
      runAutofill().then(() => sendResponse({ ok: true }));
      return true;
    }
    if (msg.type === "SAVE_JOB") {
      const info = extractJobInfo();
      chrome.runtime.sendMessage(
        {
          type: "API_REQUEST",
          path: "/applications",
          options: {
            method: "POST",
            body: JSON.stringify({
              company: info.company || "Unknown",
              role: info.role || "Unknown",
              date_applied: new Date().toISOString(),
              source_channel: "job_board",
              url: info.url,
            }),
          },
        },
        (res) => {
          if (res?.ok) {
            sendResponse({ ok: true, company: info.company, role: info.role });
          } else {
            sendResponse({ ok: false, error: res?.error });
          }
        }
      );
      return true;
    }
  });
})();
