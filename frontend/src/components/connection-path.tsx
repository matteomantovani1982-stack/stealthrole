// @ts-nocheck
"use client";

import { useState, useEffect } from "react";

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
  connectionDegree: 1 | 2 | 3;
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

const DEGREE: Record<number, { bg: string; text: string; label: string }> = {
  1: { bg: "rgba(34,197,94,0.15)",  text: "#22c55e", label: "1st" },
  2: { bg: "rgba(251,191,36,0.15)", text: "#fbbf24", label: "2nd" },
  3: { bg: "rgba(255,255,255,0.08)", text: "#8B92B0", label: "3rd" },
};

const SOURCE: Record<string, { bg: string; border: string; text: string }> = {
  worked_together: { bg: "rgba(34,197,94,0.12)",  border: "rgba(34,197,94,0.25)",  text: "#22c55e" },
  alumni:          { bg: "rgba(167,139,250,0.12)", border: "rgba(167,139,250,0.25)", text: "#a78bfa" },
  location:        { bg: "rgba(251,191,36,0.12)",  border: "rgba(251,191,36,0.25)",  text: "#fbbf24" },
  mutual:          { bg: "rgba(77,142,245,0.12)",  border: "rgba(77,142,245,0.25)",  text: "#4d8ef5" },
};

function color(name: string) {
  const k = ["blue", "teal", "amber", "purple", "coral"] as const;
  return k[(name.charCodeAt(0) || 0) % 5];
}
function initials(name: string) {
  return name.split(" ").map(w => w[0]).join("").toUpperCase().substring(0, 2);
}


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
    const token = localStorage.getItem("sr_token");
    try {
      const res = await fetch("/api/v1/relationships/find-way-in", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
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
  const targetMap: Record<string, KeyPerson> = {};
  const seenConnectors = new Set<string>();

  // Helper: add a connector to a target person
  function addConnector(targetName: string, targetTitle: string, targetCompany: string, targetUrl: string, connector: any) {
    if (!connector?.name || seenConnectors.has(connector.name)) return;
    seenConnectors.add(connector.name);

    if (!targetMap[targetName]) {
      targetMap[targetName] = {
        id: "target-" + targetName,
        name: targetName,
        role: targetTitle,
        company: targetCompany || company,
        connectionDegree: 2,
        linkedinUrl: targetUrl || "",
        avatarInitials: initials(targetName),
        avatarColor: color(targetName),
        connections: [],
      };
    }

    const firstName = connector.name.split(" ")[0];
    const targetFirst = targetName.split(" ")[0];
    const connRole = connector.title || "";
    const connCompany = connector.company || "";

    // Generate a personalized message based on the connector's background
    let message = connector.suggestedMessage || "";
    if (!message || message.startsWith("Ask ")) {
      const templates = [
        `Hi ${firstName}, hope you're doing well! I'm exploring the ${role} opportunity at ${company} and I noticed you're connected to ${targetFirst} at ${targetCompany || company}. Given your experience${connRole ? " as " + connRole : ""}${connCompany ? " at " + connCompany : ""}, I'd really value your perspective. Would you be open to a quick intro? Happy to share more context.`,
        `${firstName}, I'm reaching out because I'm pursuing the ${role} role at ${company}. I see you know ${targetFirst}${targetCompany ? " at " + targetCompany : ""} — would you be comfortable making an introduction? I'd be happy to share my background first so you can decide if it's a good fit.`,
        `Hi ${firstName}, I've been following ${company}'s growth and I'm very interested in the ${role} position. I noticed you're connected to ${targetFirst} — would you be willing to put in a word or make an intro? I'd really appreciate it and am happy to return the favor anytime.`,
      ];
      // Pick a template deterministically based on connector name
      const idx = (connector.name.charCodeAt(0) + connector.name.length) % templates.length;
      message = templates[idx];
    }

    targetMap[targetName].connections.push({
      id: "conn-" + connector.name,
      name: connector.name,
      role: connRole,
      company: connCompany,
      source: "mutual",
      sourceLabel: "Mutual connection",
      avatarInitials: initials(connector.name),
      avatarColor: color(connector.name),
      linkedinUrl: connector.linkedin_url || "",
      suggestedMessage: message,
    });
  }

  // Collect ALL paths — best + backups all point to target people with connectors
  const allPaths = [];
  if (data.best_path) allPaths.push(data.best_path);
  for (const bp of (data.backup_paths || [])) allPaths.push(bp);

  for (const path of allPaths) {
    if (!path.target?.name || !path.connector?.name) continue;
    addConnector(
      path.target.name,
      path.target.title || "",
      path.target.company || "",
      path.target.linkedin_url || "",
      { ...path.connector, action: path.action },
    );
  }

  // Add grouped targets to people list (2nd degree)
  for (const person of Object.values(targetMap)) {
    people.push(person);
  }

  // Direct contacts (1st degree) — skip anyone already in targets
  const targetNames = new Set(Object.keys(targetMap));
  for (const c of (data.direct_contacts || [])) {
    if (targetNames.has(c.name)) continue;
    people.push({
      id: c.connection_id || c.name,
      name: c.name,
      role: c.title || "",
      company: c.company || company,
      connectionDegree: 1,
      linkedinUrl: c.linkedin_url || "",
      avatarInitials: initials(c.name),
      avatarColor: color(c.name),
      connections: [{
        id: "d-" + c.name,
        name: c.name,
        role: c.title || "",
        company: c.company || company,
        source: "mutual",
        sourceLabel: "Direct connection",
        avatarInitials: initials(c.name),
        avatarColor: color(c.name),
        linkedinUrl: c.linkedin_url || "",
        suggestedMessage: c.message || `Hi ${c.name.split(" ")[0]}, I'm exploring the ${role} role at ${company} and would love to connect.`,
      }],
    });
  }

  return people;
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
          const deg = DEGREE[person.connectionDegree] || DEGREE[3];

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
                    <div className="text-[15px] font-medium text-white">{person.name}</div>
                    <div className="text-[12px] text-[#8B92B0]">{person.role} · {person.company}</div>
                  </div>
                  <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full shrink-0"
                    style={{ background: deg.bg, color: deg.text }}>
                    {deg.label}
                  </span>
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
                    ) : (
                      <div className="text-[13px] text-[#8B92B0] mt-0.5">
                        {person.connections.length} {person.connections.length === 1 ? "person" : "people"} can introduce you — each from a different angle
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
                        <button onClick={() => copy(person.connections[0].suggestedMessage, person.connections[0].id)}
                          className="text-[12px] font-semibold px-4 py-2 rounded-lg"
                          style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#ccc" }}>
                          {copiedId === person.connections[0].id ? "Copied!" : "Copy message"}
                        </button>
                        <a href={person.linkedinUrl} target="_blank" rel="noopener"
                          className="text-[12px] font-semibold px-4 py-2 rounded-lg inline-flex items-center"
                          style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#ccc" }}>
                          View on LinkedIn
                        </a>
                      </div>
                    </div>
                  )}

                  {/* 2nd/3rd degree — connection rows */}
                  {person.connectionDegree !== 1 && (
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
                                <div className="text-[14px] font-medium text-white">{conn.name}</div>
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
                              <button onClick={() => copy(conn.suggestedMessage, conn.id)}
                                className="text-[12px] font-semibold px-4 py-2 rounded-lg transition-colors"
                                style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#ccc" }}>
                                {copiedId === conn.id ? "Copied!" : "Copy message"}
                              </button>
                              <a href={conn.linkedinUrl} target="_blank" rel="noopener"
                                className="text-[12px] font-semibold px-4 py-2 rounded-lg inline-flex items-center transition-colors"
                                style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#ccc" }}>
                                View on LinkedIn
                              </a>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* No connections yet */}
                  {person.connections.length === 0 && (
                    <div className="rounded-xl p-6 text-center" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                      <div className="text-[12px] text-[#555C7A]">No connection paths mapped yet for {person.name}</div>
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
