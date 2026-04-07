// @ts-nocheck
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getHiddenMarket, type HiddenSignal } from "@/lib/api";
import MarketSignals from "@/components/market-signals";

const TRIGGER_COLORS = {
  funding: "bg-green-50 text-green-700",
  regulatory: "bg-red-50 text-red-700",
  expansion: "bg-blue-50 text-blue-700",
  competitive: "bg-amber-50 text-amber-700",
  lifecycle: "bg-purple-50 text-purple-700",
  industry_shift: "bg-cyan-50 text-cyan-700",
  ma_activity: "bg-orange-50 text-orange-700",
};

async function addAndGeneratePack(company: string, role: string, url: string | null, description: string) {
  const tk = localStorage.getItem("sr_token");
  const hdrs = tk ? { Authorization: `Bearer ${tk}` } : {};

  // 1. Get latest CV first
  const cvsRes = await fetch("/api/v1/cvs", { headers: hdrs });
  const cvs = cvsRes.ok ? await cvsRes.json() : [];
  const cv = Array.isArray(cvs) ? cvs.find((c: any) => c.status === "parsed") : null;

  // 2. Create job run (pack) first so we have the ID
  let jobRunId: string | null = null;
  if (cv) {
    const jdText = `Role: ${role}\nCompany: ${company}\n\n${description || `${role} position at ${company}`}${url ? `\n\nSource: ${url}` : ""}`;
    const jobRes = await fetch("/api/v1/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...hdrs },
      body: JSON.stringify({
        cv_id: cv.id,
        jd_text: jdText,
        preferences: { tone: "professional", region: "MENA" },
      }),
    });
    if (jobRes.ok) {
      const job = await jobRes.json();
      jobRunId = job.id;
    }
  }

  // 3. Create application WITH job_run_id already linked
  const appRes = await fetch("/api/v1/applications", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...hdrs },
    body: JSON.stringify({
      company, role,
      date_applied: new Date().toISOString(),
      source_channel: "job_board",
      stage: "watching",
      url: url || undefined,
      job_run_id: jobRunId || undefined,
    }),
  });
  if (!appRes.ok) throw new Error("Failed to create application");
  return await appRes.json();
}

