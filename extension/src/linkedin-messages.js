// StealthRole LinkedIn — Messages sync (v2.0.0)
// Fetches conversation threads from LinkedIn's Voyager messaging API,
// extracts structured data, and POSTs to /api/v1/linkedin/messages/sync.
//
// Key improvements over v1:
//   1. PerformanceObserver-first: uses endpoints discovered from LinkedIn's
//      own React app before falling back to hardcoded URL list.
//   2. is_mine detection: fetches current user's profile URN via /me and
//      compares against message sender URNs.
//   3. Real pagination: pages through all conversations, not just the first 20.
//   4. Single code path: no more duplicate scrapeMessages() vs autoScrapeMessages().

(() => {
  "use strict";
  const SR = window.SR;

  // ── Hardcoded endpoint candidates ──
  // LinkedIn rotates these, so discovered endpoints (from PerformanceObserver)
  // are always tried first.

  const HARDCODED_MSG_URLS = [
    (count, start) => `https://www.linkedin.com/voyager/api/voyagerMessagingDashMessengerConversations?count=${count}&start=${start}`,
    (count, start) => `https://www.linkedin.com/voyager/api/voyagerMessagingDashMessengerConversations?q=search&count=${count}&start=${start}`,
    (count, start) => `https://www.linkedin.com/voyager/api/voyagerMessagingDashMessengerConversations?q=participants&count=${count}&start=${start}`,
    (count, start) => `https://www.linkedin.com/voyager/api/messaging/conversations?keyVersion=LEGACY_INBOX&count=${count}&start=${start}`,
    (count, start) => `https://www.linkedin.com/voyager/api/messaging/conversations?count=${count}&start=${start}`,
  ];

  /**
   * Build URL builders from discovered PerformanceObserver URLs.
   * We take the base path + fixed params, and make count/start injectable.
   */
  function buildersFromDiscovered() {
    const builders = [];
    for (const raw of SR._discoveredMsgEndpoints) {
      try {
        const u = new URL(raw);
        // Remove count/start so we can inject our own
        u.searchParams.delete("count");
        u.searchParams.delete("start");
        const base = u.toString();
        builders.push((count, start) => {
          const sep = base.includes("?") ? "&" : "?";
          return `${base}${sep}count=${count}&start=${start}`;
        });
      } catch {}
    }
    return builders;
  }

  // ── Main entry point ──

  SR.autoScrapeMessages = async function () {
    if (SR._autoMessagesInProgress) {
      console.warn("[SR] autoScrapeMessages already running — ignoring");
      return;
    }
    SR._autoMessagesInProgress = true;
    console.log("[SR] autoScrapeMessages starting");

    const progress = (count, status, error) => SR.sendProgress("messages", count, status, error);
    progress(0, "scanning");

    try {
      const headers = SR.voyagerHeaders();
      if (!headers) {
        console.warn("[SR] messaging: no CSRF token");
        progress(0, "error", "No LinkedIn session — are you logged in?");
        return;
      }

      // Fetch the current user's URN so we can tag is_mine on messages
      await SR.fetchMyProfile();

      // ── Step 1: Probe endpoints to find one that works ──

      // Discovered endpoints go first — they reflect what LinkedIn's
      // own frontend is actually using right now.
      const allBuilders = [...buildersFromDiscovered(), ...HARDCODED_MSG_URLS];
      console.log(`[SR] messaging: ${buildersFromDiscovered().length} discovered + ${HARDCODED_MSG_URLS.length} hardcoded endpoints to try`);

      let workingBuilder = null;
      let firstPageData = null;

      for (let i = 0; i < allBuilders.length; i++) {
        const build = allBuilders[i];
        const url = build(20, 0);
        try {
          const res = await fetch(url, { headers, credentials: "include" });
          console.log(`[SR] msg probe ${i}:`, url.slice(0, 120), "→", res.status);
          if (!res.ok) {
            try { const body = await res.text(); console.log(`[SR] msg probe ${i} body:`, body.slice(0, 300)); } catch {}
            continue;
          }
          const data = await res.json();
          console.log(`[SR] msg probe ${i}: top keys =`, Object.keys(data || {}).join(", "));
          const extracted = extractConversationIndex(data);
          console.log(`[SR] msg probe ${i}: extracted`, extracted.length, "conversations");
          if (extracted.length > 0) {
            workingBuilder = build;
            firstPageData = { data, extracted };
            console.log("[SR] msg probe hit — sample:", JSON.stringify(extracted[0]).slice(0, 300));
            break;
          }
        } catch (e) {
          console.warn(`[SR] msg probe ${i} failed:`, e.message);
        }
      }

      // ── Step 1b: DOM sidebar fallback ──
      let conversationIndex = firstPageData ? firstPageData.extracted : [];

      if (conversationIndex.length === 0) {
        console.log("[SR] voyager messaging failed — trying DOM sidebar scrape");
        conversationIndex = scrapeMessagingSidebar();
        console.log("[SR] DOM sidebar:", conversationIndex.length, "conversations");
      }

      if (conversationIndex.length === 0) {
        console.warn("[SR] messages sync: nothing found via API or DOM");
        progress(0, "error", "No conversations found — try reloading the messaging page");
        return;
      }

      // ── Step 2: Paginate if we have a working API endpoint ──

      if (workingBuilder && firstPageData) {
        const BATCH = 20;
        const MAX_CONVOS = 500; // safety cap
        let start = BATCH;
        const seenUrns = new Set(conversationIndex.map((c) => c.conversation_urn));

        while (start < MAX_CONVOS) {
          const url = workingBuilder(BATCH, start);
          try {
            const res = await fetch(url, { headers, credentials: "include" });
            if (!res.ok) { console.warn("[SR] msg page", start, "→", res.status); break; }
            const data = await res.json();
            const page = extractConversationIndex(data);
            if (page.length === 0) { console.log("[SR] msg: end of list at start=", start); break; }
            let added = 0;
            for (const c of page) {
              if (!seenUrns.has(c.conversation_urn)) {
                seenUrns.add(c.conversation_urn);
                conversationIndex.push(c);
                added++;
              }
            }
            console.log(`[SR] msg page ${start / BATCH}: ${page.length} extracted, ${added} new, total ${conversationIndex.length}`);
            if (page.length < BATCH) break;
            start += BATCH;
            progress(conversationIndex.length, "scanning");
            await new Promise((r) => setTimeout(r, 500)); // gentle rate limit
          } catch (e) {
            console.warn("[SR] msg page", start, "error:", e.message);
            break;
          }
        }
      }

      console.log(`[SR] messaging: ${conversationIndex.length} total conversations to sync`);
      progress(conversationIndex.length, "scanning");

      // ── Step 3: POST to backend in batches ──

      const CHUNK = 20;
      let posted = 0;
      for (let i = 0; i < conversationIndex.length; i += CHUNK) {
        const batch = conversationIndex.slice(i, i + CHUNK);
        const res = await SR.apiPost("/linkedin/messages/sync", { conversations: batch });
        if (!res?.ok) console.warn("[SR] messages batch error:", res?.error);
        else console.log("[SR] messages batch ok:", JSON.stringify(res.data).slice(0, 200));
        posted += batch.length;
        progress(posted, "scanning");
      }

      progress(conversationIndex.length, "done");
      console.log(`[SR] autoScrapeMessages done: ${conversationIndex.length} conversations`);
    } catch (e) {
      console.error("[SR] autoScrapeMessages error:", e);
      progress(0, "error", String(e?.message || e));
    } finally {
      SR._autoMessagesInProgress = false;
    }
  };

  // ── DOM scraper fallback for messaging sidebar ──
  // When voyager endpoints all fail, scrape what's visible in the LinkedIn
  // messaging UI. Each sidebar item has a thread link, contact name, preview,
  // and timestamp.

  function scrapeMessagingSidebar() {
    const results = [];
    const seen = new Set();
    const threadLinks = document.querySelectorAll("a[href*='/messaging/thread/']");
    console.log(`[SR] DOM sidebar: ${threadLinks.length} thread links`);

    for (const link of threadLinks) {
      const href = (link.href || "").split("?")[0];
      const threadId = href.split("/messaging/thread/")[1]?.replace(/\/$/, "") || "";
      if (!threadId || seen.has(threadId)) continue;
      seen.add(threadId);

      // Walk up to find the conversation item container
      let container = link;
      for (let i = 0; i < 8; i++) {
        if (!container.parentElement) break;
        container = container.parentElement;
        const t = (container.innerText || "").trim();
        if (t.length > 10 && t.length < 500) break;
      }

      const text = (container.innerText || "").replace(/\s+/g, " ").trim();

      // Contact name: <img alt>, aria-label, or first text token
      let contactName = "";
      const img = container.querySelector("img[alt]");
      if (img && img.alt) contactName = img.alt.trim();
      if (!contactName) {
        const ariaEl = container.querySelector("[aria-label]");
        if (ariaEl) {
          const a = ariaEl.getAttribute("aria-label") || "";
          contactName = a.replace(/^conversation with /i, "").replace(/'s? conversation$/i, "").trim();
        }
      }
      if (!contactName && text) {
        contactName = text.split(/\s*[|·\n]/)[0]?.trim() || "";
      }
      if (!contactName || contactName.length < 2) continue;

      // Timestamp
      let lastMessageAt = null;
      const timeEl = container.querySelector("time[datetime]");
      if (timeEl) lastMessageAt = timeEl.getAttribute("datetime");

      // Preview: longest non-name text chunk
      let preview = "";
      const textParts = text.split(/\n/).map((s) => s.trim()).filter(Boolean);
      for (const part of textParts) {
        if (part === contactName) continue;
        if (part.length > preview.length && part.length > 5) preview = part;
      }

      // Unread badge
      const isUnread = !!(
        container.querySelector("[class*='unread']") ||
        container.querySelector("[class*='badge']") ||
        container.getAttribute("class")?.includes("unread")
      );

      results.push({
        conversation_urn: `thread:${threadId}`,
        contact_name: contactName.slice(0, 255),
        contact_linkedin_id: null,
        contact_linkedin_url: null,
        contact_title: null,
        contact_company: null,
        messages: preview
          ? [{ sender: "them", text: preview.slice(0, 500), sent_at: lastMessageAt, is_mine: false }]
          : [],
        last_message_at: lastMessageAt,
        last_sender: "them",
        is_unread: isUnread,
      });
    }
    return results;
  }

  // ── Extract conversations from a voyager messaging API response ──
  // Response shapes vary — both `elements` and `included` carry data.
  // We walk recursively, collecting conversations, messages, and profiles,
  // then join by URN.

  function extractConversationIndex(data) {
    const conversations = {};       // convoUrn → conversation object
    const messagesByConvo = {};     // convoUrn → message[]
    const profilesByUrn = {};       // profileUrn → { name, linkedinId, url, title, company }
    const participantsByConvo = {}; // convoUrn → Set<profileUrn>

    const walk = (obj) => {
      if (!obj || typeof obj !== "object") return;
      if (Array.isArray(obj)) { for (const x of obj) walk(x); return; }

      const urn = typeof (obj.entityUrn || obj.$urn) === "string" ? (obj.entityUrn || obj.$urn) : "";

      // ─ Conversation objects ─
      if (urn && /urn:li:(?:fs|fsd)_conversation:/.test(urn)) {
        if (!conversations[urn]) {
          conversations[urn] = {
            conversation_urn: urn,
            contact_name: null,
            contact_linkedin_id: null,
            contact_linkedin_url: null,
            contact_title: null,
            contact_company: null,
            messages: [],
            last_message_at: null,
            last_sender: null,
            is_unread: false,
          };
        }
        const c = conversations[urn];
        if (obj.read === false || obj.unreadCount > 0) c.is_unread = true;
        if (obj.lastActivityAt) c.last_message_at = String(obj.lastActivityAt);

        // Collect participant URNs for contact attribution
        const parts = obj.participants || obj["*participants"] || obj.conversationParticipants || [];
        if (Array.isArray(parts)) {
          if (!participantsByConvo[urn]) participantsByConvo[urn] = new Set();
          for (const p of parts) {
            const pUrn = typeof p === "string" ? p : (p?.entityUrn || p?.["*miniProfile"] || "");
            if (pUrn) participantsByConvo[urn].add(pUrn);
          }
        }
      }

      // ─ Profile objects ─
      if (urn && /urn:li:(fs_miniProfile|fsd_profile|dash_profile|fs_member):/i.test(urn)) {
        if (obj.firstName || obj.lastName || obj.publicIdentifier) {
          const headline = obj.occupation || obj.headline || "";
          let title = headline;
          let company = "";
          const m = headline.match(/^(.+?)\s+(?:at|@)\s+(.+)$/i);
          if (m) { title = m[1].trim(); company = m[2].trim(); }
          profilesByUrn[urn] = {
            name: [obj.firstName, obj.lastName].filter(Boolean).join(" ").trim(),
            linkedinId: obj.publicIdentifier || "",
            url: obj.publicIdentifier ? `https://www.linkedin.com/in/${obj.publicIdentifier}/` : "",
            title,
            company,
          };
        }
      }

      // ─ Message event objects ─
      if (urn && /urn:li:(?:fs|fsd)_event:|fsd_message:/i.test(urn)) {
        let text = "";
        if (obj.eventContent?.["com.linkedin.voyager.messaging.event.MessageEvent"]) {
          const me = obj.eventContent["com.linkedin.voyager.messaging.event.MessageEvent"];
          text = me?.attributedBody?.text || me?.body?.text || "";
        } else if (obj.body?.text) {
          text = obj.body.text;
        } else if (obj.attributedBody?.text) {
          text = obj.attributedBody.text;
        } else if (typeof obj.text === "string") {
          text = obj.text;
        }

        const convoRef = obj.conversation || obj["*conversation"] || obj.conversationUrn || "";
        const convoUrn = typeof convoRef === "string" ? convoRef : (convoRef?.entityUrn || "");

        const fromRef = obj.from || obj.sender || obj["*from"] || "";
        const fromUrn = typeof fromRef === "string" ? fromRef : (fromRef?.entityUrn || "");

        const createdAt = obj.createdAt || obj.timestamp || null;

        if (text && convoUrn) {
          if (!messagesByConvo[convoUrn]) messagesByConvo[convoUrn] = [];
          messagesByConvo[convoUrn].push({ text, sent_at: createdAt ? String(createdAt) : null, fromUrn });
        }
      }

      // Recurse
      for (const key in obj) {
        const v = obj[key];
        if (v && typeof v === "object") walk(v);
      }
    };

    walk(data);

    // ── Join: messages + profiles → conversations ──

    const myUrn = SR._myProfileUrn || "";
    const myId = SR._myPublicId || "";
    const result = [];

    for (const convoUrn in conversations) {
      const c = conversations[convoUrn];
      const msgs = (messagesByConvo[convoUrn] || []).sort((a, b) => (a.sent_at || "").localeCompare(b.sent_at || ""));

      // Determine is_mine for each message
      c.messages = msgs.map((m) => {
        let isMine = false;
        if (myUrn && m.fromUrn) {
          // URN match (handles both exact and contains — LinkedIn sometimes nests URNs)
          isMine = m.fromUrn === myUrn || m.fromUrn.includes(myUrn) || myUrn.includes(m.fromUrn);
        }
        if (!isMine && myId && m.fromUrn) {
          // Fallback: check if the sender URN resolves to a profile with my publicIdentifier
          const senderProfile = profilesByUrn[m.fromUrn];
          if (senderProfile && senderProfile.linkedinId === myId) isMine = true;
        }
        return {
          sender: isMine ? "me" : "them",
          text: m.text,
          sent_at: m.sent_at,
          is_mine: isMine,
        };
      });

      // Fill contact fields from participants (pick the first non-me participant)
      const participants = participantsByConvo[convoUrn] || new Set();
      for (const pUrn of participants) {
        // Skip if this is me
        if (myUrn && (pUrn === myUrn || pUrn.includes(myUrn))) continue;
        const p = profilesByUrn[pUrn];
        if (p?.name) {
          c.contact_name = p.name;
          c.contact_linkedin_id = p.linkedinId;
          c.contact_linkedin_url = p.url;
          c.contact_title = p.title;
          c.contact_company = p.company;
          break;
        }
      }

      // If participant matching didn't work, fall back to any non-me profile
      if (!c.contact_name) {
        for (const profileUrn in profilesByUrn) {
          if (myUrn && (profileUrn === myUrn || profileUrn.includes(myUrn))) continue;
          const p = profilesByUrn[profileUrn];
          if (p?.name) {
            c.contact_name = p.name;
            c.contact_linkedin_id = p.linkedinId;
            c.contact_linkedin_url = p.url;
            c.contact_title = p.title;
            c.contact_company = p.company;
            break;
          }
        }
      }

      if (msgs.length > 0) {
        c.last_message_at = c.last_message_at || msgs[msgs.length - 1].sent_at;
        c.last_sender = c.messages[c.messages.length - 1].sender;
      }

      if (c.contact_name || c.messages.length > 0) {
        result.push(c);
      }
    }
    return result;
  }
})();
