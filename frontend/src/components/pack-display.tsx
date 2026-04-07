// @ts-nocheck
"use client";

import { useState } from "react";
import type { JobRun } from "@/lib/api";
import ConnectionPath from "./connection-path";

interface LinkedInContact {
  name: string;
  title: string | null;
  is_recruiter: boolean;
  is_hiring_manager: boolean;
  linkedin_url: string | null;
}

interface Props {
  pack: JobRun;
  downloadUrl?: string;
  linkedinContacts?: LinkedInContact[];
}

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "strategy", label: "Strategy" },
  { id: "strengths", label: "Strengths" },
  { id: "salary", label: "Salary" },
  { id: "interview", label: "Interview" },
  { id: "contacts", label: "Contacts" },
];

export default function PackDisplay({ pack, downloadUrl, linkedinContacts = [] }: Props) {
  const [tab, setTab] = useState("overview");
  const reports = (pack.reports || {}) as Record<string, any>;
  const positioning = (pack.positioning || {}) as Record<string, any>;

  const company = reports.company || {};
  const salary = Array.isArray(reports.salary) ? reports.salary[0] || {} : reports.salary || {};
  const networking = reports.networking || {};
  const application = reports.application || {};
  const execSummary = Array.isArray(reports.exec_summary) ? reports.exec_summary : [];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-surface-200">
        <div className="flex items-center gap-4">
          {pack.keyword_match_score ? (
            <div className="w-16 h-16 rounded-2xl bg-brand-50 border-2 border-brand-200 flex flex-col items-center justify-center">
              <span className="text-xl font-bold text-brand-600">{pack.keyword_match_score}</span>
              <span className="text-[9px] text-brand-500 uppercase">Match</span>
            </div>
          ) : null}
          <div>
            <div className="text-lg font-bold text-ink-900">{pack.role_title || company.role_title || "Role"}</div>
            <div className="text-sm text-ink-400">{pack.company_name || company.company_name || "Company"}</div>
          </div>
        </div>
        {downloadUrl && (
          <a href={downloadUrl} target="_blank" rel="noopener" className="px-4 py-2 bg-brand-600 text-white text-sm font-semibold rounded-lg hover:bg-brand-700 transition-colors">
            Download Tailored CV
          </a>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 overflow-x-auto border-b border-surface-200 -mx-1 px-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-3 py-2 text-[13px] font-medium border-b-2 whitespace-nowrap transition-colors ${
              tab === t.id
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-ink-400 hover:text-ink-600"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ═══ OVERVIEW ═══ */}
      {tab === "overview" && (
        <div className="space-y-4">
          {execSummary.length > 0 && (
            <Section title="Executive Summary" description="Key takeaways from your application analysis">
              {execSummary.map((line, i) => (
                <BulletItem key={i} icon="→" color="brand">{line}</BulletItem>
              ))}
            </Section>
          )}
          {positioning.positioning_headline && (
            <Section title="Your Positioning" description="How to present yourself for this role">
              <div className="text-base font-semibold text-brand-700 mb-2">{positioning.positioning_headline}</div>
              {positioning.positioning_narrative && <p className="text-sm text-ink-600 leading-relaxed">{positioning.positioning_narrative}</p>}
            </Section>
          )}
          {company.company_name && (
            <Section title="Company Snapshot" description="What you need to know about this company">
              <div className="grid grid-cols-2 gap-2">
                {company.company_name && <InfoRow label="Company" value={company.company_name} />}
                {company.hq_location && <InfoRow label="Location" value={company.hq_location} />}
                {company.industry && <InfoRow label="Industry" value={company.industry} />}
                {company.employee_count && <InfoRow label="Size" value={company.employee_count} />}
              </div>
            </Section>
          )}
        </div>
      )}

      {/* ═══ STRATEGY ═══ */}
      {tab === "strategy" && (
        <div className="space-y-4">
          {positioning.positioning_headline && (
            <Section title="Positioning Strategy" description="Your unique angle for this application">
              <div className="bg-brand-50 rounded-lg p-4 mb-3">
                <div className="text-base font-semibold text-brand-700">{positioning.positioning_headline}</div>
              </div>
              {positioning.positioning_narrative && <p className="text-sm text-ink-700 leading-relaxed mb-3">{positioning.positioning_narrative}</p>}
              {positioning.angle_for_this_role && (
                <div className="bg-surface-50 rounded-lg p-3">
                  <div className="text-[11px] font-medium text-ink-400 uppercase mb-1">Angle for This Role</div>
                  <p className="text-sm text-ink-700">{positioning.angle_for_this_role}</p>
                </div>
              )}
            </Section>
          )}
          {Array.isArray(positioning.what_to_emphasise_in_interview) && positioning.what_to_emphasise_in_interview.length > 0 && (
            <Section title="What to Emphasise" description="Key points to highlight in your application and interview">
              {positioning.what_to_emphasise_in_interview.map((item, i) => (
                <BulletItem key={i} icon="★" color="brand">{item}</BulletItem>
              ))}
            </Section>
          )}
          {application.cover_letter_angle && (
            <Section title="Cover Letter Angle" description="The narrative hook for your cover letter">
              <p className="text-sm text-ink-700 leading-relaxed">{application.cover_letter_angle}</p>
            </Section>
          )}
        </div>
      )}

      {/* ═══ STRENGTHS ═══ */}
      {tab === "strengths" && (
        <div className="space-y-4">
          {Array.isArray(positioning.key_differentiators) && positioning.key_differentiators.length > 0 && (
            <Section title="Your Strengths" description="What makes you stand out for this role">
              {positioning.key_differentiators.map((item, i) => (
                <BulletItem key={i} icon="✓" color="green">{item}</BulletItem>
              ))}
            </Section>
          )}
          {Array.isArray(application.differentiators) && application.differentiators.length > 0 && (
            <Section title="Key Differentiators" description="Competitive advantages vs other candidates">
              {application.differentiators.map((item, i) => (
                <BulletItem key={i} icon="◆" color="brand">{item}</BulletItem>
              ))}
            </Section>
          )}
          {Array.isArray(application.risks_to_address) && application.risks_to_address.length > 0 && (
            <Section title="Weaknesses & Risks" description="Gaps to address proactively in your application">
              {application.risks_to_address.map((item, i) => (
                <BulletItem key={i} icon="⚠" color="amber">{item}</BulletItem>
              ))}
            </Section>
          )}
          {Array.isArray(application.gaps) && application.gaps.length > 0 && (
            <Section title="Skill Gaps" description="Areas where you may need to upskill or frame differently">
              {application.gaps.map((item, i) => (
                <BulletItem key={i} icon="—" color="red">{item}</BulletItem>
              ))}
            </Section>
          )}
        </div>
      )}

      {/* ═══ SALARY ═══ */}
      {tab === "salary" && (
        <div className="space-y-4">
          <Section title="Salary Intelligence" description="Compensation data for this role and region">
            <div className="grid grid-cols-2 gap-3 mb-3">
              {salary.base_low && salary.base_high && (
                <div className="bg-green-50 rounded-lg p-3 col-span-2">
                  <div className="text-[11px] font-medium text-green-600 uppercase mb-1">Base Salary Range</div>
                  <div className="text-xl font-bold text-green-700">{salary.base_low} – {salary.base_high}</div>
                </div>
              )}
              {salary.title && <InfoRow label="Role" value={salary.title} />}
              {salary.region && <InfoRow label="Region" value={salary.region} />}
              {salary.currency && <InfoRow label="Currency" value={salary.currency} />}
              {salary.source && <InfoRow label="Source" value={salary.source} />}
              {salary.confidence && <InfoRow label="Confidence" value={salary.confidence} />}
            </div>
            {salary.total_comp_note && (
              <div className="bg-surface-50 rounded-lg p-3">
                <div className="text-[11px] font-medium text-ink-400 uppercase mb-1">Total Compensation</div>
                <p className="text-sm text-ink-700">{salary.total_comp_note}</p>
              </div>
            )}
            {salary.negotiation_tips && (
              <div className="bg-surface-50 rounded-lg p-3 mt-2">
                <div className="text-[11px] font-medium text-ink-400 uppercase mb-1">Negotiation Tips</div>
                <p className="text-sm text-ink-700">{salary.negotiation_tips}</p>
              </div>
            )}
          </Section>
        </div>
      )}

      {/* ═══ INTERVIEW ═══ */}
      {tab === "interview" && (
        <div className="space-y-4">
          {Array.isArray(application.interview_process) && application.interview_process.length > 0 && (
            <Section title="Interview Process" description="Expected stages and what to prepare for each">
              <div className="space-y-2">
                {application.interview_process.map((step, i) => (
                  <div key={i} className="flex gap-3 bg-surface-50 rounded-lg p-3">
                    <div className="w-8 h-8 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-sm font-bold shrink-0">{i + 1}</div>
                    <div>
                      <div className="text-sm font-semibold text-ink-900">{safeStr(step.stage_name || step.stage || step.who || step.format || (typeof step === "string" ? step : `Round ${i + 1}`))}</div>
                      {step.what_to_expect && <div className="text-[12px] text-ink-500 mt-0.5">{safeStr(step.what_to_expect)}</div>}
                      {step.who && <div className="text-[12px] text-ink-500">Who: {safeStr(step.who)}</div>}
                      {step.format && <div className="text-[12px] text-ink-500">Format: {safeStr(step.format)}</div>}
                      {step.duration && <div className="text-[12px] text-ink-500">Duration: {safeStr(step.duration)}</div>}
                      {step.how_to_prepare && <div className="text-[12px] text-ink-600 mt-1">Prep: {safeStr(step.how_to_prepare)}</div>}
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}
          {company.recent_news && Array.isArray(company.recent_news) && company.recent_news.length > 0 && (
            <Section title="Recent Company News" description="Mention these in your interview to show you've done research">
              {company.recent_news.map((news, i) => (
                <BulletItem key={i} icon="📰" color="ink">{safeStr(news)}</BulletItem>
              ))}
            </Section>
          )}
          {company.hiring_signals && Array.isArray(company.hiring_signals) && company.hiring_signals.length > 0 && (
            <Section title="Hiring Signals" description="Why this company is hiring right now">
              {company.hiring_signals.map((signal, i) => (
                <BulletItem key={i} icon="📡" color="green">{safeStr(signal)}</BulletItem>
              ))}
            </Section>
          )}
        </div>
      )}

      {/* ═══ CONTACTS ═══ */}
      {tab === "contacts" && (
        <div className="space-y-4">
          {/* Connection Path — Find My Way In */}
          <ConnectionPathLoader company={company?.company_name || pack.company_name || ""} role={pack.role_title || ""} />

          {/* Your LinkedIn connections at this company */}
          {linkedinContacts.length > 0 && (
            <Section title="Your Network at This Company" description="People you already know — warm intro paths from your LinkedIn connections">
              <div className="space-y-2">
                {linkedinContacts.map((contact, i) => (
                  <div key={i} className="bg-brand-50 rounded-lg p-3 flex items-start gap-3 border border-brand-100">
                    <div className="w-9 h-9 rounded-full bg-brand-200 text-brand-700 flex items-center justify-center text-sm font-bold shrink-0">
                      {contact.name[0]?.toUpperCase() || "?"}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <div className="text-sm font-semibold text-ink-900">{contact.name}</div>
                        {contact.is_recruiter && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-700 font-medium">Recruiter</span>}
                        {contact.is_hiring_manager && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">Hiring Manager</span>}
                      </div>
                      {contact.title && <div className="text-[12px] text-ink-400">{contact.title}</div>}
                      {contact.linkedin_url && <a href={contact.linkedin_url} target="_blank" rel="noopener" className="text-[12px] text-brand-600 hover:underline">View on LinkedIn →</a>}
                    </div>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium shrink-0">1st</span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Claude-researched contacts */}
          {Array.isArray(networking.named_contacts) && networking.named_contacts.length > 0 && (
            <Section title="Researched Contacts" description="People identified by AI research — reach out via LinkedIn or email">
              <div className="space-y-2">
                {networking.named_contacts.map((contact, i) => (
                  <div key={i} className="bg-surface-50 rounded-lg p-3 flex items-start gap-3">
                    <div className="w-9 h-9 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-sm font-bold shrink-0">
                      {(contact.name || "?")[0].toUpperCase()}
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-ink-900">{contact.name}</div>
                      {contact.title && <div className="text-[12px] text-ink-400">{contact.title}</div>}
                      {contact.relevance && <div className="text-[12px] text-ink-500 mt-0.5">{contact.relevance}</div>}
                      <a href={`https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(contact.name + (contact.title ? " " + contact.title : ""))}`} target="_blank" rel="noopener" className="text-[12px] text-brand-600 hover:underline">Search on LinkedIn →</a>
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}
          {Array.isArray(networking.target_contacts) && networking.target_contacts.length > 0 && (
            <Section title="Target Roles to Find" description="Job titles to search for on LinkedIn">
              {networking.target_contacts.map((title, i) => (
                <BulletItem key={i} icon="🎯" color="brand">{safeStr(title)}</BulletItem>
              ))}
            </Section>
          )}
          {Array.isArray(networking.linkedin_search_strings) && networking.linkedin_search_strings.length > 0 && (
            <Section title="LinkedIn Search Strings" description="Copy-paste these into LinkedIn search">
              {networking.linkedin_search_strings.map((query, i) => (
                <div key={i} className="bg-surface-50 rounded-lg px-3 py-2 text-sm font-mono text-ink-700 mb-1">{query}</div>
              ))}
            </Section>
          )}
          {Array.isArray(networking.seven_day_action_plan) && networking.seven_day_action_plan.length > 0 && (
            <Section title="7-Day Action Plan" description="Step-by-step networking plan for this application">
              <div className="space-y-2">
                {networking.seven_day_action_plan.map((step, i) => (
                  <div key={i} className="flex gap-3 items-start">
                    <div className="w-16 shrink-0">
                      <span className="text-[11px] font-bold text-brand-600 uppercase">Day {step.day || i + 1}</span>
                    </div>
                    <div className="text-sm text-ink-700">{safeStr(step.action || step)}</div>
                  </div>
                ))}
              </div>
            </Section>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-surface-200 p-5">
      <h3 className="text-sm font-bold text-ink-900">{title}</h3>
      <p className="text-[12px] text-ink-400 mb-3">{description}</p>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

function safeStr(val: any): string {
  if (val === null || val === undefined) return "";
  if (typeof val === "string") return val;
  if (typeof val === "number" || typeof val === "boolean") return String(val);
  if (Array.isArray(val)) return val.map(safeStr).join(", ");
  if (typeof val === "object") {
    return Object.entries(val)
      .filter(([, v]) => v !== null && v !== undefined && v !== "")
      .map(([k, v]) => `${k.replace(/_/g, " ")}: ${safeStr(v)}`)
      .join(" · ");
  }
  return String(val);
}

function BulletItem({ icon, color, children }: { icon: string; color: string; children: any }) {
  const colors: Record<string, string> = {
    brand: "text-brand-600",
    green: "text-green-600",
    amber: "text-amber-500",
    red: "text-red-500",
    ink: "text-ink-500",
  };
  const text = typeof children === "object" && children !== null && !children?.$$typeof
    ? safeStr(children)
    : children;
  return (
    <div className="flex gap-2.5 text-sm">
      <span className={`shrink-0 ${colors[color] || "text-ink-400"}`}>{icon}</span>
      <span className="text-ink-700">{text}</span>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface-50 rounded-lg px-3 py-2">
      <div className="text-[10px] font-medium text-ink-400 uppercase">{label}</div>
      <div className="text-sm font-medium text-ink-900">{value}</div>
    </div>
  );
}

function ConnectionPathLoader({ company, role }: { company: string; role: string }) {
  const [loading, setLoading] = useState(false);
  const [keyPeople, setKeyPeople] = useState<any[] | null>(null);

  const AVATAR_COLORS = ["blue", "teal", "amber", "purple", "coral"] as const;
  function assignColor(name: string) { return AVATAR_COLORS[(name.charCodeAt(0) || 0) % 5]; }
  function initials(name: string) { return name.split(" ").map(w => w[0]).join("").toUpperCase().substring(0, 2); }

  async function loadPaths() {
    setLoading(true);
    const token = localStorage.getItem("sr_token");
    try {
      const res = await fetch("/api/v1/relationships/find-way-in", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ company, role }),
      });
      if (!res.ok) { setLoading(false); return; }
      const data = await res.json();

      // Map API response → ConnectionPath keyPeople format
      const people: any[] = [];

      // Direct contacts — separate real 1st-degree from visited profiles
      for (const c of (data.direct_contacts || [])) {
        const isVisited = c.is_visited_profile === true;
        people.push({
          id: c.connection_id || c.name,
          name: c.name,
          role: c.title || "",
          company: c.company || company,
          connectionDegree: isVisited ? 3 : 1,
          linkedinUrl: c.linkedin_url || "",
          avatarInitials: initials(c.name),
          avatarColor: assignColor(c.name),
          connections: [{
            id: (isVisited ? "cold-" : "direct-") + c.name,
            name: c.name,
            role: c.title || "",
            company: c.company || company,
            source: "mutual" as const,
            sourceLabel: isVisited ? "Cold outreach" : "Direct connection",
            avatarInitials: initials(c.name),
            avatarColor: assignColor(c.name),
            linkedinUrl: c.linkedin_url || "",
            suggestedMessage: c.message || (isVisited
              ? `Hi ${c.name.split(" ")[0]}, I came across your profile while researching ${company}. I'd love to connect and learn about the team.`
              : `Hi ${c.name.split(" ")[0]}, I'm exploring the ${role || "opportunity"} at ${company} and would love to connect.`),
          }],
        });
      }

      // Visited targets (from updated backend — cold outreach)
      for (const c of (data.visited_targets || [])) {
        if (people.find(p => p.name === c.name)) continue; // skip duplicates
        people.push({
          id: "visited-" + c.name,
          name: c.name,
          role: c.title || "",
          company: c.company || company,
          connectionDegree: 3,
          linkedinUrl: c.linkedin_url || "",
          avatarInitials: initials(c.name),
          avatarColor: assignColor(c.name),
          connections: [{
            id: "cold-" + c.name,
            name: c.name,
            role: c.title || "",
            company: c.company || company,
            source: "mutual" as const,
            sourceLabel: "Cold outreach",
            avatarInitials: initials(c.name),
            avatarColor: assignColor(c.name),
            linkedinUrl: c.linkedin_url || "",
            suggestedMessage: c.message || `Hi ${c.name.split(" ")[0]}, I came across your profile while researching ${company}. I'd love to connect and learn about the team.`,
          }],
        });
      }

      // Warm paths (2nd degree via mutual connections)
      if (data.best_path) {
        const bp = data.best_path;
        const target = bp.target || {};
        const connector = bp.connector || {};
        people.push({
          id: "path-" + (target.name || "target"),
          name: target.name || "Decision maker",
          role: target.title || "",
          company: target.company || company,
          connectionDegree: 2,
          linkedinUrl: target.linkedin_url || "",
          avatarInitials: initials(target.name || "DM"),
          avatarColor: assignColor(target.name || "DM"),
          connections: [{
            id: "connector-" + connector.name,
            name: connector.name || "",
            role: connector.title || "",
            company: connector.company || "",
            source: "mutual" as const,
            sourceLabel: "Mutual connection",
            avatarInitials: initials(connector.name || "??"),
            avatarColor: assignColor(connector.name || "??"),
            linkedinUrl: connector.linkedin_url || "",
            suggestedMessage: bp.action || `Ask ${connector.name?.split(" ")[0]} to introduce you.`,
          }],
        });
      }
      for (const bp of (data.backup_paths || [])) {
        const target = bp.target || {};
        const connector = bp.connector || {};
        if (target.name && !people.find(p => p.name === target.name)) {
          people.push({
            id: "bpath-" + target.name,
            name: target.name,
            role: target.title || "",
            company: target.company || company,
            connectionDegree: 2,
            linkedinUrl: target.linkedin_url || "",
            avatarInitials: initials(target.name),
            avatarColor: assignColor(target.name),
            connections: [{
              id: "bconn-" + (connector.name || target.name),
              name: connector.name || "",
              role: connector.title || "",
              company: connector.company || "",
              source: "mutual" as const,
              sourceLabel: "Mutual connection",
              avatarInitials: initials(connector.name || "??"),
              avatarColor: assignColor(connector.name || "??"),
              linkedinUrl: connector.linkedin_url || "",
              suggestedMessage: bp.action || "",
            }],
          });
        }
      }

      // Discover targets (not yet visited)
      for (const dt of (data.discover_targets || [])) {
        if (!people.find(p => p.name === dt.name)) {
          people.push({
            id: "discover-" + dt.name,
            name: dt.name,
            role: dt.title || "",
            company: company,
            connectionDegree: 3,
            linkedinUrl: dt.linkedin_url || "",
            avatarInitials: initials(dt.name),
            avatarColor: assignColor(dt.name),
            connections: [],
          });
        }
      }

      setKeyPeople(people);
    } catch (e) {
      console.error("ConnectionPathLoader failed:", e);
    }
    setLoading(false);
  }

  if (!keyPeople && !loading) {
    return (
      <div className="rounded-xl p-5 text-center" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="text-[13px] text-[#8B92B0] mb-3">Find your way into {company || "this company"}</div>
        <button
          onClick={loadPaths}
          className="px-5 py-2.5 text-sm font-semibold text-white rounded-lg"
          style={{ background: "linear-gradient(135deg, #5B6CFF 0%, #7F8CFF 100%)" }}
        >
          Find My Way In
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-end mb-2">
        <button onClick={loadPaths} className="text-[11px] text-[#7F8CFF] font-medium hover:text-white transition-colors">
          Refresh paths
        </button>
      </div>
      <ConnectionPath
        opportunityId=""
        targetCompany={company}
        targetRole={role}
        keyPeople={keyPeople || []}
        loading={loading}
      />
    </div>
  );
}

function FindWayInSection({ company, role }: { company: string; role: string }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  async function findPath() {
    setLoading(true);
    const token = localStorage.getItem("sr_token");
    try {
      const res = await fetch("/api/v1/relationships/find-way-in", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ company, role }),
      });
      if (res.ok) setResult(await res.json());
    } catch { /* ignore */ }
    setLoading(false);
  }

  if (!result) {
    return (
      <div className="bg-violet-50 border border-violet-200 rounded-xl p-5">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-violet-900">Find your way into {company || "this company"}</div>
            <div className="text-[12px] text-violet-600 mt-0.5">Scans your LinkedIn connections for warm paths, recruiters, and intro opportunities</div>
          </div>
          <button
            onClick={findPath}
            disabled={loading}
            className="px-5 py-2.5 text-sm font-semibold text-white rounded-lg shrink-0 disabled:opacity-50"
            style={{ background: "linear-gradient(135deg, #5B6CFF 0%, #7F8CFF 100%)" }}
          >
            {loading ? "Mapping connections..." : "Find My Way In"}
          </button>
        </div>
      </div>
    );
  }

  const { direct_contacts = [], visited_targets = [], best_path, backup_paths = [], recommended_action, total_direct } = result;
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  function copyMsg(msg: string, idx: number) {
    navigator.clipboard.writeText(msg).then(() => { setCopiedIdx(idx); setTimeout(() => setCopiedIdx(null), 2000); });
  }

  return (
    <div className="space-y-3">
      {/* Recommended Action */}
      <div className="bg-violet-50 border border-violet-200 rounded-xl p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="text-[11px] font-medium text-violet-600 uppercase">Recommended Action</div>
          <button onClick={() => { setResult(null); findPath(); }} className="text-[11px] text-violet-600 hover:text-violet-700 font-medium">Refresh</button>
        </div>
        <div className="text-sm font-semibold text-violet-900">{recommended_action}</div>
      </div>

      {/* Best Way In */}
      {best_path && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
          <div className="text-[11px] font-medium text-emerald-600 uppercase mb-3">Best Way In</div>
          {/* Visual path chain */}
          <div className="flex items-center gap-1.5 flex-wrap mb-3">
            <span className="text-[11px] px-2.5 py-1 rounded-md bg-violet-100 text-violet-700 font-semibold">You</span>
            {best_path.connector && (
              <>
                <span className="text-ink-300 text-[10px]">→</span>
                <span className="text-[11px] px-2.5 py-1 rounded-md bg-blue-50 text-blue-700 font-medium">{best_path.connector.name}</span>
              </>
            )}
            {best_path.target && (
              <>
                <span className="text-ink-300 text-[10px]">→</span>
                <span className="text-[11px] px-2.5 py-1 rounded-md bg-emerald-100 text-emerald-700 font-medium">{best_path.target.name || best_path.target.title}</span>
              </>
            )}
          </div>
          {best_path.target && (
            <div className="bg-white border border-emerald-100 rounded-lg p-3 mb-2">
              <div className="text-[10px] font-medium text-ink-400 uppercase mb-1">Target</div>
              <div className="text-sm font-semibold text-ink-900">{best_path.target.name || best_path.target.title}</div>
              {best_path.target.title && best_path.target.name && <div className="text-[12px] text-ink-400">{best_path.target.title}</div>}
              <div className="text-[11px] text-emerald-700 mt-0.5">{best_path.target.why_target}</div>
            </div>
          )}
          {best_path.connector && (
            <div className="bg-white border border-emerald-100 rounded-lg p-3 mb-2">
              <div className="text-[10px] font-medium text-ink-400 uppercase mb-1">Your Connector</div>
              <div className="text-sm font-semibold text-ink-900">{best_path.connector.name}</div>
              <div className="text-[12px] text-ink-400">{best_path.connector.title} at {best_path.connector.company}</div>
            </div>
          )}
          <div className="text-[12px] text-ink-700 mt-1">{best_path.reason}</div>
          <div className="mt-2 bg-white border border-emerald-100 rounded-lg p-3">
            <div className="text-[11px] font-bold text-emerald-700">{best_path.action}</div>
          </div>
          {best_path.strength && (
            <span className={`inline-block mt-2 text-[10px] font-medium px-2 py-0.5 rounded-full ${best_path.strength === "strong" ? "bg-emerald-100 text-emerald-700" : best_path.strength === "medium" ? "bg-amber-100 text-amber-700" : "bg-surface-200 text-ink-500"}`}>
              {best_path.strength} path
            </span>
          )}
        </div>
      )}

      {/* Alternative Paths */}
      {backup_paths.length > 0 && (
        <div className="bg-white border border-surface-200 rounded-xl p-4">
          <div className="text-[11px] font-medium text-amber-600 uppercase mb-3">Alternative Paths</div>
          <div className="space-y-3">
            {backup_paths.map((p: any, i: number) => (
              <div key={i} className="bg-amber-50 border border-amber-100 rounded-lg p-3">
                <div className="flex items-center gap-1.5 flex-wrap mb-1.5">
                  {p.path?.split(" → ").map((node: string, ni: number, arr: string[]) => (
                    <span key={ni} className="contents">
                      <span className={`text-[11px] px-2 py-0.5 rounded font-medium ${ni === 0 ? "bg-violet-100 text-violet-700" : "bg-white text-ink-700"}`}>{node}</span>
                      {ni < arr.length - 1 && <span className="text-ink-300 text-[10px]">→</span>}
                    </span>
                  ))}
                </div>
                <div className="text-[12px] text-ink-600">{p.reason}</div>
                <div className="text-[11px] font-semibold text-amber-700 mt-1">{p.action}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Direct Contacts (1st degree) */}
      {direct_contacts.length > 0 && (
        <div className="bg-white border border-surface-200 rounded-xl p-4">
          <div className="text-[11px] font-medium text-blue-600 uppercase mb-3">Your Direct Contacts at {company} ({total_direct})</div>
          <div className="space-y-3">
            {direct_contacts.map((c: any, i: number) => (
              <div key={i} className="pb-3 border-b border-surface-100 last:border-0 last:pb-0">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-bold shrink-0">
                    {c.name?.[0]?.toUpperCase() || "?"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-ink-900">{c.name}</span>
                      {c.is_recruiter && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-medium">Recruiter</span>}
                      {c.is_hiring_manager && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">Decision Maker</span>}
                    </div>
                    <div className="text-[12px] text-ink-400">{c.title}</div>
                    {c.intro_angle && <div className="text-[11px] text-emerald-600 mt-1">{c.intro_angle}</div>}
                    {c.linkedin_url && (
                      <a href={c.linkedin_url} target="_blank" rel="noopener" className="text-[11px] text-violet-600 hover:underline mt-0.5 inline-block">Message on LinkedIn →</a>
                    )}
                  </div>
                </div>
                {c.message && (
                  <div className="ml-12 mt-2">
                    <div className="text-[11px] text-ink-500 p-2.5 rounded-lg bg-surface-50 border border-surface-100 leading-relaxed">{c.message}</div>
                    <button onClick={() => copyMsg(c.message, i)} className="mt-1 text-[10px] font-medium text-violet-600 hover:text-violet-700">
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
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <div className="text-[11px] font-medium text-amber-700 uppercase mb-1">People You've Researched at {company} ({result.total_visited})</div>
          <div className="text-[12px] text-ink-400 mb-3">You visited these profiles — here's how to reach out cold.</div>
          <div className="space-y-3">
            {visited_targets.map((c: any, i: number) => (
              <div key={i} className="bg-white border border-amber-100 rounded-lg p-3">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-sm font-bold shrink-0">
                    {c.name?.[0]?.toUpperCase() || "?"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-ink-900">{c.name}</span>
                      {c.is_hiring_manager && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">Decision Maker</span>}
                      {c.is_recruiter && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-medium">Recruiter</span>}
                      <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-surface-100 text-ink-400 font-medium">Cold outreach</span>
                    </div>
                    <div className="text-[12px] text-ink-400">{c.title}</div>
                    {c.intro_angle && <div className="text-[11px] text-amber-700 mt-1">{c.intro_angle}</div>}
                    {c.linkedin_url && (
                      <a href={c.linkedin_url} target="_blank" rel="noopener" className="text-[11px] text-violet-600 hover:underline mt-0.5 inline-block">Connect on LinkedIn →</a>
                    )}
                  </div>
                </div>
                {c.message && (
                  <div className="ml-12 mt-2">
                    <div className="text-[11px] text-ink-500 p-2.5 rounded-lg bg-surface-50 border border-surface-100 leading-relaxed">{c.message}</div>
                    <button onClick={() => copyMsg(c.message, 100 + i)} className="mt-1 text-[10px] font-medium text-amber-700 hover:text-amber-800">
                      {copiedIdx === 100 + i ? "Copied!" : "Copy outreach message"}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Discover targets — visit their profiles to map paths */}
      {result.discover_targets?.length > 0 && !best_path && (
        <div className="bg-white border border-surface-200 rounded-xl p-4">
          <div className="text-[11px] font-medium text-violet-600 uppercase mb-2">Visit these profiles to map your paths</div>
          <div className="text-[12px] text-ink-400 mb-3">Click a profile → the extension saves them and checks for mutual connections. Then hit <strong className="text-violet-600">Refresh</strong> above.</div>
          <div className="space-y-2">
            {result.discover_targets.map((person: any, i: number) => (
              <a key={i} href={person.linkedin_url} target="_blank" rel="noopener" className="flex items-center gap-3 p-3 rounded-lg bg-violet-50 border border-violet-100 hover:bg-violet-100 transition-colors">
                <div className="w-9 h-9 rounded-full bg-violet-200 text-violet-700 flex items-center justify-center text-sm font-bold shrink-0">
                  {person.name?.[0]?.toUpperCase() || "?"}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-ink-900">{person.name}</div>
                  {person.title && <div className="text-[12px] text-ink-400">{person.title}</div>}
                </div>
                <span className="text-[11px] text-violet-600 font-medium shrink-0">Visit profile →</span>
              </a>
            ))}
          </div>
          <div className="mt-3 text-center">
            <button onClick={() => { setResult(null); findPath(); }} className="text-[11px] font-semibold text-violet-600 hover:text-violet-700 px-4 py-1.5 rounded-lg border border-violet-200 hover:bg-violet-50 transition-all">
              I visited profiles — refresh
            </button>
          </div>
        </div>
      )}

      {!best_path && direct_contacts.length === 0 && visited_targets.length === 0 && (!result.discover_targets || result.discover_targets.length === 0) && (
        <div className="bg-surface-50 rounded-xl p-5 text-center">
          <div className="text-sm text-ink-500">No verified paths found for {company}.</div>
          <div className="text-[12px] text-ink-400 mt-1">Search LinkedIn for people at {company} and visit their profiles with the StealthRole extension installed.</div>
        </div>
      )}
    </div>
  );
}
