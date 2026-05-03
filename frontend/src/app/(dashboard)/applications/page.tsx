"use client";

import Link from "next/link";
import { SR, STAGE_COLORS, STAGE_TINTS } from "@/lib/constants";

const APP_PIPELINE = [
  {
    id: "app_1",
    company: "Anthropic",
    role: "Senior Product Manager",
    match: 92,
    stage: "watching" as const,
    lastEvent: "Posted 2 days ago",
    nextAction: "Review company culture",
    nextDue: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString(),
    urgent: false,
  },
  {
    id: "app_2",
    company: "OpenAI",
    role: "ML Engineer",
    match: 88,
    stage: "watching" as const,
    lastEvent: "Found on LinkedIn",
    nextAction: "Check team composition",
    nextDue: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString(),
    urgent: false,
  },
  {
    id: "app_3",
    company: "Scale AI",
    role: "Head of Data Operations",
    match: 85,
    stage: "watching" as const,
    lastEvent: "Saved from email",
    nextAction: "Reach out to recruiter",
    nextDue: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
    urgent: false,
  },
  {
    id: "app_4",
    company: "Stripe",
    role: "Staff Engineer",
    match: 78,
    stage: "applied" as const,
    lastEvent: "Applied 4 days ago",
    nextAction: "Follow-up email",
    nextDue: new Date(Date.now() + 1 * 24 * 60 * 60 * 1000).toISOString(),
    urgent: true,
  },
  {
    id: "app_5",
    company: "Notion",
    role: "Senior Design Lead",
    match: 82,
    stage: "applied" as const,
    lastEvent: "Applied 3 days ago",
    nextAction: "Portfolio review feedback",
    nextDue: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString(),
    urgent: false,
  },
  {
    id: "app_6",
    company: "Figma",
    role: "Product Designer",
    match: 75,
    stage: "applied" as const,
    lastEvent: "Applied 1 day ago",
    nextAction: "Await initial screening",
    nextDue: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString(),
    urgent: false,
  },
  {
    id: "app_7",
    company: "Google",
    role: "Senior Research Scientist",
    match: 91,
    stage: "interview" as const,
    lastEvent: "Phone screen passed",
    nextAction: "Technical interview",
    nextDue: new Date(Date.now() + 4 * 24 * 60 * 60 * 1000).toISOString(),
    urgent: false,
  },
  {
    id: "app_8",
    company: "Meta",
    role: "Engineering Manager",
    match: 89,
    stage: "interview" as const,
    lastEvent: "Video call scheduled",
    nextAction: "Prepare system design",
    nextDue: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString(),
    urgent: true,
  },
  {
    id: "app_9",
    company: "Microsoft",
    role: "Principal Software Architect",
    match: 87,
    stage: "offer" as const,
    lastEvent: "Final round passed",
    nextAction: "Review offer details",
    nextDue: new Date(Date.now() + 1 * 24 * 60 * 60 * 1000).toISOString(),
    urgent: false,
  },
  {
    id: "app_10",
    company: "Amazon",
    role: "Senior SDE",
    match: 72,
    stage: "rejected" as const,
    lastEvent: "Rejected after phone screen",
    nextAction: "Request feedback",
    nextDue: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
    urgent: false,
  },
  {
    id: "app_11",
    company: "Apple",
    role: "Hardware Engineer",
    match: 68,
    stage: "rejected" as const,
    lastEvent: "Position filled",
    nextAction: "No action needed",
    nextDue: new Date().toISOString(),
    urgent: false,
  },
];

const STAGE_LABELS: Record<string, { name: string; color: string }> = {
  watching: { name: "Watching", color: "#4d8ef5" },
  applied: { name: "Applied", color: "#a78bfa" },
  interview: { name: "Interview", color: "#22c55e" },
  offer: { name: "Offer", color: "#fbbf24" },
  rejected: { name: "Rejected", color: "#ef4444" },
};

function getMatchColor(score: number): string {
  if (score > 85) return "#22c55e";
  if (score > 70) return "#4d8ef5";
  return "#fbbf24";
}

