// @ts-nocheck
"use client";

import { useState, useEffect } from "react";
import { initials, avatarColor, getAuthHeaders } from "@/lib/utils";

/* ── Types ─────────────────────────────────────────────────────────── */

interface Connection {
  id: string;
  name: string;
  role: string;
  company: string;
  source: "worked_together" | "alumni" | "location" | "mutual";
  sourceLabel: string;
  avatarInitials: string;
  avatarColor: string;
  linkedinUrl: string;
  suggestedMessage: string;
}

interface KeyPerson {
  id: string;
  name: string;
  role: string;
  company: string;
  /** 0 = no 1st/2nd label (3rd+ or unknown) */
  connectionDegree: 0 | 1 | 2;
  linkedinUrl: string;
  avatarInitials: string;
  avatarColor: "blue" | "teal" | "amber" | "purple" | "coral";
  connections: Connection[];
}

interface ConnectionPathProps {
  company: string;
  role: string;
}

/* ── Colors ────────────────────────────────────────────────────────── */

const AVATAR: Record<string, { bg: string; text: string }> = {
  blue:   { bg: "#1a3a6e", text: "#4d8ef5" },
  teal:   { bg: "#0f2e28", text: "#22c55e" },
  amber:  { bg: "#2e2008", text: "#fbbf24" },
  purple: { bg: "#1e1a3e", text: "#a78bfa" },
  coral:  { bg: "#2e1208", text: "#f87171" },
};

const DEGREE: Record<1 | 2, { bg: string; text: string; label: string }> = {
  1: { bg: "rgba(34,197,94,0.15)",  text: "#22c55e", label: "1st" },
  2: { bg: "rgba(251,191,36,0.15)", text: "#fbbf24", label: "2nd" },
};

const SOURCE: Record<string, { bg: string; border: string; text: string }> = {
  worked_together: { bg: "rgba(34,197,94,0.12)",  border: "rgba(34,197,94,0.25)",  text: "#22c55e" },
  alumni:          { bg: "rgba(167,139,250,0.12)", border: "rgba(167,139,250,0.25)", text: "#a78bfa" },
  location:        { bg: "rgba(251,191,36,0.12)",  border: "rgba(251,191,36,0.25)",  text: "#fbbf24" },
  mutual:          { bg: "rgba(77,142,245,0.12)",  border: "rgba(77,142,245,0.25)",  text: "#4d8ef5" },
};

// color() and initials() imported from @/lib/utils (avatarColor, initials)
const color = avatarColor;


/* ── Data fetching ─────────────────────────────────────────────────── */