function FindWayInPanel({ company, role, headers }: { company: string; role: string; headers: Record<string, string> }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [open, setOpen] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

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
      if (res.ok) setResult(await res.json());
    } catch {}
    setLoading(false);
  }

  function copyMessage(msg: string, idx: number) {
    navigator.clipboard.writeText(msg).then(() => {
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 2000);
    });
  }

  const { direct_contacts = [], visited_targets = [], best_path, backup_paths = [], recommended_action, discover_targets = [] } = result || {};

  return (
    <>
      <button onClick={() => findPath(false)} className="px-3 py-1.5 border border-white/10 text-[#8B92B0] text-[12px] font-semibold rounded-lg hover:bg-white/[0.04] transition-colors">
        {loading ? "Mapping connections..." : "Find My Way In"}
      </button>
      {open && !loading && result && (
        <div className="mt-3 space-y-2 animate-in fade-in slide-in-from-top-2 duration-300">
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

          {/* Best path */}
          {best_path && (
            <div className="rounded-lg p-3 border border-emerald-500/20" style={{ background: "rgba(52,211,153,0.06)" }}>
              <div className="text-[10px] font-medium text-emerald-400 uppercase mb-2">Best Way In</div>
              {/* Connection chain */}
              <div className="flex items-center gap-1.5 flex-wrap mb-2">
                <span className="text-[11px] px-2 py-0.5 rounded bg-[#4d8ef5]/20 text-[#4d8ef5] font-medium">You</span>
                {best_path.connector && (
                  <>
                    <span className="text-[#555C7A] text-[10px]">→</span>
                    <span className="text-[11px] px-2 py-0.5 rounded bg-white/[0.08] text-[#c4c9e0] font-medium">{best_path.connector.name}</span>
                  </>
                )}
                {best_path.target && (
                  <>
                    <span className="text-[#555C7A] text-[10px]">→</span>
                    <span className="text-[11px] px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 font-medium">{best_path.target.name || best_path.target.title}</span>
                  </>
                )}
              </div>
              {best_path.connector && (
                <div className="text-[12px] text-[#8B92B0] mb-1">
                  <span className="text-white font-medium">{best_path.connector.name}</span> — {best_path.connector.title} at {best_path.connector.company}
                </div>
              )}
              {best_path.target?.why_target && (
                <div className="text-[11px] text-emerald-400">{best_path.target.why_target}</div>
              )}
              {best_path.reason && <div className="text-[11px] text-[#8B92B0] mt-1">{best_path.reason}</div>}
              {best_path.action && (
                <div className="text-[11px] font-semibold text-emerald-400 mt-2 p-2 rounded bg-emerald-500/10">{best_path.action}</div>
              )}
              {best_path.strength && (
                <span className={`inline-block mt-2 text-[10px] font-medium px-2 py-0.5 rounded-full ${best_path.strength === "strong" ? "bg-emerald-500/20 text-emerald-400" : best_path.strength === "medium" ? "bg-amber-500/20 text-amber-400" : "bg-white/10 text-[#8B92B0]"}`}>
                  {best_path.strength} path
                </span>
              )}
            </div>
          )}

          {/* Alternative paths */}
          {backup_paths.length > 0 && (
            <div className="rounded-lg p-3 border border-amber-500/20" style={{ background: "rgba(245,158,11,0.06)" }}>
              <div className="text-[10px] font-medium text-amber-400 uppercase mb-2">Alternative Paths</div>
              <div className="space-y-2">
                {backup_paths.map((p: any, i: number) => (
                  <div key={i} className="rounded-lg p-2.5 bg-white/[0.04]">
                    <div className="flex items-center gap-1.5 flex-wrap mb-1">
                      {p.path?.split(" → ").map((node: string, ni: number, arr: string[]) => (
                        <span key={ni} className="contents">
                          <span className={`text-[11px] px-2 py-0.5 rounded font-medium ${ni === 0 ? "bg-[#4d8ef5]/20 text-[#4d8ef5]" : "bg-white/[0.08] text-[#c4c9e0]"}`}>{node}</span>
                          {ni < arr.length - 1 && <span className="text-[#555C7A] text-[10px]">→</span>}
                        </span>
                      ))}
                    </div>
                    <div className="text-[11px] text-[#8B92B0]">{p.reason}</div>
                    <div className="text-[11px] font-semibold text-amber-400 mt-1">{p.action}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Direct contacts — with angle + message */}
          {direct_contacts.length > 0 && (
            <div className="rounded-lg p-3 border border-[#4d8ef5]/20" style={{ background: "rgba(77,142,245,0.06)" }}>
              <div className="text-[10px] font-medium text-[#4d8ef5] uppercase mb-2">
                People to Tap Into at {company} ({result.total_direct})
              </div>
              <div className="space-y-3">
                {direct_contacts.map((c: any, i: number) => (
                  <div key={i} className="rounded-lg p-2.5 bg-white/[0.04]">
                    <div className="flex items-center gap-2.5 mb-1.5">
                      <div className="w-8 h-8 rounded-full bg-[#4d8ef5]/15 text-[#4d8ef5] flex items-center justify-center text-[12px] font-bold shrink-0">
                        {c.name?.[0]?.toUpperCase() || "?"}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[12px] font-medium text-white">{c.name}</span>
                          {c.is_recruiter && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-medium">Recruiter</span>}
                          {c.is_hiring_manager && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[#4d8ef5]/20 text-[#4d8ef5] font-medium">Decision Maker</span>}
                        </div>
                        <div className="text-[11px] text-[#6B7194]">{c.title}</div>
                      </div>
                      {c.linkedin_url && (
                        <a href={c.linkedin_url} target="_blank" rel="noopener" className="text-[11px] text-[#7F8CFF] hover:text-white font-medium shrink-0">
                          LinkedIn →
                        </a>
                      )}
                    </div>
                    {/* Angle to leverage */}
                    {c.intro_angle && (
                      <div className="text-[11px] text-emerald-400 mb-1.5 pl-[42px]">
                        {c.intro_angle}
                      </div>
                    )}
                    {/* Pre-written intro message */}
                    {c.message && (
                      <div className="pl-[42px]">
                        <div className="text-[11px] text-[#8B92B0] p-2 rounded bg-white/[0.03] border border-white/[0.05] leading-relaxed">
                          {c.message}
                        </div>
                        <button
                          onClick={() => copyMessage(c.message, i)}
                          className="mt-1.5 text-[10px] font-medium text-[#7F8CFF] hover:text-white transition-colors"
                        >
                          {copiedIdx === i ? "Copied!" : "Copy intro message"}
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Visited targets — profiles you've researched, cold outreach */}
          {visited_targets.length > 0 && (
            <div className="rounded-lg p-3 border border-amber-500/20" style={{ background: "rgba(245,158,11,0.06)" }}>
              <div className="text-[10px] font-medium text-amber-400 uppercase mb-2">
                People You've Researched at {company} ({result.total_visited})
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
                          <span className="text-[12px] font-medium text-white">{c.name}</span>
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
                      <div className="text-[12px] font-medium text-white">{person.name}</div>
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

          {!best_path && direct_contacts.length === 0 && discover_targets.length === 0 && (
            <div className="rounded-lg p-3 text-center" style={{ background: "rgba(255,255,255,0.04)" }}>
              <div className="text-[12px] text-[#6B7194]">No verified paths found for {company}.</div>
              <div className="text-[11px] text-[#555C7A] mt-1">Search LinkedIn for people at {company} with the StealthRole extension installed, then come back and refresh.</div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

export default function ScoutPage() {
  const router = useRouter();
  const [vacancies, setVacancies] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [signals, setSignals] = useState([]);
  const [freelance, setFreelance] = useState([]);
  const [platformLinks, setPlatformLinks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [tab, setTab] = useState("vacancies");

  const token = typeof window !== "undefined" ? localStorage.getItem("sr_token") : null;
  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  // Load on mount — use sessionStorage cache to avoid re-fetching on navigation
  useEffect(() => {
    try {
      const cached = sessionStorage.getItem("sr_scout_data");
      if (cached) {
        const d = JSON.parse(cached);
        if (d.vacancies?.length) setVacancies(d.vacancies);
        if (d.signals?.length) setSignals(d.signals);
        if (d.predictions?.length) setPredictions(d.predictions);
        if (d.freelance?.length) setFreelance(d.freelance);
        if (d.platformLinks?.length) setPlatformLinks(d.platformLinks);
        return; // Use cache, don't re-fetch
      }
    } catch {}
    setLoading(true);
    Promise.allSettled([
      fetch("/api/v1/scout/vacancies?limit=30", { headers }).then(r => r.ok ? r.json() : {}).then(d => setVacancies(d.vacancies || [])),
      getHiddenMarket().then(r => setSignals(r.signals || [])),
    ]).finally(() => setLoading(false));
  }, []);

  // Cache scout data for navigation persistence
  useEffect(() => {
    if (vacancies.length || signals.length || predictions.length || freelance.length) {
      try {
        sessionStorage.setItem("sr_scout_data", JSON.stringify({ vacancies, signals, predictions, freelance, platformLinks }));
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
    { id: "vacancies", label: "Current Vacancies", count: vacancies.length },
    { id: "predictions", label: "Predicted Opportunities", count: predictions.length },
    { id: "signals", label: "Hiring Signals", count: signals.length },
    { id: "freelance", label: "Freelance", count: freelance.length },
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

      {/* ═══ CURRENT VACANCIES ═══ */}
      {!loading && tab === "vacancies" && (
        <div className="space-y-3">
          {vacancies.length === 0 ? (
            <div className="rounded-xl p-12 text-center text-[#6B7194] text-sm" style={{ background: "rgba(255,255,255,0.04)" }}>
              No vacancies found. Click "Unleash the Scout" to search LinkedIn, Bayt, Indeed, and more.
            </div>
          ) : (
            vacancies.map((job, i) => (
              <div key={i} className="rounded-xl border border-white/[0.08] p-4 hover:border-[#7F8CFF]/30 transition-all" style={{ background: "rgba(255,255,255,0.04)" }}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <a href={job.url} target="_blank" rel="noopener" className="text-sm font-semibold text-white hover:text-[#7F8CFF] transition-colors">{job.role || job.title}</a>
                    {job.company && <div className="text-[12px] text-[#8B92B0] mt-0.5">{job.company}</div>}
                    {job.role && job.title !== job.role && <div className="text-[11px] text-[#555C7A] mt-0.5">{job.title}</div>}
                    <div className="text-[12px] text-[#6B7194] mt-1 line-clamp-2">{job.description}</div>
                    <div className="flex items-center gap-3 mt-3">
                      <button
                        onClick={async (e) => {
                          const btn = e.currentTarget;
                          btn.textContent = "Preparing your pack...";
                          btn.disabled = true;
                          try {
                            await addAndGeneratePack(job.company || "Company", job.role || job.title, job.url, job.description || "");
                            btn.textContent = "Added! Redirecting...";
                            setTimeout(() => router.push("/applications"), 1000);
                          } catch { btn.textContent = "Apply & Prepare Pack"; btn.disabled = false; }
                        }}
                        className="px-3 py-1.5 text-[12px] font-semibold text-white rounded-lg" style={{ background: "linear-gradient(135deg, #5B6CFF, #7F8CFF)" }}
                      >Apply & Prepare Pack</button>
                      <a href={job.url} target="_blank" rel="noopener" className="text-[11px] text-[#6B7194] hover:text-[#7F8CFF]">View listing →</a>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span className="text-[11px] px-2.5 py-1 rounded-full border border-white/10 text-[#8B92B0] font-medium" style={{ background: "rgba(255,255,255,0.06)" }}>
                      {job.source}
                    </span>
                    {job.date && <div className="text-[10px] text-[#555C7A] mt-1">{job.date}</div>}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* ═══ PREDICTED OPPORTUNITIES ═══ */}
      {!loading && tab === "predictions" && (
        <div className="space-y-3">
          {predictions.length === 0 ? (
            <div className="rounded-xl p-12 text-center text-[#6B7194] text-sm" style={{ background: "rgba(255,255,255,0.04)" }}>
              No predictions yet. Click "Unleash the Scout" to analyze market signals.
            </div>
          ) : (
            predictions.map((pred, i) => (
              <div key={i} className="rounded-xl border border-white/[0.08] p-5" style={{ background: "rgba(255,255,255,0.04)" }}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-base font-semibold text-white">{pred.predicted_role}</span>
                      <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${
                        pred.urgency === "imminent" ? "bg-red-500/20 text-red-400" :
                        pred.urgency === "likely" ? "bg-amber-500/20 text-amber-400" :
                        "bg-white/10 text-[#8B92B0]"
                      }`}>{pred.urgency}</span>
                      <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${TRIGGER_COLORS[pred.trigger_type] || "bg-white/10 text-[#8B92B0]"}`}>
                        {pred.trigger_type?.replace(/_/g, " ")}
                      </span>
                    </div>
                    <div className="text-sm text-[#8B92B0] mb-2">
                      {pred.company} · Hiring in <strong className="text-white">{pred.timeline}</strong> · Decision maker: <strong className="text-white">{pred.decision_maker}</strong>
                    </div>
                    <div className="text-[13px] text-[#8B92B0] mb-2">
                      <span className="text-[#6B7194]">Trigger:</span> {pred.trigger_event}
                    </div>
                    <div className="text-[12px] text-[#6B7194] rounded-lg p-2.5 mb-2" style={{ background: "rgba(255,255,255,0.04)" }}>
                      {pred.reasoning}
                    </div>
                    <div className="text-[12px] text-[#7F8CFF] font-medium">
                      → {pred.recommended_action}
                    </div>
                    {pred.source_url && (
                      <a href={pred.source_url} target="_blank" rel="noopener" className="text-[11px] text-[#555C7A] hover:text-[#7F8CFF] mt-1 block truncate">
                        Source: {pred.source_name || "News"} · {pred.published_date || ""}
                      </a>
                    )}
                    <div className="flex gap-2 mt-3 pt-3 border-t border-white/[0.06]">
                      <button onClick={async (e) => {
                        const btn = e.currentTarget;
                        btn.textContent = "Preparing your pack...";
                        btn.disabled = true;
                        try {
                          await addAndGeneratePack(pred.company, pred.predicted_role, pred.source_url, `${pred.trigger_event || ""}\n${pred.reasoning || ""}`);
                          btn.textContent = "Added! Pack generating...";
                          btn.style.background = "#22c55e";
                          btn.style.cursor = "default";
                        } catch { btn.textContent = "Add & Prepare Pack"; btn.disabled = false; }
                      }} className="px-3 py-1.5 text-[12px] font-semibold text-white rounded-lg disabled:opacity-50" style={{ background: "linear-gradient(135deg, #5B6CFF, #7F8CFF)" }}>
                        Add & Prepare Pack
                      </button>
                      <FindWayInPanel company={pred.company} role={pred.predicted_role} headers={headers} />
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className={`text-2xl font-bold ${pred.confidence >= 80 ? "text-emerald-400" : pred.confidence >= 60 ? "text-amber-400" : "text-[#6B7194]"}`}>
                      {pred.confidence}%
                    </div>
                    <div className="text-[11px] text-[#555C7A]">confidence</div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* ═══ HIRING SIGNALS ═══ */}
      {!loading && tab === "signals" && (
        <MarketSignals signals={signals} />
      )}

      {/* ═══ FREELANCE ═══ */}
      {!loading && tab === "freelance" && (
        <div className="space-y-3">
          {freelance.length === 0 ? (
            <div className="rounded-xl p-12 text-center text-[#6B7194] text-sm" style={{ background: "rgba(255,255,255,0.04)" }}>
              No freelance opportunities found. Click "Unleash the Scout" to search.
            </div>
          ) : (
            <>
              {freelance.map((gig, i) => (
                <a key={i} href={gig.url} target="_blank" rel="noopener" className="block rounded-xl border border-white/[0.08] p-4 hover:border-[#7F8CFF]/30 transition-all" style={{ background: "rgba(255,255,255,0.04)" }}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold text-white">{gig.title}</div>
                      <div className="text-[12px] text-[#6B7194] mt-1 line-clamp-2">{gig.description}</div>
                      {gig.date && <div className="text-[11px] text-[#555C7A] mt-1">{gig.date}</div>}
                    </div>
                    <span className="text-[11px] px-2.5 py-1 rounded-full border border-violet-500/20 text-violet-400 font-medium shrink-0" style={{ background: "rgba(127,140,255,0.1)" }}>
                      {gig.source}
                    </span>
                  </div>
                </a>
              ))}
              {platformLinks.length > 0 && (
                <div className="mt-6">
                  <div className="text-[11px] font-medium text-[#555C7A] uppercase mb-3">Browse Freelance Platforms</div>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {platformLinks.map((p, i) => (
                      <a key={i} href={p.url} target="_blank" rel="noopener" className="rounded-xl border border-white/[0.08] p-4 hover:border-[#7F8CFF]/30 transition-all text-center" style={{ background: "rgba(255,255,255,0.04)" }}>
                        <div className="text-sm font-bold text-[#7F8CFF] mb-1">{p.name}</div>
                        <div className="text-[11px] text-[#6B7194]">{p.description}</div>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
