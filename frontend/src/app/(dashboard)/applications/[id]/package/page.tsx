// @ts-nocheck
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getAuthHeaders } from "@/lib/utils";
import {
  getApplication,
  getJobRun,
  getDownloadUrl,
  createJobRun,
  updateApplication,
  listCVs,
  type ApplicationItem,
  type JobRun,
} from "@/lib/api";
import PackDisplay from "@/components/pack-display";

function normEntity(v: string | null | undefined): string {
  return (v || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
}

function entitiesClash(a: string, b: string): boolean {
  const x = normEntity(a);
  const y = normEntity(b);
  if (!x || !y) return false;
  return !(x === y || x.includes(y) || y.includes(x));
}

/** True when the stored job run / report was generated for a different app than this tracker row. */
function computePackContentMismatch(
  application: ApplicationItem | null,
  packData: JobRun | null
): boolean {
  if (!application || !packData) return false;
  const reports: any = packData.reports || {};
  const packCo =
    (packData as any).company_name ||
    reports?.company?.company_name ||
    "";
  const packRo =
    (packData as any).role_title ||
    reports?.role?.role_title ||
    "";
  const companyBad =
    !!String(application.company).trim() &&
    !!String(packCo).trim() &&
    entitiesClash(application.company, String(packCo));
  const roleBad =
    !!String(application.role).trim() &&
    !!String(packRo).trim() &&
    entitiesClash(application.role, String(packRo));
  return companyBad || roleBad;
}

const STAGE_COLORS: Record<string, { bg: string; text: string }> = {
  watching: { bg: "#78350f", text: "#fbbf24" },
  applied: { bg: "#1e3a5f", text: "#60a5fa" },
  interview: { bg: "#3b1f6e", text: "#a78bfa" },
  offer: { bg: "#14532d", text: "#4ade80" },
  rejected: { bg: "#7f1d1d", text: "#f87171" },
};

export default function PackagePage() {
  const params = useParams();
  const router = useRouter();
  const appId = params.id as string;

  const [app, setApp] = useState<ApplicationItem | null>(null);
  const [pack, setPack] = useState<JobRun | null>(null);
  const [downloadUrl, setDownloadUrl] = useState("");
  const [linkedinContacts, setLinkedinContacts] = useState<
    {
      name: string;
      title: string | null;
      is_recruiter: boolean;
      is_hiring_manager: boolean;
      linkedin_url: string | null;
    }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [progressStep, setProgressStep] = useState(0); // 0=idle, 1-5=steps
  const [generating, setGenerating] = useState(false);
  const [showWorkerHint, setShowWorkerHint] = useState(false);

  useEffect(() => {
    const inProgress =
      generating ||
      (pack != null &&
        pack.status !== "completed" &&
        pack.status !== "failed");
    if (!inProgress) {
      setShowWorkerHint(false);
      return;
    }
    const t = window.setTimeout(() => setShowWorkerHint(true), 45000);
    return () => window.clearTimeout(t);
  }, [generating, pack?.status, pack?.id]);

  useEffect(() => {
    let pollId: ReturnType<typeof setInterval> | null = null;
    let progressId: ReturnType<typeof setInterval> | null = null;
    let cancelled = false;
    let consecutivePollFailures = 0;

    async function startProgress() {
      let step = 1;
      setProgressStep(step);
      progressId = setInterval(() => {
        step = Math.min(step + 1, 5);
        setProgressStep(step);
        if (step >= 5 && progressId) clearInterval(progressId);
      }, 12000);
    }

    async function pollPack(jobRunId: string) {
      try {
        const updated = await getJobRun(jobRunId);
        if (cancelled) return;
        consecutivePollFailures = 0;
        setPack(updated);
        if (updated.status === "completed") {
          if (pollId) clearInterval(pollId);
          if (progressId) clearInterval(progressId);
          setProgressStep(0);
          setGenerating(false);
          try {
            const dl = await getDownloadUrl(jobRunId);
            setDownloadUrl(dl.download_url);
          } catch {}
        } else if (updated.status === "failed") {
          if (pollId) clearInterval(pollId);
          if (progressId) clearInterval(progressId);
          setProgressStep(0);
          setGenerating(false);
          setError("Pack generation failed: " + (updated.error_message || "unknown error") + ". Your credits have not been charged.");
        }
      } catch (e: any) {
        consecutivePollFailures += 1;
        if (consecutivePollFailures >= 8) {
          if (pollId) clearInterval(pollId);
          if (progressId) clearInterval(progressId);
          setProgressStep(0);
          setGenerating(false);
          setError(
            "Could not read pack status (API unreachable or signed out). " +
              (e?.message || "Try refreshing.")
          );
        }
      }
    }

    async function startGeneration(application: ApplicationItem) {
      // Need a parsed CV
      const cvs = await listCVs().catch(() => []);
      const cv = (cvs || []).find((c: any) => c.status === "parsed");
      if (!cv) {
        setError("Upload a CV on the Profile page before generating a pack.");
        setLoading(false);
        return;
      }
      setGenerating(true);
      startProgress();
      try {
        const jdText = `Role: ${application.role}\nCompany: ${application.company}${application.url ? `\n\nSource: ${application.url}` : ""}${application.notes ? `\n\n${application.notes}` : ""}`;
        const job = await createJobRun({
          cv_id: cv.id,
          jd_text: jdText,
          jd_url: application.url || undefined,
          preferences: { tone: "executive", region: "UAE" },
        } as any);
        // Link the job_run to the application
        try {
          await updateApplication(application.id, { job_run_id: job.id } as any);
        } catch {}
        setPack(job as any);
        // Start polling
        pollId = setInterval(() => pollPack(job.id), 4000);
      } catch (e: any) {
        setError("Failed to start pack generation: " + (e?.message || "unknown error"));
        setGenerating(false);
        setProgressStep(0);
      }
    }

    async function loadData() {
      try {
        // 1. Fetch the application directly by ID (not via board — avoids race condition)
        let found: ApplicationItem | null = null;
        try {
          found = await getApplication(appId);
        } catch (e: any) {
          // Retry once after short delay (DB transaction may not be committed yet)
          await new Promise((r) => setTimeout(r, 1500));
          try {
            found = await getApplication(appId);
          } catch (e2: any) {
            setError("Application not found: " + (e2?.message || ""));
            setLoading(false);
            return;
          }
        }
        setApp(found);
        setLoading(false);

        // 2. Fetch LinkedIn contacts (best-effort, non-blocking)
        try {
          const res = await fetch(
            `/api/v1/relationships/company/${encodeURIComponent(found.company)}`,
            { headers: getAuthHeaders(false) }
          );
          if (res.ok) {
            const data = await res.json();
            setLinkedinContacts(
              (data.people || []).map((p: Record<string, unknown>) => ({
                name: p.name,
                title: p.title,
                is_recruiter: p.is_recruiter,
                is_hiring_manager: p.is_hiring_manager,
                linkedin_url: p.linkedin_url,
              }))
            );
          }
        } catch {}

        // 3. If pack already exists, load it; otherwise auto-start generation
        if (found.job_run_id) {
          try {
            const packData = await getJobRun(found.job_run_id);
            if (computePackContentMismatch(found, packData)) {
              // Linked pack is stale/wrong (e.g. from another application).
              // Regenerate from THIS application context and relink.
              await startGeneration(found);
              return;
            }
            setPack(packData);
            if (packData.status === "completed") {
              try {
                const dl = await getDownloadUrl(found.job_run_id);
                setDownloadUrl(dl.download_url);
              } catch {}
            } else if (packData.status === "failed") {
              setError("Pack generation failed: " + (packData.error_message || "unknown error"));
            } else {
              // Still processing — show progress and poll
              setGenerating(true);
              startProgress();
              pollId = setInterval(() => pollPack(found!.job_run_id!), 4000);
            }
          } catch (e: any) {
            setError("Failed to load pack: " + (e?.message || "unknown"));
          }
        } else {
          // No pack yet — auto-generate one
          await startGeneration(found);
        }
      } catch (e: any) {
        setError("Failed to load: " + (e?.message || "unknown error"));
        setLoading(false);
      }
    }

    loadData();
    return () => {
      cancelled = true;
      if (pollId) clearInterval(pollId);
      if (progressId) clearInterval(progressId);
    };
  }, [appId]);

  const PROGRESS_STEPS = [
    "",
    "Analysing job description...",
    "Matching to your profile...",
    "Building application strategy...",
    "Generating contact paths...",
    "Finalising your pack...",
  ];

  // Loading state (initial fetch)
  if (loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "#03040f",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            width: 40,
            height: 40,
            border: "3px solid rgba(255,255,255,0.1)",
            borderTopColor: "#60a5fa",
            borderRadius: "50%",
            animation: "spin 0.8s linear infinite",
          }}
        />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  // Generation in progress — show step progress
  if (generating || (pack && pack.status !== "completed" && pack.status !== "failed")) {
    return (
      <div style={{ minHeight: "100vh", background: "#03040f", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 24 }}>
        <div style={{ maxWidth: 520, width: "100%", textAlign: "center" }}>
          <div style={{ fontSize: 22, fontWeight: 600, color: "#fff", marginBottom: 8 }}>
            Generating your Intelligence Pack
          </div>
          <div style={{ fontSize: 14, color: "rgba(255,255,255,0.5)", marginBottom: 32 }}>
            for {app?.role} at {app?.company}
          </div>

          {/* Step bars */}
          <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
            {[1, 2, 3, 4, 5].map((step) => (
              <div
                key={step}
                style={{
                  flex: 1,
                  height: 4,
                  borderRadius: 2,
                  background: step <= progressStep ? "#4d8ef5" : "rgba(255,255,255,0.08)",
                  transition: "background 0.4s",
                }}
              />
            ))}
          </div>
          <div style={{ fontSize: 13, color: "#93c5fd", marginBottom: 24 }}>
            Step {Math.max(1, progressStep)}/5: {PROGRESS_STEPS[Math.max(1, progressStep)]}
          </div>

          <div style={{ fontSize: 11, color: "rgba(255,255,255,0.3)" }}>
            This usually takes 1-3 minutes. You can navigate away and come back —
            your pack will be ready when you return.
          </div>

          {showWorkerHint && (
            <div
              style={{
                marginTop: 24,
                padding: "14px 16px",
                borderRadius: 12,
                background: "rgba(234, 179, 8, 0.12)",
                border: "1px solid rgba(234, 179, 8, 0.35)",
                textAlign: "left",
                fontSize: 12,
                lineHeight: 1.45,
                color: "rgba(254, 243, 199, 0.95)",
              }}
            >
              <strong style={{ display: "block", marginBottom: 8 }}>Still stuck after ~1 minute?</strong>
              The pack runs in background workers (not only the API). From your project folder start them:
              <pre
                style={{
                  margin: "10px 0 0",
                  padding: "10px 12px",
                  borderRadius: 8,
                  background: "rgba(0,0,0,0.35)",
                  fontSize: 11,
                  overflow: "auto",
                  color: "#fef08a",
                }}
              >
                cd careeros && docker compose -f docker/docker-compose.yml up -d worker_llm worker_default
              </pre>
              Then refresh this page. Check Flower at http://localhost:5555 to see if tasks are running.
            </div>
          )}
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "#03040f",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 16,
          color: "#fff",
        }}
      >
        <p style={{ color: "#f87171", fontSize: 18 }}>{error}</p>
        <button
          onClick={() => router.back()}
          style={{
            background: "#1e293b",
            color: "#e2e8f0",
            border: "1px solid #334155",
            borderRadius: 8,
            padding: "8px 20px",
            cursor: "pointer",
            fontSize: 14,
          }}
        >
          Go Back
        </button>
      </div>
    );
  }

  // No pack state
  if (!pack) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "#03040f",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 16,
          color: "#fff",
        }}
      >
        <p style={{ fontSize: 20, color: "#94a3b8" }}>
          No Intelligence Pack yet
        </p>
        <button
          onClick={() => router.push("/applications")}
          style={{
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            color: "#fff",
            border: "none",
            borderRadius: 8,
            padding: "10px 24px",
            cursor: "pointer",
            fontSize: 14,
            fontWeight: 600,
          }}
        >
          Generate Pack
        </button>
      </div>
    );
  }

  const stageColor = STAGE_COLORS[app?.stage || ""] || {
    bg: "#1e293b",
    text: "#94a3b8",
  };

  const packContentMismatch = computePackContentMismatch(app, pack);

  async function handleRegeneratePack() {
    if (!app) return;
    setError("");
    try {
      await updateApplication(app.id, { job_run_id: null } as any);
      window.location.reload();
    } catch {
      setError("Could not reset this pack. Try again or update the job link on this application in the tracker.");
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "#03040f" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "16px 24px",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <button
            onClick={() => router.back()}
            style={{
              background: "none",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              fontSize: 20,
              padding: "4px 8px",
              borderRadius: 6,
              lineHeight: 1,
            }}
            title="Go back"
          >
            &#8592;
          </button>
          <h1
            style={{
              margin: 0,
              fontSize: 20,
              fontWeight: 600,
              color: "#f1f5f9",
            }}
          >
            {app?.company} &mdash; {app?.role}
          </h1>
          {app?.stage && (
            <span
              style={{
                background: stageColor.bg,
                color: stageColor.text,
                padding: "4px 12px",
                borderRadius: 9999,
                fontSize: 12,
                fontWeight: 600,
                textTransform: "capitalize",
              }}
            >
              {app.stage}
            </span>
          )}
        </div>
        {downloadUrl && (
          <a
            href={downloadUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              background: "#1e293b",
              color: "#60a5fa",
              border: "1px solid #334155",
              borderRadius: 8,
              padding: "8px 16px",
              textDecoration: "none",
              fontSize: 13,
              fontWeight: 500,
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            Download CV
          </a>
        )}
      </div>

      {packContentMismatch && (
        <div
          style={{
            margin: "0 24px 16px",
            padding: 14,
            borderRadius: 10,
            background: "rgba(239,68,68,0.12)",
            border: "1px solid rgba(248,113,113,0.45)",
            color: "#fecaca",
            fontSize: 13,
            lineHeight: 1.5,
          }}
        >
          <div style={{ marginBottom: 10 }}>
            This pack does not match this application (wrong company/role in stored run). Executive summary, interview, and networking text may
            be for a different job until you regenerate.
          </div>
          <button
            type="button"
            onClick={handleRegeneratePack}
            style={{
              background: "#7f1d1d",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              padding: "8px 14px",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Regenerate pack for {app?.company} — {app?.role}
          </button>
        </div>
      )}

      {/* Pack Display */}
      <div style={{ padding: "0 24px 24px" }}>
        <PackDisplay
          pack={pack}
          downloadUrl={downloadUrl}
          linkedinContacts={linkedinContacts}
          baseCompany={app?.company || ""}
          baseRole={app?.role || ""}
          baseApplicationId={app?.id || ""}
          applicationUrl={app?.url || ""}
          packContentMismatch={packContentMismatch}
        />
      </div>
    </div>
  );
}
