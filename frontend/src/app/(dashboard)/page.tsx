// @ts-nocheck
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  getDashboard,
  getApplicationAnalytics,
  getBoard,
  getRadar,
  getHiddenMarket,
  type DashboardSummary,
  type ApplicationAnalytics,
  type BoardResponse,
  type Opportunity,
  type HiddenSignal,
} from "@/lib/api";

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning,";
  if (h < 18) return "Good afternoon,";
  return "Good evening,";
}

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

const TIER_COLORS: Record<string, string> = {
  high: "#4d8ef5",
  medium: "#a78bfa",
  low: "#22c55e",
};

const STAGE_COLORS: Record<string, string> = {
  watching: "#4d8ef5",
  applied: "#a78bfa",
  interview: "#22c55e",
  offer: "#fbbf24",
  closed: "rgba(255,255,255,0.3)",
};

const HOME_CACHE_KEY = "sr_home_cache";
const HOME_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

async function createAppAndPack(company: string, role: string, jdUrl: string | null = null): Promise<{ id: string } | null> {
  const tk = typeof window !== "undefined" ? localStorage.getItem("sr_token") : null;
  const hdrs = { "Content-Type": "application/json", ...(tk ? { Authorization: `Bearer ${tk}` } : {}) };

  // Get latest parsed CV
  const cvsRes = await fetch("/api/v1/cvs", { headers: hdrs });
  const cvs = cvsRes.ok ? await cvsRes.json() : [];
  const cv = Array.isArray(cvs) ? cvs.find((c: any) => c.status === "parsed") : null;
  if (!cv) {
    throw new Error("Upload a CV on the Profile page before generating a pack.");
  }

  // Start job run
  const jdText = `Role: ${role}\nCompany: ${company}${jdUrl ? `\n\nSource: ${jdUrl}` : ""}`;
  const jobRes = await fetch("/api/v1/jobs", {
    method: "POST",
    headers: hdrs,
    body: JSON.stringify({ cv_id: cv.id, jd_text: jdText, preferences: { tone: "professional", region: "MENA" } }),
  });
  if (!jobRes.ok) {
    const body = await jobRes.json().catch(() => ({}));
    throw new Error(body.detail || "Failed to start pack generation");
  }
  const job = await jobRes.json();

  // Create application linked to job run
  const appRes = await fetch("/api/v1/applications", {
    method: "POST",
    headers: hdrs,
    body: JSON.stringify({
      company, role,
      date_applied: new Date().toISOString(),
      source_channel: "job_board",
      stage: "watching",
      url: jdUrl || undefined,
      job_run_id: job.id,
    }),
  });
  if (!appRes.ok) throw new Error("Failed to create application");
  return await appRes.json();
}

