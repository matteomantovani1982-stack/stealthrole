// @ts-nocheck
"use client";

// Build: scout-fix-v2 — force new chunk hash to bust browser cache

import { useEffect, useState, Component } from "react";
import { useRouter } from "next/navigation";
import { getHiddenMarket, createAppAndPack, formatApiError, type HiddenSignal } from "@/lib/api";
import { getAuthHeaders, timeAgo, initials as makeInitials } from "@/lib/utils";
import { TRIGGER_COLORS } from "@/lib/constants";
import MarketSignals from "@/components/market-signals";
import FindWayInPanel from "@/components/find-way-in";

// ═══ Error Boundary — catches runtime crashes and shows a friendly message ═══
class ScoutErrorBoundary extends Component<{ children: React.ReactNode }, { hasError: boolean; error: Error | null }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, errorInfo: any) {
    console.error("[ScoutPage] Runtime error:", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: "48px 24px", textAlign: "center" }}>
          <div style={{ fontSize: 18, color: "#fca5a5", marginBottom: 12 }}>Something went wrong loading the Scout</div>
          <div style={{ fontSize: 13, color: "rgba(255,255,255,0.4)", marginBottom: 20, maxWidth: 500, margin: "0 auto 20px" }}>
            {this.state.error?.message || "Unknown error"}
          </div>
          <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
            <button
              onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
              style={{ background: "#4d8ef5", color: "#fff", borderRadius: 10, padding: "10px 20px", fontSize: 13, fontWeight: 600, border: "none", cursor: "pointer" }}
            >
              Reload page
            </button>
            <a href="/" style={{ background: "rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.7)", borderRadius: 10, padding: "10px 20px", fontSize: 13, fontWeight: 600, textDecoration: "none" }}>
              Back to home
            </a>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// TRIGGER_COLORS imported from @/lib/constants
// createAppAndPack imported from @/lib/api


export default function ScoutPageWrapper() {
  return (
    <ScoutErrorBoundary>
      <ScoutPage />
    </ScoutErrorBoundary>
  );
}

