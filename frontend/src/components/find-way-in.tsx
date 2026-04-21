// @ts-nocheck
"use client";

import { useEffect, useState } from "react";

interface FindWayInPanelProps {
  company: string;
  role: string;
  headers: Record<string, string>;
  // Optional: render the panel always-open (no toggle button) — used in pack contacts tab
  alwaysOpen?: boolean;
}

export default function FindWayInPanel({ company, role, headers, alwaysOpen = false }: FindWayInPanelProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [open, setOpen] = useState(alwaysOpen);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [scanProgress, setScanProgress] = useState<string | null>(null);
  const [scanningConnector, setScanningConnector] = useState<string | null>(null);

  // Auto-load when always-open mode (used in pack contacts tab)
  useEffect(() => {
    if (alwaysOpen) {
      findPath(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [alwaysOpen, company]);

  async function findPath(forceRefresh = false) {
    if (result && !forceRefresh) { setOpen(!open); return; }
    setOpen(true);
    setLoading(true);
    try {
      const res = await fetch("/api/v1/relationships/find-way-in", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({ company, role }),
      });
      if (res.ok) {
        const data = await res.json();
        console.log("[SR] find-way-in response:", JSON.stringify(data.direct_contacts?.slice(0, 3), null, 2));
        setResult(data);
      } else {
        console.error("[SR] find-way-in failed:", res.status, await res.text().catch(() => ""));
      }
    } catch (err) {
      console.error("[SR] find-way-in error:", err);
    }
    setLoading(false);
  }

  function copyMessage(msg: string, idx: number) {
    navigator.clipboard.writeText(msg).then(() => {
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 2000);
    });
  }

  // Trigger the Chrome extension to open the connector's profile and
  // scrape their connections list for matches at the target company
  function scanConnectorNetwork(connectorUrl: string, connectorName: string) {
    if (typeof window === "undefined") return;
    if (!connectorUrl) {
      alert("This contact has no LinkedIn URL on file. Re-import your CSV from LinkedIn.");
      return;
    }
    const marker = document.getElementById("sr-extension-marker");
    if (!marker) {
      alert("Install the StealthRole Chrome extension first to scan networks. (chrome://extensions → load unpacked from the extension folder)");
      return;
    }
    setScanningConnector(connectorUrl);
    setScanProgress("Opening LinkedIn in a new tab...");
    window.postMessage({
      type: "SR_SCAN_NETWORK",
      connectorUrl,
      connectorName,
      targetCompany: company,
    }, window.location.origin);
  }

  // Listen for progress updates from the extension
  useEffect(() => {
    function onMsg(event: MessageEvent) {
      if (event.source !== window || !event.data || typeof event.data !== "object") return;
      const msg = event.data;
      if (msg.type === "SR_SCAN_NETWORK_ACK") {
        if (!msg.ok) {
          setScanProgress("Scan failed: " + (msg.error || "unknown"));
          setTimeout(() => { setScanProgress(null); setScanningConnector(null); }, 4000);
        }
      }
      if (msg.type === "SR_SCAN_NETWORK_PROGRESS" && msg.payload) {
        setScanProgress(msg.payload.progress || "Scanning...");
        if (msg.payload.status === "complete") {
          // Refetch paths so the new matches show up
          setTimeout(() => {
            findPath(true);
            setScanProgress(null);
            setScanningConnector(null);
          }, 1500);
        }
      }
    }
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const {
    direct_contacts = [],
    recruiter_contacts = [],
    visited_targets = [],
    best_path,
    backup_paths = [],
    recommended_action,
    discover_targets = [],
    total_connections = 0,
  } = result || {};

  // Always return a usable LinkedIn URL — fall back to a search URL
  // so the "Open LinkedIn ↗" button NEVER does nothing.
  function linkedInUrlFor(contact: any): string {
    if (contact?.linkedin_url) return contact.linkedin_url;
    const q = encodeURIComponent(`${contact?.name || ""} ${contact?.company || company || ""}`.trim());
    return `https://www.linkedin.com/search/results/people/?keywords=${q}`;
  }

  // Combine best_path + backup_paths into a single layer-2 list
  const introPaths: any[] = [];
  if (best_path) introPaths.push(best_path);
  introPaths.push(...backup_paths);

  const hasAnyPaths = direct_contacts.length > 0 || introPaths.length > 0 || recruiter_contacts.length > 0 || visited_targets.length > 0;

  return (
    <>
      {!alwaysOpen && (
        <button onClick={() => findPath(false)} className="px-3 py-1.5 border border-white/10 text-[#8B92B0] text-[12px] font-semibold rounded-lg hover:bg-white/[0.04] transition-colors">
          {loading ? "Mapping connections..." : "Find My Way In"}
        </button>
      )}
      {alwaysOpen && loading && (
        <div className="text-[12px] text-[#8B92B0] py-2">Mapping connections at {company}...</div>
      )}
      {open && !loading && result && (
        <div className="mt-3 space-y-2 animate-in fade-in slide-in-from-top-2 duration-300">
          {/* ═══ Scan progress banner (extension) ═══ */}
          {scanProgress && (
            <div className="rounded-lg p-3 border border-violet-500/30" style={{ background: "rgba(139,92,246,0.12)" }}>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full border-2 border-violet-400 border-t-transparent animate-spin shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-[11px] font-semibold text-violet-300">Scanning network via Chrome extension</div>
                  <div className="text-[10px] text-violet-200/70 truncate">{scanProgress}</div>
                </div>
                <button
                  onClick={() => {
                    if (typeof window !== "undefined") window.postMessage({ type: "SR_CANCEL_SCAN" }, window.location.origin);
                    setScanProgress(null);
                    setScanningConnector(null);
                  }}
                  className="text-[10px] text-violet-300 hover:text-white"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Recommended action + refresh */}
          {recommended_action && (
            <div className="rounded-lg p-3 border border-[#7F8CFF]/20" style={{ background: "rgba(127,140,255,0.08)" }}>
              <div className="flex items-center justify-between mb-1">
                <div className="text-[10px] font-medium text-[#7F8CFF] uppercase">Recommended Action</div>
                <button onClick={() => findPath(true)} className="text-[10px] text-[#7F8CFF] hover:text-white font-medium transition-colors">
                  Refresh paths
                </button>
              </div>
              <div className="text-[13px] font-semibold text-white">{recommended_action}</div>
            </div>
          )}

          {/* ═══ LAYER 1 — DIRECT (1st degree, recruiter-free, sorted by seniority) ═══ */}
          {direct_contacts.length > 0 && (
            <div className="rounded-lg p-3 border border-emerald-500/20" style={{ background: "rgba(52,211,153,0.06)" }}>
              <div className="text-[10px] font-medium text-emerald-400 uppercase mb-2">
                Direct contacts at {company} · {result.total_direct} found
              </div>
              <div className="space-y-3">
                {direct_contacts.map((c: any, i: number) => {
                  const tier = c.seniority_tier || "IC";
                  const tierLabel = tier === "C_SUITE" ? "C-Suite" : tier === "VP_DIRECTOR" ? "VP / Director" : tier === "MANAGER" ? "Manager" : "IC";
                  const tierColor = tier === "C_SUITE" ? "#fbbf24" : tier === "VP_DIRECTOR" ? "#4d8ef5" : tier === "MANAGER" ? "#a78bfa" : "#86efac";
                  const linkUrl = linkedInUrlFor(c);
                  return (
                    <div key={i} className="rounded-lg p-2.5 bg-white/[0.04]">
                      <div className="flex items-center gap-2.5 mb-1.5">
                        <div className="w-8 h-8 rounded-full bg-emerald-500/15 text-emerald-400 flex items-center justify-center text-[12px] font-bold shrink-0">
                          {c.name?.[0]?.toUpperCase() || "?"}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            {linkedInUrlFor(c) ? (
                              <a href={linkedInUrlFor(c)} target="_blank" rel="noopener noreferrer" className="text-[13px] font-semibold text-[#7F8CFF] hover:text-white underline decoration-[#7F8CFF]/40 hover:decoration-white/60 transition-colors">{c.name}</a>
                            ) : (
                              <span className="text-[13px] font-semibold text-white">{c.name}</span>
                            )}
                            <span className="text-[9px] px-1.5 py-0.5 rounded-full font-medium" style={{ background: `${tierColor}26`, color: tierColor }}>{tierLabel}</span>
                            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-white/10 text-[#8B92B0] font-medium">1st</span>
                          </div>
                          <div className="text-[11px] text-[#6B7194]">{c.title}{c.company ? ` · ${c.company}` : ""}</div>
                          {c._debug_title_used && <div className="text-[9px] text-orange-400/80 font-mono">tier={c.seniority_tier} from=&quot;{c._debug_title_used}&quot;</div>}
                        </div>
                        {c.message ? (
                          <button
                            onClick={() => {
                              window.postMessage({
                                type: "SR_SEND_LINKEDIN_MESSAGE",
                                linkedinUrl: linkUrl,
                                draftText: c.message,
                              }, window.location.origin);
                            }}
                            className="text-[11px] text-[#7F8CFF] hover:text-white font-medium shrink-0 px-2 py-1 rounded bg-[#7F8CFF]/10 hover:bg-[#7F8CFF]/20 inline-flex items-center gap-1"
                          >
                            <svg width="10" height="10" viewBox="0 0 16 16" fill="none"><path d="M14 2L7 9M14 2L9.5 14L7 9M14 2L2 6.5L7 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                            Send on LinkedIn
                          </button>
                        ) : (
                          <a href={linkUrl} target="_blank" rel="noopener noreferrer" className="text-[11px] text-emerald-400 hover:text-white font-medium shrink-0 px-2 py-1 rounded bg-emerald-500/10 hover:bg-emerald-500/20">
                            Open LinkedIn ↗
                          </a>
                        )}
                      </div>
                      {c.message && (
                        <div className="pl-[42px]">
                          <div className="text-[11px] text-[#8B92B0] p-2 rounded bg-white/[0.03] border border-white/[0.05] leading-relaxed whitespace-pre-wrap">{c.message}</div>
                          <div className="flex items-center gap-2 mt-1.5">
                            <button onClick={() => copyMessage(c.message, i)} className="text-[10px] font-medium text-[#888] hover:text-white transition-colors">
                              {copiedIdx === i ? "Copied!" : "Copy"}
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ═══ LAYER 2 — INTRO PATHS (2nd degree) ═══ */}
          {introPaths.length > 0 && (
            <div className="rounded-lg p-3 border border-[#4d8ef5]/20" style={{ background: "rgba(77,142,245,0.06)" }}>
              <div className="text-[10px] font-medium text-[#4d8ef5] uppercase mb-2">
                Intro paths via your network · {introPaths.length}
              </div>
              <div className="space-y-3">
                {introPaths.map((p: any, i: number) => {
                  const targetDisplayName = p.target?.name || `someone at ${company}`;
                  const targetTitle = p.target?.title || "";
                  return (
                  <div key={i} className="rounded-lg p-3 bg-white/[0.04]">
                    {/* Path chain */}
                    <div className="flex items-center gap-1.5 flex-wrap mb-2">
                      <span className="text-[10px] px-2 py-0.5 rounded bg-[#4d8ef5]/20 text-[#4d8ef5] font-medium">You</span>
                      <span className="text-[#555C7A] text-[10px]">→</span>
                      {p.connector?.linkedin_url ? (
                        <a href={p.connector.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-[10px] px-2 py-0.5 rounded bg-white/[0.08] text-[#7F8CFF] font-medium underline decoration-[#7F8CFF]/40 hover:text-white transition-colors">{p.connector?.name}</a>
                      ) : (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.08] text-[#c4c9e0] font-medium">{p.connector?.name}</span>
                      )}
                      <span className="text-[#555C7A] text-[10px]">→</span>
                      {p.target?.linkedin_url ? (
                        <a href={p.target.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/15 text-[#7F8CFF] font-medium underline decoration-[#7F8CFF]/40 hover:text-white transition-colors">{targetDisplayName}</a>
                      ) : (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 font-medium">{targetDisplayName}</span>
                      )}
                    </div>
                    {/* Connector details */}
                    {p.connector && (
                      <div className="text-[11px] text-[#8B92B0] mb-1">
                        Ask {p.connector.linkedin_url ? (
                          <a href={p.connector.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-[#7F8CFF] font-medium underline decoration-[#7F8CFF]/40 hover:text-white transition-colors">{p.connector.name}</a>
                        ) : (
                          <span className="text-white font-medium">{p.connector.name}</span>
                        )} ({p.connector.title}{p.connector.company ? ` at ${p.connector.company}` : ""}) to introduce you to {p.target?.linkedin_url ? (
                          <a href={p.target.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-[#7F8CFF] underline decoration-[#7F8CFF]/40 hover:text-white transition-colors">{targetDisplayName}</a>
                        ) : (
                          <span className="text-emerald-400">{targetDisplayName}</span>
                        )}{targetTitle ? ` (${targetTitle})` : ""}.
                      </div>
                    )}
                    {/* AI-generated intro message (with fallback) */}
                    {(() => {
                      const connFirst = p.connector?.name?.split(" ")[0] || "there";
                      const tgtName = p.target?.name || `your contact at ${company}`;
                      const tgtTitle = p.target?.title || "employee";
                      const msg = p.intro_message || `Hi ${connFirst}, I'd love to connect with ${tgtName} (${tgtTitle}) at ${company}. I know you're connected and I'd be grateful if you could introduce me. No pressure at all!`;
                      return (
                      <div className="mt-2">
                        <div className="text-[11px] text-[#8B92B0] p-2 rounded bg-white/[0.03] border border-white/[0.05] leading-relaxed whitespace-pre-wrap">{msg}</div>
                        <div className="flex items-center gap-2 mt-1.5">
                          <button
                            onClick={() => {
                              const connUrl = linkedInUrlFor({ name: p.connector?.name, company: p.connector?.company, linkedin_url: p.connector?.linkedin_url });
                              window.postMessage({
                                type: "SR_SEND_LINKEDIN_MESSAGE",
                                linkedinUrl: connUrl,
                                draftText: msg,
                              }, window.location.origin);
                            }}
                            className="text-[10px] font-medium text-[#7F8CFF] hover:text-white inline-flex items-center gap-1"
                          >
                            <svg width="9" height="9" viewBox="0 0 16 16" fill="none"><path d="M14 2L7 9M14 2L9.5 14L7 9M14 2L2 6.5L7 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                            Send to {connFirst} on LinkedIn
                          </button>
                          <button
                            onClick={() => copyMessage(msg, 200 + i)}
                            className="text-[10px] font-medium text-[#888] hover:text-white transition-colors"
                          >
                            {copiedIdx === 200 + i ? "Copied!" : "Copy"}
                          </button>
                        </div>
                      </div>
                      );
                    })()}
                  </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ═══ RECRUITERS AT TARGET COMPANY (separate bucket from direct contacts) ═══ */}
          {recruiter_contacts.length > 0 && (
            <div className="rounded-lg p-3 border border-amber-500/20" style={{ background: "rgba(245,158,11,0.06)" }}>
              <div className="text-[10px] font-medium text-amber-400 uppercase mb-2">
                Recruiters / talent at {company} · {result.total_recruiters} found
              </div>
              <div className="text-[11px] text-[#6B7194] mb-2">
                Reach out directly about open roles. They handle hiring pipeline.
              </div>
              <div className="space-y-3">
                {recruiter_contacts.map((c: any, i: number) => {
                  const linkUrl = linkedInUrlFor(c);
                  return (
                    <div key={i} className="rounded-lg p-2.5 bg-white/[0.04]">
                      <div className="flex items-center gap-2.5 mb-1.5">
                        <div className="w-8 h-8 rounded-full bg-amber-500/15 text-amber-400 flex items-center justify-center text-[12px] font-bold shrink-0">
                          {c.name?.[0]?.toUpperCase() || "?"}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            {linkUrl ? (
                              <a href={linkUrl} target="_blank" rel="noopener noreferrer" className="text-[13px] font-semibold text-[#7F8CFF] hover:text-white underline decoration-[#7F8CFF]/40 hover:decoration-white/60 transition-colors">{c.name}</a>
                            ) : (
                              <span className="text-[13px] font-semibold text-white">{c.name}</span>
                            )}
                            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 font-medium">Recruiter</span>
                            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-white/10 text-[#8B92B0] font-medium">1st</span>
                          </div>
                          <div className="text-[11px] text-[#6B7194]">{c.title}{c.company ? ` · ${c.company}` : ""}</div>
                        </div>
                        <a href={linkUrl} target="_blank" rel="noopener noreferrer" className="text-[11px] text-amber-400 hover:text-white font-medium shrink-0 px-2 py-1 rounded bg-amber-500/10 hover:bg-amber-500/20">
                          Open LinkedIn ↗
                        </a>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ═══ Visited targets (cold outreach to people you researched) ═══ */}
          {visited_targets.length > 0 && (
            <div className="rounded-lg p-3 border border-amber-500/20" style={{ background: "rgba(245,158,11,0.06)" }}>
              <div className="text-[10px] font-medium text-amber-400 uppercase mb-2">
                Profiles you researched at {company} ({result.total_visited})
              </div>
              <div className="space-y-3">
                {visited_targets.map((c: any, i: number) => (
                  <div key={i} className="rounded-lg p-2.5 bg-white/[0.04]">
                    <div className="flex items-center gap-2.5 mb-1.5">
                      <div className="w-8 h-8 rounded-full bg-amber-500/15 text-amber-400 flex items-center justify-center text-[12px] font-bold shrink-0">
                        {c.name?.[0]?.toUpperCase() || "?"}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          {c.linkedin_url ? (
                            <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-[13px] font-semibold text-[#7F8CFF] hover:text-white underline decoration-[#7F8CFF]/40 hover:decoration-white/60 transition-colors">{c.name}</a>
                          ) : (
                            <span className="text-[13px] font-semibold text-white">{c.name}</span>
                          )}
                          {c.is_hiring_manager && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 font-medium">Decision Maker</span>}
                          {c.is_recruiter && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-medium">Recruiter</span>}
                          <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-white/10 text-[#8B92B0] font-medium">Cold outreach</span>
                        </div>
                        <div className="text-[11px] text-[#6B7194]">{c.title}</div>
                      </div>
                      {c.linkedin_url && (
                        <a href={c.linkedin_url} target="_blank" rel="noopener" className="text-[11px] text-amber-400 hover:text-white font-medium shrink-0">
                          LinkedIn →
                        </a>
                      )}
                    </div>
                    {c.intro_angle && (
                      <div className="text-[11px] text-amber-400 mb-1.5 pl-[42px]">{c.intro_angle}</div>
                    )}
                    {c.message && (
                      <div className="pl-[42px]">
                        <div className="text-[11px] text-[#8B92B0] p-2 rounded bg-white/[0.03] border border-white/[0.05] leading-relaxed">{c.message}</div>
                        <button onClick={() => copyMessage(c.message, 100 + i)} className="mt-1.5 text-[10px] font-medium text-amber-400 hover:text-white transition-colors">
                          {copiedIdx === 100 + i ? "Copied!" : "Copy outreach message"}
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Discover targets — people to visit on LinkedIn */}
          {discover_targets.length > 0 && !best_path && (
            <div className="rounded-lg p-3 border border-violet-500/20" style={{ background: "rgba(139,92,246,0.06)" }}>
              <div className="text-[10px] font-medium text-violet-400 uppercase mb-1">Visit These Profiles to Map Your Paths</div>
              <div className="text-[11px] text-[#6B7194] mb-2">
                Open each profile with the StealthRole extension active. It will scan mutual connections automatically. Then come back and hit <strong className="text-violet-400">Refresh paths</strong> above.
              </div>
              <div className="space-y-1.5">
                {discover_targets.map((person: any, i: number) => (
                  <a key={i} href={person.linkedin_url} target="_blank" rel="noopener" className="flex items-center gap-2.5 p-2.5 rounded-lg bg-white/[0.04] hover:bg-violet-500/10 border border-transparent hover:border-violet-500/20 transition-all">
                    <div className="w-8 h-8 rounded-full bg-violet-500/15 text-violet-400 flex items-center justify-center text-[11px] font-bold shrink-0">
                      {person.name?.[0]?.toUpperCase() || "?"}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-[12px] font-semibold text-[#7F8CFF] underline decoration-[#7F8CFF]/40">{person.name}</div>
                      {person.title && <div className="text-[11px] text-[#6B7194]">{person.title}</div>}
                    </div>
                    <span className="text-[10px] text-violet-400 font-medium shrink-0">Visit profile →</span>
                  </a>
                ))}
              </div>
              <div className="mt-2.5 text-center">
                <button
                  onClick={() => findPath(true)}
                  className="text-[11px] font-semibold text-violet-400 hover:text-white px-4 py-1.5 rounded-lg border border-violet-500/20 hover:bg-violet-500/10 transition-all"
                >
                  I visited profiles — refresh paths
                </button>
              </div>
            </div>
          )}

          {!hasAnyPaths && discover_targets.length === 0 && (
            <div className="rounded-lg p-4 text-center border border-white/10" style={{ background: "rgba(255,255,255,0.04)" }}>
              <div className="text-[13px] text-white font-medium mb-1">No direct or indirect connections at {company} yet</div>
              <div className="text-[11px] text-[#6B7194] mb-3">
                {total_connections > 0
                  ? `You have ${total_connections} connections imported, but none at this company. Import more LinkedIn connections to improve coverage.`
                  : "Import your LinkedIn connections to start finding paths into companies."}
              </div>
              <a href="/settings#linkedin" className="inline-block px-4 py-1.5 rounded-lg bg-[#4d8ef5] text-white text-[11px] font-semibold hover:bg-[#3b7de0] transition-colors">
                Import connections →
              </a>
            </div>
          )}
        </div>
      )}
    </>
  );
}
