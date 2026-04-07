// @ts-nocheck
"use client";

import { useState } from "react";

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
  opportunityId: string;
  targetCompany: string;
  targetRole: string;
  keyPeople: KeyPerson[];
  loading?: boolean;
}

/* ── Color maps ────────────────────────────────────────────────────── */

const AVATAR_COLORS: Record<string, { bg: string; text: string }> = {
  blue: { bg: "#1a3a6e", text: "#4d8ef5" },
  teal: { bg: "#0f2e28", text: "#22c55e" },
  amber: { bg: "#2e2008", text: "#fbbf24" },
  purple: { bg: "#1e1a3e", text: "#a78bfa" },
  coral: { bg: "#2e1208", text: "#f87171" },
};

const DEGREE_STYLES: Record<number, { bg: string; text: string; label: string }> = {
  1: { bg: "rgba(34,197,94,0.15)", text: "#22c55e", label: "1st · Direct" },
  2: { bg: "rgba(251,191,36,0.15)", text: "#fbbf24", label: "2nd · Intro needed" },
  3: { bg: "rgba(255,255,255,0.08)", text: "#8B92B0", label: "3rd · Cold outreach" },
};

const SOURCE_STYLES: Record<string, { bg: string; text: string }> = {
  worked_together: { bg: "rgba(34,197,94,0.12)", text: "#22c55e" },
  alumni: { bg: "rgba(167,139,250,0.12)", text: "#a78bfa" },
  location: { bg: "rgba(251,191,36,0.12)", text: "#fbbf24" },
  mutual: { bg: "rgba(77,142,245,0.12)", text: "#4d8ef5" },
};

function getAvatarColor(name: string): "blue" | "teal" | "amber" | "purple" | "coral" {
  const colors: Array<"blue" | "teal" | "amber" | "purple" | "coral"> = ["blue", "teal", "amber", "purple", "coral"];
  const code = name.charCodeAt(0) || 0;
  return colors[code % 5];
}

/* ── Component ─────────────────────────────────────────────────────── */

