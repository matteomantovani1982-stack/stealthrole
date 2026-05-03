"use client";

import { useEffect, useState } from "react";
import { getAuthHeaders } from "@/lib/utils";

interface EmailIntelData {
  scan_status: string;
  total_emails_scanned: number;
  job_emails_found: number;
  applications_reconstructed: number;
  patterns: {
    avg_response_days: number | null;
    response_rate_pct: number;
    best_day_to_apply: string | null;
    best_time_to_apply: string | null;
    avg_interviews_per_app: number;
    total_companies_applied: number;
    total_responses: number;
    rejection_stage_distribution: Record<string, number>;
  } | null;
  industry_breakdown: Record<string, { applied: number; interview: number; offer: number; rejected: number }> | null;
  writing_style: {
    formality: string;
    tone: string;
    greeting_style: string;
    closing_style: string;
    common_phrases: string[];
  } | null;
  insights: {
    strengths: string[];
    weaknesses: string[];
    recommendations: string[];
    career_trajectory: string;
  } | null;
}

export default function EmailIntelligenceTab() {
  const [connected, setConnected] = useState(false);
  const [data, setData] = useState<EmailIntelData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const headers = getAuthHeaders();

    Promise.allSettled([
      fetch("/api/v1/email-integration/accounts", { headers }).then((r) => r.ok ? r.json() : null),
      fetch("/api/v1/email-intelligence/report", { headers }).then((r) => r.ok ? r.json() : null),
    ]).then(([accountsRes, reportRes]) => {
      const accounts = accountsRes.status === "fulfilled" ? accountsRes.value : null;
      if (accounts?.total > 0) setConnected(true);
      if (reportRes.status === "fulfilled" && reportRes.value) setData(reportRes.value);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-24 bg-surface-100 rounded-xl animate-pulse" />)}</div>;

  // Not connected state
  if (!connected) {
    return (
      <div className="bg-white rounded-xl border border-surface-200 p-8 text-center">
        <div className="w-16 h-16 bg-surface-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
          <span className="text-3xl">📧</span>
        </div>
        <h3 className="text-lg font-semibold text-ink-900 mb-2">Email Intelligence</h3>
        <p className="text-sm text-ink-400 mb-4 max-w-md mx-auto">Connect your Gmail or Outlook to unlock email intelligence — see your application history, response rates, and patterns from the last 3 years.</p>
        <a href="/settings" className="inline-block px-5 py-2.5 bg-brand-600 text-white text-sm font-semibold rounded-lg hover:bg-brand-700 transition-colors">
          Connect Email
        </a>
      </div>
    );
  }

  // Connected but no data yet — show scan button
  if (connected && (!data || !data.patterns)) {
    const scanStatus = data?.scan_status;
    return (
      <div className="bg-white rounded-xl border border-surface-200 p-8 text-center">
        <div className="w-16 h-16 bg-green-50 rounded-2xl flex items-center justify-center mx-auto mb-4">
          <span className="text-3xl">✅</span>
        </div>
        <h3 className="text-lg font-semibold text-ink-900 mb-2">Email Connected</h3>
        {scanStatus === "scanning" || scanStatus === "analyzing" ? (
          <>
            <p className="text-sm text-ink-400 mb-4">Scanning your emails... this can take a few minutes.</p>
            <div className="w-6 h-6 border-2 border-brand-600 border-t-transparent rounded-full animate-spin mx-auto" />
          </>
        ) : (
          <>
            <p className="text-sm text-ink-400 mb-4">Your email is connected. Run a scan to analyze your application history, response rates, and writing style.</p>
            <button id="scan-emails-btn" onClick={async () => {
              const btn = document.getElementById("scan-emails-btn") as HTMLButtonElement;
              if (btn) { btn.textContent = "Diving into your inbox..."; btn.disabled = true; btn.style.opacity = "0.5"; btn.style.cursor = "not-allowed"; }
              const headers = getAuthHeaders();
              await fetch("/api/v1/email-intelligence/scan", {
                method: "POST",
                headers,
              });
              window.location.reload();
            }} className="px-5 py-2.5 bg-brand-600 text-white text-sm font-semibold rounded-lg hover:bg-brand-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
              Scan My Emails
            </button>
          </>
        )}
      </div>
    );
  }

  const patterns = data?.patterns;
  const industry = data?.industry_breakdown || {};
  const insights = data?.insights;
  const style = data?.writing_style;

  // Compute top industries
  const topIndustries = Object.entries(industry)
    .map(([name, stats]) => ({ name, total: stats.applied + stats.interview + stats.offer + stats.rejected, ...stats }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 8);

  return (
    <div className="space-y-4">
      {/* Re-scan button */}
      <div className="flex justify-end">
        <button onClick={async () => {
          const btn = document.getElementById("rescan-btn");
          if (btn) btn.textContent = "Reading between the lines...";
          try {
            const headers = getAuthHeaders();
            const res = await fetch("/api/v1/email-intelligence/scan", {
              method: "POST",
              headers,
            });
            const data = await res.json();
            if (btn) btn.textContent = res.ok ? "Scan started! Refresh in 60s..." : `Error: ${data.detail || res.status}`;
            if (res.ok) setTimeout(() => window.location.reload(), 60000);
          } catch (err: unknown) {
            if (btn) btn.textContent = `Failed: ${err instanceof Error ? err.message : "Unknown error"}`;
          }
        }} id="rescan-btn" className="px-4 py-2 text-[12px] font-semibold text-[#7F8CFF] bg-[#7F8CFF]/10 rounded-lg hover:bg-[#7F8CFF]/20 transition-colors">
          Re-scan Emails
        </button>
      </div>
      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatBox label="Applications Found" value={data?.applications_reconstructed || 0} />
        <StatBox label="Response Rate" value={`${patterns?.response_rate_pct || 0}%`} accent={(patterns?.response_rate_pct ?? 0) > 25} />
        <StatBox label="Avg. Reply Time" value={patterns?.avg_response_days ? `${patterns.avg_response_days}d` : "—"} />
        <StatBox label="Emails Scanned" value={data?.total_emails_scanned || 0} />
      </div>

      {/* Patterns */}
      {patterns && (
        <div className="bg-white rounded-xl border border-surface-200 p-5">
          <h3 className="text-sm font-bold text-ink-900 mb-3">Application Patterns</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {patterns.best_day_to_apply && (
              <div className="bg-surface-50 rounded-lg p-3">
                <div className="text-[10px] font-medium text-ink-400 uppercase">Best Day to Apply</div>
                <div className="text-sm font-semibold text-ink-900">{patterns.best_day_to_apply}</div>
              </div>
            )}
            {patterns.best_time_to_apply && (
              <div className="bg-surface-50 rounded-lg p-3">
                <div className="text-[10px] font-medium text-ink-400 uppercase">Best Time</div>
                <div className="text-sm font-semibold text-ink-900 capitalize">{patterns.best_time_to_apply}</div>
              </div>
            )}
            <div className="bg-surface-50 rounded-lg p-3">
              <div className="text-[10px] font-medium text-ink-400 uppercase">Interview Rate</div>
              <div className="text-sm font-semibold text-ink-900">{((patterns.avg_interviews_per_app || 0) * 100).toFixed(0)}%</div>
            </div>
            <div className="bg-surface-50 rounded-lg p-3">
              <div className="text-[10px] font-medium text-ink-400 uppercase">Companies Applied</div>
              <div className="text-sm font-semibold text-ink-900">{patterns.total_companies_applied || 0}</div>
            </div>
            <div className="bg-surface-50 rounded-lg p-3">
              <div className="text-[10px] font-medium text-ink-400 uppercase">Total Responses</div>
              <div className="text-sm font-semibold text-ink-900">{patterns.total_responses || 0}</div>
            </div>
          </div>

          {/* Stage distribution bar */}
          {patterns.rejection_stage_distribution && (
            <div className="mt-4">
              <div className="text-[10px] font-medium text-ink-400 uppercase mb-2">Outcome Distribution</div>
              <div className="flex h-6 rounded-full overflow-hidden">
                {Object.entries(patterns.rejection_stage_distribution).map(([stage, count]) => {
                  const total = Object.values(patterns.rejection_stage_distribution).reduce((a, b) => a + b, 0);
                  const pct = total > 0 ? (count / total) * 100 : 0;
                  const colors: Record<string, string> = { applied: "bg-blue-400", interview: "bg-amber-400", offer: "bg-green-400", rejected: "bg-red-400", unknown: "bg-surface-300" };
                  return pct > 0 ? <div key={stage} className={`${colors[stage] || "bg-surface-300"} relative group`} style={{ width: `${pct}%` }} title={`${stage}: ${count}`} /> : null;
                })}
              </div>
              <div className="flex gap-3 mt-1.5">
                {Object.entries(patterns.rejection_stage_distribution).map(([stage, count]) => (
                  <div key={stage} className="flex items-center gap-1 text-[10px] text-ink-400">
                    <div className={`w-2 h-2 rounded-full ${{ applied: "bg-blue-400", interview: "bg-amber-400", offer: "bg-green-400", rejected: "bg-red-400" }[stage] || "bg-surface-300"}`} />
                    {stage} ({count})
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Industries targeted */}
      {topIndustries.length > 0 && (
        <div className="bg-white rounded-xl border border-surface-200 p-5">
          <h3 className="text-sm font-bold text-ink-900 mb-3">Industries Targeted</h3>
          <div className="space-y-2">
            {topIndustries.map((ind) => (
              <div key={ind.name} className="flex items-center gap-3">
                <div className="w-28 text-sm text-ink-700 truncate">{ind.name}</div>
                <div className="flex-1 h-5 bg-surface-100 rounded-full overflow-hidden flex">
                  <div className="bg-blue-400 h-full" style={{ width: `${(ind.applied / Math.max(ind.total, 1)) * 100}%` }} />
                  <div className="bg-amber-400 h-full" style={{ width: `${(ind.interview / Math.max(ind.total, 1)) * 100}%` }} />
                  <div className="bg-green-400 h-full" style={{ width: `${(ind.offer / Math.max(ind.total, 1)) * 100}%` }} />
                </div>
                <div className="text-[11px] text-ink-400 w-8 text-right">{ind.total}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Writing style */}
      {style && (
        <div className="bg-white rounded-xl border border-surface-200 p-5">
          <h3 className="text-sm font-bold text-ink-900 mb-3">Your Writing Style</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-surface-50 rounded-lg p-3">
              <div className="text-[10px] font-medium text-ink-400 uppercase">Formality</div>
              <div className="text-sm font-semibold text-ink-900 capitalize">{style.formality}</div>
            </div>
            <div className="bg-surface-50 rounded-lg p-3">
              <div className="text-[10px] font-medium text-ink-400 uppercase">Tone</div>
              <div className="text-sm font-semibold text-ink-900 capitalize">{style.tone}</div>
            </div>
            <div className="bg-surface-50 rounded-lg p-3">
              <div className="text-[10px] font-medium text-ink-400 uppercase">Greeting</div>
              <div className="text-sm font-semibold text-ink-900">{style.greeting_style}</div>
            </div>
            <div className="bg-surface-50 rounded-lg p-3">
              <div className="text-[10px] font-medium text-ink-400 uppercase">Closing</div>
              <div className="text-sm font-semibold text-ink-900">{style.closing_style}</div>
            </div>
          </div>
          {style.common_phrases?.length > 0 && (
            <div className="mt-3">
              <div className="text-[10px] font-medium text-ink-400 uppercase mb-1.5">Your Common Phrases</div>
              <div className="flex flex-wrap gap-1.5">{style.common_phrases.map((p) => <span key={p} className="px-2 py-0.5 rounded bg-brand-50 text-brand-700 text-[12px]">{p}</span>)}</div>
            </div>
          )}
        </div>
      )}

      {/* Insights */}
      {insights && (
        <div className="bg-white rounded-xl border border-surface-200 p-5">
          <h3 className="text-sm font-bold text-ink-900 mb-3">AI Insights</h3>
          {insights.strengths?.length > 0 && (
            <div className="mb-3">
              <div className="text-[10px] font-medium text-green-600 uppercase mb-1">Strengths</div>
              {insights.strengths.map((s, i) => <div key={i} className="text-sm text-ink-700 flex gap-2"><span className="text-green-500 shrink-0">✓</span>{s}</div>)}
            </div>
          )}
          {insights.weaknesses?.length > 0 && (
            <div className="mb-3">
              <div className="text-[10px] font-medium text-amber-600 uppercase mb-1">Areas to Improve</div>
              {insights.weaknesses.map((w, i) => <div key={i} className="text-sm text-ink-700 flex gap-2"><span className="text-amber-500 shrink-0">⚠</span>{w}</div>)}
            </div>
          )}
          {insights.recommendations?.length > 0 && (
            <div>
              <div className="text-[10px] font-medium text-brand-600 uppercase mb-1">Recommendations</div>
              {insights.recommendations.map((r, i) => <div key={i} className="text-sm text-ink-700 flex gap-2"><span className="text-brand-500 shrink-0">→</span>{r}</div>)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatBox({ label, value, accent }: { label: string; value: string | number; accent?: boolean }) {
  return (
    <div className="bg-white rounded-xl border border-surface-200 p-4">
      <div className="text-[10px] font-medium text-ink-400 uppercase mb-1">{label}</div>
      <div className={`text-xl font-bold ${accent ? "text-brand-600" : "text-ink-900"}`}>{value}</div>
    </div>
  );
}
