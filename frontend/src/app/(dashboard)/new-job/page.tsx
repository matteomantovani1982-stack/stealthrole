"use client";

import { useEffect, useState } from "react";
import {
  listCVs,
  createJobRun,
  getJobRun,
  getDownloadUrl,
  generateOutreach,
  type JobRun,
} from "@/lib/api";

type Step = "input" | "processing" | "done" | "error";

export default function NewJobPage() {
  const [cvs, setCvs] = useState<{ id: string; original_filename: string; status: string }[]>([]);
  const [selectedCv, setSelectedCv] = useState("");
  const [jdText, setJdText] = useState("");
  const [jdUrl, setJdUrl] = useState("");
  const [region, setRegion] = useState("UAE");
  const [step, setStep] = useState<Step>("input");
  const [jobRun, setJobRun] = useState<JobRun | null>(null);
  const [error, setError] = useState("");
  const [downloadUrl, setDownloadUrl] = useState("");
  const [outreach, setOutreach] = useState<{ linkedin_note: string; cold_email: string; follow_up: string } | null>(null);

  useEffect(() => {
    listCVs().then((data) => {
      const parsed = (data || []).filter((cv) => cv.status === "parsed");
      setCvs(parsed);
      if (parsed.length > 0) setSelectedCv(parsed[0].id);
    }).catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedCv) { setError("Upload and parse a CV first (go to Profile page)"); return; }
    if (!jdText.trim() && !jdUrl.trim()) { setError("Provide a job description"); return; }

    setStep("processing");
    setError("");

    try {
      const run = await createJobRun({
        cv_id: selectedCv,
        jd_text: jdText.trim() || undefined,
        jd_url: jdUrl.trim() || undefined,
        preferences: { region },
      });
      setJobRun(run);

      const pollInterval = setInterval(async () => {
        try {
          const updated = await getJobRun(run.id);
          setJobRun(updated);
          if (updated.status === "completed" || updated.status === "failed") {
            clearInterval(pollInterval);
            if (updated.status === "completed") {
              setStep("done");
              try { const dl = await getDownloadUrl(run.id); setDownloadUrl(dl.download_url); } catch {}
              if (updated.company_name && updated.role_title) {
                try {
                  const o = await generateOutreach({ company: updated.company_name, role: updated.role_title, jd_text: jdText || undefined });
                  setOutreach(o);
                } catch {}
              }
            } else {
              setStep("error");
              setError(updated.error_message || "Generation failed");
            }
          }
        } catch {
          clearInterval(pollInterval);
          setStep("error");
          setError("Lost connection while processing");
        }
      }, 2000);
    } catch (err: unknown) {
      setStep("error");
      setError(err instanceof Error ? err.message : "Failed to start");
    }
  }

  // Extract report sections for display
  const reports = jobRun?.reports as Record<string, unknown> | undefined;
  const positioning = jobRun?.positioning as Record<string, unknown> | undefined;
  const company = reports?.company as Record<string, unknown> | undefined;
  const salary = reports?.salary as Record<string, unknown> | undefined;
  const networking = reports?.networking as Record<string, unknown> | undefined;
  const application = reports?.application as Record<string, unknown> | undefined;
  const execSummary = reports?.exec_summary as Record<string, unknown> | undefined;

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold text-ink-900">New Intelligence Pack</h1>

      {/* INPUT */}
      {step === "input" && (
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="bg-white rounded-xl border border-surface-200 p-5">
            <label className="text-sm font-semibold text-ink-900 block mb-2">Select CV</label>
            {cvs.length > 0 ? (
              <select value={selectedCv} onChange={(e) => setSelectedCv(e.target.value)} className="w-full px-3 py-2.5 rounded-lg border border-surface-200 text-sm bg-white">
                {cvs.map((cv) => <option key={cv.id} value={cv.id}>{cv.original_filename}</option>)}
              </select>
            ) : (
              <div className="text-sm text-ink-400 bg-surface-50 rounded-lg p-4 text-center">
                No parsed CVs. <a href="/profile" className="text-brand-600 font-medium">Upload a CV first</a>
              </div>
            )}
          </div>
          <div className="bg-white rounded-xl border border-surface-200 p-5">
            <label className="text-sm font-semibold text-ink-900 block mb-2">Job Description</label>
            <input type="url" value={jdUrl} onChange={(e) => setJdUrl(e.target.value)} placeholder="Paste job posting URL" className="w-full px-3 py-2.5 rounded-lg border border-surface-200 text-sm mb-3" />
            <div className="text-center text-[12px] text-ink-400 mb-3">or paste text</div>
            <textarea value={jdText} onChange={(e) => setJdText(e.target.value)} placeholder="Paste full job description..." rows={8} className="w-full px-3 py-2.5 rounded-lg border border-surface-200 text-sm resize-none" />
          </div>
          <div className="bg-white rounded-xl border border-surface-200 p-5">
            <label className="text-sm font-semibold text-ink-900 block mb-2">Region</label>
            <select value={region} onChange={(e) => setRegion(e.target.value)} className="w-full px-3 py-2.5 rounded-lg border border-surface-200 text-sm bg-white">
              {["UAE", "KSA", "EU", "US", "APAC", "OTHER"].map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          {error && <div className="px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm">{error}</div>}
          <button type="submit" disabled={!selectedCv} className="w-full py-3 bg-brand-600 text-white text-base font-semibold rounded-xl hover:bg-brand-700 disabled:opacity-50">
            Generate Intelligence Pack
          </button>
        </form>
      )}

      {/* PROCESSING */}
      {step === "processing" && (
        <div className="bg-white rounded-xl border border-surface-200 p-8 text-center">
          <div className="w-10 h-10 border-[3px] border-brand-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <div className="text-lg font-semibold text-ink-900 mb-2">Generating Intelligence Pack</div>
          <div className="text-sm text-ink-400 mb-4">
            {jobRun?.status === "created" && "Starting..."}
            {jobRun?.status === "parsing" && "Parsing your CV..."}
            {jobRun?.status === "retrieving" && "Researching the company..."}
            {jobRun?.status === "llm_processing" && "AI building your strategy..."}
            {jobRun?.status === "rendering" && "Generating tailored DOCX..."}
          </div>
        </div>
      )}

      {/* RESULTS */}
      {step === "done" && jobRun && (
        <div className="space-y-5">
          {/* Header */}
          <div className="bg-green-50 border border-green-200 rounded-xl p-5">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-lg font-semibold text-green-800">{jobRun.role_title || "Role"} at {jobRun.company_name || "Company"}</div>
                <div className="text-sm text-green-700">Intelligence Pack ready {jobRun.keyword_match_score ? `\u2014 ${jobRun.keyword_match_score}% keyword match` : ""}</div>
              </div>
              {downloadUrl && (
                <a href={downloadUrl} target="_blank" rel="noopener" className="px-5 py-2.5 bg-green-700 text-white text-sm font-semibold rounded-lg hover:bg-green-800 shrink-0">
                  Download CV
                </a>
              )}
            </div>
          </div>

          {/* Executive Summary */}
          {execSummary && (
            <Section title="Executive Summary">
              <div className="text-sm text-ink-700 whitespace-pre-wrap">{JSON.stringify(execSummary, null, 2)}</div>
            </Section>
          )}

          {/* Positioning / Strategy */}
          {positioning && (
            <Section title="Positioning Strategy">
              {(positioning as Record<string, unknown>).headline ? (
                <div className="text-base font-semibold text-brand-700 mb-3">{String((positioning as Record<string, unknown>).headline)}</div>
              ) : null}
              {renderKeyValue(positioning, ["headline"])}
            </Section>
          )}

          {/* Company Intelligence */}
          {company && (
            <Section title="Company Intelligence">
              {renderKeyValue(company)}
            </Section>
          )}

          {/* Salary */}
          {salary && (
            <Section title="Salary & Compensation">
              {renderKeyValue(salary)}
            </Section>
          )}

          {/* Interview Prep */}
          {application && (
            <Section title="Interview & Application Strategy">
              {renderKeyValue(application)}
            </Section>
          )}

          {/* Networking */}
          {networking && (
            <Section title="Networking & Contacts">
              {renderKeyValue(networking)}
            </Section>
          )}

          {/* Outreach */}
          {outreach && (
            <Section title="Ready-to-Send Outreach">
              <div className="space-y-3">
                <div>
                  <div className="text-[11px] text-ink-400 uppercase mb-1">LinkedIn Note</div>
                  <div className="bg-surface-50 rounded-lg p-3 text-sm text-ink-700">{outreach.linkedin_note}</div>
                </div>
                <div>
                  <div className="text-[11px] text-ink-400 uppercase mb-1">Cold Email</div>
                  <div className="bg-surface-50 rounded-lg p-3 text-sm text-ink-700 whitespace-pre-wrap">{outreach.cold_email}</div>
                </div>
                <div>
                  <div className="text-[11px] text-ink-400 uppercase mb-1">Follow-Up</div>
                  <div className="bg-surface-50 rounded-lg p-3 text-sm text-ink-700 whitespace-pre-wrap">{outreach.follow_up}</div>
                </div>
              </div>
            </Section>
          )}

          <button onClick={() => { setStep("input"); setJobRun(null); setOutreach(null); setDownloadUrl(""); setJdText(""); setJdUrl(""); }}
            className="w-full py-2.5 border border-surface-300 text-ink-700 text-sm font-semibold rounded-xl hover:bg-surface-100">
            Generate Another
          </button>
        </div>
      )}

      {/* ERROR */}
      {step === "error" && (
        <div className="bg-white rounded-xl border border-surface-200 p-8 text-center">
          <div className="text-lg font-semibold text-ink-900 mb-2">Generation Failed</div>
          <div className="text-sm text-red-600 mb-4">{error}</div>
          <button onClick={() => setStep("input")} className="px-6 py-2.5 bg-brand-600 text-white text-sm font-semibold rounded-lg hover:bg-brand-700">Try Again</button>
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-surface-200 p-5">
      <h3 className="text-base font-semibold text-ink-900 mb-3">{title}</h3>
      {children}
    </div>
  );
}

function renderKeyValue(obj: Record<string, unknown>, skip: string[] = []) {
  return (
    <div className="space-y-2">
      {Object.entries(obj).filter(([k]) => !skip.includes(k)).map(([key, value]) => {
        const label = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
        if (value === null || value === undefined || value === "") return null;
        if (Array.isArray(value)) {
          if (value.length === 0) return null;
          return (
            <div key={key}>
              <div className="text-[11px] text-ink-400 uppercase mb-1">{label}</div>
              {typeof value[0] === "object" ? (
                <div className="space-y-1.5">
                  {value.map((item, i) => (
                    <div key={i} className="bg-surface-50 rounded-lg p-2.5 text-sm text-ink-700">
                      {typeof item === "object" ? Object.entries(item as Record<string, unknown>).map(([k, v]) => (
                        <div key={k}><span className="font-medium">{k.replace(/_/g, " ")}:</span> {String(v)}</div>
                      )) : String(item)}
                    </div>
                  ))}
                </div>
              ) : (
                <ul className="list-disc list-inside text-sm text-ink-700 space-y-0.5">
                  {value.map((item, i) => <li key={i}>{String(item)}</li>)}
                </ul>
              )}
            </div>
          );
        }
        if (typeof value === "object") {
          return (
            <div key={key}>
              <div className="text-[11px] text-ink-400 uppercase mb-1">{label}</div>
              <div className="bg-surface-50 rounded-lg p-2.5 text-sm text-ink-700">
                {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
                  <div key={k}><span className="font-medium">{k.replace(/_/g, " ")}:</span> {String(v)}</div>
                ))}
              </div>
            </div>
          );
        }
        return (
          <div key={key}>
            <div className="text-[11px] text-ink-400 uppercase mb-1">{label}</div>
            <div className="text-sm text-ink-700">{String(value)}</div>
          </div>
        );
      })}
    </div>
  );
}