function useConnectionPath(company: string, role: string) {
  const [loading, setLoading] = useState(false);
  const [people, setPeople] = useState<KeyPerson[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [autoLoaded, setAutoLoaded] = useState(false);

  // Auto-refresh when user switches back to this tab (after visiting LinkedIn)
  useEffect(() => {
    function onFocus() {
      if (people !== null) {
        // User came back — silently refresh to pick up new mutual connections
        load();
      }
    }
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [people, company, role]);

  // Auto-load on mount
  useEffect(() => {
    if (!autoLoaded) {
      setAutoLoaded(true);
      load();
    }
  }, [autoLoaded]);

  async function load() {
    setLoading(true);
    setError(null);
    const headers = getAuthHeaders();
    try {
      const res = await fetch("/api/v1/relationships/find-way-in", {
        method: "POST",
        headers,
        body: JSON.stringify({ company, role }),
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data = await res.json();

      const mapped = mapApiToKeyPeople(data, company, role);
      setPeople(mapped);
    } catch (e: any) {
      console.error("ConnectionPath load failed:", e);
      setError(e.message);
      setPeople([]);
    }
    setLoading(false);
  }

  return { loading, people, error, load };
}

function mapApiToKeyPeople(data: any, company: string, role: string): KeyPerson[] {
  const people: KeyPerson[] = [];
  const seenPeople = new Set<string>();

  // Primary source: backend-enforced discover_targets (3–5).
  const discoverTargets = Array.isArray(data.discover_targets) ? data.discover_targets : [];
  for (const t of discoverTargets) {
    const degree: 0 | 1 | 2 = t.degree === "1st" ? 1 : t.degree === "2nd" ? 2 : 0;
    const idKey = String(t.linkedin_url || t.name || "").toLowerCase();
    if (!idKey || seenPeople.has(idKey)) continue;
    seenPeople.add(idKey);

    const connections: Connection[] = [];
    if (degree === 1 && t.message) {
      connections.push({
        id: `d-${t.name}`,
        name: t.name,
        role: t.title || "",
        company: company,
        source: "mutual",
        sourceLabel: "Direct connection",
        avatarInitials: initials(t.name || ""),
        avatarColor: color(t.name || ""),
        linkedinUrl: t.linkedin_url || "",
        suggestedMessage: t.message,
      });
    } else if (degree === 2 && t.connection_path?.connector_name) {
      connections.push({
        id: `c-${t.connection_path.connector_name}-${t.name}`,
        name: t.connection_path.connector_name,
        role: t.connection_path.connector_title || "",
        company: t.connection_path.connector_company || "",
        source: "mutual",
        sourceLabel: "Mutual connection",
        avatarInitials: initials(t.connection_path.connector_name || ""),
        avatarColor: color(t.connection_path.connector_name || ""),
        linkedinUrl: t.connection_path.connector_url || "",
        suggestedMessage: t.message || `Hi ${t.connection_path.connector_name?.split(" ")[0] || "there"}, would you be open to introducing me to ${t.name} at ${company}?`,
      });
    }

    people.push({
      id: `target-${t.name || t.linkedin_url}`,
      name: t.name || "Target Contact",
      role: t.title || "",
      company: company,
      connectionDegree: degree,
      linkedinUrl: t.linkedin_url || "",
      avatarInitials: initials(t.name || "T"),
      avatarColor: color(t.name || "Target"),
      connections,
    });
  }

  // Safety fallback: if backend returns fewer than 3, top up from direct contacts.
  if (people.length < 3) {
    for (const c of (data.direct_contacts || [])) {
      const idKey = String(c.linkedin_url || c.name || "").toLowerCase();
      if (!idKey || seenPeople.has(idKey)) continue;
      seenPeople.add(idKey);
      people.push({
        id: c.connection_id || c.name,
        name: c.name,
        role: c.title || "",
        company: c.company || company,
        connectionDegree: 1,
        linkedinUrl: c.linkedin_url || "",
        avatarInitials: initials(c.name || ""),
        avatarColor: color(c.name || ""),
        connections: [{
          id: "d-" + c.name,
          name: c.name,
          role: c.title || "",
          company: c.company || company,
          source: "mutual",
          sourceLabel: "Direct connection",
          avatarInitials: initials(c.name || ""),
          avatarColor: color(c.name || ""),
          linkedinUrl: c.linkedin_url || "",
          suggestedMessage: c.message || `Hi ${c.name.split(" ")[0]}, I'm exploring the ${role} role at ${company} and would love to connect.`,
        }],
      });
      if (people.length >= 3) break;
    }
  }

  return people.slice(0, 5);
}

/* ── Component ─────────────────────────────────────────────────────── */

export default function ConnectionPathPanel({ company, role }: ConnectionPathProps) {
  const { loading, people, error, load } = useConnectionPath(company, role);
  const [openId, setOpenId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  function toggle(id: string) { setOpenId(openId === id ? null : id); }
  function copy(text: string, id: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    });
  }

  // Error state
  if (error && (!people || people.length === 0)) {
    return (
      <div className="rounded-xl p-6" style={{ background: "#0d0f1e", border: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="text-[13px] text-red-400 mb-2">Failed to load connection paths</div>
        <div className="text-[11px] text-[#555C7A] mb-3">{error}</div>
        <button onClick={load} className="text-[12px] font-semibold text-[#4d8ef5]">Try again</button>
      </div>
    );
  }

  // Not loaded yet — show the trigger button
  if (!people && !loading) {
    return (
      <div className="rounded-xl p-6 text-center" style={{ background: "#0d0f1e", border: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="text-[13px] text-[#8B92B0] mb-3">Find your way into {company}</div>
        <button onClick={load}
          className="px-5 py-2.5 text-[13px] font-semibold text-white rounded-lg"
          style={{ background: "linear-gradient(135deg, #5B6CFF 0%, #7F8CFF 100%)" }}>
          Find My Way In
        </button>
      </div>
    );
  }

  // Loading
  if (loading) {
    return (
      <div className="rounded-xl p-5 space-y-3" style={{ background: "#0d0f1e" }}>
        <div className="h-4 w-72 rounded animate-pulse" style={{ background: "rgba(255,255,255,0.06)" }} />
        <div className="h-3 w-96 rounded mt-1 animate-pulse" style={{ background: "rgba(255,255,255,0.04)" }} />
        {[1, 2, 3].map(i => (
          <div key={i} className="rounded-xl p-5 animate-pulse" style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)" }}>
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full" style={{ background: "rgba(255,255,255,0.08)" }} />
              <div className="flex-1">
                <div className="h-4 w-40 rounded" style={{ background: "rgba(255,255,255,0.08)" }} />
                <div className="h-3 w-56 rounded mt-2" style={{ background: "rgba(255,255,255,0.06)" }} />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Empty
  if (!people?.length) {
    return (
      <div className="rounded-xl p-10 text-center" style={{ background: "#0d0f1e", border: "1px solid rgba(255,255,255,0.06)" }}>
        <svg className="mx-auto mb-3" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#555C7A" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
        <div className="text-[14px] font-medium text-[#8B92B0]">No connections mapped yet</div>
        <div className="text-[12px] text-[#555C7A] mt-1.5 max-w-xs mx-auto">
          Visit the LinkedIn profiles of key people at {company} and the extension will automatically map your path
        </div>
      </div>
    );
  }

  /* ── Render ── */
  return (
    <div className="rounded-xl p-5" style={{ background: "#0d0f1e" }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-[#555C7A]">
          Key people to contact — {role} role at {company}
        </div>
        <button onClick={load} className="text-[11px] text-[#7F8CFF] font-medium hover:text-white transition-colors">
          Refresh
        </button>
      </div>

      <div className="space-y-3">
        {people.map(person => {
          const open = openId === person.id;
          const ac = AVATAR[person.avatarColor] || AVATAR.blue;
          const degBadge = person.connectionDegree === 1 ? DEGREE[1] : person.connectionDegree === 2 ? DEGREE[2] : null;

          return (
            <div key={person.id}>
              {/* ── Target card ── */}
              <div
                className="rounded-xl transition-all duration-200"
                style={{
                  background: open ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.04)",
                  border: `1px solid ${open ? "rgba(77,142,245,0.3)" : "rgba(255,255,255,0.06)"}`,
                }}
              >
                <div className="p-4 flex items-center gap-3.5">
                  <div className="w-12 h-12 rounded-full flex items-center justify-center text-[15px] font-bold shrink-0"
                    style={{ background: ac.bg, color: ac.text }}>
                    {person.avatarInitials}
                  </div>
                  <div className="flex-1 min-w-0">
                    {person.linkedinUrl ? (
                      <a href={person.linkedinUrl} target="_blank" rel="noopener noreferrer"
                        className="text-[15px] font-semibold text-[#7F8CFF] hover:text-white underline decoration-[#7F8CFF]/40 hover:decoration-white/60 transition-colors cursor-pointer">
                        {person.name}
                      </a>
                    ) : (
                      <div className="text-[15px] font-semibold text-white">{person.name}</div>
                    )}
                    <div className="text-[12px] text-[#8B92B0]">{person.role} · {person.company}</div>
                  </div>
                  {degBadge && (
                    <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full shrink-0"
                      style={{ background: degBadge.bg, color: degBadge.text }}>
                      {degBadge.label}
                    </span>
                  )}
                  <button onClick={() => toggle(person.id)}
                    className="text-[12px] font-semibold px-4 py-2 rounded-lg shrink-0 transition-all duration-200"
                    style={{
                      background: open ? "#4d8ef5" : "rgba(255,255,255,0.06)",
                      color: open ? "#fff" : "#ccc",
                      border: `1px solid ${open ? "#4d8ef5" : "rgba(255,255,255,0.1)"}`,
                    }}>
                    {open ? "Close \u00d7" : "Leverage my connections \u2192"}
                  </button>
                </div>
              </div>

              {/* ── Expanded panel ── */}
              <div style={{
                maxHeight: open ? "99999px" : "0px",
                opacity: open ? 1 : 0,
                overflow: "hidden",
                transition: "max-height 0.3s ease, opacity 0.3s ease",
              }}>
                <div className="pt-5 pb-3 px-1">
                  {/* Panel header */}
                  <div className="mb-4">
                    <div className="text-[15px] font-medium text-white">Your path to {person.name}</div>
                    {person.connectionDegree === 1 ? (
                      <div className="text-[13px] text-[#22c55e] mt-0.5">
                        You're directly connected — reach out directly
                      </div>
                    ) : person.connectionDegree === 2 ? (
                      <div className="text-[13px] text-[#8B92B0] mt-0.5">
                        {person.connections.length} {person.connections.length === 1 ? "person" : "people"} can introduce you — each from a different angle
                      </div>
                    ) : (
                      <div className="text-[13px] text-[#8B92B0] mt-0.5">
                        No direct link or verified mutual path yet. Visit their profile with the extension to map your network, or reach out from LinkedIn.
                      </div>
                    )}
                  </div>

                  {/* 1st degree — direct message */}
                  {person.connectionDegree === 1 && person.connections.length > 0 && (
                    <div className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)" }}>
                      <div className="rounded-lg p-4" style={{ background: "rgba(255,255,255,0.03)", borderLeft: "3px solid #22c55e" }}>
                        <div className="text-[12px] text-[#ccc] leading-relaxed">"{person.connections[0].suggestedMessage}"</div>
                      </div>
                      <div className="flex gap-2.5 mt-3">
                        <button
                          onClick={() => {
                            window.postMessage({
                              type: "SR_SEND_LINKEDIN_MESSAGE",
                              linkedinUrl: person.linkedinUrl,
                              draftText: person.connections[0].suggestedMessage,
                            }, window.location.origin);
                          }}
                          className="text-[12px] font-semibold px-4 py-2 rounded-lg inline-flex items-center gap-1.5"
                          style={{ background: "rgba(127,140,255,0.15)", border: "1px solid rgba(127,140,255,0.25)", color: "#7F8CFF" }}>
                          <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                            <path d="M14 2L7 9M14 2L9.5 14L7 9M14 2L2 6.5L7 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                          Send on LinkedIn
                        </button>
                        <button onClick={() => copy(person.connections[0].suggestedMessage, person.connections[0].id)}
                          className="text-[12px] font-semibold px-4 py-2 rounded-lg"
                          style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#888" }}>
                          {copiedId === person.connections[0].id ? "Copied!" : "Copy"}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* 2nd degree — connection rows */}
                  {person.connectionDegree === 2 && (
                    <div className="space-y-3">
                      {person.connections.map(conn => {
                        const cc = AVATAR[conn.avatarColor] || AVATAR[color(conn.name)];
                        const src = SOURCE[conn.source] || SOURCE.mutual;

                        return (
                          <div key={conn.id} className="rounded-xl p-4"
                            style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)" }}>
                            {/* Header */}
                            <div className="flex items-center gap-3 mb-3">
                              <div className="w-10 h-10 rounded-full flex items-center justify-center text-[13px] font-bold shrink-0"
                                style={{ background: cc.bg, color: cc.text }}>
                                {conn.avatarInitials}
                              </div>
                              <div className="flex-1 min-w-0">
                                {conn.linkedinUrl ? (
                                  <a href={conn.linkedinUrl} target="_blank" rel="noopener noreferrer"
                                    className="text-[14px] font-semibold text-[#7F8CFF] hover:text-white underline decoration-[#7F8CFF]/40 hover:decoration-white/60 transition-colors cursor-pointer">
                                    {conn.name}
                                  </a>
                                ) : (
                                  <div className="text-[14px] font-semibold text-white">{conn.name}</div>
                                )}
                                <div className="text-[11px] text-[#8B92B0]">{conn.role} · {conn.company}</div>
                              </div>
                              <span className="text-[11px] font-medium px-2.5 py-1 rounded-full shrink-0"
                                style={{ background: src.bg, border: `1px solid ${src.border}`, color: src.text }}>
                                {conn.sourceLabel}
                              </span>
                            </div>

                            {/* Label */}
                            <div className="text-[10px] font-semibold uppercase tracking-wider text-[#555C7A] mb-2">
                              Suggested message to {conn.name.split(" ")[0]}
                            </div>

                            {/* Message */}
                            <div className="rounded-lg p-4"
                              style={{ background: "rgba(255,255,255,0.03)", borderLeft: "3px solid rgba(77,142,245,0.4)" }}>
                              <div className="text-[12px] text-[#ccc] leading-relaxed">
                                "{conn.suggestedMessage}"
                              </div>
                            </div>

                            {/* Buttons */}
                            <div className="flex gap-2.5 mt-3">
                              <button
                                onClick={() => {
                                  window.postMessage({
                                    type: "SR_SEND_LINKEDIN_MESSAGE",
                                    linkedinUrl: conn.linkedinUrl,
                                    draftText: conn.suggestedMessage,
                                  }, window.location.origin);
                                }}
                                className="text-[12px] font-semibold px-4 py-2 rounded-lg inline-flex items-center gap-1.5 transition-colors"
                                style={{ background: "rgba(127,140,255,0.15)", border: "1px solid rgba(127,140,255,0.25)", color: "#7F8CFF" }}>
                                <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                                  <path d="M14 2L7 9M14 2L9.5 14L7 9M14 2L2 6.5L7 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                                </svg>
                                Send on LinkedIn
                              </button>
                              <button onClick={() => copy(conn.suggestedMessage, conn.id)}
                                className="text-[12px] font-semibold px-4 py-2 rounded-lg transition-colors"
                                style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#888" }}>
                                {copiedId === conn.id ? "Copied!" : "Copy"}
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* No connections yet */}
                  {person.connections.length === 0 && (
                    <div className="rounded-xl p-6 text-center" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                      <div className="text-[12px] text-[#555C7A]">No connection paths mapped yet for {person.linkedinUrl ? <a href={person.linkedinUrl} target="_blank" rel="noopener noreferrer" className="text-[#7F8CFF] underline decoration-[#7F8CFF]/40 hover:text-white transition-colors">{person.name}</a> : person.name}</div>
                      <a href={person.linkedinUrl} target="_blank" rel="noopener"
                        className="text-[11px] text-[#4d8ef5] font-medium mt-1.5 inline-block hover:underline">
                        Visit their LinkedIn profile →
                      </a>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
