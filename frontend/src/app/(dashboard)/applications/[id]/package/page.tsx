// @ts-nocheck
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getBoard,
  getJobRun,
  getDownloadUrl,
  type ApplicationItem,
  type JobRun,
} from "@/lib/api";
import PackDisplay from "@/components/pack-display";

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

  useEffect(() => {
    let pollId: ReturnType<typeof setInterval> | null = null;

    async function loadData() {
      try {
        const board = await getBoard();
        let found: ApplicationItem | null = null;
        for (const col of board.columns || []) {
          const match = col.applications.find((a) => a.id === appId);
          if (match) {
            found = { ...match, stage: col.stage } as ApplicationItem;
            break;
          }
        }
        if (!found) {
          setError("Application not found");
          setLoading(false);
          return;
        }
        setApp(found);

        // Fetch LinkedIn contacts
        try {
          const token = localStorage.getItem("sr_token");
          const res = await fetch(
            `/api/v1/relationships/company/${encodeURIComponent(found.company)}`,
            {
              headers: token ? { Authorization: `Bearer ${token}` } : {},
            }
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

        // Load pack if exists
        if (found.job_run_id) {
          try {
            const packData = await getJobRun(found.job_run_id);
            setPack(packData);
            if (packData.status === "completed") {
              try {
                const dl = await getDownloadUrl(found.job_run_id);
                setDownloadUrl(dl.download_url);
              } catch {}
            }

            // Poll if still processing
            if (
              packData.status !== "completed" &&
              packData.status !== "failed"
            ) {
              pollId = setInterval(async () => {
                try {
                  const updated = await getJobRun(found!.job_run_id!);
                  setPack(updated);
                  if (
                    updated.status === "completed" ||
                    updated.status === "failed"
                  ) {
                    if (pollId) clearInterval(pollId);
                    if (updated.status === "completed") {
                      try {
                        const dl = await getDownloadUrl(found!.job_run_id!);
                        setDownloadUrl(dl.download_url);
                      } catch {}
                    }
                  }
                } catch {}
              }, 15000);
            }
          } catch {}
        }
      } catch (e) {
        setError("Failed to load data");
      }
      setLoading(false);
    }

    loadData();
    return () => {
      if (pollId) clearInterval(pollId);
    };
  }, [appId]);

  // Loading state
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

      {/* Pack Display */}
      <div style={{ padding: "0 24px 24px" }}>
        <PackDisplay
          pack={pack}
          downloadUrl={downloadUrl}
          linkedinContacts={linkedinContacts}
        />
      </div>
    </div>
  );
}
