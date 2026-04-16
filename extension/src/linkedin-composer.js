// StealthRole LinkedIn — Message Composer + AI Reply (v2.0.0)
//
// PEN: the action layer. Drafts context-aware replies to recruiter
// messages, generates outreach for warm intros, and pre-fills
// LinkedIn message compose boxes.
//
// Works with the backend's /outreach/generate and /linkedin/analyze-conversation
// endpoints which use Claude to draft messages tuned to the conversation
// context, the user's profile, and the target company.

(() => {
  "use strict";
  const SR = window.SR;

  // ══════════════════════════════════════════════════════════════════════
  // Reply drafting for active conversation
  // ══════════════════════════════════════════════════════════════════════

  /**
   * When viewing a conversation thread, extract the messages and ask
   * the backend to draft an AI reply. Injects the reply into LinkedIn's
   * compose box with a "Use this reply" button.
   */
  SR.draftReply = async function () {
    // Extract conversation from the active thread
    const thread = extractActiveThread();
    if (!thread || thread.messages.length === 0) {
      SR.showToast("Open a conversation first");
      return;
    }

    console.log(`[SR] draftReply: ${thread.messages.length} messages with ${thread.contactName}`);
    SR.showToast("Drafting reply…");

    const res = await SR.apiPost("/linkedin/analyze-conversation", {
      contact_name: thread.contactName,
      contact_title: thread.contactTitle,
      contact_company: thread.contactCompany,
      messages: thread.messages,
      context: {
        source: "linkedin_messaging",
        thread_url: window.location.href,
      },
    });

    if (res?.ok && res.data) {
      const draft = res.data.suggested_reply || res.data.reply || res.data.message || "";
      const analysis = res.data.analysis || res.data.classification || "";
      if (draft) {
        showReplyDraft(draft, analysis, thread.contactName);
      } else {
        SR.showToast("No reply generated — try again");
      }
    } else {
      SR.showToast(res?.error || "Reply generation failed");
    }
  };

  /**
   * Extract messages from the currently visible conversation thread.
   */
  function extractActiveThread() {
    const result = {
      contactName: "",
      contactTitle: "",
      contactCompany: "",
      messages: [],
    };

    // Contact name from thread header
    const headerEl = document.querySelector(
      ".msg-overlay-bubble-header__title, " +
      ".msg-thread__link-to-profile, " +
      ".msg-s-message-list-container [class*='profile-link'], " +
      "h2.msg-overlay-bubble-header__title"
    );
    if (headerEl) result.contactName = headerEl.textContent.trim();

    // Fallback: profile link in the thread
    if (!result.contactName) {
      const profileLink = document.querySelector(".msg-thread a[href*='/in/']");
      if (profileLink) {
        result.contactName = profileLink.textContent.trim() || profileLink.getAttribute("aria-label") || "";
      }
    }

    // Extract messages from the thread
    const msgEls = document.querySelectorAll(
      ".msg-s-event-listitem, " +
      ".msg-s-message-list__event, " +
      "[class*='msg-s-event']"
    );

    for (const el of msgEls) {
      const senderEl = el.querySelector(
        ".msg-s-event-listitem__link span.t-bold, " +
        ".msg-s-message-group__name, " +
        "[class*='message-sender']"
      );
      const textEl = el.querySelector(
        ".msg-s-event-listitem__body, " +
        ".msg-s-event__content, " +
        "[class*='message-body']"
      );
      const timeEl = el.querySelector("time");

      if (!textEl) continue;
      const senderName = senderEl?.textContent?.trim() || "";
      const text = textEl.textContent.trim();
      const sentAt = timeEl?.getAttribute("datetime") || "";

      // Determine if this is my message
      const isMine = SR._myPublicId
        ? senderName.toLowerCase().includes("you") || el.classList.contains("msg-s-event-listitem--other") === false
        : senderName.toLowerCase().includes("you");

      result.messages.push({
        sender: isMine ? "me" : senderName || "them",
        text: text.slice(0, 2000),
        sent_at: sentAt,
        is_mine: isMine,
      });
    }

    return result;
  }

  /**
   * Show the draft reply in a floating panel near the compose box.
   */
  function showReplyDraft(draft, analysis, contactName) {
    // Remove existing draft panel
    document.getElementById("sr-draft-panel")?.remove();

    const panel = document.createElement("div");
    panel.id = "sr-draft-panel";
    panel.className = "sr-draft-panel";
    panel.innerHTML = `
      <div class="sr-draft-header">
        <span>⚡ StealthRole Draft</span>
        <button class="sr-draft-close" id="sr-draft-close">&times;</button>
      </div>
      ${analysis ? `<div class="sr-draft-analysis">${analysis}</div>` : ""}
      <div class="sr-draft-body" contenteditable="false">${escapeHtml(draft)}</div>
      <div class="sr-draft-actions">
        <button class="sr-intel-btn sr-intel-btn--primary" id="sr-draft-use">📋 Copy & Use</button>
        <button class="sr-intel-btn" id="sr-draft-refine">🔄 Refine</button>
        <button class="sr-intel-btn" id="sr-draft-formal">👔 More Formal</button>
        <button class="sr-intel-btn" id="sr-draft-casual">🤙 More Casual</button>
      </div>
    `;
    document.body.appendChild(panel);

    // Wire up buttons
    document.getElementById("sr-draft-close").onclick = () => panel.remove();

    document.getElementById("sr-draft-use").onclick = async () => {
      // Copy to clipboard
      try { await navigator.clipboard.writeText(draft); } catch {}
      // Try to inject into LinkedIn's compose box
      const composeBox = document.querySelector(
        ".msg-form__contenteditable, " +
        "[role='textbox'][contenteditable='true'], " +
        ".msg-form__msg-content-container div[contenteditable]"
      );
      if (composeBox) {
        composeBox.focus();
        // LinkedIn uses contenteditable with a <p> inside
        const p = composeBox.querySelector("p") || composeBox;
        p.textContent = draft;
        // Trigger input event so LinkedIn detects the change
        composeBox.dispatchEvent(new Event("input", { bubbles: true }));
        composeBox.dispatchEvent(new Event("change", { bubbles: true }));
        SR.showToast("Reply inserted — review before sending");
      } else {
        SR.showToast("Reply copied to clipboard — paste into message box");
      }
      panel.remove();
    };

    // Refine buttons re-call the API with tone adjustments
    const refineWith = async (tone) => {
      SR.showToast("Refining…");
      const thread = extractActiveThread();
      const res = await SR.apiPost("/linkedin/analyze-conversation", {
        contact_name: contactName,
        messages: thread.messages,
        tone,
        previous_draft: draft,
      });
      if (res?.ok && (res.data?.suggested_reply || res.data?.reply)) {
        const newDraft = res.data.suggested_reply || res.data.reply;
        panel.querySelector(".sr-draft-body").textContent = newDraft;
        draft = newDraft;
        SR.showToast("Draft updated");
      }
    };
    document.getElementById("sr-draft-refine").onclick = () => refineWith("balanced");
    document.getElementById("sr-draft-formal").onclick = () => refineWith("formal");
    document.getElementById("sr-draft-casual").onclick = () => refineWith("casual");
  }

  function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // ══════════════════════════════════════════════════════════════════════
  // Warm intro pre-fill
  // ══════════════════════════════════════════════════════════════════════
  // When user clicks "Request Intro" from the intel panel, opens LinkedIn
  // messaging with the connector and pre-fills a draft message.

  SR.prefillWarmIntro = async function (connectorLinkedinId, targetName, targetCompany) {
    SR.showToast("Generating intro message…");

    const res = await SR.apiPost("/outreach/generate", {
      type: "warm_intro",
      connector_linkedin_id: connectorLinkedinId,
      target_name: targetName,
      target_company: targetCompany,
    });

    if (res?.ok && res.data?.message) {
      const message = res.data.message;
      // Navigate to the messaging page with the connector
      const msgUrl = `https://www.linkedin.com/messaging/compose/?connectedProfileUrn=urn:li:fsd_profile:${connectorLinkedinId}`;
      // Copy message to clipboard first
      try { await navigator.clipboard.writeText(message); } catch {}
      SR.showToast("Message copied — paste into LinkedIn compose");
      window.location.href = msgUrl;
    } else {
      SR.showToast(res?.error || "Failed to generate intro");
    }
  };

  // ══════════════════════════════════════════════════════════════════════
  // Inject "Draft Reply" button into messaging UI
  // ══════════════════════════════════════════════════════════════════════
  // Adds a small ⚡ button next to LinkedIn's compose box.

  function injectDraftButton() {
    if (document.getElementById("sr-draft-btn")) return;

    const composeForm = document.querySelector(
      ".msg-form__footer, " +
      ".msg-form__right-actions, " +
      ".msg-form__send-toggle"
    );
    if (!composeForm) return;

    const btn = document.createElement("button");
    btn.id = "sr-draft-btn";
    btn.className = "sr-overlay-btn sr-draft-trigger";
    btn.textContent = "⚡ AI Reply";
    btn.style.cssText = "margin-right:8px;font-size:12px;padding:4px 10px;";
    btn.onclick = () => SR.draftReply();
    composeForm.prepend(btn);
    console.log("[SR] Draft reply button injected");
  }

  // Watch for compose box appearing (LinkedIn lazy-loads it)
  if (SR.getPageType() === "messaging") {
    const composeObserver = new MutationObserver(() => {
      injectDraftButton();
    });
    setTimeout(() => {
      composeObserver.observe(document.body, { childList: true, subtree: true });
      injectDraftButton(); // initial attempt
    }, 2000);
  }
})();