function ScoutPage() {
  const router = useRouter();
  const [vacancies, setVacancies] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [signals, setSignals] = useState([]);
  const [freelance, setFreelance] = useState([]);
  const [platformLinks, setPlatformLinks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [tab, setTab] = useState("vacancies");

  const headers = getAuthHeaders(false);
  const roleFromHeadline = (headline: string) => {
    const h = (headline || "").trim();
    if (!h) return "Senior Role";
    if (h.includes(" — ")) {
      const parts = h.split(" — ").map((p) => p.trim()).filter(Boolean);
      if (parts.length >= 2) return parts[1];
    }
    if (h.includes(" - ")) {
      const parts = h.split(" - ").map((p) => p.trim()).filter(Boolean);
      if (parts.length >= 2) return parts[1];
    }
    return h;
  };

  // Load on mount — use sessionStorage cache to avoid re-fetching on navigation
  useEffect(() => {
    const currentUserId = typeof window !== "undefined" ? localStorage.getItem("sr_user_id") : null;
    try {
      const cached = sessionStorage.getItem("sr_scout_data");
      if (cached) {
        const d = JSON.parse(cached);
        // SECURITY: only restore cache if it belongs to the current user
        if (d._user_id && d._user_id === currentUserId) {
          if (d.vacancies?.length) setVacancies(d.vacancies);
          if (d.signals?.length) setSignals(d.signals);
          if (d.predictions?.length) setPredictions(d.predictions);
          if (d.freelance?.length) setFreelance(d.freelance);
          if (d.platformLinks?.length) setPlatformLinks(d.platformLinks);
          return; // Use cache, don't re-fetch
        } else {
          // Stale cache from another user — discard
          sessionStorage.removeItem("sr_scout_data");
        }
      }
    } catch {}
    setLoading(true);
    Promise.allSettled([
      fetch("/api/v1/scout/vacancies?limit=30", { headers }).then(r => r.ok ? r.json() : {}).then(d => setVacancies(d.vacancies || [])),
      getHiddenMarket().then(r => setSignals(r.signals || [])),
      // Prefetch predictions so the Future Openings tab count is accurate on first render
      fetch("/api/v1/scout/predictions", { headers }).then(r => r.ok ? r.json() : {}).then(d => setPredictions(d.predictions || [])).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  // Cache scout data for navigation persistence
  useEffect(() => {
    if (vacancies.length || signals.length || predictions.length || freelance.length) {
      try {
        const userId = typeof window !== "undefined" ? localStorage.getItem("sr_user_id") : null;
        sessionStorage.setItem("sr_scout_data", JSON.stringify({ vacancies, signals, predictions, freelance, platformLinks, _user_id: userId }));
      } catch {}
    }
  }, [vacancies, signals, predictions, freelance, platformLinks]);

  // Lazy load tabs
  useEffect(() => {
    if (tab === "predictions" && predictions.length === 0) {
      fetch("/api/v1/scout/predictions", { headers }).then(r => r.ok ? r.json() : {}).then(d => setPredictions(d.predictions || [])).catch(() => {});
    }
    if (tab === "freelance" && freelance.length === 0) {
      fetch("/api/v1/scout/freelance?limit=20", { headers }).then(r => r.ok ? r.json() : {}).then(d => { setFreelance(d.freelance || []); setPlatformLinks(d.platform_links || []); }).catch(() => {});
    }
  }, [tab]);

  async function unleashScout() {
    setScanning(true);
    try {
      // Run signal engine first, then load everything
      await fetch("/api/v1/scout/signals", { headers }).catch(() => {});
      await Promise.allSettled([
        fetch("/api/v1/scout/vacancies?limit=30", { headers }).then(r => r.ok ? r.json() : {}).then(d => setVacancies(d.vacancies || [])),
        getHiddenMarket().then(r => setSignals(r.signals || [])),
        fetch("/api/v1/scout/predictions", { headers }).then(r => r.ok ? r.json() : {}).then(d => setPredictions(d.predictions || [])),
        fetch("/api/v1/scout/freelance?limit=20", { headers }).then(r => r.ok ? r.json() : {}).then(d => { setFreelance(d.freelance || []); setPlatformLinks(d.platform_links || []); }),
      ]);
    } catch {}
    setScanning(false);
  }

  const TABS = [
    { id: "intelligence", label: "Intelligence", count: predictions.length + signals.length },
    { id: "vacancies", label: "Current Vacancies", count: vacancies.length },
    { id: "predictions", label: "Future Openings", count: predictions.length },
    { id: "signals", label: "Hiring Signals", count: signals.length },
    { id: "freelance", label: "Freelance", count: freelance.length || 14 },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Job Scout</h1>
          <p className="text-sm text-[#6B7194] mt-1">
            {vacancies.length} vacancies &middot; {signals.length} signals &middot; {predictions.length} predictions &middot; {freelance.length} freelance
          </p>
        </div>
        <button
          onClick={unleashScout}
          disabled={scanning}
          className="px-6 py-3 text-sm font-semibold text-white rounded-xl disabled:opacity-60 transition-all shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40"
          style={{ background: "linear-gradient(135deg, #5B6CFF 0%, #9F7AEA 50%, #7F8CFF 100%)" }}
        >
          {scanning ? "Scanning the hidden market..." : "Unleash the Scout"}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-white/10">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.id ? "border-[#7F8CFF] text-[#7F8CFF]" : "border-transparent text-[#6B7194] hover:text-white"
            }`}
          >
            {t.label} ({t.count})
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-20 rounded-xl animate-pulse" style={{ background: "rgba(255,255,255,0.04)" }} />
          ))}
        </div>
      )}

      {/* ═══ INTELLIGENCE (merged, additive) ═══ */}
      {!loading && tab === "intelligence" && (
        <IntelligenceTab
          predictions={predictions}
          signals={signals}
          onAddPack={createAppAndPack}
        />
      )}

      {/* ═══ CURRENT VACANCIES ═══ */}
      {!loading && tab === "vacancies" && <VacanciesTab onAddPack={createAppAndPack} vacancies={vacancies} />}

      {/* ═══ PREDICTED OPPORTUNITIES ═══ */}
      {!loading && tab === "predictions" && <PredictionsTab onAddPack={createAppAndPack} predictions={predictions} />}

      {/* ═══ HIRING SIGNALS ═══ */}
      {!loading && tab === "signals" && <SignalsTab signals={signals} />}

      {/* ═══ FREELANCE ═══ */}
      {!loading && tab === "freelance" && <FreelanceTab />}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   VACANCIES TAB — Heat-coloured current vacancies
   ═══════════════════════════════════════════════════════════════ */

function heatColor(pct: number) {
  if (pct >= 90) return { main: "#4d8ef5", light: "#93c5fd", name: "blue", tier: "Closest match", bg: "linear-gradient(160deg, #0a1a3a, #060e22)", border: "rgba(77,142,245,0.32)", band: "linear-gradient(90deg, #1e3a8a, #4d8ef5, #1e3a8a)" };
  if (pct >= 75) return { main: "#22c55e", light: "#86efac", name: "green", tier: "Strong match", bg: "linear-gradient(160deg, #042e12, #021808)", border: "rgba(34,197,94,0.28)", band: "linear-gradient(90deg, #166534, #22c55e, #166534)" };
  if (pct >= 60) return { main: "#eab308", light: "#fde047", name: "yellow", tier: "Medium match", bg: "linear-gradient(160deg, #2a2200, #1a1500)", border: "rgba(234,179,8,0.28)", band: "linear-gradient(90deg, #713f12, #eab308, #713f12)" };
  if (pct >= 45) return { main: "#ea580c", light: "#fdba74", name: "orange", tier: "Partial match", bg: "linear-gradient(160deg, #2e1200, #1a0a00)", border: "rgba(234,88,12,0.28)", band: "linear-gradient(90deg, #9a3412, #ea580c, #9a3412)" };
  return { main: "#ef4444", light: "#fca5a5", name: "red", tier: "Weak match", bg: "linear-gradient(160deg, #2e0606, #180303)", border: "rgba(239,68,68,0.25)", band: "linear-gradient(90deg, #7f1d1d, #ef4444, #7f1d1d)" };
}

function MatchGauge({ pct, delay = 0 }: { pct: number; delay?: number }) {
  const c = heatColor(pct);
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;

  return (
    <div style={{ position: "relative", width: 64, height: 64, flexShrink: 0 }}>
      <svg width="64" height="64" viewBox="0 0 64 64" style={{ transform: "rotate(-90deg)" }}>
        <circle cx="32" cy="32" r="30" fill={`${c.main}0d`} />
        <circle cx="32" cy="32" r="26" fill="#06070f" />
        <circle cx="32" cy="32" r="26" fill="none" stroke={`${c.main}1f`} strokeWidth="7" />
        <circle
          cx="32" cy="32" r="26" fill="none"
          stroke={c.main} strokeWidth="7" strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference}
          style={{
            animation: `arcDraw 1s ease ${delay}s forwards`,
            "--target-offset": offset,
          } as any}
        />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: c.main, lineHeight: 1 }}>{pct}</div>
        <div style={{ fontSize: 8, color: "rgba(255,255,255,0.25)", textTransform: "uppercase", marginTop: 1 }}>match</div>
      </div>
      <style jsx>{`
        @keyframes arcDraw {
          to { stroke-dashoffset: ${offset}; }
        }
      `}</style>
    </div>
  );
}

function VacanciesTab({ onAddPack, vacancies = [] }: { onAddPack: (company: string, role: string, url: string | null, description: string) => Promise<any>; vacancies?: any[] }) {
  const router = useRouter();
  const [wayInTarget, setWayInTarget] = useState<{ company: string; role: string } | null>(null);

  // Build rows from real vacancy data
  const rows = vacancies
    .filter((job: any) => {
      const company = job.company || "";
      const title = job.role || job.title || "";
      const desc = (job.description || "").toLowerCase();
      if (!company || company === "Company" || company.length < 2) return false;
      if (title.includes("jobs in") || title.includes("Jobs in") || title.includes("Search Results")) return false;
      if (
        desc.includes("no longer accepting applications")
        || desc.includes("job expired")
        || desc.includes("application closed")
        || title.toLowerCase().includes("no longer accepting applications")
      ) return false;
      if (job.date) {
        try { if (Date.now() - new Date(job.date).getTime() > 60 * 86400000) return false; } catch {}
      }
      return true;
    })
    .slice(0, 30)
    .map((job: any, i: number) => ({
      pct: job.radar_score || job.fit_score || job.match_score || Math.max(35, Math.round(85 - i * 6 + ((job.company || "").charCodeAt(0) % 11) - 5)),
      company: job.company || "Company",
      role: job.role || job.title || "Role",
      location: job.location || "",
      desc: job.description?.substring(0, 120) || "",
      source: job.source || "LinkedIn",
      date: job.date || "",
      // Some providers return source_url/job_url instead of url.
      url: job.url || job.source_url || job.job_url || null,
    }));

  async function handleApply(company: string, role: string, url?: string | null) {
    try {
      const app = await onAddPack(company, role, url || null, "");
      // FIX 6: navigate to the application package page so user sees real-time progress
      if (app?.id) {
        router.push(`/applications/${app.id}/package`);
      } else {
        router.push("/applications");
      }
    } catch (err: any) {
      const msg = err?.message || "Failed to start pack generation";
      if (typeof window !== "undefined") {
        if (msg.startsWith("NO_CV:")) {
          alert(msg.replace("NO_CV: ", ""));
        } else {
          alert(msg);
        }
      }
    }
  }

  if (rows.length === 0) {
    return (
      <div style={{ padding: "48px 24px", textAlign: "center" }}>
        <div style={{ fontSize: 16, color: "rgba(255,255,255,0.4)", marginBottom: 12 }}>No vacancies found yet</div>
        <div style={{ fontSize: 13, color: "rgba(255,255,255,0.2)", marginBottom: 24, maxWidth: 420, margin: "0 auto 24px" }}>
          Upload your CV and set your preferences to start finding matching vacancies across job boards and company career pages.
        </div>
        <a href="/profile" style={{ background: "#4d8ef5", color: "#fff", borderRadius: 10, padding: "10px 20px", fontSize: 13, fontWeight: 600, textDecoration: "none" }}>Set up profile →</a>
      </div>
    );
  }

  // Top match = first row
  const hero = rows[0];
  const heroC = heatColor(hero.pct);
  const rest = rows.slice(1);

  return (
    <div style={{ padding: "16px 8px" }}>
      <style jsx>{`
        @keyframes slideUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>

      {/* Hero — top match */}
      <div style={{
        background: heroC.bg, border: `1px solid ${heroC.main}59`,
        borderRadius: 18, padding: 20, position: "relative", overflow: "hidden",
        animation: "slideUp 0.5s ease", marginBottom: 16,
      }}>
        <div style={{ position: "absolute", top: 0, left: "10%", right: "10%", height: 1, background: `linear-gradient(90deg, transparent, ${heroC.main}cc, transparent)` }} />
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 20 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <span style={{ fontSize: 10, background: `${heroC.main}26`, color: heroC.light, padding: "4px 10px", borderRadius: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.3 }}>
              {hero.pct}% match · Top result
            </span>
            <div style={{ fontSize: 22, fontWeight: 500, color: "#fff", marginTop: 12, marginBottom: 4 }}>{hero.role}</div>
            <div style={{ fontSize: 13, color: "rgba(255,255,255,0.45)", marginBottom: 12 }}>{hero.company}{hero.location ? ` · ${hero.location}` : ""}</div>
            {hero.desc && (
              <div style={{ fontSize: 12, color: "rgba(255,255,255,0.5)", lineHeight: 1.5, marginBottom: 14 }}>{hero.desc}</div>
            )}
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={() => handleApply(hero.company, hero.role)} style={{ background: heroC.main, color: "#fff", border: "none", borderRadius: 10, padding: "9px 16px", fontSize: 11, fontWeight: 600, cursor: "pointer" }}>Prepare with AI</button>
              <button onClick={() => setWayInTarget(wayInTarget?.company === hero.company ? null : { company: hero.company, role: hero.role })} style={{ background: wayInTarget?.company === hero.company ? "#4d8ef5" : "rgba(255,255,255,0.04)", color: wayInTarget?.company === hero.company ? "#fff" : "rgba(255,255,255,0.6)", border: "0.5px solid rgba(255,255,255,0.1)", borderRadius: 10, padding: "9px 14px", fontSize: 11, fontWeight: 500, cursor: "pointer" }}>Way in →</button>
              {hero.url && <a href={hero.url} target="_blank" rel="noopener" style={{ background: "rgba(255,255,255,0.04)", color: "rgba(255,255,255,0.6)", border: "0.5px solid rgba(255,255,255,0.1)", borderRadius: 10, padding: "9px 14px", fontSize: 11, fontWeight: 500, textDecoration: "none" }}>View posting →</a>}
            </div>
          </div>
          <div style={{ fontSize: 60, fontWeight: 500, color: heroC.light, lineHeight: 0.9, flexShrink: 0 }}>{hero.pct}<span style={{ fontSize: 22, opacity: 0.5 }}>%</span></div>
        </div>
      </div>

      {/* Way In Panel */}
      {wayInTarget && (
        <div style={{ marginBottom: 16 }}>
          <FindWayInPanel company={wayInTarget.company} role={wayInTarget.role} headers={getAuthHeaders(false)} />
        </div>
      )}

      {/* Vacancy list */}
      <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.7, color: "rgba(255,255,255,0.25)", marginBottom: 10 }}>
        {rest.length} more vacancies
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 10 }}>
        {rest.map((row, i) => {
          const c = heatColor(row.pct);
          return (
            <div key={i} style={{
              background: "rgba(255,255,255,0.03)",
              border: "0.5px solid rgba(255,255,255,0.08)",
              borderRadius: 14,
              padding: 16,
              animation: `slideUp 0.35s ease ${i * 0.04}s both`,
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}>
              {/* Header row: score + title */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 500, color: "#fff", lineHeight: 1.3 }}>{row.role}</div>
                  <div style={{ fontSize: 12, color: "rgba(255,255,255,0.4)", marginTop: 3 }}>
                    {row.company}{row.location ? ` · ${row.location}` : ""}
                  </div>
                </div>
                <div style={{ fontSize: 36, fontWeight: 600, color: c.main, lineHeight: 1, flexShrink: 0 }}>
                  {row.pct}<span style={{ fontSize: 14, opacity: 0.5 }}>%</span>
                </div>
              </div>

              {/* Action buttons */}
              <div style={{ display: "flex", gap: 6, marginTop: "auto" }}>
                {row.url ? (
                  <a
                    href={row.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      flex: 1,
                      textAlign: "center",
                      background: "rgba(255,255,255,0.04)",
                      color: "rgba(255,255,255,0.65)",
                      border: "0.5px solid rgba(255,255,255,0.1)",
                      borderRadius: 10,
                      padding: "8px 10px",
                      fontSize: 11,
                      fontWeight: 500,
                      textDecoration: "none",
                    }}
                  >
                    See posting →
                  </a>
                ) : (
                  <button
                    disabled
                    title="Source not available"
                    style={{
                      flex: 1,
                      background: "rgba(255,255,255,0.02)",
                      color: "rgba(255,255,255,0.25)",
                      border: "0.5px solid rgba(255,255,255,0.06)",
                      borderRadius: 10,
                      padding: "8px 10px",
                      fontSize: 11,
                      fontWeight: 500,
                      cursor: "not-allowed",
                    }}
                  >
                    No source
                  </button>
                )}
                <button
                  onClick={() => handleApply(row.company, row.role, row.url)}
                  style={{
                    flex: 1,
                    background: "#4d8ef5",
                    color: "#fff",
                    border: "none",
                    borderRadius: 10,
                    padding: "8px 10px",
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Generate pack
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

type PredStatus = "imminent" | "strong" | "forming" | "early" | "speculative";

const PRED_COLORS: Record<PredStatus, { main: string; light: string; bg: string; border: string; barPct: number; btn: string }> = {
  imminent:    { main: "#4d8ef5", light: "#93c5fd", bg: "rgba(77,142,245,0.08)",  border: "rgba(77,142,245,0.25)",  barPct: 90, btn: "Apply" },
  strong:      { main: "#22c55e", light: "#86efac", bg: "rgba(34,197,94,0.08)",   border: "rgba(34,197,94,0.25)",   barPct: 75, btn: "Prepare" },
  forming:     { main: "#eab308", light: "#fde047", bg: "rgba(234,179,8,0.08)",   border: "rgba(234,179,8,0.22)",   barPct: 58, btn: "Watch" },
  early:       { main: "#ea580c", light: "#fdba74", bg: "rgba(234,88,12,0.08)",   border: "rgba(234,88,12,0.22)",   barPct: 42, btn: "Watch" },
  speculative: { main: "#ef4444", light: "#fca5a5", bg: "rgba(239,68,68,0.06)",   border: "rgba(239,68,68,0.18)",   barPct: 25, btn: "Watch" },
};

const PRED_LABELS: Record<PredStatus, string> = {
  imminent: "Imminent",
  strong: "Strong Signal",
  forming: "Forming",
  early: "Early",
  speculative: "Speculative",
};

function PredictionsTab({ onAddPack, predictions = [] }: { onAddPack: (company: string, role: string, url: string | null, description: string) => Promise<any>; predictions?: any[] }) {
  const router = useRouter();
  const [wayInTarget, setWayInTarget] = useState<{ company: string; role: string } | null>(null);

  // Map real predictions to cards if available
  function mapUrgencyToStatus(urgency: string, confidence: number): PredStatus {
    if (urgency === "imminent" || confidence >= 85) return "imminent";
    if (urgency === "likely" || confidence >= 70) return "strong";
    if (confidence >= 55) return "forming";
    if (confidence >= 40) return "early";
    return "speculative";
  }

  const realCards = predictions.slice(0, 6).map((p: any) => {
    const status = mapUrgencyToStatus(p.urgency, p.confidence);
    return {
      status,
      initials: makeInitials(p.company || "??"),
      window: p.timeline || "30 days",
      title: p.predicted_role || "Role",
      company: p.company || "Company",
      location: p.decision_maker ? `Decision: ${p.decision_maker}` : "",
      stats: [
        { v: p.trigger_type?.replace(/_/g, " ") || "Signal", l: "trigger" },
        { v: String(p.confidence || 0) + "%", l: "confidence" },
        { v: p.timeline || "TBD", l: "timeline" },
      ],
      intel: (p.trigger_event ? p.trigger_event + ". " : "") + (p.reasoning || "Signal detected."),
    };
  });

  // No hardcoded feed items — use real predictions only

  async function handleApply(company: string, role: string, url?: string | null) {
    try {
      const app = await onAddPack(company, role, url || null, "");
      // FIX 6: navigate to the application package page so user sees real-time progress
      if (app?.id) {
        router.push(`/applications/${app.id}/package`);
      } else {
        router.push("/applications");
      }
    } catch (err: any) {
      const msg = err?.message || "Failed to start pack generation";
      if (typeof window !== "undefined") {
        if (msg.startsWith("NO_CV:")) {
          alert(msg.replace("NO_CV: ", ""));
        } else {
          alert(msg);
        }
      }
    }
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 270px", gap: 16, padding: "16px 8px" }}>
      <style jsx>{`
        @keyframes cardIn { from { opacity: 0; transform: translateY(8px) scale(0.93); } to { opacity: 1; transform: translateY(0) scale(1); } }
        @keyframes feedScroll { from { transform: translateY(0); } to { transform: translateY(-50%); } }
        .feed-track:hover { animation-play-state: paused; }
      `}</style>

      {/* ═══ LEFT: Cards grid ═══ */}
      <div>
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.7, color: "rgba(255,255,255,0.35)", fontWeight: 600 }}>
            Predicted before posting · ranked by signal strength
          </div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.25)", marginTop: 3 }}>{realCards.length > 0 ? `${realCards.length} hidden opportunities detected` : "Scanning for predicted opportunities..."}</div>
        </div>

        {/* Legend */}
        <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 10, color: "rgba(255,255,255,0.25)", marginBottom: 14, flexWrap: "wrap" }}>
          <span>Opportunity status:</span>
          {([["#4d8ef5", "Imminent"], ["#22c55e", "Strong Signal"], ["#eab308", "Forming"], ["#ea580c", "Early"], ["#ef4444", "Speculative"]] as [string, string][]).map(([c, l], i) => (
            <span key={i} style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: c }} /> {l}
            </span>
          ))}
        </div>

        {realCards.length === 0 && (
          <div style={{ background: "rgba(255,255,255,0.025)", border: "0.5px solid rgba(255,255,255,0.06)", borderRadius: 16, padding: 32, textAlign: "center", marginBottom: 16 }}>
            <div style={{ fontSize: 14, color: "rgba(255,255,255,0.4)", marginBottom: 8 }}>Scanning the market for signals</div>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,0.2)", marginBottom: 16, maxWidth: 420, margin: "0 auto 16px" }}>
              We are scanning news, funding rounds, leadership changes and market shifts. Check back in 24 hours — or import your LinkedIn connections to improve matching.
            </div>
            <a href="/settings#linkedin" style={{ background: "#4d8ef5", color: "#fff", borderRadius: 10, padding: "8px 16px", fontSize: 12, fontWeight: 600, textDecoration: "none" }}>Import LinkedIn connections →</a>
          </div>
        )}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
          {realCards.map((card, i) => {
            const c = PRED_COLORS[card.status];
            const label = PRED_LABELS[card.status];
            return (
              <div key={i} style={{
                background: c.bg, border: `1px solid ${c.border}`,
                borderRadius: 16, padding: 16, position: "relative", overflow: "hidden",
                animation: `cardIn 0.35s ease ${i * 0.06}s both`,
                display: "flex", flexDirection: "column",
              }}>
                <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 4, background: c.band }} />

                {/* Top row: icon left + status right */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginTop: 8, marginBottom: 10 }}>
                  <div style={{ width: 36, height: 36, borderRadius: 10, background: `${c.main}2e`, color: c.light, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 700 }}>{card.initials}</div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 20, fontWeight: 500, color: c.light, lineHeight: 1.1 }}>{label}</div>
                    <div style={{ display: "flex", justifyContent: "flex-end", gap: 6, marginTop: 4 }}>
                      <span style={{ fontSize: 9, fontWeight: 700, color: c.light, background: `${c.main}22`, padding: "3px 8px", borderRadius: 10, textTransform: "uppercase", letterSpacing: 0.4 }}>{label}</span>
                    </div>
                    <div style={{ fontSize: 9, color: "rgba(255,255,255,0.4)", marginTop: 3 }}>{card.window} window</div>
                  </div>
                </div>

                <div style={{ fontSize: 17, fontWeight: 500, color: "#fff", marginBottom: 2 }}>{card.title}</div>
                <div style={{ fontSize: 12, color: "rgba(255,255,255,0.4)", marginBottom: 12 }}>{card.company} · {card.location}</div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, marginBottom: 12 }}>
                  {card.stats.map((s, si) => (
                    <div key={si} style={{ background: "rgba(0,0,0,0.25)", borderRadius: 8, padding: 8, textAlign: "center" }}>
                      <div style={{ fontSize: 13, fontWeight: 500, color: c.light, lineHeight: 1 }}>{s.v}</div>
                      <div style={{ fontSize: 8, color: "rgba(255,255,255,0.3)", textTransform: "uppercase", letterSpacing: 0.3, marginTop: 3 }}>{s.l}</div>
                    </div>
                  ))}
                </div>

                <div style={{ height: 0.5, background: "rgba(255,255,255,0.08)", margin: "0 0 12px 0" }} />
                <div style={{ fontSize: 11, fontStyle: "italic", color: "rgba(255,255,255,0.5)", lineHeight: 1.5, marginBottom: 12, flex: 1 }}>"{card.intel}"</div>

                <div style={{ display: "flex", gap: 6 }}>
                  <button onClick={() => handleApply(card.company, card.title)} style={{ flex: 1, background: "#4d8ef5", color: "#fff", border: "none", borderRadius: 8, padding: "8px 10px", fontSize: 10, fontWeight: 600, cursor: "pointer" }}>Generate pack</button>
                  <button
                    onClick={() => setWayInTarget(wayInTarget?.company === card.company ? null : { company: card.company, role: card.title })}
                    style={{
                      background: wayInTarget?.company === card.company ? "#4d8ef5" : "rgba(255,255,255,0.04)",
                      color: wayInTarget?.company === card.company ? "#fff" : "rgba(255,255,255,0.55)",
                      border: "0.5px solid rgba(255,255,255,0.08)",
                      borderRadius: 8,
                      padding: "8px 12px",
                      fontSize: 10,
                      fontWeight: 500,
                      cursor: "pointer",
                    }}
                  >
                    Way in
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Way In panel for the selected prediction */}
        {wayInTarget && (
          <div style={{ marginTop: 16 }}>
            <FindWayInPanel
              company={wayInTarget.company}
              role={wayInTarget.role}
              headers={getAuthHeaders(false)}
              alwaysOpen={true}
            />
          </div>
        )}
      </div>

      {/* ═══ RIGHT: Bloomberg feed ═══ */}
      <div style={{ background: "rgba(255,255,255,0.025)", border: "0.5px solid rgba(255,255,255,0.06)", borderRadius: 14, overflow: "hidden", height: "fit-content", position: "sticky", top: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 14px", borderBottom: "0.5px solid rgba(255,255,255,0.06)" }}>
          <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.7, color: "rgba(255,255,255,0.55)", fontWeight: 600 }}>Market intelligence</div>
        </div>
        {realCards.length > 0 ? (
          <div style={{ position: "relative", height: 520, overflow: "hidden" }}>
            <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 28, background: "linear-gradient(to bottom, rgba(3,4,15,1), transparent)", zIndex: 2, pointerEvents: "none" }} />
            <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 28, background: "linear-gradient(to top, rgba(3,4,15,1), transparent)", zIndex: 2, pointerEvents: "none" }} />
            <div className="feed-track" style={{ animation: "feedScroll 28s linear infinite" }}>
              {[...realCards, ...realCards].map((card, i) => {
                const c = PRED_COLORS[card.status];
                const label = PRED_LABELS[card.status];
                return (
                  <div key={i} style={{ padding: "11px 14px", borderBottom: "0.5px solid rgba(255,255,255,0.04)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: c.light, letterSpacing: 0.3 }}>{card.company}</span>
                    </div>
                    <div style={{ fontSize: 11, color: "rgba(255,255,255,0.6)", lineHeight: 1.45, marginBottom: 6 }}>{card.intel.slice(0, 80)}...</div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontSize: 9, color: c.light, background: `${c.main}22`, padding: "2px 6px", borderRadius: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.3 }}>{label}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div style={{ padding: "32px 16px", textAlign: "center" }}>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,0.3)", marginBottom: 8 }}>No market intelligence yet</div>
            <div style={{ fontSize: 11, color: "rgba(255,255,255,0.15)" }}>Intelligence feed activates once signals are detected</div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   SIGNALS TAB — Hiring signals with live ticker + cards + side panel
   ═══════════════════════════════════════════════════════════════ */

type SignalType = "fundraise" | "departure" | "expansion" | "other";

const SIGNAL_COLORS: Record<SignalType, { main: string; light: string; bg: string; border: string; band: string; snippetBorder: string; snippetBg: string; aiBg: string }> = {
  fundraise: { main: "#4d8ef5", light: "#93c5fd", bg: "linear-gradient(160deg, #0a1a3a, #060e22)", border: "1px solid rgba(77,142,245,0.3)", band: "linear-gradient(90deg, #1e3a8a, #4d8ef5, #1e3a8a)", snippetBorder: "rgba(77,142,245,0.3)", snippetBg: "rgba(77,142,245,0.06)", aiBg: "rgba(77,142,245,0.05)" },
  departure: { main: "#ef4444", light: "#fca5a5", bg: "linear-gradient(160deg, #2e0606, #180303)", border: "1px solid rgba(239,68,68,0.28)", band: "linear-gradient(90deg, #7f1d1d, #ef4444, #7f1d1d)", snippetBorder: "rgba(239,68,68,0.3)", snippetBg: "rgba(239,68,68,0.06)", aiBg: "rgba(239,68,68,0.05)" },
  expansion: { main: "#22c55e", light: "#86efac", bg: "linear-gradient(160deg, #042e12, #021808)", border: "1px solid rgba(34,197,94,0.25)", band: "linear-gradient(90deg, #166534, #22c55e, #166534)", snippetBorder: "rgba(34,197,94,0.3)", snippetBg: "rgba(34,197,94,0.06)", aiBg: "rgba(34,197,94,0.05)" },
  other: { main: "#a78bfa", light: "#c4b5fd", bg: "linear-gradient(160deg, #140838, #0a0420)", border: "1px solid rgba(167,139,250,0.25)", band: "linear-gradient(90deg, #5b3a8e, #a78bfa, #5b3a8e)", snippetBorder: "rgba(167,139,250,0.3)", snippetBg: "rgba(167,139,250,0.06)", aiBg: "rgba(167,139,250,0.05)" },
};

interface SignalCard {
  type: SignalType;
  initials: string;
  company: string;
  typeLabel: string;
  time: string;
  score: number;
  headline: string;
  snippet: string;
  sourceInitials: string;
  sourceName: string;
  url: string;
  ai: string;
  tags: string[];
  primaryLabel: string;
}

function SignalsTab({ signals = [] }: { signals?: import("@/lib/api").HiddenSignal[] }) {
  const router = useRouter();
  const [filter, setFilter] = useState("All");
  const [wayInCard, setWayInCard] = useState<string | null>(null);

  const SIGNAL_TYPE_MAP: Record<string, SignalType> = {
    funding: "fundraise",
    hiring_surge: "other",
    leadership: "departure",
    expansion: "expansion",
    product_launch: "other",
    velocity: "other",
    distress: "other",
    pain_signal: "other",
    structural: "other",
    market_signal: "other",
    ma_activity: "fundraise",
    board_change: "departure",
  };

  // timeAgo imported from @/lib/utils at module level

  // Map real signals to card format — defensive against any missing/null fields
  const cards: SignalCard[] = (signals || []).filter(s => s && s.company_name).map((s) => {
    const signalType = SIGNAL_TYPE_MAP[s.signal_type] || "other";
    const companyName = s.company_name || "Unknown";
    const sourceName = s.source_name && s.source_name.length > 0 ? s.source_name : "Web";
    const rawConfidence = typeof s.confidence === "number" ? s.confidence : 0;
    // Handle confidence expressed as 0-1 or 0-100
    const confidencePct = rawConfidence <= 1 ? Math.round(rawConfidence * 100) : Math.round(rawConfidence);
    const initials = makeInitials(companyName) || "??";
    const signalTypeLabel = s.signal_type ? s.signal_type.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase()) : "Signal";
    return {
      type: signalType,
      initials,
      company: companyName,
      typeLabel: signalTypeLabel,
      time: s.created_at ? timeAgo(s.created_at) : "",
      score: confidencePct,
      headline: `${companyName} — ${(s.likely_roles && s.likely_roles[0]) || signalTypeLabel.toLowerCase() || "signal detected"}`,
      snippet: s.reasoning || "Signal detected from market activity.",
      sourceInitials: sourceName.charAt(0).toUpperCase() || "W",
      sourceName,
      url: s.source_url || "",
      ai: s.reasoning || "Signal detected — analysing hiring implications.",
      tags: [signalTypeLabel.toLowerCase(), ...((s.likely_roles || []).slice(0, 2))],
      primaryLabel: confidencePct >= 70 ? "Apply" : confidencePct >= 50 ? "Scout" : "Watch",
    };
  });

  const filterChips = [
    { key: "All", color: "#4d8ef5" },
    { key: "Fundraise", color: "#4d8ef5" },
    { key: "Departure", color: "#ef4444" },
    { key: "Expansion", color: "#22c55e" },
    { key: "Other", color: "#a78bfa" },
  ];

  const visibleCards = cards.filter((c) => {
    if (filter === "All") return true;
    if (filter === "Fundraise") return c.type === "fundraise";
    if (filter === "Departure") return c.type === "departure";
    if (filter === "Expansion") return c.type === "expansion";
    if (filter === "Other") return c.type === "other";
    return true;
  });

  // Dynamic breakdown from real signals
  const typeCounts: Record<string, number> = {};
  for (const c of cards) {
    typeCounts[c.type] = (typeCounts[c.type] || 0) + 1;
  }
  const total = cards.length || 1;
  const breakdown = [
    { key: "Fundraise", icon: "$", color: "#4d8ef5", pct: Math.round((typeCounts["fundraise"] || 0) / total * 100), count: typeCounts["fundraise"] || 0 },
    { key: "Departure", icon: "\u2197", color: "#ef4444", pct: Math.round((typeCounts["departure"] || 0) / total * 100), count: typeCounts["departure"] || 0 },
    { key: "Expansion", icon: "\u2192", color: "#22c55e", pct: Math.round((typeCounts["expansion"] || 0) / total * 100), count: typeCounts["expansion"] || 0 },
    { key: "Other", icon: "\u25C8", color: "#a78bfa", pct: Math.round((typeCounts["other"] || 0) / total * 100), count: typeCounts["other"] || 0 },
  ].filter(b => b.count > 0);

  // Hottest = top 6 by score
  const hottest = cards.slice(0, 6).map((c) => ({
    initials: c.initials,
    company: c.company,
    desc: c.tags.slice(0, 2).join(" \u00b7 "),
    score: c.score,
    type: c.type,
  }));

  if (cards.length === 0) {
    return (
      <div style={{ padding: "48px 24px", textAlign: "center" }}>
        <div style={{ fontSize: 16, color: "rgba(255,255,255,0.4)", marginBottom: 12 }}>No hiring signals detected yet</div>
        <div style={{ fontSize: 13, color: "rgba(255,255,255,0.2)", marginBottom: 24, maxWidth: 420, margin: "0 auto 24px" }}>
          Signals are generated by scanning news sources, job boards, and market data. Connect your email and import LinkedIn connections to start detecting signals.
        </div>
        <a href="/profile" style={{ background: "#4d8ef5", color: "#fff", borderRadius: 10, padding: "10px 20px", fontSize: 13, fontWeight: 600, textDecoration: "none" }}>Set up your profile \u2192</a>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "calc(100vh - 200px)" }}>
      <style jsx>{`
        @keyframes signalsTickerScroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }
        @keyframes signalsSlideUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes signalsPulse { 0%, 100% { opacity: 0.3; transform: scale(1); } 50% { opacity: 1; transform: scale(1.3); } }
        @keyframes signalsBarFill { from { width: 0; } to { width: var(--w); } }
        @keyframes signalsGlow { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }
      `}</style>

      {/* \u2550\u2550\u2550 LIVE TICKER \u2550\u2550\u2550 */}
      <div style={{ background: "rgba(77,142,245,0.05)", borderBottom: "0.5px solid rgba(77,142,245,0.1)", padding: "7px 0", overflow: "hidden", position: "relative" }}>
        <div style={{ display: "inline-flex", animation: "signalsTickerScroll 40s linear infinite", whiteSpace: "nowrap" }}>
          {[...cards.slice(0, 6), ...cards.slice(0, 6), ...cards.slice(0, 6)].map((it, i) => {
            const c = SIGNAL_COLORS[it.type];
            return (
              <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 11, color: "rgba(255,255,255,0.55)", marginRight: 24 }}>
                <span style={{ width: 4, height: 4, borderRadius: "50%", background: c.main }} />
                <strong style={{ color: c.light, fontWeight: 600 }}>{it.company}</strong>
                <span>{it.headline.split(" \u2014 ")[1] || it.typeLabel}</span>
                <span style={{ color: "rgba(255,255,255,0.3)" }}>\u00b7 {it.sourceName}</span>
                <span style={{ color: "rgba(255,255,255,0.2)" }}>\u00b7 {it.time}</span>
              </span>
            );
          })}
        </div>
      </div>

      {/* \u2550\u2550\u2550 HEADER \u2550\u2550\u2550 */}
      <div style={{ padding: "13px 24px", borderBottom: "0.5px solid rgba(255,255,255,0.05)", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <h2 style={{ fontSize: 20, fontWeight: 500, color: "#fff", margin: 0 }}>Hiring Signals</h2>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "rgba(34,197,94,0.08)", border: "0.5px solid rgba(34,197,94,0.2)", padding: "3px 10px", borderRadius: 12, fontSize: 10, color: "#86efac" }}>
            <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#22c55e", animation: "signalsPulse 1.5s ease-in-out infinite" }} />
            {cards.length} signals
          </span>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {filterChips.map((c) => {
            const active = filter === c.key;
            return (
              <button key={c.key} onClick={() => setFilter(c.key)} style={{
                fontSize: 10, padding: "5px 11px", borderRadius: 12, cursor: "pointer", fontWeight: 500,
                background: active ? `${c.color}26` : "rgba(255,255,255,0.03)",
                color: active ? c.color : "rgba(255,255,255,0.4)",
                border: `0.5px solid ${active ? `${c.color}59` : "rgba(255,255,255,0.06)"}`,
              }}>{c.key}</button>
            );
          })}
        </div>
      </div>


      {/* ═══ MAIN SPLIT ═══ */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 290px", flex: 1, minHeight: 0 }}>
        {/* LEFT — Cards grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, padding: "14px 18px", overflowY: "auto", alignContent: "start" }}>
          {visibleCards.map((card, i) => {
            const c = SIGNAL_COLORS[card.type];
            return (
              <div key={i} style={{
                borderRadius: 16, overflow: "hidden", cursor: "pointer", transition: "transform 0.15s",
                background: c.bg, border: c.border,
                animation: `signalsSlideUp 0.35s ease ${i * 0.04}s both`,
                display: "flex", flexDirection: "column",
              }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.transform = "translateY(-2px)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.transform = "translateY(0)"; }}
              >
                {/* Top band */}
                <div style={{ height: 3, background: c.band }} />

                {/* Body */}
                <div style={{ padding: 14, display: "flex", flexDirection: "column", flex: 1 }}>
                  {/* Top row */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 9, minWidth: 0, flex: 1 }}>
                      <div style={{ width: 32, height: 32, borderRadius: 9, background: `${c.main}2e`, color: c.light, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, flexShrink: 0 }}>
                        {card.initials}
                      </div>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "#fff" }}>{card.company}</div>
                        <div style={{ fontSize: 9, color: c.light, fontWeight: 500 }}>{card.typeLabel} · {card.time}</div>
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
                      <span style={{ fontSize: 20, fontWeight: 500, color: c.main }}>{card.score}</span>
                      <span style={{ fontSize: 9, color: "rgba(255,255,255,0.25)", marginTop: 2 }}>%</span>
                    </div>
                  </div>

                  {/* Headline */}
                  <div style={{ fontSize: 12, fontWeight: 500, color: "rgba(255,255,255,0.8)", marginBottom: 8, lineHeight: 1.4 }}>{card.headline}</div>

                  {/* Source */}
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                    <div style={{ width: 14, height: 14, borderRadius: 3, background: "rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.5)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 6, fontWeight: 700 }}>{card.sourceInitials}</div>
                    <span style={{ fontSize: 9, color: "rgba(255,255,255,0.4)" }}>{card.sourceName}</span>
                    {card.url && <a href={card.url.startsWith("http") ? card.url : `https://${card.url}`} target="_blank" rel="noopener" style={{ fontSize: 9, color: "#4d8ef5", textDecoration: "none" }}>Source →</a>}
                  </div>

                  {/* AI interpretation */}
                  <div style={{ fontSize: 10, color: "rgba(255,255,255,0.55)", lineHeight: 1.6, padding: "8px 11px", borderRadius: 8, background: c.aiBg, marginBottom: 10, display: "flex", gap: 8, alignItems: "flex-start" }}>
                    <span style={{ width: 5, height: 5, borderRadius: "50%", background: c.main, marginTop: 5, flexShrink: 0, animation: "signalsGlow 2s ease-in-out infinite" }} />
                    <span>{card.ai}</span>
                  </div>

                  {/* Footer */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "auto", gap: 8 }}>
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      {card.tags.map((t, ti) => (
                        <span key={ti} style={{ fontSize: 8, padding: "2px 6px", borderRadius: 5, background: "rgba(255,255,255,0.05)", color: "rgba(255,255,255,0.4)" }}>{t}</span>
                      ))}
                    </div>
                    <div style={{ display: "flex", gap: 5 }}>
                      <button
                        onClick={async () => {
                          try {
                            const app = await createAppAndPack(card.company, roleFromHeadline(card.headline), card.url || null, "");
                            if (app?.id) router.push(`/applications/${app.id}/package`);
                            else router.push("/applications");
                          } catch (err: any) {
                            const msg = err?.message || "Failed to start pack generation";
                            if (msg.startsWith("NO_CV:")) alert(msg.replace("NO_CV: ", ""));
                            else alert(msg);
                          }
                        }}
                        style={{ background: c.main, color: "#fff", border: "none", borderRadius: 8, padding: "5px 11px", fontSize: 10, fontWeight: 600, cursor: "pointer" }}
                      >
                        Generate pack
                      </button>
                      <button onClick={() => setWayInCard(wayInCard === card.company ? null : card.company)} style={{ background: wayInCard === card.company ? "#4d8ef5" : "rgba(255,255,255,0.04)", color: wayInCard === card.company ? "#fff" : "rgba(255,255,255,0.55)", border: "0.5px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "5px 11px", fontSize: 10, fontWeight: 500, cursor: "pointer" }}>Way in</button>
                    </div>
                  </div>
                  {wayInCard === card.company && (
                    <div style={{ marginTop: 10 }}>
                      <FindWayInPanel company={card.company} role={roleFromHeadline(card.headline)} headers={getAuthHeaders(false)} />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* RIGHT — Side panel */}
        <div style={{ borderLeft: "0.5px solid rgba(255,255,255,0.05)", padding: 16, overflowY: "auto", display: "flex", flexDirection: "column", gap: 18 }}>
          {/* Signal breakdown */}
          <div>
            <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.6, color: "rgba(255,255,255,0.25)", fontWeight: 600, marginBottom: 10 }}>Signal breakdown</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {breakdown.map((b, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ width: 26, height: 26, borderRadius: 7, background: `${b.color}22`, color: b.color, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700, flexShrink: 0 }}>{b.icon}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 10, color: "rgba(255,255,255,0.55)", marginBottom: 4 }}>{b.key}</div>
                    <div style={{ height: 3, background: "rgba(255,255,255,0.06)", borderRadius: 2, overflow: "hidden" }}>
                      <div style={{ height: "100%", background: b.color, borderRadius: 2, width: b.pct + "%", animation: `signalsBarFill 1s ease ${0.2 + i * 0.1}s both`, "--w": b.pct + "%" } as any} />
                    </div>
                  </div>
                  <span style={{ fontSize: 12, fontWeight: 500, color: b.color, minWidth: 18, textAlign: "right" }}>{b.count}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Hottest right now */}
          {hottest.length > 0 && (
          <div>
            <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.6, color: "rgba(255,255,255,0.25)", fontWeight: 600, marginBottom: 10 }}>Hottest right now</div>
            <div>
              {hottest.map((h, i) => {
                const c = SIGNAL_COLORS[h.type];
                return (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 9, padding: "8px 0", borderBottom: i < hottest.length - 1 ? "0.5px solid rgba(255,255,255,0.04)" : "none" }}>
                    <div style={{ width: 28, height: 28, borderRadius: 7, background: `${c.main}22`, color: c.light, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700, flexShrink: 0 }}>{h.initials}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.65)" }}>{h.company}</div>
                      <div style={{ fontSize: 9, color: "rgba(255,255,255,0.3)" }}>{h.desc}</div>
                    </div>
                    <span style={{ fontSize: 12, fontWeight: 500, color: c.main }}>{h.score}</span>
                  </div>
                );
              })}
            </div>
          </div>
          )}
        </div>
      </div>
    </div>
  );
}