export default function ConnectionPath({
  opportunityId,
  targetCompany,
  targetRole,
  keyPeople,
  loading = false,
}: ConnectionPathProps) {
  const [openPanel, setOpenPanel] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  function togglePanel(personId: string) {
    setOpenPanel(openPanel === personId ? null : personId);
  }

  function copyMessage(text: string, connectionId: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(connectionId);
      setTimeout(() => setCopiedId(null), 2000);
    });
  }

  /* Loading skeleton */
  if (loading) {
    return (
      <div className="space-y-3">
        <div className="mb-4">
          <div className="h-4 w-64 rounded animate-pulse" style={{ background: "rgba(255,255,255,0.06)" }} />
          <div className="h-3 w-96 rounded animate-pulse mt-2" style={{ background: "rgba(255,255,255,0.04)" }} />
        </div>
        {[1, 2, 3].map((i) => (
          <div key={i} className="rounded-xl p-5 animate-pulse" style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)" }}>
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-full" style={{ background: "rgba(255,255,255,0.08)" }} />
              <div className="flex-1">
                <div className="h-4 w-40 rounded" style={{ background: "rgba(255,255,255,0.08)" }} />
                <div className="h-3 w-56 rounded mt-2" style={{ background: "rgba(255,255,255,0.06)" }} />
              </div>
              <div className="h-6 w-24 rounded-full" style={{ background: "rgba(255,255,255,0.06)" }} />
            </div>
          </div>
        ))}
      </div>
    );
  }

  /* Empty state */
  if (!keyPeople || keyPeople.length === 0) {
    return (
      <div className="rounded-xl p-10 text-center" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
        <svg className="mx-auto mb-3" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#555C7A" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
        <div className="text-[14px] font-medium text-[#8B92B0]">No connections mapped yet</div>
        <div className="text-[12px] text-[#555C7A] mt-1.5 max-w-xs mx-auto">
          Visit the LinkedIn profiles of key people at {targetCompany} and the extension will automatically map your path
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-4">
        <div className="text-[13px] font-medium text-[#8B92B0]">
          Key people to contact — {targetRole} at {targetCompany}
        </div>
        <div className="text-[11px] text-[#555C7A] mt-0.5">
          Click "Leverage my connections" to see your path to each person
        </div>
      </div>

      {/* Target cards */}
      <div className="space-y-2.5">
        {keyPeople.map((person) => {
          const isOpen = openPanel === person.id;
          const ac = AVATAR_COLORS[person.avatarColor] || AVATAR_COLORS.blue;
          const degree = DEGREE_STYLES[person.connectionDegree] || DEGREE_STYLES[3];

          return (
            <div key={person.id}>
              {/* Target card */}
              <div
                className="rounded-xl transition-all"
                style={{
                  background: isOpen ? "rgba(77,142,245,0.06)" : "rgba(255,255,255,0.04)",
                  border: `1px solid ${isOpen ? "rgba(77,142,245,0.2)" : "rgba(255,255,255,0.06)"}`,
                }}
              >
                <div className="p-4 flex items-center gap-3">
                  {/* Avatar */}
                  <div
                    className="w-11 h-11 rounded-full flex items-center justify-center text-[14px] font-bold shrink-0"
                    style={{ background: ac.bg, color: ac.text }}
                  >
                    {person.avatarInitials}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="text-[15px] font-medium text-white">{person.name}</div>
                    <div className="text-[12px] text-[#6B7194]">
                      {person.role} · {person.company}
                    </div>
                  </div>

                  {/* Degree badge */}
                  <span
                    className="text-[10px] font-semibold px-2.5 py-1 rounded-full shrink-0 hidden sm:inline-block"
                    style={{ background: degree.bg, color: degree.text }}
                  >
                    {degree.label}
                  </span>

                  {/* Leverage button */}
                  <button
                    onClick={() => togglePanel(person.id)}
                    className="text-[11px] font-semibold px-3 py-1.5 rounded-lg shrink-0 transition-all"
                    style={{
                      background: isOpen ? "#4d8ef5" : "rgba(77,142,245,0.1)",
                      color: isOpen ? "#fff" : "#4d8ef5",
                    }}
                  >
                    {isOpen ? "Close ×" : "Leverage my connections →"}
                  </button>
                </div>

                {/* Expanded panel */}
                <div
                  style={{
                    maxHeight: isOpen ? "2000px" : "0px",
                    opacity: isOpen ? 1 : 0,
                    overflow: "hidden",
                    transition: "max-height 0.3s ease, opacity 0.3s ease",
                  }}
                >
                  <div className="px-4 pb-4">
                    <div className="rounded-lg p-4" style={{ background: "#1a1d35" }}>
                      {/* Panel header */}
                      <div className="mb-3">
                        <div className="text-[13px] font-medium text-white">Your path to {person.name}</div>
                        {person.connectionDegree === 1 ? (
                          <div className="text-[11px] text-emerald-400 mt-0.5">
                            You're directly connected — reach out directly
                          </div>
                        ) : (
                          <div className="text-[11px] text-[#6B7194] mt-0.5">
                            {person.connections.length} {person.connections.length === 1 ? "person" : "people"} can introduce you — each from a different angle
                          </div>
                        )}
                      </div>

                      {/* 1st degree — direct message */}
                      {person.connectionDegree === 1 && person.connections.length > 0 && (
                        <div className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.04)", borderLeft: "3px solid #22c55e" }}>
                          <div className="text-[11px] font-medium text-[#6B7194] mb-1.5">Direct message to {person.name}</div>
                          <div className="text-[12px] text-[#c4c9e0] leading-relaxed">{person.connections[0].suggestedMessage}</div>
                          <div className="flex gap-2 mt-3">
                            <button
                              onClick={() => copyMessage(person.connections[0].suggestedMessage, person.connections[0].id)}
                              className="text-[11px] font-semibold px-3 py-1.5 rounded-lg transition-colors"
                              style={{ background: "rgba(77,142,245,0.15)", color: "#4d8ef5" }}
                            >
                              {copiedId === person.connections[0].id ? "Copied!" : "Copy message"}
                            </button>
                            <a
                              href={person.linkedinUrl}
                              target="_blank"
                              rel="noopener"
                              className="text-[11px] font-semibold px-3 py-1.5 rounded-lg transition-colors"
                              style={{ background: "rgba(255,255,255,0.06)", color: "#8B92B0" }}
                            >
                              View on LinkedIn
                            </a>
                          </div>
                        </div>
                      )}

                      {/* 2nd/3rd degree — connection rows */}
                      {person.connectionDegree !== 1 && (
                        <div className="space-y-2.5">
                          {person.connections.map((conn) => {
                            const connColor = AVATAR_COLORS[conn.avatarColor] || AVATAR_COLORS[getAvatarColor(conn.name)];
                            const srcStyle = SOURCE_STYLES[conn.source] || SOURCE_STYLES.mutual;

                            return (
                              <div
                                key={conn.id}
                                className="rounded-lg p-3"
                                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}
                              >
                                {/* Connection header */}
                                <div className="flex items-center gap-2.5 mb-2.5">
                                  <div
                                    className="w-9 h-9 rounded-full flex items-center justify-center text-[12px] font-bold shrink-0"
                                    style={{ background: connColor.bg, color: connColor.text }}
                                  >
                                    {conn.avatarInitials}
                                  </div>
                                  <div className="flex-1 min-w-0">
                                    <div className="text-[13px] font-medium text-white">{conn.name}</div>
                                    <div className="text-[11px] text-[#6B7194]">
                                      {conn.role} · {conn.company}
                                    </div>
                                  </div>
                                  <span
                                    className="text-[10px] font-medium px-2 py-0.5 rounded-full shrink-0"
                                    style={{ background: srcStyle.bg, color: srcStyle.text }}
                                  >
                                    {conn.sourceLabel}
                                  </span>
                                </div>

                                {/* Message box */}
                                <div className="rounded-lg p-3 ml-[46px]" style={{ background: "rgba(255,255,255,0.02)", borderLeft: "3px solid rgba(77,142,245,0.3)" }}>
                                  <div className="text-[10px] font-medium text-[#555C7A] uppercase mb-1.5">
                                    Suggested message to {conn.name.split(" ")[0]}
                                  </div>
                                  <div className="text-[12px] text-[#c4c9e0] leading-relaxed">
                                    {conn.suggestedMessage}
                                  </div>
                                </div>

                                {/* Actions */}
                                <div className="flex gap-2 mt-2.5 ml-[46px]">
                                  <button
                                    onClick={() => copyMessage(conn.suggestedMessage, conn.id)}
                                    className="text-[11px] font-semibold px-3 py-1.5 rounded-lg transition-colors"
                                    style={{ background: "rgba(77,142,245,0.15)", color: "#4d8ef5" }}
                                  >
                                    {copiedId === conn.id ? "Copied!" : "Copy message"}
                                  </button>
                                  <a
                                    href={conn.linkedinUrl}
                                    target="_blank"
                                    rel="noopener"
                                    className="text-[11px] font-semibold px-3 py-1.5 rounded-lg transition-colors"
                                    style={{ background: "rgba(255,255,255,0.06)", color: "#8B92B0" }}
                                  >
                                    View on LinkedIn
                                  </a>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {/* No connections for this person */}
                      {person.connections.length === 0 && (
                        <div className="text-center py-4">
                          <div className="text-[12px] text-[#555C7A]">No connection paths mapped yet for {person.name}</div>
                          <a
                            href={person.linkedinUrl}
                            target="_blank"
                            rel="noopener"
                            className="text-[11px] text-[#4d8ef5] font-medium mt-1 inline-block"
                          >
                            Visit their LinkedIn profile →
                          </a>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
