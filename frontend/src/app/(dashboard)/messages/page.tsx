"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getInbox, type InboxConversation, type InboxMessage } from "@/lib/api";

// ── Filter tabs ──────────────────────────────────────────────────────────────

const FILTERS = [
  { key: "all", label: "All" },
  { key: "job_related", label: "Job Related" },
  { key: "recruiter", label: "Recruiters" },
  { key: "needs_reply", label: "Needs Reply" },
  { key: "unread", label: "Unread" },
] as const;

type FilterKey = (typeof FILTERS)[number]["key"];

// ── Badge colors ─────────────────────────────────────────────────────────────

function classificationBadge(c: string | null) {
  switch (c) {
    case "recruiter":
      return { label: "Recruiter", bg: "bg-purple-500/15", text: "text-purple-400" };
    case "opportunity":
      return { label: "Opportunity", bg: "bg-emerald-500/15", text: "text-emerald-400" };
    case "interview":
      return { label: "Interview", bg: "bg-amber-500/15", text: "text-amber-400" };
    case "networking":
      return { label: "Network", bg: "bg-blue-500/15", text: "text-blue-400" };
    default:
      return null;
  }
}

// ── Time formatting ──────────────────────────────────────────────────────────

function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d`;
  if (diffDay < 30) return `${Math.floor(diffDay / 7)}w`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const sameDay =
    d.getDate() === now.getDate() &&
    d.getMonth() === now.getMonth() &&
    d.getFullYear() === now.getFullYear();
  if (sameDay) return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

// ── Component ────────────────────────────────────────────────────────────────

const PAGE_SIZE = 2000;

export default function MessagesPage() {
  const [conversations, setConversations] = useState<InboxConversation[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<InboxConversation | null>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  // Fetch first page (resets list)
  const fetchInbox = useCallback(
    async (f: FilterKey, s: string) => {
      setLoading(true);
      setError(null);
      try {
        const res = await getInbox({
          filter: f === "all" ? undefined : f,
          search: s || undefined,
          limit: PAGE_SIZE,
          offset: 0,
        });
        setConversations(res.conversations);
        setTotal(res.total);
      } catch (e: any) {
        console.error("Failed to load inbox", e);
        setError(e?.message || "Failed to load messages. The API may be down.");
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  // Fetch next page (appends to list)
  const fetchMore = useCallback(async () => {
    if (loadingMore) return;
    setLoadingMore(true);
    try {
      const res = await getInbox({
        filter: filter === "all" ? undefined : filter,
        search: search || undefined,
        limit: PAGE_SIZE,
        offset: conversations.length,
      });
      setConversations((prev) => [...prev, ...res.conversations]);
      setTotal(res.total);
    } catch (e) {
      console.error("Failed to load more", e);
    } finally {
      setLoadingMore(false);
    }
  }, [filter, search, conversations.length, loadingMore]);

  useEffect(() => {
    fetchInbox(filter, search);
  }, [filter, fetchInbox]); // eslint-disable-line react-hooks/exhaustive-deps

  // Infinite scroll: load more when near bottom of conversation list
  const handleListScroll = useCallback(() => {
    const el = listRef.current;
    if (!el || loadingMore || loading) return;
    if (conversations.length >= total) return; // all loaded
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 300;
    if (nearBottom) fetchMore();
  }, [loadingMore, loading, conversations.length, total, fetchMore]);

  const handleSearch = (val: string) => {
    setSearch(val);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => fetchInbox(filter, val), 350);
  };

  // Preview text: last message truncated
  function preview(conv: InboxConversation): string {
    if (!conv.messages?.length) return "No messages";
    const last = conv.messages[conv.messages.length - 1];
    const prefix = last.is_mine ? "You: " : "";
    const text = last.text || "";
    return prefix + (text.length > 100 ? text.slice(0, 100) + "…" : text);
  }

  return (
    <div className="flex h-[calc(100vh-1px)] overflow-hidden">
      {/* ── Left panel: conversation list ────────────────────────────── */}
      <div className="w-[380px] flex-shrink-0 border-r border-white/[0.06] flex flex-col">
        {/* Header */}
        <div className="px-5 pt-6 pb-3">
          <h1 className="text-lg font-semibold text-white/90 mb-3">Messages</h1>

          {/* Search */}
          <div className="relative mb-3">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 text-[#555C7A]"
              width="14"
              height="14"
              viewBox="0 0 16 16"
              fill="none"
            >
              <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.5" />
              <path d="M10.5 10.5L14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <input
              type="text"
              placeholder="Search name, company, title…"
              value={search}
              onChange={(e) => handleSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 rounded-lg border border-[rgba(255,255,255,0.1)] bg-[rgba(255,255,255,0.04)] text-white text-sm placeholder:text-[rgba(255,255,255,0.3)] focus:outline-none focus:ring-2 focus:ring-[#4d8ef5]/20"
            />
          </div>

          {/* Filter tabs */}
          <div className="flex gap-1.5 overflow-x-auto pb-1 scrollbar-none">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium whitespace-nowrap transition-colors ${
                  filter === f.key
                    ? "bg-[#7F8CFF]/15 text-[#7F8CFF]"
                    : "text-[#6B7194] hover:bg-white/[0.04] hover:text-[#8B92B0]"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto" ref={listRef} onScroll={handleListScroll}>
          {loading ? (
            <div className="px-5 py-12 text-center text-[#555C7A] text-sm">Loading…</div>
          ) : error ? (
            <div className="px-5 py-12 text-center">
              <div className="text-red-400 text-sm mb-1">Failed to load messages</div>
              <div className="text-[#3E4460] text-xs">{error}</div>
              <button
                onClick={() => fetchInbox(filter, search)}
                className="mt-3 px-3 py-1.5 rounded-lg bg-[#7F8CFF]/15 text-[#7F8CFF] text-xs font-medium hover:bg-[#7F8CFF]/25 transition-colors"
              >
                Retry
              </button>
            </div>
          ) : conversations.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <div className="text-[#555C7A] text-sm mb-1">No conversations found</div>
              <div className="text-[#3E4460] text-xs">
                {filter !== "all"
                  ? "Try a different filter"
                  : "Sync your LinkedIn messages from the extension"}
              </div>
            </div>
          ) : (
            <>
              <div className="px-5 pb-1.5 text-[11px] text-[#555C7A]">
                {total} conversation{total !== 1 ? "s" : ""}
              </div>
              {conversations.map((conv) => {
                const isSelected = selected?.id === conv.id;
                const badge = classificationBadge(conv.classification);
                return (
                  <button
                    key={conv.id}
                    onClick={() => setSelected(conv)}
                    className={`w-full text-left px-5 py-3.5 border-b border-white/[0.03] transition-colors ${
                      isSelected
                        ? "bg-[#7F8CFF]/8"
                        : "hover:bg-white/[0.03]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <div className="flex items-center gap-2 min-w-0">
                        {/* Avatar */}
                        <div
                          className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-semibold ${
                            conv.is_unread
                              ? "bg-[#7F8CFF]/20 text-[#7F8CFF]"
                              : "bg-white/[0.06] text-[#6B7194]"
                          }`}
                        >
                          {conv.contact_name?.[0]?.toUpperCase() || "?"}
                        </div>
                        <div className="min-w-0">
                          {conv.contact_linkedin_url ? (
                            <a
                              href={conv.contact_linkedin_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="text-[13px] truncate block font-semibold text-[#7F8CFF] hover:text-white underline decoration-[#7F8CFF]/40 hover:decoration-white/60 transition-colors"
                            >
                              {conv.contact_name || "Unknown"}
                            </a>
                          ) : (
                            <div
                              className={`text-[13px] truncate ${
                                conv.is_unread ? "font-semibold text-white" : "font-medium text-white/80"
                              }`}
                            >
                              {conv.contact_name || "Unknown"}
                            </div>
                          )}
                          {conv.contact_company && (
                            <div className="text-[11px] text-[#555C7A] truncate">
                              {conv.contact_title ? `${conv.contact_title} · ` : ""}
                              {conv.contact_company}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1 flex-shrink-0">
                        <span className="text-[11px] text-[#555C7A]">
                          {relativeTime(conv.last_message_at)}
                        </span>
                        {conv.is_unread && (
                          <span className="w-2 h-2 rounded-full bg-[#7F8CFF]" />
                        )}
                      </div>
                    </div>
                    {/* Preview + badges */}
                    <div className="pl-10">
                      <div className="text-[12px] text-[#6B7194] truncate leading-relaxed">
                        {preview(conv)}
                      </div>
                      <div className="flex gap-1.5 mt-1.5">
                        {badge && (
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${badge.bg} ${badge.text}`}
                          >
                            {badge.label}
                          </span>
                        )}
                        {conv.is_job_related && !badge && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400">
                            Job Related
                          </span>
                        )}
                        {conv.days_since_reply != null && conv.days_since_reply > 0 && conv.last_sender === "them" && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-400">
                            {conv.days_since_reply}d waiting
                          </span>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}
              {/* Load more indicator */}
              {conversations.length < total && (
                <div className="px-5 py-4 text-center">
                  {loadingMore ? (
                    <div className="text-[12px] text-[#555C7A]">Loading more…</div>
                  ) : (
                    <button
                      onClick={fetchMore}
                      className="text-[12px] text-[#7F8CFF] hover:text-[#9BA6FF] transition-colors"
                    >
                      Load more ({total - conversations.length} remaining)
                    </button>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── Right panel: thread detail ───────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        {selected ? (
          <ThreadDetail conversation={selected} />
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <svg
                className="mx-auto mb-3 text-[#3E4460]"
                width="40"
                height="40"
                viewBox="0 0 16 16"
                fill="none"
              >
                <path
                  d="M2 3.5C2 2.67 2.67 2 3.5 2H12.5C13.33 2 14 2.67 14 3.5V10.5C14 11.33 13.33 12 12.5 12H5L2 14.5V3.5Z"
                  stroke="currentColor"
                  strokeWidth="1.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <div className="text-sm text-[#555C7A]">Select a conversation</div>
              <div className="text-xs text-[#3E4460] mt-1">
                Choose a thread from the left to view the full conversation
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Thread detail component ──────────────────────────────────────────────────

function ThreadDetail({ conversation }: { conversation: InboxConversation }) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const badge = classificationBadge(conversation.classification);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation.id]);

  const messages = conversation.messages ?? [];

  return (
    <>
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/[0.06] flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-full bg-[#7F8CFF]/15 text-[#7F8CFF] flex items-center justify-center text-sm font-semibold flex-shrink-0">
            {conversation.contact_name?.[0]?.toUpperCase() || "?"}
          </div>
          <div className="min-w-0">
            {conversation.contact_linkedin_url ? (
              <a href={conversation.contact_linkedin_url} target="_blank" rel="noopener noreferrer"
                className="text-[14px] font-semibold text-[#7F8CFF] truncate block hover:text-white underline decoration-[#7F8CFF]/40 hover:decoration-white/60 transition-colors">
                {conversation.contact_name || "Unknown"}
              </a>
            ) : (
              <div className="text-[14px] font-semibold text-white/90 truncate">
                {conversation.contact_name || "Unknown"}
              </div>
            )}
            <div className="text-[12px] text-[#6B7194] truncate">
              {[conversation.contact_title, conversation.contact_company]
                .filter(Boolean)
                .join(" · ") || "LinkedIn connection"}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {badge && (
            <span
              className={`px-2 py-1 rounded-md text-[11px] font-medium ${badge.bg} ${badge.text}`}
            >
              {badge.label}
            </span>
          )}
          {conversation.contact_linkedin_url && (
            <a
              href={conversation.contact_linkedin_url}
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 rounded-lg text-[#555C7A] hover:bg-white/[0.04] hover:text-[#8B92B0] transition-colors"
              title="View on LinkedIn"
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path
                  d="M6 3H3V13H6V3Z"
                  fill="currentColor"
                  opacity="0.3"
                />
                <path
                  d="M4.5 2C3.67 2 3 2.67 3 3.5C3 4.33 3.67 5 4.5 5C5.33 5 6 4.33 6 3.5C6 2.67 5.33 2 4.5 2Z"
                  fill="currentColor"
                />
                <path d="M3 6.5H6V14H3V6.5Z" fill="currentColor" />
                <path
                  d="M8.5 6.5H11V7.5C11.5 6.8 12.3 6.3 13.3 6.3C14.8 6.3 15.5 7.3 15.5 9V14H13V9.5C13 8.7 12.7 8.2 12 8.2C11.2 8.2 10.8 8.8 10.8 9.6V14H8.5V6.5Z"
                  fill="currentColor"
                  opacity="0.6"
                />
              </svg>
            </a>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
        {messages.length === 0 ? (
          <div className="text-center text-[#555C7A] text-sm py-12">No messages in this thread</div>
        ) : (
          messages.map((msg: InboxMessage, i: number) => (
            <div
              key={i}
              className={`flex ${msg.is_mine ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[70%] rounded-xl px-4 py-2.5 ${
                  msg.is_mine
                    ? "bg-[#7F8CFF]/15 text-white/90"
                    : "bg-white/[0.06] text-white/80"
                }`}
              >
                <div className="text-[13px] leading-relaxed whitespace-pre-wrap break-words">
                  {msg.text}
                </div>
                <div
                  className={`text-[10px] mt-1.5 ${
                    msg.is_mine ? "text-[#7F8CFF]/50 text-right" : "text-[#555C7A]"
                  }`}
                >
                  {formatTimestamp(msg.sent_at)}
                </div>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* AI Draft banner (if available) */}
      {conversation.ai_draft_reply && (
        <div className="mx-6 mb-4 px-4 py-3 rounded-xl bg-[#7F8CFF]/8 border border-[#7F8CFF]/15">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-semibold text-[#7F8CFF] uppercase tracking-wider">
              AI Suggested Reply
            </span>
            <button
              onClick={() => {
                window.postMessage(
                  {
                    type: "SR_SEND_LINKEDIN_MESSAGE",
                    conversationUrn: conversation.conversation_urn,
                    draftText: conversation.ai_draft_reply,
                  },
                  window.location.origin,
                );
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#7F8CFF]/20 hover:bg-[#7F8CFF]/30 text-[#7F8CFF] text-[11px] font-semibold transition-colors"
            >
              <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                <path d="M14 2L7 9M14 2L9.5 14L7 9M14 2L2 6.5L7 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Send on LinkedIn
            </button>
          </div>
          <div className="text-[13px] text-white/70 leading-relaxed whitespace-pre-wrap">
            {conversation.ai_draft_reply}
          </div>
        </div>
      )}
    </>
  );
}