function FreelanceTab() {
  return (
    <div style={{ padding: "48px 24px", textAlign: "center" }}>
      <div style={{ fontSize: 16, color: "rgba(255,255,255,0.4)", marginBottom: 12 }}>No freelance opportunities yet</div>
      <div style={{ fontSize: 13, color: "rgba(255,255,255,0.2)", marginBottom: 24, maxWidth: 420, margin: "0 auto 24px" }}>
        Freelance and interim executive projects will appear here as they are detected. Set up your profile to start matching.
      </div>
      <a href="/profile" style={{ background: "#4d8ef5", color: "#fff", borderRadius: 10, padding: "10px 20px", fontSize: 13, fontWeight: 600, textDecoration: "none" }}>Set up profile →</a>
    </div>
  );
}

function IntelligenceTab({
  predictions = [],
  signals = [],
  onAddPack,
}: {
  predictions?: any[];
  signals?: any[];
  onAddPack: (company: string, role: string, url: string | null, description: string) => Promise<any>;
}) {
  const router = useRouter();
  const [wayInTarget, setWayInTarget] = useState<{ company: string; role: string } | null>(null);
  const [view, setView] = useState<"all" | "predictions" | "signals">("all");

  const predictionItems = (predictions || []).slice(0, 12).map((p: any) => ({
    kind: "prediction" as const,
    company: p.company || "Unknown Company",
    role: p.predicted_role || "Predicted Role",
    confidence: Math.max(0, Math.min(100, Number(p.confidence || 0))),
    timeline: p.timeline || "TBD",
    summary: p.reasoning || p.trigger_event || "Predicted opportunity from market signals.",
    sourceUrl: p.source_url || null,
  }));

  const signalItems = (signals || []).slice(0, 12).map((s: any) => ({
    kind: "signal" as const,
    company: s.company_name || "Unknown Company",
    role: (Array.isArray(s.likely_roles) && s.likely_roles[0]) || "Potential Role",
    confidence: (() => {
      const raw = Number(s.confidence || 0);
      return raw <= 1 ? Math.round(raw * 100) : Math.round(raw);
    })(),
    timeline: s.signal_type ? String(s.signal_type).replace(/_/g, " ") : "market signal",
    summary: s.reasoning || "Hiring signal detected.",
    sourceUrl: s.source_url || null,
  }));

  const mergedAll = [...predictionItems, ...signalItems]
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 20);

  const merged = mergedAll.filter((item) => {
    if (view === "all") return true;
    if (view === "predictions") return item.kind === "prediction";
    if (view === "signals") return item.kind === "signal";
    return true;
  });

  async function handleGenerate(company: string, role: string, url: string | null) {
    try {
      const app = await onAddPack(company, role, url, "");
      if (app?.id) router.push(`/applications/${app.id}/package`);
      else router.push("/applications");
    } catch (err: any) {
      const msg = err?.message || "Failed to start pack generation";
      if (msg.startsWith("NO_CV:")) alert(msg.replace("NO_CV: ", ""));
      else alert(msg);
    }
  }

  if (!merged.length) {
    return (
      <div style={{ padding: "48px 24px", textAlign: "center" }}>
        <div style={{ fontSize: 16, color: "rgba(255,255,255,0.4)", marginBottom: 10 }}>No intelligence items yet</div>
        <div style={{ fontSize: 13, color: "rgba(255,255,255,0.25)" }}>
          Run scout to populate future openings and hiring signals.
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: "16px 8px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
        <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.7, color: "rgba(255,255,255,0.35)" }}>
          Combined feed — future openings + hiring signals
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            onClick={() => setView("all")}
            style={{
              fontSize: 10,
              padding: "4px 10px",
              borderRadius: 10,
              cursor: "pointer",
              border: view === "all" ? "1px solid rgba(77,142,245,0.5)" : "1px solid rgba(255,255,255,0.12)",
              background: view === "all" ? "rgba(77,142,245,0.15)" : "rgba(255,255,255,0.03)",
              color: view === "all" ? "#93c5fd" : "rgba(255,255,255,0.6)",
            }}
          >
            All
          </button>
          <button
            onClick={() => setView("predictions")}
            style={{
              fontSize: 10,
              padding: "4px 10px",
              borderRadius: 10,
              cursor: "pointer",
              border: view === "predictions" ? "1px solid rgba(77,142,245,0.5)" : "1px solid rgba(255,255,255,0.12)",
              background: view === "predictions" ? "rgba(77,142,245,0.15)" : "rgba(255,255,255,0.03)",
              color: view === "predictions" ? "#93c5fd" : "rgba(255,255,255,0.6)",
            }}
          >
            Predictions
          </button>
          <button
            onClick={() => setView("signals")}
            style={{
              fontSize: 10,
              padding: "4px 10px",
              borderRadius: 10,
              cursor: "pointer",
              border: view === "signals" ? "1px solid rgba(34,197,94,0.45)" : "1px solid rgba(255,255,255,0.12)",
              background: view === "signals" ? "rgba(34,197,94,0.15)" : "rgba(255,255,255,0.03)",
              color: view === "signals" ? "#86efac" : "rgba(255,255,255,0.6)",
            }}
          >
            Signals
          </button>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 10 }}>
        {merged.map((item, i) => (
          <div key={`${item.kind}-${item.company}-${i}`} style={{
            background: "rgba(255,255,255,0.03)",
            border: "0.5px solid rgba(255,255,255,0.08)",
            borderRadius: 14,
            padding: 16,
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: "#fff", lineHeight: 1.3 }}>{item.role}</div>
                <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", marginTop: 3 }}>{item.company}</div>
              </div>
              <div style={{ fontSize: 26, fontWeight: 600, color: "#4d8ef5", lineHeight: 1 }}>
                {item.confidence}<span style={{ fontSize: 11, opacity: 0.6 }}>%</span>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontSize: 10, padding: "3px 8px", borderRadius: 10, background: item.kind === "prediction" ? "rgba(77,142,245,0.15)" : "rgba(34,197,94,0.15)", color: item.kind === "prediction" ? "#93c5fd" : "#86efac", textTransform: "uppercase" }}>
                {item.kind}
              </span>
              <span style={{ fontSize: 10, padding: "3px 8px", borderRadius: 10, background: "rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.6)" }}>
                {item.timeline}
              </span>
            </div>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,0.55)", lineHeight: 1.5 }}>{item.summary}</div>
            <div style={{ display: "flex", gap: 6, marginTop: "auto" }}>
              <button
                onClick={() => handleGenerate(item.company, item.role, item.sourceUrl)}
                style={{ flex: 1, background: "#4d8ef5", color: "#fff", border: "none", borderRadius: 10, padding: "8px 10px", fontSize: 11, fontWeight: 600, cursor: "pointer" }}
              >
                Generate pack
              </button>
              <button
                onClick={() => setWayInTarget(wayInTarget?.company === item.company ? null : { company: item.company, role: item.role })}
                style={{ background: wayInTarget?.company === item.company ? "#4d8ef5" : "rgba(255,255,255,0.04)", color: wayInTarget?.company === item.company ? "#fff" : "rgba(255,255,255,0.65)", border: "0.5px solid rgba(255,255,255,0.1)", borderRadius: 10, padding: "8px 12px", fontSize: 11, fontWeight: 500, cursor: "pointer" }}
              >
                Way in
              </button>
              {item.sourceUrl && (
                <a href={item.sourceUrl} target="_blank" rel="noopener" style={{ background: "rgba(255,255,255,0.04)", color: "rgba(255,255,255,0.65)", border: "0.5px solid rgba(255,255,255,0.1)", borderRadius: 10, padding: "8px 12px", fontSize: 11, fontWeight: 500, textDecoration: "none" }}>
                  Source →
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
      {wayInTarget && (
        <div style={{ marginTop: 16 }}>
          <FindWayInPanel company={wayInTarget.company} role={wayInTarget.role} headers={getAuthHeaders(false)} />
        </div>
      )}
    </div>
  );
}
