"use client";

import Link from "next/link";

// Design tokens
const APL = {
  bg: "#eef0fa",
  panel: "#ffffff",
  panelTint: "rgba(91,108,255,0.04)",
  panel2: "#fafbff",
  border: "rgba(15,18,40,0.08)",
  border2: "rgba(15,18,40,0.14)",
  ink: "#0c1030",
  ink2: "rgba(12,16,48,0.82)",
  ink3: "rgba(12,16,48,0.62)",
  ink4: "rgba(12,16,48,0.45)",
  ink5: "rgba(12,16,48,0.30)",
  brand: "#5B6CFF",
  brand2: "#4754E8",
  brand3: "#7F60E8",
  brandTint: "rgba(91,108,255,0.08)",
  brandTint2: "rgba(91,108,255,0.14)",
};

const STAGES = [
  { id: "watching", label: "Watching", color: "#4d8ef5", desc: "signal-flagged" },
  { id: "applied", label: "Applied", color: "#a78bfa", desc: "awaiting reply" },
  { id: "interview", label: "Interview", color: "#22c55e", desc: "in process" },
  { id: "offer", label: "Offer", color: "#fbbf24", desc: "deciding" },
  { id: "rejected", label: "Rejected", color: "#ef4444", desc: "closed" },
];

const STAGE_TINT = {
  watching: { bg: "rgba(77,142,245,0.06)", border: "rgba(77,142,245,0.18)" },
  applied: { bg: "rgba(167,139,250,0.06)", border: "rgba(167,139,250,0.20)" },
  interview: { bg: "rgba(34,197,94,0.07)", border: "rgba(34,197,94,0.20)" },
  offer: { bg: "rgba(251,191,36,0.08)", border: "rgba(251,191,36,0.22)" },
  rejected: { bg: "rgba(239,68,68,0.04)", border: "rgba(239,68,68,0.14)" },
};