function formatDueDate(dateStr: string): string {
  const date = new Date(dateStr);
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);

  const isToday =
    date.getFullYear() === today.getFullYear() &&
    date.getMonth() === today.getMonth() &&
    date.getDate() === today.getDate();

  const isTomorrow =
    date.getFullYear() === tomorrow.getFullYear() &&
    date.getMonth() === tomorrow.getMonth() &&
    date.getDate() === tomorrow.getDate();

  if (isToday) return "Today";
  if (isTomorrow) return "Tomorrow";

  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export default function ApplicationsPage() {
  const stageOrder = ["watching", "applied", "interview", "offer", "rejected"];

  const groupedByStage = stageOrder.reduce(
    (acc, stage) => {
      acc[stage] = APP_PIPELINE.filter((app) => app.stage === stage);
      return acc;
    },
    {} as Record<string, typeof APP_PIPELINE>
  );

  const totalCards = APP_PIPELINE.length;
  const stageCounts = Object.entries(groupedByStage).map(([stage, apps]) => ({
    stage,
    count: apps.length,
    percentage: (apps.length / totalCards) * 100,
  }));

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#f4f5fb", padding: "32px 24px" }}>
      {/* Header Section */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, color: "#1a202c", margin: "0 0 4px 0" }}>
          Applications
        </h1>
        <p style={{ fontSize: 14, color: "#718096", margin: 0 }}>Your active pipeline.</p>
      </div>

      {/* Funnel Bar - Stage Distribution */}
      <div style={{ marginBottom: 28, display: "flex", height: 32, borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.05)", gap: 0 }}>
        {stageCounts.map(({ stage, percentage }) => {
          const stageInfo = STAGE_LABELS[stage];
          return (
            <div
              key={stage}
              style={{
                flex: percentage,
                backgroundColor: stageInfo.color,
                transition: "flex 0.3s ease",
                position: "relative",
                cursor: "pointer",
              }}
              title={`${stage}: ${groupedByStage[stage].length} cards`}
            />
          );
        })}
      </div>

      {/* Kanban Board */}
      <div style={{ display: "flex", gap: 16, overflowX: "auto", paddingBottom: 16 }}>
        {stageOrder.map((stage) => {
          const apps = groupedByStage[stage];
          const stageInfo = STAGE_LABELS[stage];

          return (
            <div
              key={stage}
              style={{
                minWidth: 260,
                flexShrink: 0,
                display: "flex",
                flexDirection: "column",
                gap: 10,
              }}
            >
              {/* Column Header */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "0 0 12px 0",
                }}
              >
                <div
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    backgroundColor: stageInfo.color,
                  }}
                />
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: "#1a202c",
                    textTransform: "capitalize",
                  }}
                >
                  {stageInfo.name}
                </span>
                <span
                  style={{
                    marginLeft: "auto",
                    fontSize: 12,
                    fontWeight: 500,
                    color: "#718096",
                    backgroundColor: "#e2e8f0",
                    padding: "2px 8px",
                    borderRadius: 6,
                  }}
                >
                  {apps.length}
                </span>
              </div>

              {/* Column Body */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 10,
                  backgroundColor: "#ffffff",
                  borderRadius: 12,
                  padding: 12,
                  minHeight: 200,
                  border: `1px solid ${SR.border}`,
                }}
              >
                {apps.length === 0 ? (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      height: 100,
                      color: "#cbd5e0",
                      fontSize: 12,
                    }}
                  >
                    No applications
                  </div>
                ) : (
                  apps.map((app) => (
                    <Link
                      key={app.id}
                      href={`/applications/${app.id}/package`}
                      style={{
                        textDecoration: "none",
                        backgroundColor: "#ffffff",
                        border: app.urgent ? "3px solid #ef4444" : `3px solid ${stageInfo.color}`,
                        borderRadius: 10,
                        padding: 14,
                        display: "flex",
                        flexDirection: "column",
                        gap: 8,
                        transition: "box-shadow 0.2s ease, transform 0.2s ease",
                        cursor: "pointer",
                      }}
                      onMouseEnter={(e) => {
                        const elem = e.currentTarget as HTMLAnchorElement;
                        elem.style.boxShadow = "0 4px 12px rgba(0,0,0,0.08)";
                        elem.style.transform = "translateY(-2px)";
                      }}
                      onMouseLeave={(e) => {
                        const elem = e.currentTarget as HTMLAnchorElement;
                        elem.style.boxShadow = "none";
                        elem.style.transform = "translateY(0)";
                      }}
                    >
                      {/* Company & Role */}
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "#1a202c", margin: 0 }}>
                          {app.company}
                        </div>
                        <div style={{ fontSize: 12, color: "#718096", margin: "2px 0 0 0" }}>
                          {app.role}
                        </div>
                      </div>

                      {/* Match % Pill */}
                      <div
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          width: "fit-content",
                          fontSize: 11,
                          fontWeight: 600,
                          color: "#ffffff",
                          backgroundColor: getMatchColor(app.match),
                          padding: "4px 10px",
                          borderRadius: 6,
                        }}
                      >
                        <span>Match</span>
                        <span>{app.match}%</span>
                      </div>

                      {/* Last Event */}
                      <div
                        style={{
                          fontSize: 11,
                          color: "#a0aec0",
                          fontStyle: "italic",
                          margin: 0,
                        }}
                      >
                        {app.lastEvent}
                      </div>

                      {/* Next Action with Due Date */}
                      <div
                        style={{
                          fontSize: 11,
                          color: app.urgent ? "#ef4444" : "#1a202c",
                          fontWeight: app.urgent ? 600 : 400,
                          margin: 0,
                        }}
                      >
                        <div>{app.nextAction}</div>
                        <div style={{ fontSize: 10, color: app.urgent ? "#dc2626" : "#718096", marginTop: 2 }}>
                          {app.urgent && "🔴 "} {formatDueDate(app.nextDue)}
                        </div>
                      </div>

                      {/* Open Dossier Link */}
                      <div
                        style={{
                          fontSize: 12,
                          fontWeight: 500,
                          color: "#4d8ef5",
                          marginTop: 4,
                          cursor: "pointer",
                        }}
                      >
                        Open Dossier →
                      </div>
                    </Link>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