export default function HomePage() {
  const router = useRouter();
  const { user } = useAuth();
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [analytics, setAnalytics] = useState<ApplicationAnalytics | null>(null);
  const [board, setBoard] = useState<BoardResponse | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [signals, setSignals] = useState<HiddenSignal[]>([]);
  // Track which sections have loaded so we can show partial content
  const [sectionsLoaded, setSectionsLoaded] = useState<Set<string>>(new Set());
  const [generatingFor, setGeneratingFor] = useState<string | null>(null);

  async function handleGeneratePack(company: string, role: string, url: string | null = null) {
    if (generatingFor) return;
    setGeneratingFor(`${company}|${role}`);
    try {
      const app = await createAppAndPack(company, role, url);
      if (app?.id) {
        router.push(`/applications/${app.id}/package`);
      } else {
        router.push("/applications");
      }
    } catch (err: any) {
      alert(err?.message || "Failed to start pack generation");
      setGeneratingFor(null);
    }
  }

  useEffect(() => {
    // 1. Hydrate from cache instantly (if same user + fresh)
    if (typeof window !== "undefined") {
      try {
        const cached = localStorage.getItem(HOME_CACHE_KEY);
        if (cached) {
          const parsed = JSON.parse(cached);
          const userId = localStorage.getItem("sr_user_id");
          const age = Date.now() - (parsed._cached_at || 0);
          if (parsed._user_id === userId && age < HOME_CACHE_TTL_MS) {
            if (parsed.dashboard) setDashboard(parsed.dashboard);
            if (parsed.analytics) setAnalytics(parsed.analytics);
            if (parsed.board) setBoard(parsed.board);
            if (parsed.opportunities) setOpportunities(parsed.opportunities);
            if (parsed.signals) setSignals(parsed.signals);
            setSectionsLoaded(new Set(["dashboard", "analytics", "board", "opportunities", "signals"]));
          } else if (parsed._user_id !== userId) {
            // Stale cache from another user
            localStorage.removeItem(HOME_CACHE_KEY);
          }
        }
      } catch {}
    }

    // 2. Fetch fresh data in parallel — update each section as it arrives (progressive)
    const markLoaded = (key: string) => setSectionsLoaded(prev => new Set([...prev, key]));
    const fetched: Record<string, unknown> = {};

    getDashboard().then(d => { setDashboard(d); fetched.dashboard = d; markLoaded("dashboard"); }).catch(() => markLoaded("dashboard"));
    getApplicationAnalytics().then(a => { setAnalytics(a); fetched.analytics = a; markLoaded("analytics"); }).catch(() => markLoaded("analytics"));
    getBoard().then(b => { setBoard(b); fetched.board = b; markLoaded("board"); }).catch(() => markLoaded("board"));
    getRadar(10).then(r => { const o = r.opportunities || []; setOpportunities(o); fetched.opportunities = o; markLoaded("opportunities"); }).catch(() => markLoaded("opportunities"));
    getHiddenMarket().then(r => { const s = r.signals || []; setSignals(s); fetched.signals = s; markLoaded("signals"); }).catch(() => markLoaded("signals"));

    // Persist cache once everything has loaded
    const cacheTimer = setTimeout(() => {
      if (typeof window !== "undefined") {
        try {
          const userId = localStorage.getItem("sr_user_id");
          localStorage.setItem(HOME_CACHE_KEY, JSON.stringify({
            ...fetched,
            _user_id: userId,
            _cached_at: Date.now(),
          }));
        } catch {}
      }
    }, 4000);
    return () => clearTimeout(cacheTimer);
  }, []);

  const displayName = user?.full_name || user?.email?.split("@")[0] || "there";

  // Show shell immediately — sections fill in as they arrive
  // Only show full skeleton if NO section has loaded yet (first visit, no cache)
  const hasAnyData = sectionsLoaded.size > 0;
  if (!hasAnyData) {
    return (
      <div style={{ padding: "36px" }}>
        <div className="animate-pulse" style={{ height: 270, borderRadius: 20, background: "rgba(255,255,255,0.04)", marginBottom: 20 }} />
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 10 }}>
          {[1,2,3].map(i => <div key={i} className="animate-pulse" style={{ height: 220, borderRadius: 16, background: "rgba(255,255,255,0.04)" }} />)}
        </div>
      </div>
    );
  }

  const today = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });

  // Derive real stats from fetched data
  const interviewCount = board?.columns?.find(c => c.stage === "interview")?.count ?? 0;
  const followUpsDue = board?.columns?.find(c => c.stage === "applied")?.applications?.filter(a => {
    const d = new Date(a.date_applied);
    return (Date.now() - d.getTime()) / 86400000 > 3;
  }).length ?? 0;

  // Get recent pipeline items (from board data)
  const pipelineItems: { company: string; role: string; stage: string }[] = [];
  if (board?.columns) {
    for (const col of board.columns) {
      for (const app of (col.applications || []).slice(0, 2)) {
        pipelineItems.push({ company: app.company, role: app.role, stage: col.stage });
      }
    }
  }

  // Build action items from real data
  const actionItems: { color: string; title: string; sub: string; cta: string; href: string }[] = [];
  if (board?.columns) {
    const interviewCol = board.columns.find(c => c.stage === "interview");
    if (interviewCol) {
      for (const app of (interviewCol.applications || []).slice(0, 2)) {
        actionItems.push({
          color: "#22c55e",
          title: `Interview — ${app.company}`,
          sub: app.role + (app.interview_at ? ` · ${new Date(app.interview_at).toLocaleDateString()}` : ""),
          cta: "Prep →",
          href: `/applications`,
        });
      }
    }
    const appliedCol = board.columns.find(c => c.stage === "applied");
    if (appliedCol) {
      for (const app of (appliedCol.applications || []).filter(a => (Date.now() - new Date(a.date_applied).getTime()) / 86400000 > 3).slice(0, 2)) {
        const days = Math.floor((Date.now() - new Date(a.date_applied).getTime()) / 86400000);
        actionItems.push({
          color: "#fbbf24",
          title: `Follow up — ${app.company}`,
          sub: `${days} days · no response`,
          cta: "Send →",
          href: `/applications`,
        });
      }
    }
  }
  if (opportunities.length > 0) {
    actionItems.push({
      color: "#4d8ef5",
      title: `New signal — ${opportunities[0].company}`,
      sub: opportunities[0].role || opportunities[0].reasoning?.slice(0, 40) || "New opportunity detected",
      cta: "View →",
      href: `/scout`,
    });
  }

  return (
    <>
      <style jsx global>{`
        @keyframes logoFloat{0%,100%{transform:translateX(-50%) translateY(0)}50%{transform:translateX(-50%) translateY(-8px)}}
        @keyframes shimmer{0%{background-position:200% center}100%{background-position:-200% center}}
        @keyframes glowDot{0%,100%{opacity:.3}50%{opacity:.9}}
        @keyframes eyeGlow{0%,100%{opacity:.2}50%{opacity:.6}}
        @keyframes pulseGlow{0%,100%{opacity:.2}50%{opacity:.6}}
        @keyframes slideRight{from{width:0}to{width:var(--w)}}
        @keyframes ticker{from{opacity:0;transform:translateX(-8px)}to{opacity:1;transform:translateX(0)}}
        @media (max-width: 768px) {
          .hero-text-block { max-width: 100% !important; }
          .hero-stats-row { flex-wrap: wrap !important; gap: 14px !important; }
          .opp-grid { grid-template-columns: 1fr !important; }
          .bottom-panels { grid-template-columns: 1fr !important; }
        }
      `}</style>

      <div style={{ minHeight: "100vh" }}>
        {/* ═══ HERO ═══ */}
        <div style={{ position: "relative", minHeight: 270, overflow: "hidden", borderBottom: "0.5px solid rgba(77,142,245,0.07)" }}>
          {/* Blue radial glow */}
          <div style={{ position: "absolute", left: "50%", top: "50%", transform: "translate(-50%,-50%)", width: 420, height: 420, borderRadius: "50%", background: "radial-gradient(circle, rgba(77,142,245,0.08) 0%, transparent 65%)", zIndex: 0, animation: "pulseGlow 5s ease-in-out infinite" }} />

          {/* Figure */}
          <img src="/images/sr-logo.png?v=2" alt="" style={{
            position: "absolute", left: "50%", top: -10, width: 380, height: 290,
            objectFit: "contain",
            filter: "drop-shadow(0 0 40px rgba(77,142,245,0.4)) drop-shadow(0 0 15px rgba(77,142,245,0.25))",
            opacity: 0.95,
            animation: "logoFloat 7s ease-in-out infinite",
            zIndex: 1, pointerEvents: "none",
            mixBlendMode: "screen",
            WebkitMaskImage: "radial-gradient(ellipse 60% 70% at center, black 40%, transparent 85%)",
            maskImage: "radial-gradient(ellipse 60% 70% at center, black 40%, transparent 85%)",
          }} />

          {/* Eye ambient */}
          <div style={{ position: "absolute", left: "50%", top: 105, transform: "translateX(-44%)", width: 90, height: 20, borderRadius: "50%", background: "radial-gradient(ellipse, rgba(255,255,255,0.15) 0%, rgba(77,142,245,0.08) 50%, transparent 100%)", zIndex: 2, animation: "eyeGlow 3s ease-in-out infinite" }} />

          {/* Left fade */}
          <div style={{ position: "absolute", left: 0, top: 0, height: 270, width: 300, background: "linear-gradient(to right, #03040f 0%, rgba(3,4,15,0.65) 50%, transparent 100%)", zIndex: 3 }} />
          {/* Right fade */}
          <div style={{ position: "absolute", right: 0, top: 0, height: 270, width: 300, background: "linear-gradient(to left, #03040f 0%, rgba(3,4,15,0.65) 50%, transparent 100%)", zIndex: 3 }} />

          {/* Hero text */}
          <div className="hero-text-block" style={{ position: "relative", zIndex: 4, padding: "28px 36px", maxWidth: "56%" }}>
            {/* Eyebrow */}
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "rgba(34,197,94,0.08)", border: "0.5px solid rgba(34,197,94,0.2)", borderRadius: 20, padding: "4px 12px", fontSize: 10, color: "#22c55e" }}>
                <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#22c55e", animation: "glowDot 1.2s ease-in-out infinite" }} />
                Precog active
              </span>
              <span style={{ fontSize: 10, color: "rgba(255,255,255,0.16)" }}>{today}</span>
            </div>

            {/* Name */}
            <div style={{ marginBottom: 11 }}>
              <span style={{ display: "block", fontSize: 20, fontWeight: 400, color: "rgba(255,255,255,0.22)" }}>{greeting()}</span>
              <span style={{
                fontSize: 44, fontWeight: 500, lineHeight: 1.1,
                background: "linear-gradient(90deg, #fff 0%, #a78bfa 40%, #4d8ef5 70%, #fff 100%)",
                backgroundSize: "200% auto",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                animation: "shimmer 6s linear infinite",
              }}>{displayName}.</span>
            </div>

            {/* Dynamic bullets from real data */}
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              {opportunities.length > 0 && (
                <div style={{ display: "flex", gap: 8, fontSize: 12, color: "rgba(255,255,255,0.32)", lineHeight: 1.5, animation: "ticker 0.35s ease 0s both" }}>
                  <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#4d8ef5", flexShrink: 0, marginTop: 5 }} />
                  <span><span style={{ color: "#4d8ef5", fontWeight: 500 }}>{opportunities.length} opportunities</span> detected across your target market.</span>
                </div>
              )}
              {interviewCount > 0 && (
                <div style={{ display: "flex", gap: 8, fontSize: 12, color: "rgba(255,255,255,0.32)", lineHeight: 1.5, animation: "ticker 0.35s ease 0.1s both" }}>
                  <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#22c55e", flexShrink: 0, marginTop: 5 }} />
                  <span><span style={{ color: "#22c55e", fontWeight: 500 }}>{interviewCount} interview{interviewCount !== 1 ? "s" : ""}</span> booked — check your prep deck.</span>
                </div>
              )}
              {followUpsDue > 0 && (
                <div style={{ display: "flex", gap: 8, fontSize: 12, color: "rgba(255,255,255,0.32)", lineHeight: 1.5, animation: "ticker 0.35s ease 0.2s both" }}>
                  <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#fbbf24", flexShrink: 0, marginTop: 5 }} />
                  <span><span style={{ color: "#fbbf24", fontWeight: 500 }}>{followUpsDue} follow-up{followUpsDue !== 1 ? "s" : ""}</span> overdue — don&apos;t let them go cold.</span>
                </div>
              )}
              {signals.length > 0 && (
                <div style={{ display: "flex", gap: 8, fontSize: 12, color: "rgba(255,255,255,0.32)", lineHeight: 1.5, animation: "ticker 0.35s ease 0.3s both" }}>
                  <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#a78bfa", flexShrink: 0, marginTop: 5 }} />
                  <span><span style={{ color: "#a78bfa", fontWeight: 500 }}>{signals.length} market signal{signals.length !== 1 ? "s" : ""}</span> detected this week.</span>
                </div>
              )}
              {opportunities.length === 0 && signals.length === 0 && interviewCount === 0 && (
                <div style={{ display: "flex", gap: 8, fontSize: 12, color: "rgba(255,255,255,0.32)", lineHeight: 1.5, animation: "ticker 0.35s ease 0s both" }}>
                  <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#4d8ef5", flexShrink: 0, marginTop: 5 }} />
                  <span>Scanning the market for opportunities that match your profile.</span>
                </div>
              )}
            </div>

            {/* Stats */}
            <div className="hero-stats-row" style={{ display: "flex", gap: 22, marginTop: 16 }}>
              {[
                { val: String(opportunities.length), label: "opportunities", color: "#fff" },
                { val: String(interviewCount), label: "interviews booked", color: "#22c55e" },
                { val: String(followUpsDue), label: "follow-ups due", color: "#fbbf24" },
                { val: String(signals.length), label: "signals this week", color: "#a78bfa" },
              ].map((s, i) => (
                <div key={i} style={{ borderLeft: "2px solid rgba(255,255,255,0.12)", paddingLeft: 12 }}>
                  <div style={{ fontSize: 22, fontWeight: 500, color: s.color }}>{s.val}</div>
                  <div style={{ fontSize: 10, color: "rgba(255,255,255,0.55)", textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 500, marginTop: 2 }}>{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ═══ BODY ═══ */}
        <div style={{ padding: "20px 36px", display: "flex", flexDirection: "column", gap: 18 }}>

          {/* ── OPPORTUNITIES ── */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <span style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.7, color: "rgba(255,255,255,0.2)" }}>
                {opportunities.length > 0 ? "Detected before posting — your unfair advantage" : "Opportunities"}
              </span>
              <a href="/scout" style={{ fontSize: 11, color: "#4d8ef5", textDecoration: "none" }}>Scout all →</a>
            </div>

            {opportunities.length > 0 ? (
              <div className="opp-grid" style={{ display: "grid", gridTemplateColumns: opportunities.length >= 3 ? "2fr 1fr 1fr" : opportunities.length === 2 ? "1fr 1fr" : "1fr", gap: 10 }}>
                {opportunities.slice(0, 3).map((opp, i) => {
                  const color = i === 0 ? "#4d8ef5" : i === 1 ? "#a78bfa" : "#22c55e";
                  const isHero = i === 0;
                  return (
                    <div key={opp.id} style={{
                      background: `${color}11`,
                      border: `1px solid ${color}33`,
                      borderRadius: isHero ? 20 : 16,
                      padding: isHero ? 20 : 16,
                      position: "relative",
                      overflow: "hidden",
                      display: "flex",
                      flexDirection: "column",
                    }}>
                      {isHero && <div style={{ position: "absolute", top: 0, left: "10%", right: "10%", height: 1, background: `linear-gradient(90deg, transparent, ${color}, transparent)` }} />}
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                        <span style={{ fontSize: 9, textTransform: "uppercase", background: `${color}22`, color, padding: "3px 9px", borderRadius: 10, fontWeight: 600, letterSpacing: 0.5 }}>
                          {opp.evidence_tier === "high" ? "Hidden · Strong signal" : opp.evidence_tier === "medium" ? "Signal detected" : "Watching"}
                        </span>
                        <div>
                          <span style={{ fontSize: isHero ? 56 : 36, fontWeight: 500, color, lineHeight: 1 }}>{opp.radar_score}</span>
                          <span style={{ fontSize: isHero ? 16 : 12, color, opacity: 0.4 }}>%</span>
                        </div>
                      </div>
                      <div style={{ fontSize: isHero ? 16 : 14, fontWeight: 500, color: "#fff" }}>{opp.role || "Opportunity detected"}</div>
                      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", marginTop: 2, marginBottom: 10 }}>
                        {opp.company}{opp.location ? ` · ${opp.location}` : ""}{opp.sector ? ` · ${opp.sector}` : ""}
                      </div>
                      {isHero && opp.reasoning && (
                        <div style={{ fontStyle: "italic", fontSize: 11, color: `${color}99`, background: `${color}0a`, borderLeft: `2px solid ${color}44`, padding: "9px 11px", borderRadius: "0 8px 8px 0", marginBottom: 12, lineHeight: 1.5 }}>
                          &ldquo;{opp.reasoning}&rdquo;
                        </div>
                      )}
                      {!isHero && opp.reasoning && (
                        <div style={{ fontSize: 10, color: "rgba(255,255,255,0.25)", lineHeight: 1.4, marginBottom: 12, flex: 1 }}>
                          {opp.reasoning.slice(0, 80)}{opp.reasoning.length > 80 ? "..." : ""}
                        </div>
                      )}
                      <div style={{ display: "flex", gap: 8, marginTop: "auto" }}>
                        {isHero ? (
                          <>
                            <button
                              onClick={() => handleGeneratePack(opp.company, opp.role || "Senior Role", (opp as any).apply_url || (opp as any).source_url || null)}
                              disabled={generatingFor === `${opp.company}|${opp.role || "Senior Role"}`}
                              style={{ background: color, color: "#fff", border: "none", borderRadius: 11, padding: "9px 15px", fontSize: 11, fontWeight: 600, cursor: "pointer", opacity: generatingFor === `${opp.company}|${opp.role || "Senior Role"}` ? 0.6 : 1 }}
                            >
                              {generatingFor === `${opp.company}|${opp.role || "Senior Role"}` ? "Starting..." : "Apply with AI pack"}
                            </button>
                            <a href="/scout" style={{ background: "rgba(255,255,255,0.05)", color: "rgba(255,255,255,0.5)", border: "0.5px solid rgba(255,255,255,0.1)", borderRadius: 11, padding: "9px 15px", fontSize: 11, fontWeight: 500, textDecoration: "none" }}>View intel →</a>
                          </>
                        ) : (
                          <button
                            onClick={() => handleGeneratePack(opp.company, opp.role || "Senior Role", (opp as any).apply_url || (opp as any).source_url || null)}
                            disabled={generatingFor === `${opp.company}|${opp.role || "Senior Role"}`}
                            style={{ display: "block", textAlign: "center", background: color, color: "#fff", borderRadius: 10, padding: "8px 0", fontSize: 11, fontWeight: 600, border: "none", cursor: "pointer", width: "100%", opacity: generatingFor === `${opp.company}|${opp.role || "Senior Role"}` ? 0.6 : 1 }}
                          >
                            {generatingFor === `${opp.company}|${opp.role || "Senior Role"}` ? "Starting..." : "Generate pack"}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div style={{ background: "rgba(255,255,255,0.025)", border: "0.5px solid rgba(255,255,255,0.06)", borderRadius: 16, padding: 32, textAlign: "center" }}>
                <div style={{ fontSize: 13, color: "rgba(255,255,255,0.4)", marginBottom: 8 }}>No opportunities detected yet</div>
                <div style={{ fontSize: 11, color: "rgba(255,255,255,0.2)", marginBottom: 16 }}>Upload your CV and connect your email to start scanning for hidden roles.</div>
                <a href="/scout" style={{ background: "#4d8ef5", color: "#fff", borderRadius: 10, padding: "8px 16px", fontSize: 11, fontWeight: 600, textDecoration: "none" }}>Go to Scout →</a>
              </div>
            )}
          </div>

          {/* ── BOTTOM ROW ── */}
          <div className="bottom-panels" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
            {/* Panel 1 — Live Signals */}
            <div style={{ background: "rgba(255,255,255,0.025)", border: "0.5px solid rgba(255,255,255,0.06)", borderRadius: 16, padding: 16 }}>
              <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.6, color: "rgba(255,255,255,0.2)", marginBottom: 13 }}>Live Signals</div>
              {signals.length > 0 ? signals.slice(0, 4).map((s, i) => {
                const color = TIER_COLORS[s.evidence_tier || "medium"] || "#4d8ef5";
                const pct = s.confidence || 50;
                return (
                  <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 9, padding: "7px 0", borderBottom: i < Math.min(signals.length, 4) - 1 ? "0.5px solid rgba(255,255,255,0.04)" : "none" }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.55)", marginBottom: 4 }}>
                        {s.company_name} · {s.signal_type?.replace(/_/g, " ") || "signal"}
                      </div>
                      <div style={{ height: 2, background: "rgba(255,255,255,0.06)", borderRadius: 1, overflow: "hidden" }}>
                        <div style={{ height: "100%", background: color, borderRadius: 1, width: pct + "%", animation: `slideRight 1s ease ${i * 0.15}s both`, "--w": pct + "%" } as any} />
                      </div>
                    </div>
                    <span style={{ fontSize: 13, fontWeight: 500, color, minWidth: 24, textAlign: "right" }}>{pct}</span>
                    <span style={{ fontSize: 9, color: "rgba(255,255,255,0.15)", minWidth: 20, textAlign: "right" }}>{timeAgo(s.created_at)}</span>
                  </div>
                );
              }) : (
                <div style={{ padding: "16px 0", textAlign: "center" }}>
                  <div style={{ fontSize: 11, color: "rgba(255,255,255,0.25)" }}>No signals yet — check back soon</div>
                  <div style={{ fontSize: 10, color: "rgba(255,255,255,0.15)", marginTop: 4 }}>Signals appear as the market is scanned</div>
                </div>
              )}
            </div>

            {/* Panel 2 — Today's Actions */}
            <div style={{ background: "rgba(255,255,255,0.025)", border: "0.5px solid rgba(255,255,255,0.06)", borderRadius: 16, padding: 16 }}>
              <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.6, color: "rgba(255,255,255,0.2)", marginBottom: 13 }}>Today&apos;s Actions</div>
              {actionItems.length > 0 ? actionItems.slice(0, 4).map((a, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 9, padding: "7px 0", borderBottom: i < Math.min(actionItems.length, 4) - 1 ? "0.5px solid rgba(255,255,255,0.04)" : "none" }}>
                  <span style={{ width: 7, height: 7, borderRadius: "50%", background: a.color, flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 11, color: "rgba(255,255,255,0.55)" }}>{a.title}</div>
                    <div style={{ fontSize: 10, color: "rgba(255,255,255,0.2)" }}>{a.sub}</div>
                  </div>
                  <a href={a.href} style={{ fontSize: 10, fontWeight: 600, color: a.color, background: `${a.color}15`, padding: "3px 8px", borderRadius: 6, textDecoration: "none", whiteSpace: "nowrap" }}>{a.cta}</a>
                </div>
              )) : (
                <div style={{ padding: "16px 0", textAlign: "center" }}>
                  <div style={{ fontSize: 11, color: "rgba(255,255,255,0.25)" }}>No actions for today</div>
                  <div style={{ fontSize: 10, color: "rgba(255,255,255,0.15)", marginTop: 4 }}>Start scouting and applying to build your pipeline</div>
                </div>
              )}
            </div>

            {/* Panel 3 — Pipeline */}
            <div style={{ background: "rgba(255,255,255,0.025)", border: "0.5px solid rgba(255,255,255,0.06)", borderRadius: 16, padding: 16 }}>
              <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.6, color: "rgba(255,255,255,0.2)", marginBottom: 13 }}>Pipeline</div>
              {pipelineItems.length > 0 ? pipelineItems.slice(0, 4).map((p, i) => {
                const stageColor = STAGE_COLORS[p.stage] || "#4d8ef5";
                const initials = p.company.split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase();
                return (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 9, padding: "7px 0", borderBottom: i < Math.min(pipelineItems.length, 4) - 1 ? "0.5px solid rgba(255,255,255,0.04)" : "none" }}>
                    <div style={{ width: 28, height: 28, borderRadius: 8, background: `${stageColor}18`, color: stageColor, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 9, fontWeight: 700, flexShrink: 0 }}>{initials}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.55)" }}>{p.company}</div>
                      <div style={{ fontSize: 10, color: "rgba(255,255,255,0.2)" }}>{p.role}</div>
                    </div>
                    <span style={{ fontSize: 9, fontWeight: 600, color: stageColor, background: `${stageColor}15`, padding: "2px 7px", borderRadius: 6, whiteSpace: "nowrap", textTransform: "capitalize" }}>{p.stage}</span>
                  </div>
                );
              }) : (
                <div style={{ padding: "16px 0", textAlign: "center" }}>
                  <div style={{ fontSize: 11, color: "rgba(255,255,255,0.25)" }}>No applications tracked yet</div>
                  <div style={{ fontSize: 10, color: "rgba(255,255,255,0.15)", marginTop: 4 }}>
                    <a href="/applications" style={{ color: "#4d8ef5", textDecoration: "none" }}>Start tracking →</a>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