// Mock data
const APPLICATIONS = [
  {
    id: 1,
    role: "Head of Product",
    company: "Linear",
    logo: "L",
    logoColor: "#5E6AD2",
    match: 94,
    salary: "$240–$290k",
    mode: "Remote",
    stage: "watching" as const,
    lastEvent: "Detected 2h ago · pre-posting",
    nextAction: "Reply to Maya",
    nextDue: "Today 17:00",
    nextUrgent: true,
    contacts: 2,
    signals: 4,
    applyBy: "~3d",
    notes: "Funding closed today. Window open ~9h.",
  },
  {
    id: 2,
    role: "Director of Product",
    company: "Ramp",
    logo: "R",
    logoColor: "#FFB800",
    match: 81,
    salary: "$260–$310k",
    mode: "NYC",
    stage: "watching" as const,
    lastEvent: "Predicted from leadership change",
    nextAction: "Add Priya to outreach",
    nextDue: "This week",
    nextUrgent: false,
    contacts: 1,
    signals: 3,
    applyBy: "~2w",
    notes: "NYC HQ floor 21 leased.",
  },
  {
    id: 3,
    role: "VP Product",
    company: "Mercury",
    logo: "M",
    logoColor: "#22c55e",
    match: 72,
    salary: "$280–$340k",
    mode: "SF",
    stage: "watching" as const,
    lastEvent: "Series C $300M · this morning",
    nextAction: "Ask James for intro",
    nextDue: "This week",
    nextUrgent: false,
    contacts: 1,
    signals: 2,
    applyBy: "~3w",
    notes: "Consumer banking line forming.",
  },
  {
    id: 4,
    role: "Sr. Product Manager",
    company: "Vercel",
    logo: "▲",
    logoColor: "#000",
    match: 88,
    salary: "$210–$260k",
    mode: "Hybrid · NYC",
    stage: "applied" as const,
    lastEvent: "Applied 6d ago · seen by recruiter",
    nextAction: "Onsite at 14:30",
    nextDue: "Today 14:30",
    nextUrgent: true,
    contacts: 3,
    signals: 3,
    applyBy: "applied",
    notes: "Final round today.",
  },
  {
    id: 5,
    role: "Group PM",
    company: "Notion",
    logo: "N",
    logoColor: "#000",
    match: 76,
    salary: "$220–$270k",
    mode: "Remote",
    stage: "applied" as const,
    lastEvent: "Applied 11d ago · no response",
    nextAction: "Nudge recruiter",
    nextDue: "Tomorrow",
    nextUrgent: false,
    contacts: 2,
    signals: 1,
    applyBy: "applied",
    notes: "Recruiter on PTO.",
  },
  {
    id: 6,
    role: "Sr. PM, Platform",
    company: "Stripe",
    logo: "S",
    logoColor: "#635BFF",
    match: 84,
    salary: "$230–$290k",
    mode: "Remote",
    stage: "applied" as const,
    lastEvent: "Applied 3d ago",
    nextAction: "Wait — recruiter screen",
    nextDue: "~5d",
    nextUrgent: false,
    contacts: 1,
    signals: 2,
    applyBy: "applied",
    notes: "Series I funding clears freeze May 6.",
  },
  {
    id: 7,
    role: "Director, Product",
    company: "Anthropic",
    logo: "A",
    logoColor: "#D97757",
    match: 79,
    salary: "$270–$330k",
    mode: "SF · Hybrid",
    stage: "interview" as const,
    lastEvent: "Round 2 scheduled Fri",
    nextAction: "Prep system design",
    nextDue: "Thu evening",
    nextUrgent: false,
    contacts: 0,
    signals: 2,
    applyBy: "applied",
    notes: "Velocity +40% MoM.",
  },
  {
    id: 8,
    role: "Lead PM",
    company: "Figma",
    logo: "F",
    logoColor: "#F24E1E",
    match: 82,
    salary: "$220–$280k",
    mode: "SF",
    stage: "interview" as const,
    lastEvent: "Round 1 passed · 2d ago",
    nextAction: "Schedule Round 2",
    nextDue: "This week",
    nextUrgent: true,
    contacts: 2,
    signals: 1,
    applyBy: "applied",
    notes: "Hiring manager positive.",
  },
  {
    id: 9,
    role: "Head of Product",
    company: "Loom",
    logo: "○",
    logoColor: "#625DF5",
    match: 86,
    salary: "$250–$300k",
    mode: "Remote",
    stage: "offer" as const,
    lastEvent: "Offer received · 3d ago",
    nextAction: "Negotiate equity",
    nextDue: "Decide by Mon",
    nextUrgent: true,
    contacts: 1,
    signals: 0,
    applyBy: "applied",
    notes: "$285k + 0.4%. Below band.",
  },
  {
    id: 10,
    role: "Director of Product",
    company: "Airtable",
    logo: "⌑",
    logoColor: "#FCB400",
    match: 71,
    salary: "$240–$290k",
    mode: "SF",
    stage: "rejected" as const,
    lastEvent: "Rejected 1w ago · culture fit",
    nextAction: "Archive",
    nextDue: "—",
    nextUrgent: false,
    contacts: 0,
    signals: 0,
    applyBy: "closed",
    notes: "",
  },
  {
    id: 11,
    role: "Sr. PM",
    company: "Retool",
    logo: "⊟",
    logoColor: "#3D40DC",
    match: 74,
    salary: "$200–$250k",
    mode: "NYC",
    stage: "rejected" as const,
    lastEvent: "Rejected 2w ago",
    nextAction: "Archive",
    nextDue: "—",
    nextUrgent: false,
    contacts: 0,
    signals: 0,
    applyBy: "closed",
    notes: "",
  },
];

function getMatchColor(score: number): string {
  if (score >= 90) return "#22c55e";
  if (score >= 80) return APL.brand;
  return APL.ink3;
}

