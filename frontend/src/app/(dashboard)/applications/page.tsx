"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getBoard,
  getApplicationAnalytics,
  createApplication,
  updateApplicationStage,
  deleteApplication,
  updateApplication,
  extractJD,
  createJobRun,
  getJobRun,
  getDownloadUrl,
  listCVs,
  uploadCV,
  type ApplicationItem,
  type BoardResponse,
  type ApplicationAnalytics,
  type JobRun,
} from "@/lib/api";
import KanbanColumn from "@/components/kanban-column";
import Modal from "@/components/modal";
import StatCard from "@/components/stat-card";
import PackDisplay from "@/components/pack-display";

const STAGES = ["watching", "applied", "interview", "offer", "rejected"];
const SOURCES = ["linkedin", "indeed", "glassdoor", "referral", "company_site", "recruiter", "job_board", "other"];

function _extractCompanyFromUrl(url: string): string | null {
  try {
    // boards.greenhouse.io/stripe/jobs/123 → "Stripe"
    const ghMatch = url.match(/boards\.greenhouse\.io\/([^/]+)/);
    if (ghMatch) return ghMatch[1].replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    // jobs.lever.co/stripe/123 → "Stripe"
    const leverMatch = url.match(/jobs\.lever\.co\/([^/]+)/);
    if (leverMatch) return leverMatch[1].replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    // apply.workable.com/stripe/j/123 → "Stripe"
    const wkMatch = url.match(/apply\.workable\.com\/([^/]+)/);
    if (wkMatch) return wkMatch[1].replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    // jobs.ashbyhq.com/stripe/123 → "Stripe"
    const ashbyMatch = url.match(/jobs\.ashbyhq\.com\/([^/]+)/);
    if (ashbyMatch) return ashbyMatch[1].replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    // myworkdayjobs.com/stripe → "Stripe"
    const wdMatch = url.match(/myworkdayjobs\.com\/([^/]+)/);
    if (wdMatch) return wdMatch[1].replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  } catch {}
  return null;
}

