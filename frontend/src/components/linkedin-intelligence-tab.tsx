// @ts-nocheck
"use client";

import { useEffect, useState } from "react";

interface LinkedInStats {
  total_connections: number;
  recruiters: number;
  unique_companies: number;
}

interface Connection {
  full_name: string;
  current_title: string | null;
  current_company: string | null;
  is_recruiter: boolean;
  is_hiring_manager: boolean;
  location: string | null;
}

interface AIInsights {
  network_strength: string;
  top_industries: string[];
  career_leverage: string[];
  blind_spots: string[];
  recommendations: string[];
  warm_intro_potential: string;
}

export default function LinkedInIntelligenceTab() {
  const [stats, setStats] = useState<LinkedInStats | null>(null);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [aiInsights, setAiInsights] = useState<AIInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("sr_token");
    const headers = token ? { Authorization: `Bearer ${token}` } : {};

    // Load cached AI insights from localStorage
    try {
      const cached = localStorage.getItem("sr_linkedin_insights");
      if (cached) setAiInsights(JSON.parse(cached));
    } catch { /* ignore */ }

    Promise.allSettled([
      fetch("/api/v1/linkedin/stats", { headers }).then((r) => r.ok ? r.json() : null),
      fetch("/api/v1/linkedin/connections?limit=2000", { headers }).then((r) => r.ok ? r.json() : null),
    ]).then(([statsRes, connRes]) => {
      if (statsRes.status === "fulfilled" && statsRes.value) setStats(statsRes.value);
      if (connRes.status === "fulfilled" && connRes.value) setConnections(connRes.value.connections || []);
      setLoading(false);
    });
  }, []);

  async function runAIAnalysis() {
    setAnalyzing(true);
    setError("");
    try {
      const token = localStorage.getItem("sr_token");
      const res = await fetch("/api/v1/linkedin/analyze-network", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setAiInsights(data);
        try { localStorage.setItem("sr_linkedin_insights", JSON.stringify(data)); } catch { /* ignore */ }
      } else {
        const body = await res.json().catch(() => ({}));
        setError(`Error ${res.status}: ${body.detail || "Analysis failed"}`);
      }
    } catch (err: unknown) {
      setError(`Failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    }
    setAnalyzing(false);
  }

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-24 bg-surface-100 rounded-xl animate-pulse" />)}</div>;

  if (!stats || stats.total_connections === 0) {
    return (
      <div className="bg-white rounded-xl border border-surface-200 p-8 text-center">
        <span className="text-3xl block mb-4">🔗</span>
        <h3 className="text-lg font-semibold text-ink-900 mb-2">LinkedIn Intelligence</h3>
        <p className="text-sm text-ink-400 mb-4">Import your LinkedIn connections to analyze your professional network.</p>
        <a href="/settings" className="inline-block px-5 py-2.5 bg-brand-600 text-white text-sm font-semibold rounded-lg hover:bg-brand-700">Import Connections</a>
      </div>
    );
  }

  // Compute breakdowns
  const byCompany: Record<string, number> = {};
  const bySeniority: Record<string, number> = {};
  const byRegion: Record<string, number> = {};
  let recruiters = 0;
  let hiringManagers = 0;
  let executives = 0;

  connections.forEach((c) => {
    const company = c.current_company || "Unknown";
    byCompany[company] = (byCompany[company] || 0) + 1;

    const title = (c.current_title || "").toLowerCase();
    if (c.is_recruiter) { bySeniority["Recruiter"] = (bySeniority["Recruiter"] || 0) + 1; recruiters++; }
    else if (title.match(/\b(ceo|coo|cfo|cto|cmo|chief|founder|president|co-founder)\b/)) { bySeniority["C-Level / Founder"] = (bySeniority["C-Level / Founder"] || 0) + 1; executives++; }
    else if (c.is_hiring_manager || title.match(/\b(director|vp|vice president|head of|partner|svp|evp)\b/)) { bySeniority["Director / VP"] = (bySeniority["Director / VP"] || 0) + 1; hiringManagers++; }
    else if (title.match(/\b(manager|lead|senior manager|team lead|principal)\b/)) { bySeniority["Manager / Lead"] = (bySeniority["Manager / Lead"] || 0) + 1; }
    else if (title.match(/\b(senior|sr\.)\b/)) { bySeniority["Senior IC"] = (bySeniority["Senior IC"] || 0) + 1; }
    else { bySeniority["Other"] = (bySeniority["Other"] || 0) + 1; }

    const loc = (c.location || "").toLowerCase();
    if (loc.match(/dubai|abu dhabi|uae|sharjah|ajman/)) byRegion["UAE"] = (byRegion["UAE"] || 0) + 1;
    else if (loc.match(/riyadh|jeddah|saudi|ksa|dammam/)) byRegion["KSA"] = (byRegion["KSA"] || 0) + 1;
    else if (loc.match(/london|uk|manchester|birmingham/)) byRegion["UK"] = (byRegion["UK"] || 0) + 1;
    else if (loc.match(/new york|san francisco|us|california|texas|chicago|boston/)) byRegion["US"] = (byRegion["US"] || 0) + 1;
    else if (loc.match(/doha|qatar/)) byRegion["Qatar"] = (byRegion["Qatar"] || 0) + 1;
    else if (loc.match(/india|mumbai|bangalore|delhi/)) byRegion["India"] = (byRegion["India"] || 0) + 1;
    else if (loc.match(/singapore|hong kong|asia/)) byRegion["APAC"] = (byRegion["APAC"] || 0) + 1;
    else if (loc.match(/paris|berlin|amsterdam|europe|italy|milan|rome|spain/)) byRegion["Europe"] = (byRegion["Europe"] || 0) + 1;
    else if (loc) byRegion["Other"] = (byRegion["Other"] || 0) + 1;
  });

  const total = stats.total_connections;
  const topCompanies = Object.entries(byCompany).sort((a, b) => b[1] - a[1]).slice(0, 12);
  const seniorityList = Object.entries(bySeniority).sort((a, b) => b[1] - a[1]);
  const regionList = Object.entries(byRegion).sort((a, b) => b[1] - a[1]);

  const barColors: Record<string, string> = {
    "C-Level / Founder": "bg-violet-500",
    "Director / VP": "bg-indigo-500",
    "Manager / Lead": "bg-blue-500",
    "Senior IC": "bg-cyan-500",
    "Recruiter": "bg-emerald-500",
    "Other": "bg-slate-400",
  };

  return (
    <div className="space-y-4">
      {/* AI Analyze button — always visible at top */}
      <div className="flex justify-end">
        <button
          onClick={runAIAnalysis}
          disabled={analyzing}
          className="px-5 py-2.5 text-sm font-semibold text-white rounded-lg disabled:opacity-50"
          style={{ background: "linear-gradient(135deg, #5B6CFF 0%, #7F8CFF 100%)" }}
        >
          {analyzing ? "Finding your warm paths..." : "Analyze My Network with AI"}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">{error}</div>
      )}

      {/* AI Results — show right after button if available */}
      {aiInsights && (
        <div className="bg-white rounded-xl border border-surface-200 p-5 space-y-5">
          <h3 className="text-sm font-bold text-ink-900">AI Network Intelligence</h3>

          {aiInsights.network_strength && (
            <div>
              <div className="text-[11px] font-medium text-ink-400 uppercase mb-1">Assessment</div>
              <p className="text-sm text-ink-700">{aiInsights.network_strength}</p>
            </div>
          )}

          {aiInsights.warm_paths?.length > 0 && (
            <div>
              <div className="text-[11px] font-medium text-emerald-600 uppercase mb-2">Warm Paths to Jobs</div>
              <div className="space-y-3">
                {aiInsights.warm_paths.map((wp, i) => (
                  <div key={i} className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-semibold text-ink-900">{wp.target_company}</span>
                      <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${wp.strength === "strong" ? "bg-emerald-100 text-emerald-700" : wp.strength === "medium" ? "bg-amber-100 text-amber-700" : "bg-surface-200 text-ink-500"}`}>{wp.strength}</span>
                    </div>
                    {wp.connections_there?.length > 0 && (
                      <div className="text-[12px] text-ink-500 mb-1">You know: {wp.connections_there.join(", ")}</div>
                    )}
                    <div className="text-[12px] text-ink-700">{wp.strategy}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {aiInsights.recruiter_strategy?.length > 0 && (
            <div>
              <div className="text-[11px] font-medium text-blue-600 uppercase mb-2">Recruiter Engagement Plan</div>
              <div className="space-y-2">
                {aiInsights.recruiter_strategy.map((rs, i) => (
                  <div key={i} className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                    <div className="text-sm font-semibold text-ink-900">{rs.recruiter_name} <span className="font-normal text-ink-400">at {rs.company}</span></div>
                    <div className="text-[12px] text-ink-700 mt-0.5">{rs.action}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {aiInsights.career_leverage?.length > 0 && (
            <div>
              <div className="text-[11px] font-medium text-violet-600 uppercase mb-1">How to Leverage Your Network</div>
              {aiInsights.career_leverage.map((s, i) => <div key={i} className="text-sm text-ink-700 py-0.5">• {s}</div>)}
            </div>
          )}

          {aiInsights.blind_spots?.length > 0 && (
            <div>
              <div className="text-[11px] font-medium text-amber-600 uppercase mb-1">Network Gaps</div>
              {aiInsights.blind_spots.map((s, i) => <div key={i} className="text-sm text-ink-700 py-0.5">• {s}</div>)}
            </div>
          )}

          {aiInsights.recommendations?.length > 0 && (
            <div>
              <div className="text-[11px] font-medium text-ink-900 uppercase mb-1">Do This Now</div>
              {aiInsights.recommendations.map((s, i) => <div key={i} className="text-sm text-ink-700 py-0.5">{i + 1}. {s}</div>)}
            </div>
          )}

          {aiInsights.warm_intro_potential && (
            <div className="bg-surface-50 rounded-lg p-3">
              <div className="text-[11px] font-medium text-ink-400 uppercase mb-1">Warm Intro Potential</div>
              <p className="text-sm text-ink-700">{aiInsights.warm_intro_potential}</p>
            </div>
          )}
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatBox label="Total Connections" value={total} />
        <StatBox label="Recruiters" value={recruiters} accent />
        <StatBox label="Hiring Managers" value={hiringManagers} />
        <StatBox label="Executives" value={executives} />
        <StatBox label="Companies" value={stats.unique_companies} />
      </div>

      {/* Network strength summary */}
      <div className="bg-white rounded-xl border border-surface-200 p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-ink-900">Network Strength</h3>
          <div className="text-xs text-ink-400">
            {recruiters > 50 ? "🟢 Strong recruiter network" : recruiters > 20 ? "🟡 Growing recruiter network" : "🔴 Few recruiters — expand outreach"}
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="bg-surface-50 rounded-lg p-3">
            <div className="text-lg font-bold text-ink-900">{((recruiters / total) * 100).toFixed(1)}%</div>
            <div className="text-[10px] text-ink-400 uppercase">Recruiters</div>
          </div>
          <div className="bg-surface-50 rounded-lg p-3">
            <div className="text-lg font-bold text-ink-900">{(((hiringManagers + executives) / total) * 100).toFixed(1)}%</div>
            <div className="text-[10px] text-ink-400 uppercase">Decision Makers</div>
          </div>
          <div className="bg-surface-50 rounded-lg p-3">
            <div className="text-lg font-bold text-ink-900">{Object.keys(byCompany).length}</div>
            <div className="text-[10px] text-ink-400 uppercase">Companies Reached</div>
          </div>
        </div>
      </div>

      {/* Seniority breakdown */}
      <div className="bg-white rounded-xl border border-surface-200 p-5">
        <h3 className="text-sm font-bold text-ink-900 mb-3">Network by Seniority</h3>
        <div className="space-y-2">
          {seniorityList.map(([level, count]) => (
            <div key={level} className="flex items-center gap-3">
              <div className="w-36 text-sm text-ink-700 truncate">{level}</div>
              <div className="flex-1 h-6 bg-surface-100 rounded-full overflow-hidden">
                <div className={`${barColors[level] || "bg-slate-400"} h-full rounded-full`} style={{ width: `${(count / total) * 100}%` }} />
              </div>
              <div className="text-[11px] text-ink-400 w-20 text-right">{count} ({((count / total) * 100).toFixed(0)}%)</div>
            </div>
          ))}
        </div>
      </div>

      {/* Company breakdown */}
      <div className="bg-white rounded-xl border border-surface-200 p-5">
        <h3 className="text-sm font-bold text-ink-900 mb-3">Top Companies in Network</h3>
        <div className="grid grid-cols-2 gap-2">
          {topCompanies.map(([company, count]) => (
            <div key={company} className="flex items-center justify-between bg-surface-50 rounded-lg px-3 py-2">
              <span className="text-sm text-ink-700 truncate">{company}</span>
              <span className="text-sm font-bold text-ink-900 ml-2">{count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Region breakdown */}
      <div className="bg-white rounded-xl border border-surface-200 p-5">
        <h3 className="text-sm font-bold text-ink-900 mb-3">Network by Region</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {regionList.map(([region, count]) => (
            <div key={region} className="bg-surface-50 rounded-lg p-3 text-center">
              <div className="text-lg font-bold text-ink-900">{((count / total) * 100).toFixed(0)}%</div>
              <div className="text-[11px] text-ink-400">{region} ({count})</div>
            </div>
          ))}
        </div>
      </div>

      {/* Extension insights placeholder */}
    </div>
  );
}

function StatBox({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div className="bg-white rounded-xl border border-surface-200 p-4">
      <div className="text-[10px] font-medium text-ink-400 uppercase mb-1">{label}</div>
      <div className={`text-xl font-bold ${accent ? "text-brand-600" : "text-ink-900"}`}>{value.toLocaleString()}</div>
    </div>
  );
}