export default function ApplicationsPage() {
  // Group by stage
  const groupedByStage = STAGES.reduce(
    (acc, stage) => {
      acc[stage.id] = APPLICATIONS.filter((app) => app.stage === stage.id);
      return acc;
    },
    {} as Record<string, typeof APPLICATIONS>
  );

  // Calculate stage stats for funnel
  const totalCards = APPLICATIONS.length;
  const stageCounts = STAGES.map((stage) => ({
    id: stage.id,
    label: stage.label,
    count: groupedByStage[stage.id].length,
    color: stage.color,
    percentage: (groupedByStage[stage.id].length / totalCards) * 100,
  }));

  return (
    <div style={{ minHeight: "100vh", backgroundColor: APL.bg }}>
      <style>{`
        @keyframes aplPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        .apl-pulse {
          animation: aplPulse 2s infinite;
        }
      `}</style>

      {/* HEADER */}
      <div
        style={{
          padding: "28px 36px 22px",
          background: `linear-gradient(to bottom, ${APL.panel}, ${APL.bg})`,
          borderBottom: `1px solid ${APL.border2}`,
        }}
      >
        {/* Top row: Label + Title + Button */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 22 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 10, color: APL.ink4, letterSpacing: "1.6px", textTransform: "uppercase", fontWeight: 500, marginBottom: 6 }}>
              APPLICATIONS · PIPELINE
            </div>
            <h1 style={{ fontSize: 28, fontWeight: 700, letterSpacing: "-0.8px", margin: 0, color: APL.ink, marginBottom: 6 }}>
              Applications
            </h1>
            <div style={{ fontSize: 13, color: APL.ink3, marginTop: 6 }}>
              Track opportunities across your pipeline
            </div>
          </div>

          {/* New application button */}
          <button
            style={{
              background: `linear-gradient(135deg, ${APL.brand}, ${APL.brand2})`,
              color: APL.panel,
              padding: "12px 20px",
              borderRadius: 10,
              border: "none",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              boxShadow: "0 4px 12px rgba(91,108,255,0.3)",
              transition: "transform 0.2s, box-shadow 0.2s",
              whiteSpace: "nowrap",
              marginLeft: 24,
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.transform = "translateY(-2px)";
              el.style.boxShadow = "0 6px 16px rgba(91,108,255,0.4)";
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.transform = "translateY(0)";
              el.style.boxShadow = "0 4px 12px rgba(91,108,255,0.3)";
            }}
          >
            + New application
          </button>
        </div>

        {/* Stats row */}
        <div
          style={{
            display: "flex",
            gap: 24,
            marginTop: 14,
            paddingTop: 12,
            borderTop: `1px solid ${APL.border}`,
          }}
        >
          {stageCounts.map((s) => (
            <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 2,
                }}
              >
                <div style={{ fontSize: 18, fontWeight: 700, color: APL.ink }}>
                  {s.count}
                </div>
                <div style={{ fontSize: 11, color: APL.ink3 }}>
                  {s.label}
                </div>
              </div>
              <div style={{ fontSize: 10, color: APL.ink5 }}>
                {STAGES.find((st) => st.id === s.id)?.desc}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* FUNNEL BAR */}
      <div style={{ display: "flex", margin: "0 36px 18px", gap: 2, height: 6, borderRadius: 3, overflow: "hidden" }}>
        {stageCounts.map((s) => (
          <div
            key={s.id}
            style={{
              flex: s.percentage,
              backgroundColor: s.color,
              opacity: s.count === 0 ? 0.3 : 1,
              transition: "flex 0.3s ease",
            }}
          />
        ))}
      </div>

      {/* KANBAN BOARD */}
      <div
        style={{
          padding: "0 36px 28px",
          display: "grid",
          gridTemplateColumns: "repeat(5, 1fr)",
          gap: 14,
          overflowX: "auto",
        }}
      >
        {STAGES.map((stage) => {
          const apps = groupedByStage[stage.id];
          const isActive = ["watching", "applied", "interview"].includes(stage.id);
          const tint = STAGE_TINT[stage.id as keyof typeof STAGE_TINT];

          return (
            <div key={stage.id} style={{ display: "flex", flexDirection: "column", minHeight: "100%" }}>
              {/* Column Header */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 12,
                  paddingBottom: 8,
                  borderBottom: isActive ? `2px solid ${stage.color}40%` : `1px solid ${APL.border}`,
                }}
              >
                <div
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    backgroundColor: stage.color,
                  }}
                />
                <span style={{ fontSize: 12, fontWeight: 600, color: APL.ink, flex: 1 }}>
                  {stage.label}
                </span>
                <span style={{ fontSize: 11, color: APL.ink4, fontWeight: 500 }}>
                  {apps.length}
                </span>
              </div>

              {/* Column Body */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 10,
                  minHeight: 200,
                  flex: 1,
                }}
              >
                {apps.map((app) => {
                  const matchColor = getMatchColor(app.match);
                  const isUrgent = app.nextUrgent;

                  return (
                    <Link
                      key={app.id}
                      href={`/applications/${app.id}/package`}
                      style={{
                        textDecoration: "none",
                        color: "inherit",
                        display: "block",
                      }}
                    >
                      <div
                        style={{
                          backgroundColor: isUrgent ? "rgba(239,68,68,0.04)" : tint.bg,
                          border: isUrgent ? "1px solid rgba(239,68,68,0.14)" : `1px solid ${APL.border}`,
                          borderLeft: isUrgent ? `3px solid ${stage.color}` : "none",
                          borderRadius: 10,
                          padding: 14,
                          display: "flex",
                          flexDirection: "column",
                          gap: 10,
                          transition: "all 0.2s ease",
                          cursor: "pointer",
                        }}
                        onMouseEnter={(e) => {
                          const el = e.currentTarget as HTMLDivElement;
                          el.style.boxShadow = "0 4px 12px rgba(0,0,0,0.08)";
                          el.style.transform = "translateY(-2px)";
                        }}
                        onMouseLeave={(e) => {
                          const el = e.currentTarget as HTMLDivElement;
                          el.style.boxShadow = "none";
                          el.style.transform = "translateY(0)";
                        }}
                      >
                        {/* Match Score */}
                        <div style={{ fontSize: 11, fontWeight: 700, color: matchColor }}>
                          {app.match}% match
                        </div>

                        {/* Company Logo + Role/Company */}
                        <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                          <div
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: 6,
                              backgroundColor: app.logoColor,
                              color: app.logoColor === "#000" ? APL.panel : APL.panel,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: 14,
                              fontWeight: 700,
                              flexShrink: 0,
                            }}
                          >
                            {app.logo}
                          </div>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div
                              style={{
                                fontSize: 13,
                                fontWeight: 600,
                                color: APL.ink,
                                lineHeight: 1.3,
                                wordWrap: "break-word",
                              }}
                            >
                              {app.role}
                            </div>
                            <div
                              style={{
                                fontSize: 11.5,
                                color: APL.ink3,
                                marginTop: 2,
                              }}
                            >
                              {app.company}
                            </div>
                          </div>
                        </div>

                        {/* Last Event */}
                        <div style={{ fontSize: 10.5, color: APL.ink4, fontFamily: "monospace" }}>
                          {app.lastEvent}
                        </div>

                        {/* Next Action Box */}
                        <div
                          style={{
                            padding: "6px 8px",
                            borderRadius: 6,
                            border: isUrgent ? "1px solid rgba(239,68,68,0.3)" : `1px solid ${APL.brand}`,
                            backgroundColor: isUrgent ? "rgba(239,68,68,0.06)" : APL.brandTint,
                            fontSize: 10.5,
                            fontWeight: 500,
                            color: isUrgent ? "#ef4444" : APL.ink2,
                            display: "flex",
                            alignItems: "center",
                            gap: isUrgent ? 6 : 0,
                          }}
                        >
                          {isUrgent && (
                            <div
                              className="apl-pulse"
                              style={{
                                width: 6,
                                height: 6,
                                borderRadius: "50%",
                                backgroundColor: "#ef4444",
                                flexShrink: 0,
                              }}
                            />
                          )}
                          <div style={{ flex: 1 }}>
                            {app.nextAction} · {app.nextDue}
                          </div>
                        </div>

                        {/* Activity Indicators */}
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                            fontSize: 10,
                            color: APL.ink4,
                          }}
                        >
                          {app.contacts > 0 && (
                            <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
                              <div
                                style={{
                                  width: 4,
                                  height: 4,
                                  borderRadius: "50%",
                                  backgroundColor: APL.ink4,
                                }}
                              />
                              <span>{app.contacts} contact{app.contacts !== 1 ? "s" : ""}</span>
                            </div>
                          )}
                          {app.signals > 0 && (
                            <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
                              <div
                                style={{
                                  width: 4,
                                  height: 4,
                                  borderRadius: "50%",
                                  backgroundColor: APL.ink4,
                                }}
                              />
                              <span>{app.signals} signal{app.signals !== 1 ? "s" : ""}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
