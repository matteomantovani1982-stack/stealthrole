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

  // LinkedIn (2025+) uses GraphQL for messaging. The key endpoint is
  // messengerConversations with a queryId that rotates periodically.
  // PerformanceObserver captures the live queryId from LinkedIn's own
  // React app, so we extract it and build paginated requests.

  // Legacy REST endpoints use offset-based pagination (start param).
  // For the probe (first page), createdBefore is null so start=0.
  // For pagination they won't be used (GraphQL is preferred), but keep for probing.
  const LEGACY_REST_URLS = [
    (count, createdBefore) => `https://www.linkedin.com/voyager/api/messaging/conversations?keyVersion=LEGACY_INBOX&count=${count}&start=0`,
    (count, createdBefore) => `https://www.linkedin.com/voyager/api/messaging/conversations?count=${count}&start=0`,
  ];

  /**
   * Build URL builders from discovered PerformanceObserver URLs.
   *
   * Strategy:
   *  1. Find the messengerConversations GraphQL URL (the conversation list endpoint)
   *  2. Extract its queryId and the user's mailboxUrn from the variables
   *  3. Build a paginator that injects count/start into the variables
   *  4. As fallback, also try legacy REST endpoints
   */
  function buildersFromDiscovered() {
    const builders = [];
    let foundConversationEndpoint = false;

    for (const raw of SR._discoveredMsgEndpoints) {
      try {
        // Only care about messengerConversations — that's the conversation list
        if (!raw.includes("messengerConversations")) continue;
        if (foundConversationEndpoint) continue; // only need one

        // Extract queryId from the URL
        const queryIdMatch = raw.match(/queryId=([^&]+)/);
        if (!queryIdMatch) continue;
        const queryId = queryIdMatch[1];

        // Extract mailboxUrn from variables — LinkedIn uses (key:value,...) syntax
        // The separator after "mailboxUrn" is either a literal ":" or "%3A".
        // The URN value itself starts with "urn" and runs until "," or ")" or "&".
        const mailboxMatch = raw.match(/mailboxUrn(?::|%3A)(urn[^,)&]+)/i);
        const mailboxUrn = mailboxMatch
          ? decodeURIComponent(mailboxMatch[1]).replace(/%3A/gi, ":")
          : null;

        // Also try extracting from the full variables block
        const varsMatch = raw.match(/variables=([^&]+)/);
        const rawVars = varsMatch ? decodeURIComponent(varsMatch[1]) : "";

        console.log("[SR] Found messengerConversations endpoint:", { queryId, mailboxUrn, rawVars: rawVars.slice(0, 100) });

        if (mailboxUrn) {
          // Build GraphQL conversation list URL with offset-based pagination.
          // LinkedIn's GraphQL messaging supports (count, start) for paging.
          const encodedUrn = encodeURIComponent(mailboxUrn);
          builders.push((count, start) => {
            const startParam = start ? `,start:${start}` : "";
            return `https://www.linkedin.com/voyager/api/voyagerMessagingGraphQL/graphql?queryId=${queryId}&variables=(mailboxUrn:${encodedUrn},count:${count}${startParam})`;
          });
          foundConversationEndpoint = true;
        } else if (rawVars) {
          // Fallback: inject count/start into the existing variables block.
          const stripped = rawVars
            .replace(/,?count:[^,)]+/g, "")
            .replace(/,?start:[^,)]+/g, "")
            .replace(/,?syncToken:[^,)]+/g, "")
            .replace(/\)$/, "")
            .replace(/,+/g, ",")
            .replace(/\(,/, "(");
          builders.push((count, start) => {
            const startParam = start ? `,start:${start}` : "";
            const vars = `${stripped},count:${count}${startParam})`;
            return `https://www.linkedin.com/voyager/api/voyagerMessagingGraphQL/graphql?queryId=${queryId}&variables=${vars}`;
          });
          foundConversationEndpoint = true;
        }
      } catch (e) {
        console.warn("[SR] builder parse error:", e.message);
      }
    }

    // If we didn't find a GraphQL endpoint, try building from the user's profile URN
    if (!foundConversationEndpoint && SR._myProfileUrn) {
      console.log("[SR] No discovered messengerConversations — building from profile URN");
      // Try known queryId patterns (these rotate but are stable for weeks)
      const knownQueryIds = [
        "messengerConversations.0d5e6781bbee71c3e51c8843c6519f48",
        "messengerConversations.d4dfa35051837dabb36e283ef3e6751a",
      ];
      const mailbox = encodeURIComponent(SR._myProfileUrn);
      for (const qid of knownQueryIds) {
        builders.push((count, start) => {
          const startParam = start ? `,start:${start}` : "";
          return `https://www.linkedin.com/voyager/api/voyagerMessagingGraphQL/graphql?queryId=${qid}&variables=(mailboxUrn:${mailbox},count:${count}${startParam})`;
        });
      }
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
      const discovered = buildersFromDiscovered();
      const allBuilders = [...discovered, ...LEGACY_REST_URLS];
      console.log(`[SR] messaging: ${discovered.length} discovered + ${LEGACY_REST_URLS.length} legacy endpoints to try`);

      let workingBuilder = null;
      let firstPageData = null;

      for (let i = 0; i < allBuilders.length; i++) {
        const build = allBuilders[i];
        // Request a large batch upfront — LinkedIn's GraphQL supports count up to ~200.
        // The default of 20 is just what LinkedIn's React app uses for lazy loading.
        const url = build(200, null);
        try {
          const res = await SR.fetchWithTimeout(url, { headers, credentials: "include" });
          console.log(`[SR] msg probe ${i}:`, url.slice(0, 120), "→", res.status);
          if (!res.ok) {
            try { const body = await res.text(); console.log(`[SR] msg probe ${i} body:`, body.slice(0, 300)); } catch {}
            continue;
          }
          const data = await res.json();
          console.log(`[SR] msg probe ${i}: top keys =`, Object.keys(data || {}).join(", "));

          if (data?.included?.length) {
            console.log(`[SR] msg probe ${i}: ${data.included.length} included entities`);
          }

          const extracted = extractConversationIndex(data);
          console.log(`[SR] msg probe ${i}: extracted`, extracted.length, "conversations");
          if (extracted.length > 0) {
            workingBuilder = build;
            firstPageData = { data, extracted };
            console.log("[SR] msg probe hit — first 3 names:", extracted.slice(0, 3).map(c => `${c.contact_name || 'NULL'} (${c.messages.length} msgs)`).join(", "));
            break;
          }
        } catch (e) {
          console.warn(`[SR] msg probe ${i} failed:`, e.message);
        }
      }

      // ── Step 1b: Take only the most recent conversations ──
      // We only care about the last ~100 job-relevant conversations.
      // The initial API call already returns the most recent ones (sorted by lastActivityAt desc),
      // so we just use what we got from Step 1 — no pagination or scroll needed.
      const MAX_CONVERSATIONS = 100;
      let conversationIndex = firstPageData ? firstPageData.extracted : [];
      console.log(`[SR] got ${conversationIndex.length} conversations from initial API call (keeping up to ${MAX_CONVERSATIONS})`);

      // Sort by last_message_at desc to ensure we keep the most recent
      conversationIndex.sort((a, b) => {
        const tA = a.last_message_at ? new Date(a.last_message_at).getTime() : 0;
        const tB = b.last_message_at ? new Date(b.last_message_at).getTime() : 0;
        return tB - tA;
      });

      if (conversationIndex.length > MAX_CONVERSATIONS) {
        console.log(`[SR] trimming from ${conversationIndex.length} to ${MAX_CONVERSATIONS} most recent`);
        conversationIndex = conversationIndex.slice(0, MAX_CONVERSATIONS);
      }
      progress(conversationIndex.length, "scanning");

      if (conversationIndex.length === 0) {
        console.warn("[SR] messages sync: nothing found via API or DOM");
        progress(0, "error", "No conversations found — try reloading the messaging page");
        return;
      }
      console.log(`[SR] messaging: ${conversationIndex.length} total conversations before filtering`);

      // ── Step 2a: Filter — ONLY keep job-related conversations ──
      // Aggressive filter: skip everything that isn't about jobs, recruiting,
      // interviews, networking for career purposes, or referrals.

      const SKIP_PATTERNS = [
        // Birthday / celebration / congratulations
        /\bhappy\s*birthday\b/i,
        /\bbuon\s*compleanno\b/i,
        /\bhappy\s*anniversary\b/i,
        /\bcongratulations?\b/i,
        /\bcongratulazioni\b/i,
        /\bwork\s*anniversary\b/i,
        /\bnew\s*position\b/i,
        /\bpromotion\b/i,
        /\bcelebrat/i,
        /\bkudos\b/i,
        /\bwell\s*done\b/i,
        /\bbravo\b/i,
        // Sales / marketing / spam
        /\b(buy|purchase|discount|coupon|promo\s*code|limited\s*offer|act\s*now|exclusive\s*deal)\b/i,
        /\b(webinar|masterclass|free\s*trial|sign\s*up\s*now|register\s*now|book\s*a\s*demo)\b/i,
        /\b(unsubscribe|opt[\s-]?out|email\s*list)\b/i,
        /\bsponsored\b/i,
        /\b(product|service|solution|platform|tool|software)\s+(that|which|to)\b/i,
        // Generic fluff with no job substance
        /^(hi|hello|hey|ciao|thanks|thank you|grazie)[!.,]?\s*$/i,
        // Endorsements / notifications
        /\bendorsed\s+you\b/i,
        /\bskill\s+endorsement\b/i,
        // Courses / learning
        /\b(course|certificate|certification|udemy|coursera|learning\s*path)\b/i,
        // Charity / donations / events invites (non-career)
        /\b(donate|donation|charity|volunteer|fundrais)/i,
        /\b(event|meetup|conference)\s+(invitation|invite)\b/i,
      ];

      const JOB_PATTERNS = [
        // Direct job signals — if ANY of these match, KEEP the conversation
        /\b(job|position|role|opening|opportunity|vacancy|hiring|recruit)/i,
        /\b(interview|interviewing|phone\s*screen|on-?site|technical\s*round)\b/i,
        /\b(resume|cv|portfolio|cover\s*letter)\b/i,
        /\b(salary|compensation|offer|package|equity|stock\s*options?)\b/i,
        /\b(referr|warm\s*intro|introduction|connect\s*you\s*with)\b/i,
        /\b(apply|application|applied|candidate)\b/i,
        /\b(team|company|startup|we.re\s*looking|we\s*are\s*looking|looking\s*for)\b/i,
        /\b(engineer|developer|designer|manager|director|VP|CTO|CEO|founder)\b/i,
        /\b(network|networking|career|professional)\b/i,
        /\b(talent|head\s*of|lead)\b/i,
        /\b(remote|hybrid|on-?site|full[\s-]*time|part[\s-]*time|contract)\b/i,
      ];

      const isCompanyConvo = (c) => c.conversation_urn.includes("fsd_company:");

      const beforeFilter = conversationIndex.length;
      const filtered = [];
      const filteredOut = [];

      for (const c of conversationIndex) {
        const allText = c.messages.map(m => m.text || "").join(" ");
        const previewText = allText.slice(0, 1000);

        // Company InMail with no real conversation → skip
        if (isCompanyConvo(c) && c.messages.length <= 1) {
          filteredOut.push(`COMPANY: ${c.contact_name || "?"}: "${previewText.slice(0, 60)}"`);
          continue;
        }

        // Empty conversations with no messages → skip
        if (c.messages.length === 0 && !c.contact_name) {
          filteredOut.push(`EMPTY: ${c.conversation_urn.slice(0, 40)}`);
          continue;
        }

        // Check for job signals — if found, always keep
        let hasJobSignal = false;
        for (const pat of JOB_PATTERNS) {
          if (pat.test(previewText) || pat.test(c.contact_title || "") || pat.test(c.contact_company || "")) {
            hasJobSignal = true;
            break;
          }
        }

        if (hasJobSignal) {
          filtered.push(c);
          continue;
        }

        // Check for skip patterns
        let isSpam = false;
        for (const pat of SKIP_PATTERNS) {
          if (pat.test(previewText)) { isSpam = true; break; }
        }

        if (isSpam) {
          filteredOut.push(`SPAM: ${c.contact_name || "?"}: "${previewText.slice(0, 60)}"`);
          continue;
        }

        // Short conversations with no job signal and no skip pattern:
        // Keep if they have 3+ messages (real conversation), skip if just a greeting
        if (c.messages.length >= 3) {
          filtered.push(c);
        } else if (previewText.length > 100) {
          // Some substance — keep it
          filtered.push(c);
        } else {
          filteredOut.push(`SHORT: ${c.contact_name || "?"}: "${previewText.slice(0, 60)}"`);
        }
      }

      conversationIndex = filtered;
      console.log(`[SR] job filter: ${beforeFilter} → ${conversationIndex.length} kept, ${filteredOut.length} filtered out`);
      if (filteredOut.length > 0) console.log(`[SR] filtered out samples:`, filteredOut.slice(0, 15));

      progress(conversationIndex.length, "scanning");

      // ── Step 2b: Fetch full message threads per conversation ──
      // The conversation list only returns preview/recent messages.
      // For conversations with ≤1 message, fetch the full thread.

      if (headers) {
        // ── Build per-thread URL builders ──
        // Re-check discovered endpoints NOW (not at autoScrape start) because
        // LinkedIn's React app fires messengerMessages requests AFTER the
        // conversation list loads. Give a brief moment for capture.
        await new Promise((r) => setTimeout(r, 1500));

        function buildMsgBuilders() {
          const builders = [];
          let discovered = false;
          for (const raw of SR._discoveredMsgEndpoints) {
            if (!raw.includes("messengerMessages") || raw.includes("messengerConversations")) continue;
            try {
              // Work directly with the RAW captured URL — no decoding/re-encoding.
              // Just find the encoded conversationUrn value and swap it.
              // This preserves LinkedIn's exact URL structure including all other params.
              const baseUrl = raw.split("?")[0];
              const qMatch = raw.match(/queryId=([^&]+)/);
              if (!qMatch) continue;
              const queryId = qMatch[1];
              const varsMatch = raw.match(/variables=([^&]+)/);
              if (!varsMatch) continue;
              const rawVarsEncoded = varsMatch[1]; // keep encoded!

              // Find the encoded conversationUrn value in the encoded vars string.
              // Pattern: "conversationUrn:" followed by the encoded URN value.
              // The encoded URN uses %3A for colons, %28/%29 for parens, %2C for commas.
              const convoPrefix = "conversationUrn:";
              const prefIdx = rawVarsEncoded.indexOf(convoPrefix);
              if (prefIdx < 0) continue;
              const valueStart = prefIdx + convoPrefix.length;

              // Find end of the encoded URN value: scan for unencoded , or ) at depth 0.
              // Encoded parens (%28/%29) increase/decrease depth; literal ( ) are depth markers.
              let depth = 0, end = -1;
              for (let i = valueStart; i < rawVarsEncoded.length; i++) {
                const ch = rawVarsEncoded[i];
                const nextTwo = rawVarsEncoded.slice(i, i + 3).toUpperCase();
                if (ch === "(" || nextTwo === "%28") { depth++; if (nextTwo === "%28") i += 2; continue; }
                if (ch === ")" || nextTwo === "%29") {
                  if (depth === 0) { end = i; break; }
                  depth--;
                  if (nextTwo === "%29") i += 2;
                  continue;
                }
                if ((ch === "," || nextTwo === "%2C") && depth === 0) { end = i; break; }
              }
              if (end <= valueStart) continue;

              // Build template: everything before the convoUrn value + $$CONVO$$ + everything after
              const template = rawVarsEncoded.slice(0, valueStart) + "$$CONVO$$" + rawVarsEncoded.slice(end);
              console.log("[SR] discovered messengerMessages template:", template.slice(0, 140));

              builders.push((convoUrn) => {
                // encodeURIComponent does NOT encode ( ) — but LinkedIn requires %28 %29
                const encoded = encodeURIComponent(convoUrn).replace(/\(/g, "%28").replace(/\)/g, "%29");
                const vars = template.replace("$$CONVO$$", encoded);
                return `${baseUrl}?queryId=${queryId}&variables=${vars}`;
              });
              discovered = true;
            } catch (e) {
              console.warn("[SR] msg builder parse error:", e.message);
            }
          }
          return { builders, discovered };
        }

        let { builders: msgBuilders, discovered: usedDiscovered } = buildMsgBuilders();
        console.log(`[SR] thread builders: ${msgBuilders.length} discovered from ${SR._discoveredMsgEndpoints.length} captured endpoints`);

        // Fallback: manual URL construction with encodeURIComponent
        // LinkedIn's own URLs use full percent-encoding for URN values inside variables
        if (!usedDiscovered) {
          const knownMsgQueryIds = [
            "messengerMessages.5846eeb71c981f11e0134cb6626cc314",
            "messengerMessages.4b0a2cce07d0eff095deb4c3e19786dd",
            "messengerMessages.ca41bfde2fc0bb70d7fd4ced66e2497c",
          ];
          for (const qid of knownMsgQueryIds) {
            msgBuilders.push((convoUrn) => {
              const encoded = encodeURIComponent(convoUrn).replace(/\(/g, "%28").replace(/\)/g, "%29");
              const fsd = convoUrn.match(/urn:li:fsd_profile:[A-Za-z0-9_-]+/);
              const mailbox = fsd ? `,mailboxUrn:${encodeURIComponent(fsd[0])}` : "";
              return `https://www.linkedin.com/voyager/api/voyagerMessagingGraphQL/graphql?queryId=${qid}&variables=(conversationUrn:${encoded}${mailbox},count:40)`;
            });
          }
        }
        console.log(`[SR] thread fetch: ${msgBuilders.length} URL builders (discovered: ${usedDiscovered})`);

        let threadsFetched = 0;
        const MAX_THREAD_FETCHES = 100; // cap to avoid rate limits
        const convosNeedingMessages = conversationIndex.filter((c) => c.messages.length <= 1);
        console.log(`[SR] ${convosNeedingMessages.length} conversations need full thread fetch`);

        for (const conv of convosNeedingMessages) {
          if (threadsFetched >= MAX_THREAD_FETCHES) {
            console.log("[SR] thread fetch cap reached");
            break;
          }

          let fetched = false;

          // Try GraphQL messengerMessages endpoints
          for (const builder of msgBuilders) {
            if (fetched) break;
            const url = builder(conv.conversation_urn);
            if (threadsFetched === 0) console.log("[SR] DIAG first thread URL:", url.slice(0, 200));
            try {
              const res = await SR.fetchWithRetry(url, { headers, credentials: "include" }, { retries: 1, backoffMs: 1000 });
              if (res.status === 429 || res.status === 503) {
                const wait = parseInt(res.headers?.get?.("retry-after") || "10", 10);
                console.warn(`[SR] thread fetch rate-limited, waiting ${wait}s`);
                await new Promise((r) => setTimeout(r, wait * 1000));
                continue;
              }
              if (!res.ok) {
                if (threadsFetched === 0) console.log(`[SR] thread fetch ${res.status} for:`, url.slice(0, 180));
                continue;
              }
              const data = await res.json();
              const extracted = extractConversationIndex(data);
              // Find messages for this conversation in the extracted data
              // Try exact URN match first, then flexible match (same thread ID suffix)
              let match = extracted.find((e) => e.conversation_urn === conv.conversation_urn);
              if (!match && extracted.length > 0) {
                // Flexible: match by thread-id suffix or by containing the same participant pair
                // Conversation URNs can differ in prefix (msg_ vs fsd_) but share the same inner content
                const convInner = conv.conversation_urn.replace(/^urn:li:(?:fs|fsd|msg)_conversation:/, "");
                match = extracted.find((e) => {
                  const eInner = e.conversation_urn.replace(/^urn:li:(?:fs|fsd|msg)_conversation:/, "");
                  return eInner === convInner;
                });
              }
              // Last resort: if only 1 conversation returned, it's almost certainly the right one
              if (!match && extracted.length === 1) {
                match = extracted[0];
              }

              if (match && match.messages.length > conv.messages.length) {
                console.log(`[SR] thread MERGED: ${conv.contact_name || "?"} → ${conv.messages.length} → ${match.messages.length} msgs`);
                conv.messages = match.messages;
                if (match.contact_name && !conv.contact_name) {
                  conv.contact_name = match.contact_name;
                  conv.contact_linkedin_id = match.contact_linkedin_id;
                  conv.contact_linkedin_url = match.contact_linkedin_url;
                  conv.contact_title = match.contact_title;
                  conv.contact_company = match.contact_company;
                }
                fetched = true;
                threadsFetched++;
              } else if (match) {
                // Match found but no additional messages (thread has ≤ 1 msg in API too)
                if (threadsFetched < 5) console.log(`[SR] thread no-op: ${conv.contact_name || "?"} has ${match.messages.length} msgs (same or fewer)`);
              }
            } catch (e) {
              console.warn("[SR] thread GraphQL fetch failed:", e.message);
            }
          }

          // NOTE: REST fallback endpoints (/messaging/conversations/{urn}/events and
          // voyagerMessagingDashMessengerMessages) consistently return 422/400.
          // LinkedIn has deprecated them in favor of GraphQL. Skipping to avoid
          // wasting ~2s per conversation on guaranteed failures.

          // Gentle delay between per-conversation fetches
          await new Promise((r) => setTimeout(r, 300));
        }
        console.log(`[SR] fetched full threads for ${threadsFetched} conversations`);
      }

      // ── Step 2c: Resolve missing contact names ──
      // The conversation list API doesn't include participant firstName/lastName.
      // Try: (1) Voyager profile resolution API, (2) DOM sidebar scraping.
      const unnamed = conversationIndex.filter((c) => !c.contact_name);
      if (unnamed.length > 0 && headers) {
        console.log(`[SR] ${unnamed.length} conversations still unnamed — attempting profile resolution`);

        // Collect unique participant URNs that need name resolution
        // We stored them in each conversation's internal data during extraction
        const urnSet = new Set();
        for (const c of unnamed) {
          // Extract member IDs from conversation URN for profile API
          const urnMatch = c.conversation_urn.match(/urn:li:fsd_profile:([A-Za-z0-9_-]+)/);
          if (urnMatch) {
            // The conversation URN contains participant profile IDs
            const convoMatch = c.conversation_urn.match(/urn:li:fsd_profile:([A-Za-z0-9_-]+)/g);
            if (convoMatch) {
              for (const m of convoMatch) {
                const id = m.replace("urn:li:fsd_profile:", "");
                // Skip our own profile
                const myId = (SR._myProfileUrn || "").split(":").pop() || "";
                if (id !== myId) urnSet.add(id);
              }
            }
          }
        }

        // Try Voyager REST API to resolve profiles in batch
        const profileIds = [...urnSet].slice(0, 50); // cap to avoid rate limits
        console.log(`[SR] resolving ${profileIds.length} profile URNs`);
        const resolvedNames = {}; // memberId → name

        for (const memberId of profileIds) {
          try {
            const profileUrn = `urn:li:fsd_profile:${memberId}`;
            const url = `https://www.linkedin.com/voyager/api/identity/dash/profiles?q=memberIdentity&memberIdentity=${memberId}&decorationId=com.linkedin.voyager.dash.deco.identity.profile.WebTopCardCore-18`;
            const res = await SR.fetchWithRetry(url, { headers, credentials: "include" }, { retries: 1, backoffMs: 500 });
            if (res.ok) {
              const data = await res.json();
              // Walk response for firstName/lastName
              const elements = data?.elements || data?.included || [];
              const allItems = Array.isArray(elements) ? elements : [data];
              if (data?.included) allItems.push(...data.included);
              for (const item of allItems) {
                const fn = typeof item.firstName === "string" ? item.firstName
                  : item.firstName?.text || "";
                const ln = typeof item.lastName === "string" ? item.lastName
                  : item.lastName?.text || "";
                if (fn || ln) {
                  resolvedNames[memberId] = [fn, ln].filter(Boolean).join(" ").trim();
                  break;
                }
              }
            }
            // Gentle delay to avoid rate limiting
            await new Promise((r) => setTimeout(r, 200));
          } catch (e) {
            console.warn("[SR] profile resolve failed for", memberId, e.message);
          }
        }

        console.log(`[SR] resolved ${Object.keys(resolvedNames).length} profile names:`, Object.values(resolvedNames).slice(0, 5));

        // Apply resolved names to unnamed conversations
        for (const c of unnamed) {
          if (c.contact_name) continue;
          const convoMatch = c.conversation_urn.match(/urn:li:fsd_profile:([A-Za-z0-9_-]+)/g);
          if (!convoMatch) continue;
          const myId = (SR._myProfileUrn || "").split(":").pop() || "";
          for (const m of convoMatch) {
            const id = m.replace("urn:li:fsd_profile:", "");
            if (id !== myId && resolvedNames[id]) {
              c.contact_name = resolvedNames[id];
              break;
            }
          }
        }

        // Fallback: DOM sidebar scraping for any still-unnamed conversations
        const stillUnnamed = conversationIndex.filter((c) => !c.contact_name);
        if (stillUnnamed.length > 0) {
          console.log(`[SR] ${stillUnnamed.length} still unnamed — trying DOM sidebar`);
          const domResults = scrapeMessagingSidebar();
          console.log(`[SR] DOM sidebar found ${domResults.length} conversations with names`);
          // Match DOM results to API conversations by thread ID overlap
          for (const dom of domResults) {
            const domThreadId = dom.conversation_urn.replace("thread:", "");
            for (const c of stillUnnamed) {
              if (c.contact_name) continue;
              // Match by thread ID substring in conversation URN
              if (c.conversation_urn.includes(domThreadId) || domThreadId.includes(c.conversation_urn.split(",").pop()?.replace(/[()=]/g, "") || "NOMATCH")) {
                c.contact_name = dom.contact_name;
                break;
              }
            }
          }
        }

        const finalUnnamed = conversationIndex.filter((c) => !c.contact_name).length;
        console.log(`[SR] after name resolution: ${conversationIndex.length - finalUnnamed} named, ${finalUnnamed} still unnamed`);
      }

      // ── Step 3: POST to backend in batches ──

      // Summary before posting
      const withName = conversationIndex.filter(c => c.contact_name).length;
      const withMsgs = conversationIndex.filter(c => c.messages.length > 1).length;
      const unread = conversationIndex.filter(c => c.is_unread).length;
      console.log(`[SR] sync summary: ${conversationIndex.length} convos, ${withName} named, ${withMsgs} with full threads, ${unread} unread`);
      if (conversationIndex.length > 0) {
        const s = conversationIndex[0];
        console.log(`[SR] sample convo: name="${s.contact_name}", msgs=${s.messages.length}, unread=${s.is_unread}, urn=${s.conversation_urn.slice(0, 60)}`);
      }

      const CHUNK = 20;
      const MAX_RETRIES = 2;
      let posted = 0;
      for (let i = 0; i < conversationIndex.length; i += CHUNK) {
        const batch = conversationIndex.slice(i, i + CHUNK);
        let ok = false;
        for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
          const res = await SR.apiPost("/linkedin/messages/sync", { conversations: batch });
          if (res?.ok) {
            console.log("[SR] messages batch ok:", JSON.stringify(res.data).slice(0, 200));
            ok = true;
            break;
          }
          console.warn(`[SR] messages batch error (attempt ${attempt + 1}):`, res?.error);
          if (attempt < MAX_RETRIES) await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
        }
        if (!ok) console.error("[SR] messages batch failed after retries, skipping chunk at", i);
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

  // ── Scroll sidebar to load all conversations ──
  // LinkedIn's React app uses virtual scrolling and IntersectionObserver to lazy-load
  // conversation items. Scroll to trigger LinkedIn's load → scrape → repeat until
  // no more conversations appear.
  //
  // Returns: { scrolled: number of scroll attempts, loaded: total conversations found }

  // Helper: find conversation item elements in LinkedIn's messaging sidebar.
  // LinkedIn's DOM structure changes frequently, so try multiple selectors.
  function findConversationElements() {
    // Ordered by specificity — most likely first
    const strategies = [
      { sel: "a[href*='/messaging/thread/']", desc: "thread links" },
      { sel: "li.msg-conversation-listitem", desc: "msg-conversation-listitem" },
      { sel: "div[class*='msg-conversation-listitem']", desc: "div msg-conversation-listitem" },
      { sel: "[data-entity-urn*='msg_conversation']", desc: "data-entity-urn conversation" },
      { sel: "[data-entity-urn*='thread']", desc: "data-entity-urn thread" },
      // LinkedIn sometimes uses role="option" or role="listitem" inside a role="list/listbox"
      { sel: "[role='list'] [role='option']", desc: "role=list>option" },
      { sel: "[role='listbox'] [role='option']", desc: "role=listbox>option" },
    ];

    for (const s of strategies) {
      const els = document.querySelectorAll(s.sel);
      if (els.length > 0) {
        console.log(`[SR] findConversationElements: ${els.length} via "${s.desc}" (${s.sel})`);
        return { elements: els, selector: s.sel, desc: s.desc };
      }
    }

    // Last resort: find any scrollable list inside the messaging area and count its direct children
    const msgArea = document.querySelector("[class*='msg-conversations-container']")
      || document.querySelector("[class*='scaffold-layout__list']")
      || document.querySelector("[class*='messaging']");
    if (msgArea) {
      // Look for a list-like container
      const lists = msgArea.querySelectorAll("ul, [role='list'], [role='listbox']");
      for (const list of lists) {
        const items = list.children;
        if (items.length >= 3) {
          console.log(`[SR] findConversationElements: ${items.length} via list children fallback (<${list.tagName} class="${(list.className || '').toString().slice(0, 60)}">`);
          return { elements: items, selector: null, desc: "list-children-fallback" };
        }
      }
    }

    return { elements: [], selector: null, desc: "none" };
  }

  async function scrollMessagingSidebarToLoadAll(maxScrolls = 200) {
    // Strategy: find conversation items in the DOM, then walk UP from the first
    // one to find its scrollable ancestor. This avoids guessing CSS selectors.
    let { elements: convEls, selector: itemSelector, desc: selectorDesc } = findConversationElements();

    if (convEls.length === 0) {
      console.warn("[SR] scroll: no conversation items found in DOM with any selector");
      return { scrolled: 0, loaded: 0 };
    }

    const firstItem = convEls[0];

    // Walk up from first conversation item to find the scrollable container
    let sidebar = null;
    let el = firstItem.parentElement;
    while (el && el !== document.body) {
      const style = window.getComputedStyle(el);
      const overflowY = style.overflowY || style.overflow;
      // A scrollable container has overflow auto/scroll AND scrollHeight > clientHeight
      if ((overflowY === "auto" || overflowY === "scroll") && el.scrollHeight > el.clientHeight + 50) {
        sidebar = el;
        break;
      }
      el = el.parentElement;
    }

    if (!sidebar) {
      // Fallback: try any scrollable element in the messaging area
      const candidates = document.querySelectorAll("[class*='msg'] *, [class*='messaging'] *");
      for (const c of candidates) {
        const style = window.getComputedStyle(c);
        const ov = style.overflowY || style.overflow;
        if ((ov === "auto" || ov === "scroll") && c.scrollHeight > c.clientHeight + 100) {
          sidebar = c;
          console.log("[SR] scroll: using fallback scrollable element");
          break;
        }
      }
    }

    if (!sidebar) {
      console.warn("[SR] scroll: no scrollable ancestor found for conversation items");
      return { scrolled: 0, loaded: 0 };
    }

    const tag = sidebar.tagName.toLowerCase();
    const cls = (sidebar.className || "").toString().slice(0, 80);
    console.log(`[SR] scroll: found container <${tag} class="${cls}"> (${sidebar.scrollHeight}px tall, items via "${selectorDesc}")`);

    let scrollAttempts = 0;
    let previousCount = 0;
    let stableCount = 0;
    const startTime = Date.now();
    const MAX_SCROLL_TIME_MS = 90000; // 90 seconds max total scroll time

    while (scrollAttempts < maxScrolls) {
      // Safety: cap total scroll time
      if (Date.now() - startTime > MAX_SCROLL_TIME_MS) {
        console.log(`[SR] scroll: time limit reached (${Math.round((Date.now() - startTime) / 1000)}s)`);
        break;
      }

      // Count conversation items using the same strategy that found items initially
      const currentCount = findConversationElements().elements.length;

      if (currentCount !== previousCount) {
        // Log progress every time new conversations appear
        console.log(`[SR] scroll: ${currentCount} conversations loaded (scroll #${scrollAttempts})`);
        stableCount = 0;
      } else {
        stableCount++;
        if (stableCount >= 5) {
          console.log(`[SR] scroll: no new items after 5 attempts — reached end at ${currentCount}`);
          break;
        }
      }
      previousCount = currentCount;

      // Scroll to bottom of container
      sidebar.scrollTop = sidebar.scrollHeight;

      // Wait for LinkedIn's React lazy-load to fire and render
      // Use longer delay (1200ms) to be reliable on slower connections
      await new Promise((r) => setTimeout(r, 1200));
      scrollAttempts++;
    }

    const total = findConversationElements().elements.length;
    console.log(`[SR] scroll done: ${scrollAttempts} scrolls, ${total} conversations in DOM`);
    return { scrolled: scrollAttempts, loaded: total };
  }

  // ── DOM scraper fallback for messaging sidebar ──
  // When voyager endpoints all fail, scrape what's visible in the LinkedIn
  // messaging UI. Each sidebar item has a thread link, contact name, preview,
  // and timestamp.

  function scrapeMessagingSidebar() {
    const results = [];
    const seen = new Set();

    // Find all conversation items using the multi-selector strategy
    const { elements: items, desc } = findConversationElements();
    console.log(`[SR] DOM sidebar: ${items.length} items via ${desc}`);

    // Diagnostic: log the first item's structure so we can find thread IDs
    if (items.length > 0) {
      const sample = items[0];
      const sampleTag = sample.tagName.toLowerCase();
      const sampleCls = (sample.className || "").toString().slice(0, 120);
      const sampleAttrs = [];
      for (const attr of (sample.attributes || [])) {
        sampleAttrs.push(`${attr.name}="${(attr.value || "").slice(0, 60)}"`);
      }
      console.log(`[SR] DOM sidebar first item: <${sampleTag} ${sampleAttrs.join(" ")}>`);
      // Log all links and data-attributes inside first item
      const innerLinks = sample.querySelectorAll("a[href]");
      for (const l of innerLinks) {
        console.log(`[SR] DOM sidebar first item link: ${(l.href || "").slice(0, 120)}`);
      }
      const dataEls = sample.querySelectorAll("[data-entity-urn], [data-thread-id], [data-conversation-urn]");
      for (const d of dataEls) {
        for (const attr of d.attributes) {
          if (attr.name.startsWith("data-")) {
            console.log(`[SR] DOM sidebar first item data: ${attr.name}="${(attr.value || "").slice(0, 100)}"`);
          }
        }
      }
      // Log the inner HTML structure (just tags and classes, not content)
      const logStructure = (el, depth) => {
        if (depth > 3) return;
        for (let i = 0; i < Math.min(el.children?.length || 0, 4); i++) {
          const ch = el.children[i];
          const chTag = ch.tagName?.toLowerCase() || "?";
          const chCls = (ch.className || "").toString().slice(0, 60);
          const chId = ch.id ? ` id="${ch.id}"` : "";
          const indent = "  ".repeat(depth);
          console.log(`[SR] DOM struct ${indent}<${chTag} class="${chCls}"${chId}>`);
          logStructure(ch, depth + 1);
        }
      };
      logStructure(sample, 0);
    }

    let itemIdx = 0;
    let noIdCount = 0;

    for (const item of items) {
      itemIdx++;
      const container = item; // li.msg-conversation-listitem IS the container

      // ── Extract thread ID from multiple sources ──
      let threadId = "";

      // 1. data-entity-urn on the item itself
      const entityUrn = item.getAttribute?.("data-entity-urn") || "";
      if (entityUrn) {
        // Full conversation URN: urn:li:msg_conversation:(urn:li:fsd_profile:XXX,THREAD_ID)
        const convoMatch = entityUrn.match(/,([A-Za-z0-9_+/=-]+)\)?$/);
        if (convoMatch) threadId = convoMatch[1];
        // Simpler URN formats
        if (!threadId) {
          const simpleMatch = entityUrn.match(/(?:thread|conversation)[:/]([A-Za-z0-9_+/=-]+)/);
          if (simpleMatch) threadId = simpleMatch[1];
        }
      }

      // 2. Any descendant with data-entity-urn
      if (!threadId) {
        const urnEls = item.querySelectorAll?.("[data-entity-urn]") || [];
        for (const urnEl of urnEls) {
          const urn = urnEl.getAttribute("data-entity-urn") || "";
          const m = urn.match(/,([A-Za-z0-9_+/=-]+)\)?$/);
          if (m) { threadId = m[1]; break; }
          const m2 = urn.match(/(?:thread|conversation)[:/]([A-Za-z0-9_+/=-]+)/);
          if (m2) { threadId = m2[1]; break; }
        }
      }

      // 3. Descendant <a> with /messaging/thread/ in href
      if (!threadId) {
        const innerLink = item.querySelector?.("a[href*='/messaging/thread/']");
        if (innerLink) {
          const innerHref = (innerLink.href || "").split("?")[0];
          threadId = innerHref.split("/messaging/thread/")[1]?.replace(/\/$/, "") || "";
        }
      }

      // 4. Any link inside the item — LinkedIn might use /messaging/ URLs without /thread/
      if (!threadId) {
        const anyLink = item.querySelector?.("a[href*='/messaging/']");
        if (anyLink) {
          const href = (anyLink.href || "").split("?")[0];
          // Extract last path segment as potential thread ID
          const segments = href.split("/").filter(Boolean);
          const lastSeg = segments[segments.length - 1] || "";
          if (lastSeg.length > 5 && lastSeg !== "messaging") threadId = lastSeg;
        }
      }

      // 5. Use item index as unique ID — guaranteed unique, no collisions
      if (!threadId) {
        threadId = `dom-item-${itemIdx}`;
        noIdCount++;
      }

      if (seen.has(threadId)) continue;
      seen.add(threadId);

      // ── Extract contact name ──
      const text = (container.innerText || "").replace(/\s+/g, " ").trim();
      let contactName = "";

      // Try img alt (profile picture)
      const img = container.querySelector("img[alt]");
      if (img && img.alt && img.alt.length > 1 && img.alt.length < 100) {
        contactName = img.alt.trim();
      }

      // Try aria-label on conversation item or its children
      if (!contactName) {
        const ariaEl = container.querySelector("[aria-label]") || container;
        const ariaLabel = ariaEl.getAttribute?.("aria-label") || "";
        if (ariaLabel) {
          contactName = ariaLabel
            .replace(/^conversation with /i, "")
            .replace(/'s? conversation$/i, "")
            .replace(/\s*\d+ (unread|new) messages?/i, "")
            .trim();
        }
      }

      // Try first meaningful text node
      if (!contactName && text) {
        // Split on common separators and take the first token that looks like a name
        const parts = text.split(/\s*[|·•]\s*|\n/);
        for (const p of parts) {
          const t = p.trim();
          if (t.length >= 2 && t.length < 80 && !/^\d/.test(t)) {
            contactName = t;
            break;
          }
        }
      }

      if (!contactName || contactName.length < 2) {
        // Still include the conversation even without a name — thread fetch will resolve it
        contactName = "";
      }

      // ── Timestamp ──
      let lastMessageAt = null;
      const timeEl = container.querySelector("time[datetime]");
      if (timeEl) lastMessageAt = timeEl.getAttribute("datetime");

      // ── Preview text: longest non-name text chunk ──
      let preview = "";
      const textParts = text.split(/\n/).map((s) => s.trim()).filter(Boolean);
      for (const part of textParts) {
        if (part === contactName) continue;
        if (part.length > preview.length && part.length > 5) preview = part;
      }

      // ── Unread badge ──
      const isUnread = !!(
        container.querySelector("[class*='unread']") ||
        container.querySelector("[class*='badge']") ||
        container.getAttribute("class")?.includes("unread")
      );

      results.push({
        conversation_urn: `thread:${threadId}`,
        contact_name: contactName.slice(0, 255) || null,
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

    console.log(`[SR] DOM sidebar scraped: ${results.length} conversations (${noIdCount} with synthetic IDs)`);
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
    // Helper: LinkedIn GraphQL wraps strings as {text:"value"} — unwrap them
    const str = (v) => {
      if (typeof v === "string") return v;
      if (v && typeof v === "object" && typeof v.text === "string") return v.text;
      return "";
    };

    // Helper: strip msg_messagingParticipant wrapper so all profile keys are
    // stored/looked-up under the INNER profile URN, never the wrapper URN.
    // e.g. "urn:li:msg_messagingParticipant:urn:li:fsd_profile:XXX" → "urn:li:fsd_profile:XXX"
    const normalizeProfileKey = (k) =>
      k ? k.replace(/^urn:li:msg_messagingParticipant:/, "") : "";

    const walk = (obj) => {
      if (!obj || typeof obj !== "object") return;
      if (Array.isArray(obj)) { for (const x of obj) walk(x); return; }

      const urn = typeof (obj.entityUrn || obj.$urn) === "string" ? (obj.entityUrn || obj.$urn) : "";

      // ─ Conversation objects ─
      if (urn && /urn:li:(?:fs|fsd|msg)_conversation:/i.test(urn)) {
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
        if (obj.read === false || obj.unreadCount > 0 || obj.categories?.includes?.("UNREAD")) c.is_unread = true;
        const actTs = obj.lastActivityAt || obj.lastActivityTime || obj.lastReadAt || obj.createdAt || obj.createdTime;
        if (actTs && !c.last_message_at) {
          const n = Number(actTs);
          if (!isNaN(n) && n > 1e12) c.last_message_at = new Date(n).toISOString();
          else if (!isNaN(n) && n > 1e9) c.last_message_at = new Date(n * 1000).toISOString();
          else c.last_message_at = String(actTs);
        } else if (actTs) {
          // Prefer a more recent timestamp if we already have one
          const n = Number(actTs);
          let candidate = null;
          if (!isNaN(n) && n > 1e12) candidate = new Date(n).toISOString();
          else if (!isNaN(n) && n > 1e9) candidate = new Date(n * 1000).toISOString();
          if (candidate && candidate > (c.last_message_at || "")) {
            c.last_message_at = candidate;
          }
        }

        // Extract conversation-level name/title if available
        // LinkedIn puts the contact display name in headlineText on conversation objects
        const convoName = str(obj.headlineText) || str(obj.shortHeadlineText) || str(obj.name) || str(obj.title) || str(obj.conversationName) || "";
        if (convoName && !c.contact_name) {
          c.contact_name = convoName.slice(0, 255);
        }

        // Collect participant URNs + inline profile data for contact attribution
        const parts = obj.participants || obj["*participants"] || obj.conversationParticipants
          || obj["*conversationParticipants"] || obj["*messengerConversationParticipants"]
          || obj.memberParticipants || [];
        const partArr = Array.isArray(parts) ? parts : (parts?.elements || []);
        if (partArr.length) {
          if (!participantsByConvo[urn]) participantsByConvo[urn] = new Set();
          for (const p of partArr) {
            const pUrn = typeof p === "string" ? p
              : (p?.entityUrn || p?.["*miniProfile"] || p?.participantProfile?.entityUrn
                 || p?.["*participantProfile"] || p?.["*messengerProfile"] || "");
            // Normalize: strip msg_messagingParticipant wrapper for consistent key matching
            const cleanPUrn = normalizeProfileKey(pUrn);
            if (cleanPUrn) participantsByConvo[urn].add(cleanPUrn);

            // GraphQL inline participant: extract profile data directly from participant object
            if (typeof p === "object" && p !== null) {
              const pInfo = p.participantProfile || p.messengerProfile || p;
              const pFirst = str(pInfo.firstName);
              const pLast = str(pInfo.lastName);
              if (pFirst || pLast) {
                const rawPKey = pUrn || pInfo.entityUrn || pInfo["*messengerProfile"]
                  || (pInfo["$type"] || "participant") + ":" + pFirst + ":" + pLast;
                const pKey = normalizeProfileKey(rawPKey);
                const pHead = str(pInfo.occupation || pInfo.headline || "");
                let pTitle = pHead, pCompany = "";
                if (pHead) {
                  const hm2 = pHead.match(/^(.+?)\s+(?:at|@)\s+(.+)$/i);
                  if (hm2) { pTitle = hm2[1].trim(); pCompany = hm2[2].trim(); }
                }
                const pPubId = str(pInfo.publicIdentifier);
                profilesByUrn[pKey] = {
                  name: [pFirst, pLast].filter(Boolean).join(" ").trim(),
                  linkedinId: pPubId,
                  url: pPubId ? `https://www.linkedin.com/in/${pPubId}/` : "",
                  title: pTitle,
                  company: pCompany,
                };
                // Make sure participantsByConvo has this normalized key so the join works
                if (pKey) participantsByConvo[urn].add(pKey);
              }
            }
          }
        }
      }

      // ─ Profile objects ─
      // LinkedIn GraphQL uses com.linkedin.messenger.MemberParticipantInfo with no URN
      // and wraps firstName/lastName as {text:"value"} objects
      const firstName = str(obj.firstName);
      const lastName = str(obj.lastName);
      const pubId = str(obj.publicIdentifier);

      const isProfileUrn = urn && /^urn:li:(fs_miniProfile|fsd_profile|fsd_miniProfile|dash_profile|fs_member|msg_member|member|messengerProfile|messagingMember|msg_messagingParticipant):/i.test(urn);
      const isProfileType = obj["$type"]
        && /profile|member|participant|person/i.test(obj["$type"])
        && (firstName || lastName);
      if (isProfileUrn || isProfileType || ((firstName || lastName) && urn)) {
        // Build a stable key: URN if available, else profileUrn ref, else synthesize from $type+name
        // Always normalize away the msg_messagingParticipant wrapper so keys are consistent
        const profileRef = normalizeProfileKey(obj["*messengerProfile"] || obj["*miniProfile"] || obj["*participantProfile"] || "");

        // CRITICAL: MemberParticipantInfo entities have profileUrl containing the fsd_profile ID
        // e.g. "https://www.linkedin.com/in/ACoAAEOBz6gB..." → urn:li:fsd_profile:ACoAAEOBz6gB...
        // This is the ONLY link between the named entity and the nameless msg_messagingParticipant.
        const profileUrlRaw = typeof obj.profileUrl === "string" ? obj.profileUrl : "";
        const profileUrlSlug = profileUrlRaw.match(/\/in\/([A-Za-z0-9_-]+)/);
        const profileUrlKey = profileUrlSlug ? `urn:li:fsd_profile:${profileUrlSlug[1]}` : "";

        const profileKey = normalizeProfileKey(urn) || profileRef || profileUrlKey
          || (obj["$type"] || "profile") + ":" + firstName + ":" + lastName;

        let newName = [firstName, lastName].filter(Boolean).join(" ").trim();
        let effectivePubId = pubId;
        let headlineRaw = str(obj.occupation) || str(obj.headline) || "";

        const headline = str(headlineRaw);
        let title = headline;
        let company = "";
        if (headline) {
          const hm = headline.match(/^(.+?)\s+(?:at|@)\s+(.+)$/i);
          if (hm) { title = hm[1].trim(); company = hm[2].trim(); }
        }

        // IMPORTANT: Never overwrite a profile that has a name with one that doesn't.
        // LinkedIn `included[]` can have both a named profile entity AND a nameless
        // msg_messagingParticipant wrapper entity sharing the same normalized key.
        const existing = profilesByUrn[profileKey];
        if (existing && existing.name && !newName) {
          // Keep the existing profile — it has a name, this one doesn't
        } else {
          profilesByUrn[profileKey] = {
            name: newName,
            linkedinId: effectivePubId || (profileUrlSlug ? profileUrlSlug[1] : "") || existing?.linkedinId || "",
            url: effectivePubId ? `https://www.linkedin.com/in/${effectivePubId}/` : (profileUrlRaw || existing?.url || ""),
            title: title || existing?.title || "",
            company: company || existing?.company || "",
          };
        }

        // If this profile-like object has a messengerProfile ref, also store under that key
        // so participant linking can find it
        if (profileRef && profileRef !== profileKey) {
          const refExisting = profilesByUrn[profileRef];
          if (!(refExisting && refExisting.name && !newName)) {
            profilesByUrn[profileRef] = profilesByUrn[profileKey];
          }
        }

        // CRITICAL: Also store under the fsd_profile URN derived from profileUrl.
        // This is how MemberParticipantInfo (named) links to msg_messagingParticipant (URN-keyed).
        // The join loop looks up participants by urn:li:fsd_profile:XXX — this ensures it finds
        // the named profile from MemberParticipantInfo.
        if (profileUrlKey && profileUrlKey !== profileKey) {
          const urlExisting = profilesByUrn[profileUrlKey];
          if (!(urlExisting && urlExisting.name && !newName)) {
            profilesByUrn[profileUrlKey] = profilesByUrn[profileKey];
            if (newName) console.log(`[SR] profileUrl linked: "${newName}" → ${profileUrlKey.slice(0, 60)}`);
          }
        }

      }

      // ─ Message event objects ─
      if (urn && /urn:li:(?:fs|fsd|msg)_(?:event|message):/i.test(urn)) {
        let text = "";
        if (obj.eventContent?.["com.linkedin.voyager.messaging.event.MessageEvent"]) {
          const me = obj.eventContent["com.linkedin.voyager.messaging.event.MessageEvent"];
          text = str(me?.attributedBody?.text) || str(me?.body?.text) || str(me?.body) || "";
        } else if (obj.body) {
          text = str(obj.body?.text) || str(obj.body);
        } else if (obj.attributedBody) {
          text = str(obj.attributedBody?.text) || str(obj.attributedBody);
        } else if (obj.text) {
          text = str(obj.text);
        }

        const convoRef = obj.conversation || obj["*conversation"] || obj.conversationUrn
          || obj.conversationThread || obj["*conversationThread"] || obj["*messengerConversation"] || "";
        let convoUrn = typeof convoRef === "string" ? convoRef : (convoRef?.entityUrn || "");
        // If convoUrn is empty, try to derive from this object's own URN
        // e.g. urn:li:msg_message:(urn:li:msg_conversation:xyz,eventId) → extract conversation URN
        if (!convoUrn && urn) {
          const nested = urn.match(/(urn:li:(?:fs|fsd|msg)_conversation:[^,)]+)/);
          if (nested) convoUrn = nested[1];
        }

        const fromRef = obj.from || obj.sender || obj["*from"] || obj.actor || obj["*actor"] || "";
        const fromUrnRaw = typeof fromRef === "string" ? fromRef : (fromRef?.entityUrn || fromRef?.["*miniProfile"] || "");
        // Normalize: strip msg_messagingParticipant wrapper for consistent key matching
        const fromUrn = normalizeProfileKey(fromUrnRaw);

        const rawTs = obj.createdAt || obj.timestamp || null;
        // Normalize to ISO string — LinkedIn sends epoch-ms (number or string)
        let sentAt = null;
        if (rawTs) {
          const n = Number(rawTs);
          if (!isNaN(n) && n > 1e12) sentAt = new Date(n).toISOString();       // epoch-ms
          else if (!isNaN(n) && n > 1e9) sentAt = new Date(n * 1000).toISOString(); // epoch-sec
          else sentAt = String(rawTs); // already ISO or unknown format
        }

        if (text && convoUrn) {
          if (!messagesByConvo[convoUrn]) messagesByConvo[convoUrn] = [];
          messagesByConvo[convoUrn].push({ text, sent_at: sentAt, fromUrn });
          // Track this sender as a participant of this conversation
          if (fromUrn) {
            if (!participantsByConvo[convoUrn]) participantsByConvo[convoUrn] = new Set();
            participantsByConvo[convoUrn].add(fromUrn);
          }
        }
      }

      // Recurse
      for (const key in obj) {
        const v = obj[key];
        if (v && typeof v === "object") walk(v);
      }
    };

    walk(data);

    // Post-walk summary: count named vs nameless profiles
    let namedCount = 0, namelessCount = 0;
    for (const [k, p] of Object.entries(profilesByUrn)) {
      if (p.name) namedCount++; else namelessCount++;
    }
    console.log(`[SR] profile resolution: ${namedCount} named, ${namelessCount} nameless out of ${namedCount + namelessCount} total`);

    // ── Create synthetic conversations for orphaned message buckets ──
    // Thread responses (messengerMessages) often contain message entities that
    // reference a conversationUrn but NO conversation entity. Without this step,
    // those messages are orphaned — they exist in messagesByConvo but the join
    // loop only iterates over `conversations`.
    let synthCount = 0;
    for (const convoUrn in messagesByConvo) {
      if (!conversations[convoUrn]) {
        conversations[convoUrn] = {
          conversation_urn: convoUrn,
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
        synthCount++;
      }
    }

    const nConvos = Object.keys(conversations).length;
    const nMsgBuckets = Object.keys(messagesByConvo).length;
    const nProfiles = Object.keys(profilesByUrn).length;
    const nParticipantSets = Object.keys(participantsByConvo).length;
    console.log(`[SR] extractConversationIndex: ${nConvos} conversations (${synthCount} synthetic), ${nMsgBuckets} msg buckets, ${nProfiles} profiles, ${nParticipantSets} participant sets`);
    // Debug: show first few profile keys and participant mappings
    if (nProfiles > 0) console.log("[SR] profile keys sample:", Object.keys(profilesByUrn).slice(0, 5));
    if (nParticipantSets > 0) {
      const firstConvo = Object.keys(participantsByConvo)[0];
      console.log("[SR] first convo participants:", firstConvo?.slice(0, 60), "→", [...(participantsByConvo[firstConvo] || [])].slice(0, 3));
    }

    // ── Join: messages + profiles → conversations ──

    const myUrn = SR._myProfileUrn || "";
    const myId = SR._myPublicId || "";
    const result = [];

    // Extract the member ID suffix from a URN for safe comparison.
    // e.g. "urn:li:fsd_profile:ABC123" → "ABC123"
    const urnMemberId = (urn) => {
      if (!urn) return "";
      const parts = urn.split(":");
      return parts[parts.length - 1] || "";
    };
    const myMemberId = urnMemberId(myUrn);

    // Check if two URNs refer to the same member (exact match or same member ID suffix)
    const urnMatch = (a, b) => {
      if (!a || !b) return false;
      if (a === b) return true;
      const idA = urnMemberId(a);
      const idB = urnMemberId(b);
      return idA && idB && idA === idB;
    };

    for (const convoUrn in conversations) {
      const c = conversations[convoUrn];
      // Sort messages by timestamp numerically (LinkedIn sends epoch-ms or ISO strings)
      const msgs = (messagesByConvo[convoUrn] || []).sort((a, b) => {
        const tA = Number(a.sent_at) || new Date(a.sent_at || 0).getTime();
        const tB = Number(b.sent_at) || new Date(b.sent_at || 0).getTime();
        return tA - tB;
      });

      // Determine is_mine for each message
      c.messages = msgs.map((m) => {
        let isMine = false;
        if (myUrn && m.fromUrn) {
          // Compare URN member IDs (handles different URN prefixes for same person)
          isMine = urnMatch(m.fromUrn, myUrn);
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
      // Build my name for synthetic-key matching (GraphQL profiles may lack URNs)
      const myProfile = profilesByUrn[myUrn] || null;
      const myName = myProfile?.name || "";

      const isMe = (key, profile) => {
        if (myUrn && urnMatch(key, myUrn)) return true;
        if (myMemberId && urnMemberId(key) === myMemberId) return true;
        if (myId && profile?.linkedinId === myId) return true;
        if (myName && profile?.name === myName) return true;
        return false;
      };

      const participants = participantsByConvo[convoUrn] || new Set();
      if (participants.size === 0) console.log("[SR] convo has 0 participants:", convoUrn.slice(0, 60));
      for (const rawPKey of participants) {
        // Normalize: strip msg_messagingParticipant wrapper → inner profile URN for lookup
        const pKey = normalizeProfileKey(rawPKey);
        const p = profilesByUrn[pKey];
        if (!p) {
          // Try member ID suffix match — different URN types for same person
          const pId = urnMemberId(pKey);
          if (pId) {
            for (const pk in profilesByUrn) {
              if (urnMemberId(pk) === pId && !isMe(pk, profilesByUrn[pk])) {
                const found = profilesByUrn[pk];
                c.contact_name = found.name;
                c.contact_linkedin_id = found.linkedinId;
                c.contact_linkedin_url = found.url;
                c.contact_title = found.title;
                c.contact_company = found.company;
                break;
              }
            }
          }
          if (c.contact_name) break;
          continue;
        }
        if (isMe(pKey, p)) continue;
        if (p?.name) {
          c.contact_name = p.name;
          c.contact_linkedin_id = p.linkedinId;
          c.contact_linkedin_url = p.url;
          c.contact_title = p.title;
          c.contact_company = p.company;
          break;
        }
      }

      // Fallback 2: derive contact from message sender URNs (non-me senders)
      if (!c.contact_name) {
        for (const m of msgs) {
          if (!m.fromUrn || (myUrn && urnMatch(m.fromUrn, myUrn))) continue;
          // Try exact key first, then try matching by member ID suffix
          let p = profilesByUrn[m.fromUrn];
          if (!p) {
            const senderId = urnMemberId(m.fromUrn);
            if (senderId) {
              for (const pk in profilesByUrn) {
                if (urnMemberId(pk) === senderId) { p = profilesByUrn[pk]; break; }
              }
            }
          }
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

      // NOTE: We intentionally do NOT fall back to "any non-me profile in the
      // global registry" — that assigns the WRONG person to every conversation
      // that doesn't have participant data. Better to show "Unknown" than a
      // wrong name. The per-conversation thread fetch (Step 2b) will fill in
      // the correct names when it re-extracts from per-thread API responses.

      if (c.messages.length > 0) {
        c.last_message_at = c.last_message_at || c.messages[c.messages.length - 1].sent_at;
        c.last_sender = c.messages[c.messages.length - 1].sender;
      }

      if (c.contact_name || c.messages.length > 0) {
        result.push(c);
      }
    }
    return result;
  }
})();
