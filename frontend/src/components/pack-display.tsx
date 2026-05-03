"use client";

import { useState } from "react";
import type { JobRun } from "@/lib/api";
import { getAuthHeaders } from "@/lib/utils";
import ConnectionPathPanel from "./connection-path";
import FindWayInPanel from "./find-way-in";

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
  baseCompany?: string;
  baseRole?: string;
  baseApplicationId?: string;
  applicationUrl?: string;
  /** True when job run reports do not match the application card (wrong pack linked) */
  packContentMismatch?: boolean;
}

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "strategy", label: "Strategy" },
  { id: "strengths", label: "Strengths" },
  { id: "salary", label: "Salary" },
  { id: "interview", label: "Interview" },
  { id: "contacts", label: "Contacts" },
];

export default function PackDisplay({ pack, downloadUrl, linkedinContacts = [], baseCompany = "", baseRole = "", baseApplicationId = "", applicationUrl = "", packContentMismatch = false }: Props) {
  const [tab, setTab] = useState("overview");
  const reports = (pack.reports || {}) as Record<string, any>;
  const positioning = (pack.positioning || {}) as Record<string, any>;

  const company = reports.company || {};
  const salary = Array.isArray(reports.salary) ? reports.salary[0] || {} : reports.salary || {};
  const networking = reports.networking || {};
  const application = reports.application || {};
  const effectiveCompany = (baseCompany || pack.company_name || company.company_name || "").trim();
  const effectiveRole = (baseRole || pack.role_title || company.role_title || "").trim();
  const wayInRoleContext = [
    baseRole,
    pack.role_title,
    application?.title,
    application?.job_title,
    application?.position_title,
  ]
    .filter((v, i, arr) => !!v && arr.indexOf(v) === i)
    .join(" | ");
  const postingUrl =
    (applicationUrl && String(applicationUrl).trim())
    || (application?.source_url as string | undefined)
    || (application?.job_url as string | undefined)
    || (application?.url as string | undefined)
    || ((pack as any)?.jd_url as string | undefined)
    || null;
  const jobSearchUrl =
    effectiveCompany && effectiveRole
      ? `https://www.google.com/search?q=${encodeURIComponent(`${effectiveRole} at ${effectiveCompany} job`)}`
      : null;
  const execSummary = Array.isArray(reports.exec_summary) ? reports.exec_summary : [];
  const looksLikeSpecificPerson = (value: string) => {
    const s = (value || "").trim();
    if (!s) return false;
    const genericHints = /(recruiter|hiring manager|hr|talent|panel|team|founder|leadership|manager|director|vp|head|interviewer)/i;
    if (genericHints.test(s)) return false;
    // Heuristic: "First Last" style name with capitals.
    return /^[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?\s+[A-Z][a-z]+/.test(s);
  };

  const sanitizeActionStep = (value: string) => {
    const s = safeStr(value || "");
    if (!s) return s;
    // Remove hard assumptions that target a specific person by name.
    return s
      .replace(/\bMessage [A-Z][a-z]+(?:[-'][A-Z][a-z]+)?\s+[A-Z][a-z]+[^.]*\./g, "Message the most relevant hiring manager or recruiter with a warm, specific ask.")
      .replace(/\bFollow up with [A-Z][a-z]+(?:[-'][A-Z][a-z]+)?\b/g, "Follow up with the relevant hiring contact");
  };

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
            <div className="text-lg font-bold text-ink-900">{effectiveRole || "Role"}</div>
            <div className="text-sm text-ink-400">{effectiveCompany || "Company"}</div>
          </div>
        </div>
        {downloadUrl && (
          <a href={downloadUrl} target="_blank" rel="noopener" className="px-4 py-2 bg-brand-600 text-white text-sm font-semibold rounded-lg hover:bg-brand-700 transition-colors">
            Download Tailored CV
          </a>
        )}
        <div className="flex flex-wrap items-center gap-2">
          {postingUrl && (
            <a href={postingUrl} target="_blank" rel="noopener" className="px-4 py-2 bg-surface-100 text-ink-700 text-sm font-semibold rounded-lg hover:bg-surface-200 transition-colors">
              View JD Source
            </a>
          )}
          {!postingUrl && jobSearchUrl && (
            <a href={jobSearchUrl} target="_blank" rel="noopener" className="px-4 py-2 bg-surface-100 text-ink-700 text-sm font-semibold rounded-lg hover:bg-surface-200 transition-colors">
              Find job posting
            </a>
          )}
        </div>
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
          {packContentMismatch && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              Executive summary is hidden because the stored pack does not match this application. Use <strong>Regenerate pack</strong> above, then
              return to this page.
            </div>
          )}
          {!packContentMismatch && execSummary.length > 0 && (
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
          {(effectiveCompany || company.company_name) && (
            <Section title="Company Snapshot" description="What you need to know about this company">
              <div className="grid grid-cols-2 gap-2">
                <InfoRow label="Company" value={effectiveCompany || company.company_name} />
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
              {positioning.key_differentiators.map((item: string, i: number) => (
                <BulletItem key={i} icon="✓" color="green">{item}</BulletItem>
              ))}
            </Section>
          )}
          {Array.isArray(application.differentiators) && application.differentiators.length > 0 && (
            <Section title="Key Differentiators" description="Competitive advantages vs other candidates">
              {application.differentiators.map((item: string, i: number) => (
                <BulletItem key={i} icon="◆" color="brand">{item}</BulletItem>
              ))}
            </Section>
          )}
          {Array.isArray(application.risks_to_address) && application.risks_to_address.length > 0 && (
            <Section title="Weaknesses & Risks" description="Gaps to address proactively in your application">
              {application.risks_to_address.map((item: string, i: number) => (
                <BulletItem key={i} icon="⚠" color="amber">{item}</BulletItem>
              ))}
            </Section>
          )}
          {Array.isArray(application.gaps) && application.gaps.length > 0 && (
            <Section title="Skill Gaps" description="Areas where you may need to upskill or frame differently">
              {application.gaps.map((item: string, i: number) => (
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
          {packContentMismatch && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              Interview steps below may describe the wrong company until you <strong>Regenerate pack</strong> for {effectiveCompany || "this application"}.
            </div>
          )}
          {Array.isArray(application.interview_process) && application.interview_process.length > 0 && (
            <Section title="Interview Process" description="Expected stages and what to prepare for each">
              <div className="space-y-2">
                {application.interview_process.map((step: Record<string, string>, i: number) => (
                  <div key={i} className="flex gap-3 bg-surface-50 rounded-lg p-3">
                    <div className="w-8 h-8 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-sm font-bold shrink-0">{i + 1}</div>
                    <div>
                      <div className="text-sm font-semibold text-ink-900">{safeStr(step.stage_name || step.stage || step.who || step.format || (typeof step === "string" ? step : `Round ${i + 1}`))}</div>
                      {step.what_to_expect && <div className="text-[12px] text-ink-500 mt-0.5">{safeStr(step.what_to_expect)}</div>}
                      {step.who && !looksLikeSpecificPerson(safeStr(step.who)) && (
                        <div className="text-[12px] text-ink-500">Who: {safeStr(step.who)}</div>
                      )}
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
              {company.recent_news.map((news: string, i: number) => (
                <BulletItem key={i} icon="📰" color="ink">{safeStr(news)}</BulletItem>
              ))}
            </Section>
          )}
          {company.hiring_signals && Array.isArray(company.hiring_signals) && company.hiring_signals.length > 0 && (
            <Section title="Hiring Signals" description="Why this company is hiring right now">
              {company.hiring_signals.map((signal: string, i: number) => (
                <BulletItem key={i} icon="📡" color="green">{safeStr(signal)}</BulletItem>
              ))}
            </Section>
          )}
        </div>
      )}

      {/* ═══ CONTACTS ═══ */}
      {tab === "contacts" && (
        <div className="space-y-4">
          {/* Connection Path — Find My Way In (shared component, always-open mode) */}
          <FindWayInPanel
            company={effectiveCompany}
            role={wayInRoleContext || effectiveRole || ""}
            applicationId={baseApplicationId || undefined}
            headers={getAuthHeaders(false)}
            alwaysOpen={true}
          />

          {/* 7-Day Action Plan */}
          {Array.isArray(networking.seven_day_action_plan) && networking.seven_day_action_plan.length > 0 && (
            <Section title="7-Day Action Plan" description="Step-by-step networking plan for this application">
              <div className="space-y-2">
                {networking.seven_day_action_plan.map((step: Record<string, string>, i: number) => (
                  <div key={i} className="flex gap-3 items-start">
                    <div className="w-16 shrink-0">
                      <span className="text-[11px] font-bold text-brand-600 uppercase">Day {step.day || i + 1}</span>
                    </div>
                    <div className="text-sm text-ink-700">{sanitizeActionStep(safeStr(step.action || step))}</div>
                  </div>
                ))}
              </div>
            </Section>
          )}
          {/* LinkedIn Search Strings */}
          {Array.isArray(networking.linkedin_search_strings) && networking.linkedin_search_strings.length > 0 && (
            <Section title="LinkedIn Search Strings" description="Copy-paste these into LinkedIn search">
              {networking.linkedin_search_strings.map((query: string, i: number) => (
                <div key={i} className="bg-surface-50 rounded-lg px-3 py-2 text-sm font-mono text-ink-700 mb-1">{query}</div>
              ))}
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

// ── Dead code removed: ConnectionPathLoader (~214 lines) and FindWayInSection (~241 lines)
// Both were superseded by the FindWayInPanel component import.