export default function ApplicationsPage() {
  const [board, setBoard] = useState<BoardResponse | null>(null);
  const [analytics, setAnalytics] = useState<ApplicationAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [selected, setSelected] = useState<ApplicationItem | null>(null);
  // Add form state
  const [addUrl, setAddUrl] = useState("");
  const [addCompany, setAddCompany] = useState("");
  const [addRole, setAddRole] = useState("");
  const [addJdText, setAddJdText] = useState("");
  const [extracting, setExtracting] = useState(false);
  // CV state
  const [cvs, setCvs] = useState<{ id: string; original_filename: string; status: string }[]>([]);
  const [selectedCvId, setSelectedCvId] = useState("");
  const [uploadingCv, setUploadingCv] = useState(false);
  // Pack state
  const [packMessage, setPackMessage] = useState("");
  const [generatingPack, setGeneratingPack] = useState(false);
  const [packStep, setPackStep] = useState(0); // 0=idle, 1-5=steps
  const packCancelledRef = useRef(false);
  const [showPackModal, setShowPackModal] = useState<ApplicationItem | null>(null);
  const [packJdText, setPackJdText] = useState("");
  const [packJdUrl, setPackJdUrl] = useState("");
  const [loadedPack, setLoadedPack] = useState<JobRun | null>(null);
  const [packDownloadUrl, setPackDownloadUrl] = useState("");
  const [linkedinContacts, setLinkedinContacts] = useState<{ name: string; title: string | null; is_recruiter: boolean; is_hiring_manager: boolean; linkedin_url: string | null }[]>([]);

  const refresh = useCallback(() => {
    Promise.allSettled([
      getBoard().then(setBoard),
      getApplicationAnalytics().then(setAnalytics),
      listCVs().then((data) => {
        const parsed = (data || []).filter((c) => c.status === "parsed");
        setCvs(parsed);
        if (parsed.length > 0 && !selectedCvId) setSelectedCvId(parsed[0].id);
      }).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, [selectedCvId]);

  useEffect(() => { refresh(); }, [refresh]);

  async function handleDrop(appId: string, newStage: string) {
    await updateApplicationStage(appId, newStage).catch(console.error);
    refresh();
  }

  async function handleCardClick(app: ApplicationItem) {
    setSelected(app);
    setLoadedPack(null);
    setPackDownloadUrl("");
    setLinkedinContacts([]);

    // Fetch LinkedIn connections at this company
    try {
      const token = localStorage.getItem("sr_token");
      const res = await fetch(`/api/v1/relationships/company/${encodeURIComponent(app.company)}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setLinkedinContacts((data.people || []).map((p: Record<string, unknown>) => ({
          name: p.name,
          title: p.title,
          is_recruiter: p.is_recruiter,
          is_hiring_manager: p.is_hiring_manager,
          linkedin_url: p.linkedin_url,
        })));
      }
    } catch {}

    // If app has a pack, load it and poll if not complete
    if (app.job_run_id) {
      try {
        const pack = await getJobRun(app.job_run_id);
        setLoadedPack(pack);
        if (pack.status === "completed") {
          try { const dl = await getDownloadUrl(app.job_run_id); setPackDownloadUrl(dl.download_url); } catch {}
        } else if (app.job_run_id) {
          // Auto-poll every 15 seconds until complete
          const jrId = app.job_run_id;
          const pollId = setInterval(async () => {
            try {
              const updated = await getJobRun(jrId);
              setLoadedPack(updated);
              if (updated.status === "completed" || updated.status === "failed") {
                clearInterval(pollId);
                if (updated.status === "completed") {
                  try { const dl = await getDownloadUrl(jrId); setPackDownloadUrl(dl.download_url); } catch {}
                }
              }
            } catch { clearInterval(pollId); }
          }, 15000);
          // Clear on unmount
          setTimeout(() => clearInterval(pollId), 600000); // Max 10 minutes
        }
      } catch {}
    }
  }

  // URL auto-extract
  async function handleUrlBlur(url: string) {
    const trimmed = url.trim();
    if (!trimmed || !["linkedin.com/jobs", "greenhouse.io", "lever.co", "workday.com", "ashbyhq.com"].some((p) => trimmed.includes(p))) return;
    // Try extracting company from URL pattern first (instant)
    const urlCompany = _extractCompanyFromUrl(trimmed);
    if (urlCompany && !addCompany) setAddCompany(urlCompany);

    // Auto-detect source from URL
    if (trimmed.includes("linkedin.com")) {
      const sourceEl = document.querySelector<HTMLSelectElement>("select[name='source']");
      if (sourceEl) sourceEl.value = "linkedin";
    }

    setExtracting(true);
    try {
      const result = await extractJD(trimmed);
      if (result.jd_text) {
        setAddJdText(result.jd_text);
        const lines = result.jd_text.split("\n").filter((l: string) => l.trim());
        const firstLine = lines[0] || "";
        // Try multiple patterns to extract role + company
        const atMatch = firstLine.match(/^(.+?)\s+(?:at|@|-)\s+(.+)$/i);
        if (atMatch) {
          if (!addRole) setAddRole(atMatch[1].trim());
          if (!addCompany) setAddCompany(atMatch[2].trim());
        } else {
          if (!addRole && firstLine.length < 100) setAddRole(firstLine.trim());
          if (!addCompany && lines[1] && lines[1].length < 80) setAddCompany(lines[1].trim());
        }
        // If still no company, try from JD text patterns
        if (!addCompany) {
          const aboutMatch = result.jd_text.match(/(?:About|Join)\s+([A-Z][\w\s&.-]+?)(?:\n|\.)/);
          if (aboutMatch) setAddCompany(aboutMatch[1].trim());
        }
      }
    } catch {} finally { setExtracting(false); }
  }

  // Upload CV inline
  async function handleCvUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingCv(true);
    try {
      const result = await uploadCV(file);
      // Poll until parsed
      for (let i = 0; i < 20; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const updated = await listCVs();
        const cv = (updated || []).find((c) => c.id === result.id);
        if (cv?.status === "parsed") {
          setCvs((updated || []).filter((c) => c.status === "parsed"));
          setSelectedCvId(result.id);
          break;
        }
        if (cv?.status === "failed") throw new Error("Parse failed");
      }
    } catch (err: unknown) {
      setPackMessage(err instanceof Error ? err.message : "CV upload failed");
    } finally { setUploadingCv(false); }
  }

  const PACK_STEPS = [
    "", // 0 = idle
    "Analysing job description...",
    "Matching to your profile...",
    "Generating strategy & intel...",
    "Building contact paths...",
    "Finalising pack...",
  ];

  function cancelPackGeneration() {
    packCancelledRef.current = true;
    setGeneratingPack(false);
    setPackStep(0);
    setPackMessage("Pack generation cancelled.");
    setTimeout(() => setPackMessage(""), 4000);
  }

  async function pollPackWithProgress(runId: string, company: string) {
    const POLL_INTERVAL = 5000;
    const TIMEOUT_MS = 3 * 60 * 1000; // 3 minutes
    const startTime = Date.now();
    let timedOut = false;

    for (let i = 0; i < 120; i++) {
      if (packCancelledRef.current) return;
      await new Promise((r) => setTimeout(r, POLL_INTERVAL));
      if (packCancelledRef.current) return;

      const elapsed = Date.now() - startTime;

      // Update progress step based on elapsed time
      if (elapsed < 15000) setPackStep(1);
      else if (elapsed < 40000) setPackStep(2);
      else if (elapsed < 90000) setPackStep(3);
      else if (elapsed < 140000) setPackStep(4);
      else setPackStep(5);

      try {
        const updated = await getJobRun(runId);

        if (updated.status === "completed") {
          setPackStep(0);
          setPackMessage(`Pack ready for ${company}! Click the card to view.`);
          refresh();
          return;
        }
        if (updated.status === "failed") {
          setPackStep(0);
          setPackMessage(`Pack generation failed: ${updated.error_message || "Unknown error"}. Your credits have not been charged.`);
          return;
        }

        // Check timeout
        if (elapsed > TIMEOUT_MS && !timedOut) {
          timedOut = true;
          setPackMessage(`Taking longer than expected for ${company}. We'll notify you when it's ready — you can navigate away.`);
        }
      } catch {
        // Network error — keep polling
      }
    }
    // Max polls reached
    setPackStep(0);
    setPackMessage(`Pack for ${company} is still processing. Check back shortly.`);
  }

  // Create application + auto-generate pack
  async function handleAdd(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    if (!addCompany || !addRole) return;
    try {
      const app = await createApplication({
        company: addCompany,
        role: addRole,
        date_applied: new Date().toISOString(),
        source_channel: fd.get("source") as string,
        stage: fd.get("stage") as string || "watching",
        url: addUrl || undefined,
        notes: (fd.get("notes") as string) || undefined,
      });
      setShowAdd(false);

      // Auto-trigger pack if we have JD + CV
      if ((addJdText || addUrl) && selectedCvId) {
        setGeneratingPack(true);
        setPackStep(1);
        packCancelledRef.current = false;
        setPackMessage(`Generating Intelligence Pack for ${addCompany}...`);
        try {
          const run = await createJobRun({
            cv_id: selectedCvId,
            jd_text: addJdText || undefined,
            jd_url: addUrl || undefined,
          });
          // Link job run to application — retry up to 3 times
          for (let retry = 0; retry < 3; retry++) {
            try {
              await updateApplication(app.id, { job_run_id: run.id } as Partial<ApplicationItem>);
              break;
            } catch (linkErr) {
              console.error(`Link attempt ${retry + 1} failed:`, linkErr);
              await new Promise((r) => setTimeout(r, 1000));
            }
          }
          await pollPackWithProgress(run.id, addCompany);
        } catch (err: unknown) {
          setPackMessage(err instanceof Error ? err.message : "Pack generation failed. Your credits have not been charged.");
        }
        setGeneratingPack(false);
        setPackStep(0);
        setTimeout(() => setPackMessage(""), 8000);
      }

      setAddUrl(""); setAddCompany(""); setAddRole(""); setAddJdText("");
      refresh();
    } catch (err) {
      console.error("Create failed:", err);
    }
  }

  // Generate pack — opens JD modal if no URL on the application
  async function handleGeneratePack(app: ApplicationItem) {
    // If pack already generating/exists, just show it
    if (app.job_run_id) {
      handleCardClick(app);
      return;
    }
    if (!selectedCvId) { setPackMessage("Upload a CV first on the Profile page before generating a pack."); setTimeout(() => setPackMessage(""), 5000); return; }

    // Auto-generate pack directly — no dialog needed
    setGeneratingPack(true);
    setPackStep(1);
    packCancelledRef.current = false;
    setPackMessage(`Generating pack for ${app.company}...`);
    try {
      const jdText = app.notes || `${app.role} at ${app.company}`;
      const run = await createJobRun({
        cv_id: selectedCvId,
        jd_text: jdText,
        jd_url: app.url || undefined,
      });
      // Link job run to application
      for (let retry = 0; retry < 3; retry++) {
        try { await updateApplication(app.id, { job_run_id: run.id } as any); break; } catch { await new Promise(r => setTimeout(r, 1000)); }
      }
      // Update the app in local state so it doesn't show Generate Pack again
      const updatedApp = { ...app, job_run_id: run.id };
      setSelected(updatedApp);
      // Refresh board
      const freshBoard = await getBoard();
      setBoard(freshBoard);
      // Poll with progress
      await pollPackWithProgress(run.id, app.company);
      // Load the pack
      try {
        const pack = await getJobRun(run.id);
        setLoadedPack(pack);
      } catch {}
    } catch (err: any) {
      setPackMessage(`Pack failed: ${err.message || "Unknown error"}. Your credits have not been charged.`);
    }
    setGeneratingPack(false);
    setPackStep(0);
  }

  async function handleRunPack() {
    if (!showPackModal) return;
    if (!selectedCvId) { setPackMessage("Upload a CV first on the Profile page before generating a pack."); setTimeout(() => setPackMessage(""), 5000); setShowPackModal(null); return; }
    const app = showPackModal;
    const jdText = packJdText.trim() || `${app.role} at ${app.company}`;
    const jdUrl = packJdUrl.trim() || undefined;
    const appId = app.id;
    setShowPackModal(null);
    setGeneratingPack(true);
    setPackStep(1);
    packCancelledRef.current = false;
    setPackMessage(`Generating pack for ${app.company}...`);
    try {
      const run = await createJobRun({
        cv_id: selectedCvId,
        jd_text: jdText,
        jd_url: jdUrl,
      });
      // Link job run to application — retry up to 3 times
      for (let retry = 0; retry < 3; retry++) {
        try { await updateApplication(appId, { job_run_id: run.id } as Partial<ApplicationItem>); break; }
        catch (linkErr) { console.error(`Link attempt ${retry + 1}:`, linkErr); await new Promise((r) => setTimeout(r, 1000)); }
      }
      await pollPackWithProgress(run.id, app.company);
    } catch (err: unknown) {
      setPackMessage(err instanceof Error ? err.message : "Pack generation failed. Your credits have not been charged.");
    } finally {
      setGeneratingPack(false);
      setPackStep(0);
      setTimeout(() => setPackMessage(""), 8000);
    }
  }

  async function handleDelete(id: string) {
    await deleteApplication(id).catch(console.error);
    setSelected(null);
    refresh();
  }

  const interviewCount = analytics?.by_stage?.find((s) => s.stage === "interview")?.count ?? 0;
  const offerCount = analytics?.by_stage?.find((s) => s.stage === "offer")?.count ?? 0;
  const avgDays = analytics?.avg_days_to_interview;

  const COL_STYLES: Record<string, { color: string; light: string; headerBg: string; headerBorder: string; bodyBg: string; bodyBorder: string; badgeBg: string; cardBg: string; cardBorder: string; label: string }> = {
    watching:  { color: "#fbbf24", light: "#fcd34d", headerBg: "rgba(251,191,36,0.12)", headerBorder: "0.5px solid rgba(251,191,36,0.25)", bodyBg: "rgba(251,191,36,0.04)", bodyBorder: "0.5px solid rgba(251,191,36,0.15)", badgeBg: "rgba(251,191,36,0.18)", cardBg: "rgba(251,191,36,0.08)", cardBorder: "1px solid rgba(251,191,36,0.2)", label: "Watching" },
    applied:   { color: "#4d8ef5", light: "#93c5fd", headerBg: "rgba(77,142,245,0.12)", headerBorder: "0.5px solid rgba(77,142,245,0.25)", bodyBg: "rgba(77,142,245,0.04)", bodyBorder: "0.5px solid rgba(77,142,245,0.15)", badgeBg: "rgba(77,142,245,0.18)", cardBg: "rgba(77,142,245,0.09)", cardBorder: "1px solid rgba(77,142,245,0.25)", label: "Applied" },
    interview: { color: "#a78bfa", light: "#c4b5fd", headerBg: "rgba(167,139,250,0.12)", headerBorder: "0.5px solid rgba(167,139,250,0.25)", bodyBg: "rgba(167,139,250,0.04)", bodyBorder: "0.5px solid rgba(167,139,250,0.15)", badgeBg: "rgba(167,139,250,0.18)", cardBg: "rgba(167,139,250,0.1)", cardBorder: "1px solid rgba(167,139,250,0.28)", label: "Interview" },
    offer:     { color: "#22c55e", light: "#86efac", headerBg: "rgba(34,197,94,0.1)", headerBorder: "0.5px solid rgba(34,197,94,0.22)", bodyBg: "rgba(34,197,94,0.03)", bodyBorder: "0.5px solid rgba(34,197,94,0.12)", badgeBg: "rgba(34,197,94,0.15)", cardBg: "rgba(34,197,94,0.08)", cardBorder: "1px solid rgba(34,197,94,0.2)", label: "Offer" },
    rejected:  { color: "#ef4444", light: "#fca5a5", headerBg: "rgba(239,68,68,0.1)", headerBorder: "0.5px solid rgba(239,68,68,0.2)", bodyBg: "rgba(239,68,68,0.03)", bodyBorder: "0.5px solid rgba(239,68,68,0.1)", badgeBg: "rgba(239,68,68,0.15)", cardBg: "rgba(239,68,68,0.06)", cardBorder: "1px solid rgba(239,68,68,0.18)", label: "Closed" },
  };

  const totalActive = (analytics?.total_applications ?? 0) - (analytics?.by_stage?.find(s => s.stage === "rejected")?.count ?? 0);
  const followUpCount = board?.columns?.find(c => c.stage === "applied")?.applications?.filter(a => {
    const d = a.date_applied ? (Date.now() - new Date(a.date_applied).getTime()) / 86400000 : 0;
    return d >= 3;
  }).length ?? 0;

  return (
    <div>
      <style jsx global>{`
        @keyframes appCardSlide { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>

      {/* Topbar */}
      <div style={{ padding: "16px 24px", borderBottom: "0.5px solid rgba(255,255,255,0.05)", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <h1 style={{ fontSize: 20, fontWeight: 500, color: "#fff", margin: 0 }}>Applications</h1>
          {[
            { label: "interviews", count: interviewCount, color: "#c4b5fd", bg: "rgba(167,139,250,0.1)", border: "rgba(167,139,250,0.25)" },
            { label: "follow-ups due", count: followUpCount, color: "#fcd34d", bg: "rgba(251,191,36,0.1)", border: "rgba(251,191,36,0.25)" },
            { label: "total active", count: totalActive, color: "#93c5fd", bg: "rgba(77,142,245,0.1)", border: "rgba(77,142,245,0.25)" },
          ].map((p, i) => (
            <span key={i} style={{ fontSize: 11, padding: "4px 12px", borderRadius: 14, border: `0.5px solid ${p.border}`, background: p.bg, color: "rgba(255,255,255,0.5)" }}>
              <span style={{ color: p.color, fontWeight: 500 }}>{p.count}</span> {p.label}
            </span>
          ))}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={refresh} style={{ background: "rgba(255,255,255,0.04)", color: "rgba(255,255,255,0.6)", border: "0.5px solid rgba(255,255,255,0.1)", borderRadius: 10, padding: "8px 14px", fontSize: 11, fontWeight: 500, cursor: "pointer" }}>Refresh</button>
          <button onClick={() => setShowAdd(true)} style={{ background: "#4d8ef5", color: "#fff", border: "none", borderRadius: 10, padding: "8px 14px", fontSize: 11, fontWeight: 600, cursor: "pointer" }}>+ Add application</button>
        </div>
      </div>

      {/* Pack generation progress banner */}
      {(packMessage || generatingPack) && (
        <div style={{ margin: "12px 24px", padding: "14px 18px", borderRadius: 12, background: "rgba(77,142,245,0.1)", border: "0.5px solid rgba(77,142,245,0.25)" }}>
          {generatingPack && packStep > 0 ? (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "#93c5fd" }}>Building your Intelligence Pack</span>
                <button onClick={cancelPackGeneration} style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", background: "rgba(255,255,255,0.06)", border: "0.5px solid rgba(255,255,255,0.1)", borderRadius: 6, padding: "3px 10px", cursor: "pointer" }}>Cancel</button>
              </div>
              <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
                {[1, 2, 3, 4, 5].map((step) => (
                  <div key={step} style={{ flex: 1, height: 3, borderRadius: 2, background: step <= packStep ? "#4d8ef5" : "rgba(255,255,255,0.08)", transition: "background 0.3s" }} />
                ))}
              </div>
              <div style={{ fontSize: 11, color: packStep >= 4 ? "#93c5fd" : "rgba(255,255,255,0.4)" }}>
                Step {packStep}/5: {PACK_STEPS[packStep]}
              </div>
            </div>
          ) : (
            <div style={{ fontSize: 12, color: packMessage.includes("failed") || packMessage.includes("cancelled") ? "#fca5a5" : "#93c5fd" }}>{packMessage}</div>
          )}
        </div>
      )}

      {/* Kanban */}
      <div style={{ display: "flex", gap: 14, padding: "16px 24px", overflowX: "auto", alignItems: "flex-start" }}>
        {loading ? (
          STAGES.map(s => <div key={s} style={{ width: 220, height: 400, borderRadius: 14, background: "rgba(255,255,255,0.04)" }} className="animate-pulse" />)
        ) : (
          STAGES.map((stage) => {
            const col = board?.columns.find((c) => c.stage === stage);
            const apps = col?.applications ?? [];
            const cs = COL_STYLES[stage] || COL_STYLES.watching;
            return (
              <div key={stage} style={{ width: 220, flexShrink: 0 }}
                onDragOver={(e) => { e.preventDefault(); e.currentTarget.style.outline = `2px solid ${cs.color}44`; }}
                onDragLeave={(e) => { e.currentTarget.style.outline = "none"; }}
                onDrop={(e) => { e.currentTarget.style.outline = "none"; const id = e.dataTransfer.getData("text/plain"); if (id) handleDrop(id, stage); }}
              >
                {/* Header */}
                <div style={{ background: cs.headerBg, border: cs.headerBorder, borderBottom: "none", borderRadius: "10px 10px 0 0", padding: "10px 14px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5, color: cs.light }}>{cs.label}</span>
                  <span style={{ fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 8, background: cs.badgeBg, color: cs.light }}>{apps.length}</span>
                </div>
                {/* Body */}
                <div style={{ background: cs.bodyBg, border: cs.bodyBorder, borderTop: "none", borderRadius: "0 0 12px 12px", padding: "8px 6px 6px", minHeight: 120, display: "flex", flexDirection: "column", gap: 8 }}>
                  {apps.length === 0 && stage === "offer" && (
                    <div style={{ padding: "24px 10px", textAlign: "center" }}>
                      <div style={{ fontSize: 28, opacity: 0.12, marginBottom: 6 }}>🏆</div>
                      <div style={{ fontSize: 10, color: `${cs.light}40`, lineHeight: 1.5 }}>Your offer lands here.</div>
                    </div>
                  )}
                  {apps.map((app, idx) => (
                    <div key={app.id}
                      draggable
                      onDragStart={(e) => e.dataTransfer.setData("text/plain", app.id)}
                      onClick={() => handleCardClick(app)}
                      style={{
                        background: cs.cardBg, border: cs.cardBorder, borderRadius: 12,
                        padding: 13, cursor: "pointer", transition: "transform 0.15s",
                        margin: "0 6px", opacity: stage === "rejected" ? 0.7 : 1,
                        animation: `appCardSlide 0.3s ease ${idx * 0.03}s both`,
                      }}
                      onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.transform = "translateY(-2px)"; }}
                      onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.transform = "translateY(0)"; }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                        <div style={{ width: 28, height: 28, borderRadius: 7, background: `${cs.color}26`, color: cs.light, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700 }}>
                          {(app.company || "?").split(" ").map(w => w[0]).join("").substring(0, 2).toUpperCase()}
                        </div>
                        {app.job_run_id && <span style={{ fontSize: 8, padding: "2px 5px", borderRadius: 5, background: "rgba(34,197,94,0.15)", color: "#86efac", fontWeight: 600 }}>Pack</span>}
                      </div>
                      <div style={{ fontSize: 12, fontWeight: 500, color: "#fff", marginBottom: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{app.role || "Role"}</div>
                      <div style={{ fontSize: 10, color: "rgba(255,255,255,0.4)", marginBottom: 6, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{app.company}</div>
                      <div style={{ fontSize: 9, color: "rgba(255,255,255,0.25)" }}>{app.date_applied ? new Date(app.date_applied).toLocaleDateString("en-GB", { month: "short", day: "numeric" }) : ""}</div>
                      <div style={{ display: "flex", gap: 4, marginTop: 6 }}>
                        {!app.job_run_id && (
                          <button onClick={(e) => { e.stopPropagation(); handleGeneratePack(app); }} disabled={generatingPack}
                            style={{ fontSize: 9, fontWeight: 600, padding: "3px 7px", borderRadius: 6, background: `${cs.color}2e`, color: cs.light, border: "none", cursor: "pointer", opacity: generatingPack ? 0.5 : 1 }}>
                            Gen Pack
                          </button>
                        )}
                        <button onClick={(e) => { e.stopPropagation(); handleCardClick(app); }}
                          style={{ fontSize: 9, fontWeight: 500, padding: "3px 7px", borderRadius: 6, background: "rgba(255,255,255,0.04)", color: "rgba(255,255,255,0.5)", border: "0.5px solid rgba(255,255,255,0.06)", cursor: "pointer" }}>
                          View
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* ── ADD MODAL ── */}
      <Modal open={showAdd} onClose={() => { setShowAdd(false); setAddUrl(""); setAddCompany(""); setAddRole(""); setAddJdText(""); }} title="Add Application">
        <form onSubmit={handleAdd} className="space-y-3">
          {/* URL with auto-extract */}
          <div className="relative">
            <input value={addUrl} onChange={(e) => setAddUrl(e.target.value)} onBlur={(e) => handleUrlBlur(e.target.value)} onPaste={(e) => { const p = e.clipboardData.getData("text"); setTimeout(() => handleUrlBlur(p), 100); }}
              placeholder="Job URL (paste to auto-fill company + role)" className={`w-full px-3 py-2 rounded-lg border text-sm ${extracting ? "border-amber-400 bg-amber-50/30" : "border-surface-200"}`} />
            {extracting && <div className="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-amber-600">Extracting...</div>}
          </div>

          {/* Auto-filled fields */}
          {extracting && <div className="text-[12px] text-amber-600 bg-amber-50 rounded-lg px-3 py-2">Extracting job details from URL...</div>}
          {addJdText && !extracting && <div className="text-[12px] text-green-600 bg-green-50 rounded-lg px-3 py-2">Job description extracted ({addJdText.length} chars)</div>}

          <div className="grid grid-cols-2 gap-2">
            <input value={addCompany} onChange={(e) => setAddCompany(e.target.value)} required placeholder="Company" className="px-3 py-2 rounded-lg border border-surface-200 text-sm" />
            <input value={addRole} onChange={(e) => setAddRole(e.target.value)} required placeholder="Role / Title" className="px-3 py-2 rounded-lg border border-surface-200 text-sm" />
          </div>

          {/* JD text area — paste directly or auto-filled from URL */}
          <div>
            <div className="text-[11px] font-medium text-ink-500 uppercase mb-1">Job Description (paste or auto-filled from URL)</div>
            <textarea value={addJdText} onChange={(e) => setAddJdText(e.target.value)} placeholder="Paste the full job description here, or it will be auto-extracted from the URL above..." rows={4} className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm resize-none" />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <select name="stage" className="px-3 py-2 rounded-lg border border-surface-200 text-sm bg-white">
              <option value="watching">Watching</option>
              <option value="applied">Applied</option>
            </select>
            <select name="source" required className="px-3 py-2 rounded-lg border border-surface-200 text-sm bg-white">
              {SOURCES.map((s) => <option key={s} value={s}>{s.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}</option>)}
            </select>
          </div>

          {/* CV selector + upload */}
          <div className="bg-surface-50 rounded-lg p-3">
            <div className="text-[11px] font-medium text-ink-500 uppercase mb-1.5">CV for Intelligence Pack</div>
            {cvs.length > 0 ? (
              <select value={selectedCvId} onChange={(e) => setSelectedCvId(e.target.value)} className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm bg-white mb-2">
                {cvs.map((cv) => <option key={cv.id} value={cv.id}>{cv.original_filename}</option>)}
              </select>
            ) : (
              <div className="text-sm text-ink-400 mb-2">No CVs uploaded yet</div>
            )}
            <label className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-surface-300 rounded-lg text-[12px] text-ink-700 cursor-pointer hover:bg-surface-100 transition-colors">
              {uploadingCv ? "Uploading..." : "Upload new CV"}
              <input type="file" accept=".pdf,.docx,.doc" onChange={handleCvUpload} disabled={uploadingCv} className="hidden" />
            </label>
          </div>

          <textarea name="notes" placeholder="Notes (optional)" rows={2} className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm resize-none" />

          <button type="submit" disabled={extracting || uploadingCv} className="w-full py-2.5 bg-brand-600 text-white text-sm font-semibold rounded-lg hover:bg-brand-700 disabled:opacity-50">
            {(addJdText || addUrl) && selectedCvId ? "Add + Generate Pack" : "Add Application"}
          </button>
        </form>
      </Modal>

      {/* ── DETAIL MODAL (shows pack if exists) ── */}
      <Modal open={!!selected} onClose={() => { setSelected(null); setLoadedPack(null); }} title={selected ? `${selected.company} — ${selected.role}` : ""} size={loadedPack ? "full" : "default"}>
        {selected && (
          <div className="space-y-4 max-h-[70vh] overflow-y-auto">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-ink-400 capitalize">{selected.stage} · {selected.source_channel} · {new Date(selected.date_applied).toLocaleDateString()}</div>
              </div>
              {packDownloadUrl && (
                <a href={packDownloadUrl} target="_blank" rel="noopener" className="px-3 py-1.5 bg-green-700 text-white text-xs font-semibold rounded-lg hover:bg-green-800">Download CV</a>
              )}
            </div>

            {/* Pack content */}
            {loadedPack && loadedPack.reports ? (
              <PackDisplay pack={loadedPack} downloadUrl={packDownloadUrl || undefined} linkedinContacts={linkedinContacts} />
            ) : selected.job_run_id ? (
              <div className="text-center py-8">
                <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                <div className="text-sm text-ink-400">
                  {loadedPack?.status === "llm_processing" ? "AI is analyzing this opportunity..." :
                   loadedPack?.status === "rendering" ? "Building your documents..." :
                   loadedPack?.status === "retrieving" ? "Researching the company..." :
                   "Preparing your Intelligence Pack..."}
                </div>
                <div className="text-[11px] text-ink-300 mt-1">This usually takes 2-3 minutes</div>
                <button onClick={async () => {
                  if (!selected?.job_run_id) return;
                  try {
                    const pack = await getJobRun(selected.job_run_id);
                    setLoadedPack(pack);
                    if (pack.status === "completed" && pack.reports) {
                      try { const dl = await getDownloadUrl(selected.job_run_id); setPackDownloadUrl(dl.download_url); } catch {}
                    }
                  } catch {}
                }} className="mt-3 text-[12px] text-brand-600 hover:text-brand-700 font-medium">Check status</button>
              </div>
            ) : null}

            {/* No pack yet */}
            {!selected.job_run_id && (
              <div className="text-center py-4">
                <div className="text-sm text-ink-400 mb-3">No Intelligence Pack generated yet</div>
                <button onClick={() => handleGeneratePack(selected)} disabled={generatingPack} className="px-4 py-2 text-sm text-white bg-brand-600 hover:bg-brand-700 rounded-lg font-medium disabled:opacity-50">
                  {generatingPack ? `Step ${packStep}/5...` : "Generate Pack"}
                </button>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2 pt-2 border-t border-surface-200">
              {selected.url && <a href={selected.url} target="_blank" rel="noopener" className="px-3 py-1.5 text-sm text-brand-600 hover:bg-brand-50 rounded-lg">Job Posting</a>}
              <button onClick={() => handleDelete(selected.id)} className="px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded-lg ml-auto">Delete</button>
            </div>
          </div>
        )}
      </Modal>

      {/* ── PACK JD MODAL ── */}
      <Modal open={!!showPackModal} onClose={() => setShowPackModal(null)} title={showPackModal ? `Generate Pack — ${showPackModal.company}` : ""}>
        <div className="space-y-3">
          <p className="text-sm text-ink-500">Paste the job description or URL to generate an Intelligence Pack.</p>
          <input value={packJdUrl} onChange={(e) => setPackJdUrl(e.target.value)} placeholder="Job posting URL" className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm" />
          <div className="text-center text-[11px] text-ink-400">or paste text</div>
          <textarea value={packJdText} onChange={(e) => setPackJdText(e.target.value)} placeholder="Paste full job description..." rows={6} className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm resize-none" />
          {cvs.length > 0 && (
            <div>
              <div className="text-[11px] font-medium text-ink-500 uppercase mb-1">CV</div>
              <select value={selectedCvId} onChange={(e) => setSelectedCvId(e.target.value)} className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm bg-white">
                {cvs.map((cv) => <option key={cv.id} value={cv.id}>{cv.original_filename}</option>)}
              </select>
            </div>
          )}
          <button onClick={handleRunPack} disabled={generatingPack} className="w-full py-2.5 bg-brand-600 text-white text-sm font-semibold rounded-lg hover:bg-brand-700 disabled:opacity-50">
            Generate Intelligence Pack
          </button>
        </div>
      </Modal>
    </div>
  );
}

/* PackDisplay component handles all pack rendering */
