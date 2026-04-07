// @ts-nocheck
"use client";

import { useEffect, useState } from "react";
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
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export default function HomePage() {
  const { user } = useAuth();
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [analytics, setAnalytics] = useState<ApplicationAnalytics | null>(null);
  const [board, setBoard] = useState<BoardResponse | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [signals, setSignals] = useState<HiddenSignal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      getDashboard().then(setDashboard),
      getApplicationAnalytics().then(setAnalytics),
      getBoard().then(setBoard),
      getRadar(10).then((r) => setOpportunities(r.opportunities || [])),
      getHiddenMarket().then((r) => setSignals(r.signals || [])),
    ]).finally(() => setLoading(false));
  }, []);

  const displayName =
    user?.full_name?.split(" ")[0] || user?.email?.split("@")[0] || "there";

  // Derive data from API or use placeholder defaults
  const totalApps = board?.total ?? analytics?.total_applications ?? 2;
  const interviewApps = board?.columns?.find((c) => c.stage === "interview")?.applications || [];
  const appliedApps = board?.columns?.find((c) => c.stage === "applied")?.applications || [];
  const allApps = board?.columns?.flatMap((c) => c.applications.map((a) => ({ ...a, stage: c.stage }))) || [];

  // Pipeline items sorted by recent
  const pipelineItems = [...allApps]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 5);

  // Top opportunities
  const topOpps = opportunities.slice(0, 2);

  // Signals
  const topSignals = signals.slice(0, 5);

  const stageColors: Record<string, string> = {
    watching: "bg-[#2A2D45] text-[#8B92B0]",
    applied: "bg-[#1E2A4A] text-[#5B9BFF]",
    interview: "bg-[#2A1E4A] text-[#9B7FFF]",
    offer: "bg-[#1E3A2A] text-[#5BCC7F]",
    rejected: "bg-[#3A1E1E] text-[#FF7F7F]",
  };

  if (loading) {
    return (
      <div className="space-y-6 mt-6">
        <div className="h-16 rounded-2xl animate-pulse" style={{ background: "rgba(255,255,255,0.04)" }} />
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 rounded-[14px] animate-pulse" style={{ background: "rgba(255,255,255,0.04)" }} />
          ))}
        </div>
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-40 rounded-2xl animate-pulse" style={{ background: "rgba(255,255,255,0.04)" }} />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6 mt-6 mb-12">
      {/* ── Header ──────────────────────────────────────────── */}
      <div className="mb-5">
        <h1 className="text-[22px] font-bold text-white">
          {greeting()}, {displayName}
        </h1>
        <p className="text-[13px] text-[#6B7194] mt-1">
          Scanning the market and tracking your pipeline...
        </p>
      </div>

      {/* ── Top Metrics ─────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Applications Sent"
          value={totalApps || 2}
          sub={appliedApps.length > 0 ? `+${appliedApps.length} this week` : "+1 this week"}
        />
        <MetricCard
          title="Interviews Booked"
          value={interviewApps.length || 1}
          sub={interviewApps[0] ? `${interviewApps[0].company} — upcoming` : "Careem — Thursday"}
        />
        <MetricCard
          title="Follow-ups Due"
          value={`${appliedApps.filter((a) => (Date.now() - new Date(a.date_applied).getTime()) / 86400000 >= 3).length || 1} today`}
          sub={appliedApps[0] ? `${appliedApps[0].company} pending` : "Tabby pending"}
        />
        <MetricCard
          title="Hidden Matches"
          value={`${signals.length || 3} new`}
          sub="Roles before posting"
          accent
        />
      </div>

      {/* ── Your priorities today ───────────────────────────── */}
      <section>
        <SectionTitle>Your priorities today</SectionTitle>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <PriorityCard
            icon="📩"
            title={appliedApps[0] ? `Follow up — ${appliedApps[0].company}` : "Follow up — Tabby"}
            lines={[
              appliedApps[0] ? `You applied ${Math.floor((Date.now() - new Date(appliedApps[0].date_applied).getTime()) / 86400000)} days ago` : "You applied 3 days ago",
              "No response yet",
            ]}
            cta="Send follow-up"
            href="/applications"
          />
          <PriorityCard
            icon="🎯"
            title={interviewApps[0] ? `Interview — ${interviewApps[0].company}` : "Interview — Careem"}
            lines={[
              interviewApps[0]?.role || "Strategy Lead",
              interviewApps[0]?.interview_at
                ? new Date(interviewApps[0].interview_at).toLocaleDateString("en-GB", { weekday: "long", hour: "2-digit", minute: "2-digit" })
                : "Thursday — 3:00 PM",
            ]}
            cta="Prepare interview"
            href="/applications"
          />
          <PriorityCard
            icon="🔥"
            title={topOpps[0] ? `New opportunity — ${topOpps[0].company}` : "New opportunity — Kitopi"}
            lines={[
              topOpps[0]?.role || topOpps[0]?.title || "VP Growth likely opening",
              "Strong fit detected",
            ]}
            cta="View opportunity"
            href="/scout"
          />
        </div>
      </section>

      {/* ── Top Opportunities ───────────────────────────────── */}
      <section>
        <SectionTitle href="/scout">Top Opportunities</SectionTitle>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(topOpps.length > 0 ? topOpps : placeholderOpps).map((opp, i) => (
            <div
              key={i}
              className="border border-white/[0.08] p-5"
              style={{ background: "rgba(255,255,255,0.04)", borderRadius: 14 }}
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-[11px] font-semibold tracking-wide uppercase text-[#7F8CFF] bg-[#7F8CFF]/10 px-2.5 py-1 rounded-md">
                  Hidden opportunity
                </span>
                <span className="text-[20px] font-bold text-[#5BCC7F]">
                  {opp.fit_score ?? opp.overall_score ?? 92}%
                </span>
              </div>
              <div className="text-[15px] font-semibold text-white">{opp.role || opp.title}</div>
              <div className="text-[13px] text-[#8B92B0] mt-0.5">{opp.company}</div>
              <div className="text-[12px] text-[#6B7194] mt-2 italic">
                &ldquo;{opp.evidence?.[0]
                  ? (typeof opp.evidence[0] === "string" ? opp.evidence[0] : opp.evidence[0]?.text || opp.evidence[0]?.detail || "Strong market signal detected")
                  : "Raised $200M — no ops leader yet"}&rdquo;
              </div>
              <div className="flex gap-3 mt-4">
                <a href="/scout" className="text-[12px] font-semibold text-[#7F8CFF] hover:text-[#99A5FF] transition-colors">
                  View Opportunity
                </a>
                <a href="/applications" className="text-[12px] font-semibold text-[#6B7194] hover:text-[#8B92B0] transition-colors">
                  Generate Pack
                </a>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Your active pipeline ────────────────────────────── */}
      <section>
        <SectionTitle href="/applications">Your active pipeline</SectionTitle>
        <div className="border border-white/[0.08] divide-y divide-white/[0.06]" style={{ background: "rgba(255,255,255,0.04)", borderRadius: 14 }}>
          {(pipelineItems.length > 0 ? pipelineItems : placeholderPipeline).map((app, i) => (
            <div key={i} className="px-5 py-4 flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-semibold text-white">{app.company} — {app.role}</div>
                <div className="text-[12px] text-[#6B7194] mt-0.5">
                  {app.nextStep || `Status: ${app.stage}`}
                  {app.latestUpdate && <span className="ml-2 text-[#555C7A]">{app.latestUpdate}</span>}
                </div>
              </div>
              <span className={`text-[11px] font-medium px-2.5 py-1 rounded-md capitalize ${stageColors[app.stage] || "bg-[#2A2D45] text-[#8B92B0]"}`}>
                {app.stage}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ── Relevant updates for your applications ──────────── */}
      <section>
        <SectionTitle>Relevant updates for your applications</SectionTitle>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(topSignals.length > 0
            ? topSignals.filter((s) => allApps.some((a) => a.company?.toLowerCase() === s.company?.toLowerCase())).slice(0, 2)
            : placeholderUpdates
          ).concat(
            topSignals.length === 0 || !topSignals.filter((s) => allApps.some((a) => a.company?.toLowerCase() === s.company?.toLowerCase())).length
              ? placeholderUpdates
              : []
          ).slice(0, 2).map((update, i) => (
            <div
              key={i}
              className="border border-white/[0.08] p-5"
              style={{ background: "rgba(255,255,255,0.04)", borderRadius: 14 }}
            >
              <div className="text-[14px] font-semibold text-white">{update.company} {update.headline || "raises funding"}</div>
              <div className="text-[12px] text-[#8B92B0] mt-1">{update.description || "$200M Series D"}</div>
              <div className="text-[12px] text-[#7F8CFF] mt-2">{update.why_it_matters || "Hiring urgency increasing"}</div>
              <a href="/scout" className="inline-block mt-3 text-[12px] font-semibold text-[#7F8CFF] hover:text-[#99A5FF] transition-colors">
                View opportunity
              </a>
            </div>
          ))}
        </div>
      </section>

      {/* ── Market Signals ──────────────────────────────────── */}
      <section>
        <SectionTitle href="/scout">Market Signals</SectionTitle>
        <div className="space-y-2">
          {(topSignals.length > 0 ? topSignals : placeholderSignals).map((sig, i) => {
            const icons: Record<string, string> = {
              funding: "💰", expansion: "🌍", hiring: "👥", leadership: "🏢", product: "🚀",
            };
            return (
              <div
                key={i}
                className="border border-white/[0.08] px-5 py-3.5 flex items-start gap-3"
                style={{ background: "rgba(255,255,255,0.04)", borderRadius: 14 }}
              >
                <span className="text-base mt-0.5">{icons[sig.signal_type] || "📡"}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-semibold text-white">{sig.company}</div>
                  <div className="text-[12px] text-[#8B92B0] mt-0.5">{sig.headline || sig.description}</div>
                  {Boolean(sig.why_it_matters) && (
                    <div className="text-[11px] text-[#7F8CFF] mt-1">{sig.why_it_matters}</div>
                  )}
                </div>
                <span className="text-[11px] font-medium text-[#555C7A] capitalize whitespace-nowrap mt-0.5">{sig.signal_type}</span>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

/* ── Sub-components ─────────────────────────────────────────── */

function MetricCard({ title, value, sub, accent = false }: { title: string; value: string | number; sub: string; accent?: boolean }) {
  return (
    <div
      className={`border p-5 ${accent ? "border-[#7F8CFF]/20" : "border-white/[0.08]"}`}
      style={{ background: accent ? "rgba(127,140,255,0.06)" : "rgba(255,255,255,0.04)", borderRadius: 14 }}
    >
      <div className="text-[11px] font-medium text-[#6B7194] uppercase tracking-wide">{title}</div>
      <div className={`text-[22px] font-bold mt-1.5 ${accent ? "text-[#7F8CFF]" : "text-white"}`}>{value}</div>
      <div className="text-[12px] text-[#555C7A] mt-0.5">{sub}</div>
    </div>
  );
}

function PriorityCard({ icon, title, lines, cta, href }: { icon: string; title: string; lines: string[]; cta: string; href: string }) {
  return (
    <div
      className="border border-[#7F8CFF]/15 p-5 flex flex-col justify-between"
      style={{ background: "rgba(127,140,255,0.04)", borderRadius: 14 }}
    >
      <div>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-base">{icon}</span>
          <span className="text-[13px] font-semibold text-white">{title}</span>
        </div>
        {lines.map((line, i) => (
          <div key={i} className="text-[12px] text-[#8B92B0] leading-relaxed">{line}</div>
        ))}
      </div>
      <a
        href={href}
        className="inline-block mt-4 text-[12px] font-semibold text-[#7F8CFF] bg-[#7F8CFF]/10 px-3.5 py-1.5 rounded-lg hover:bg-[#7F8CFF]/15 transition-colors self-start"
      >
        {cta}
      </a>
    </div>
  );
}

function SectionTitle({ children, href }: { children: React.ReactNode; href?: string }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-[15px] font-semibold text-white">{children}</h2>
      {href && (
        <a href={href} className="text-[12px] text-[#7F8CFF] hover:text-[#99A5FF] font-medium transition-colors">
          View all
        </a>
      )}
    </div>
  );
}

/* ── Placeholder data (used when API returns empty) ─────────── */

const placeholderOpps = [
  { company: "Tabby", role: "Head of Operations", fit_score: 92, evidence: ["Raised $200M — no ops leader yet"] },
  { company: "Careem", role: "Strategy Lead", fit_score: 87, evidence: ["Expanding into 3 new markets — hiring strategy team"] },
];

const placeholderPipeline = [
  { id: "1", company: "Tabby", role: "Head of Operations", stage: "applied", updated_at: new Date().toISOString(), nextStep: "Next step: Follow up tomorrow", latestUpdate: "· Recruiter viewed your CV" },
  { id: "2", company: "Careem", role: "Strategy Lead", stage: "interview", updated_at: new Date().toISOString(), nextStep: "Interview scheduled", latestUpdate: "· Interview confirmed" },
];

const placeholderUpdates = [
  { company: "Tabby", headline: "raises funding", description: "$200M Series D", why_it_matters: "Hiring urgency increasing" },
];

const placeholderSignals = [
  { company: "Tabby", signal_type: "funding", headline: "$200M Series D closed", description: "Major growth round signals executive hiring", why_it_matters: "Ops and strategy roles likely opening" },
  { company: "Careem", signal_type: "expansion", headline: "Expanding to Egypt and Morocco", description: "3 new markets announced this quarter", why_it_matters: "Regional strategy roles in demand" },
  { company: "Kitopi", signal_type: "hiring", headline: "VP Growth role likely opening", description: "Leadership restructuring underway", why_it_matters: "Strong fit with your experience" },
];
