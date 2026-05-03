"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { SR, STAGE_COLORS } from "@/lib/constants";

type Tab = "overview" | "strategy" | "interview" | "way-in";

interface Contact {
  name: string;
  title: string;
  company: string;
  degree: "1st" | "2nd";
  warmth: "warm" | "lukewarm" | "cold";
  mutualConnections: number;
}

export default function DossierPage() {
  const params = useParams();
  const appId = params.id as string;
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  // Mock data
  const company = "Stripe";
  const role = "Director of Product";
  const matchPercentage = 89;
  const stage = "applied";
  const salaryMin = 180000;
  const salaryMid = 220000;
  const salaryMax = 280000;
  const appliedDate = "2026-04-28";
  const stageColor = STAGE_COLORS[stage] || "#9f7aea";

  // Mock contacts
  const contacts: Contact[] = [
    {
      name: "Sarah Chen",
      title: "VP Engineering",
      company: "Stripe",
      degree: "1st",
      warmth: "warm",
      mutualConnections: 3,
    },
    {
      name: "Marcus Johnson",
      title: "Product Lead",
      company: "Stripe",
      degree: "2nd",
      warmth: "lukewarm",
      mutualConnections: 1,
    },
    {
      name: "Elena Rodriguez",
      title: "Head of Hiring",
      company: "Stripe",
      degree: "2nd",
      warmth: "cold",
      mutualConnections: 0,
    },
    {
      name: "Arun Patel",
      title: "Product Director",
      company: "Stripe",
      degree: "1st",
      warmth: "warm",
      mutualConnections: 2,
    },
  ];

  // Mock mutual connections
  const mutualConnections = [
    { name: "David Wilson", title: "Chief Product Officer" },
    { name: "Lisa Park", title: "Senior PM at Stripe" },
  ];

  // Tab styles
  const tabStyle = (isActive: boolean) => ({
    padding: "12px 16px",
    fontSize: 14,
    fontWeight: 600,
    backgroundColor: "transparent",
    border: "none",
    borderBottom: isActive ? `2px solid ${stageColor}` : "2px solid transparent",
    color: isActive ? SR.ink : SR.ink3,
    cursor: "pointer",
    transition: "all 0.2s",
  });

  const cardStyle = {
    background: SR.panel,
    border: `1px solid ${SR.border}`,
    borderRadius: 12,
    padding: "20px",
  };

  const sectionTitleStyle = {
    fontSize: 14,
    fontWeight: 700,
    color: SR.ink,
    marginBottom: 16,
    marginTop: 0,
  };

  const triggerChipStyle = (color: string) => ({
    display: "inline-block",
    background: color,
    color: SR.ink,
    padding: "4px 10px",
    borderRadius: 6,
    fontSize: 11,
    fontWeight: 600,
    marginRight: 8,
    marginBottom: 8,
  });

  const warmthColor = (warmth: string) => {
    switch (warmth) {
      case "warm":
        return SR.green;
      case "lukewarm":
        return SR.amber;
      case "cold":
        return SR.red;
      default:
        return SR.ink4;
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: SR.bg }}>
      {/* Breadcrumb */}
      <div
        style={{
          padding: "12px 24px",
          fontSize: 12,
          color: SR.ink3,
          borderBottom: `1px solid ${SR.border}`,
          background: SR.panel,
        }}
      >
        <Link
          href="/applications"
          style={{ color: SR.brand, textDecoration: "none", marginRight: 4 }}
        >
          Applications
        </Link>
        {" > "}
        <span style={{ marginRight: 4 }}>{company}</span>
        {" > "}
        <span style={{ color: SR.ink2 }}>Dossier</span>
      </div>

      {/* Hero section */}
      <div
        style={{
          padding: "32px 24px",
          background: SR.panel,
          borderBottom: `1px solid ${SR.border}`,
        }}
      >
        <div style={{ maxWidth: 1200, marginLeft: "auto", marginRight: "auto" }}>
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: 32,
            }}
          >
            <div style={{ flex: 1 }}>
              <h1 style={{ margin: "0 0 8px", fontSize: 28, fontWeight: 700, color: SR.ink }}>
                {company}
              </h1>
              <p style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 600, color: SR.ink2 }}>
                {role}
              </p>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 16,
                }}
              >
                {/* Match gauge */}
                <div
                  style={{
                    position: "relative",
                    width: 100,
                    height: 100,
                  }}
                >
                  <svg
                    viewBox="0 0 100 100"
                    style={{ width: "100%", height: "100%" }}
                  >
                    <circle
                      cx="50"
                      cy="50"
                      r="45"
                      fill="none"
                      stroke={SR.border}
                      strokeWidth="4"
                    />
                    <circle
                      cx="50"
                      cy="50"
                      r="45"
                      fill="none"
                      stroke={stageColor}
                      strokeWidth="4"
                      strokeDasharray={`${(matchPercentage / 100) * 2 * Math.PI * 45} ${2 * Math.PI * 45}`}
                      strokeLinecap="round"
                      style={{ transform: "rotate(-90deg)", transformOrigin: "50px 50px" }}
                    />
                  </svg>
                  <div
                    style={{
                      position: "absolute",
                      top: "50%",
                      left: "50%",
                      transform: "translate(-50%, -50%)",
                      textAlign: "center",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 24,
                        fontWeight: 700,
                        color: SR.ink,
                      }}
                    >
                      {matchPercentage}%
                    </div>
                    <div
                      style={{
                        fontSize: 10,
                        color: SR.ink3,
                        fontWeight: 600,
                      }}
                    >
                      Match
                    </div>
                  </div>
                </div>

                <div>
                  <div style={{ marginBottom: 12 }}>
                    <span
                      style={{
                        background: `rgba(${parseInt(stageColor.slice(1, 3), 16)}, ${parseInt(stageColor.slice(3, 5), 16)}, ${parseInt(stageColor.slice(5, 7), 16)}, 0.1)`,
                        color: stageColor,
                        padding: "6px 12px",
                        borderRadius: 6,
                        fontSize: 12,
                        fontWeight: 600,
                        textTransform: "capitalize",
                        display: "inline-block",
                      }}
                    >
                      {stage}
                    </span>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, color: SR.ink3, marginBottom: 4 }}>
                      Salary range
                    </div>
                    <div
                      style={{
                        fontSize: 14,
                        fontWeight: 700,
                        color: SR.ink,
                      }}
                    >
                      ${(salaryMin / 1000).toFixed(0)}k–${(salaryMax / 1000).toFixed(0)}k
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Tab strip */}
      <div
        style={{
          display: "flex",
          gap: 0,
          borderBottom: `1px solid ${SR.border}`,
          background: SR.panel,
          padding: "0 24px",
        }}
      >
        {["Overview", "Strategy", "Interview", "Way-In"].map((label, idx) => {
          const tabKey = (
            ["overview", "strategy", "interview", "way-in"] as const
          )[idx];
          return (
            <button
              key={tabKey}
              onClick={() => setActiveTab(tabKey)}
              style={tabStyle(activeTab === tabKey) as React.CSSProperties}
            >
              {label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <div style={{ padding: "32px 24px", maxWidth: 1200, marginLeft: "auto", marginRight: "auto" }}>
        {/* Overview Tab */}
        {activeTab === "overview" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
            {/* Left column */}
            <div>
              {/* Executive summary */}
              <div style={cardStyle as React.CSSProperties}>
                <h3 style={sectionTitleStyle as React.CSSProperties}>
                  Executive Summary
                </h3>
                <p style={{ fontSize: 13, lineHeight: 1.6, color: SR.ink2, margin: 0 }}>
                  Strong fit for this role given your 8+ years leading product at
                  growth-stage B2B SaaS companies. Your experience scaling teams
                  and shipping payment infrastructure aligns directly with Stripe's
                  expansion into merchant tools.
                </p>
              </div>

              {/* Why now signals */}
              <div style={{ ...cardStyle, marginTop: 24 } as React.CSSProperties}>
                <h3 style={sectionTitleStyle as React.CSSProperties}>
                  Why Now Signals
                </h3>
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {[
                    {
                      trigger: "funding",
                      text: "Series H raised $400M — expanding product team",
                    },
                    {
                      trigger: "expansion",
                      text: "Opening new regional offices — hiring aggressively",
                    },
                    {
                      trigger: "hiring",
                      text: "Product hiring surge in H1 2026",
                    },
                  ].map((item, idx) => (
                    <div key={idx}>
                      <div
                        style={{
                          fontSize: 12,
                          color: SR.ink2,
                          marginBottom: 6,
                        }}
                      >
                        {item.text}
                      </div>
                      <div
                        style={triggerChipStyle(
                          item.trigger === "funding"
                            ? "rgba(34, 197, 94, 0.1)"
                            : item.trigger === "expansion"
                              ? "rgba(251, 191, 36, 0.1)"
                              : "rgba(167, 139, 250, 0.1)"
                        ) as React.CSSProperties}
                      >
                        {item.trigger.charAt(0).toUpperCase() +
                          item.trigger.slice(1)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Company intel */}
              <div style={{ ...cardStyle, marginTop: 24 } as React.CSSProperties}>
                <h3 style={sectionTitleStyle as React.CSSProperties}>
                  Company Intel
                </h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  {[
                    { label: "Founded", value: "2010" },
                    { label: "Size", value: "14k+" },
                    { label: "Stage", value: "Public" },
                    { label: "HQ", value: "San Francisco, CA" },
                  ].map((item, idx) => (
                    <div key={idx}>
                      <div style={{ fontSize: 11, color: SR.ink3, marginBottom: 4 }}>
                        {item.label}
                      </div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: SR.ink }}>
                        {item.value}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right column */}
            <div>
              {/* Salary benchmark */}
              <div style={cardStyle as React.CSSProperties}>
                <h3 style={sectionTitleStyle as React.CSSProperties}>
                  Salary Benchmark
                </h3>
                <div style={{ marginBottom: 16 }}>
                  <div
                    style={{
                      display: "flex",
                      height: 8,
                      background: SR.border,
                      borderRadius: 4,
                      overflow: "hidden",
                      marginBottom: 12,
                    }}
                  >
                    <div
                      style={{
                        flex: "0 0 25%",
                        background: SR.green,
                      }}
                    />
                    <div
                      style={{
                        flex: "0 0 50%",
                        background: stageColor,
                      }}
                    />
                    <div
                      style={{
                        flex: "0 0 25%",
                        background: SR.ink5,
                      }}
                    />
                  </div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 11,
                      color: SR.ink3,
                    }}
                  >
                    <span>${(salaryMin / 1000).toFixed(0)}k</span>
                    <span>${(salaryMid / 1000).toFixed(0)}k</span>
                    <span>${(salaryMax / 1000).toFixed(0)}k</span>
                  </div>
                </div>
              </div>

              {/* Timeline */}
              <div style={{ ...cardStyle, marginTop: 24 } as React.CSSProperties}>
                <h3 style={sectionTitleStyle as React.CSSProperties}>Timeline</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {[
                    { label: "Applied", value: appliedDate },
                    { label: "Next Step", value: "Recruiter Screen" },
                  ].map((item, idx) => (
                    <div key={idx}>
                      <div style={{ fontSize: 11, color: SR.ink3, marginBottom: 2 }}>
                        {item.label}
                      </div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: SR.ink }}>
                        {item.value}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Connection paths */}
              <div style={{ ...cardStyle, marginTop: 24 } as React.CSSProperties}>
                <h3 style={sectionTitleStyle as React.CSSProperties}>
                  Connection Paths
                </h3>
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {mutualConnections.map((conn, idx) => (
                    <div key={idx}>
                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: 600,
                          color: SR.ink,
                          marginBottom: 2,
                        }}
                      >
                        {conn.name}
                      </div>
                      <div style={{ fontSize: 12, color: SR.ink3 }}>
                        {conn.title}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Strategy Tab */}
        {activeTab === "strategy" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
            <div>
              {/* Strongest matches */}
              <div style={cardStyle as React.CSSProperties}>
                <h3 style={sectionTitleStyle as React.CSSProperties}>
                  Strongest Matches
                </h3>
                <ul
                  style={{
                    listStyle: "none",
                    margin: 0,
                    padding: 0,
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                  }}
                >
                  {[
                    "Led product strategy for 100M+ user platform",
                    "Proven track record scaling teams from 5 to 50+ PMs",
                    "Built payment integrations reaching 10k+ merchants",
                    "Expert in B2B SaaS GTM and partnerships",
                  ].map((item, idx) => (
                    <li
                      key={idx}
                      style={{
                        display: "flex",
                        gap: 10,
                        fontSize: 13,
                        color: SR.ink2,
                      }}
                    >
                      <span style={{ color: SR.green, fontWeight: 700 }}>✓</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Gaps to address */}
              <div style={{ ...cardStyle, marginTop: 24 } as React.CSSProperties}>
                <h3 style={sectionTitleStyle as React.CSSProperties}>
                  Gaps to Address
                </h3>
                <ul
                  style={{
                    listStyle: "none",
                    margin: 0,
                    padding: 0,
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                  }}
                >
                  {[
                    "Limited direct fintech experience (emphasize adaptability)",
                    "Previous role in smaller company (highlight leadership scaling)",
                  ].map((item, idx) => (
                    <li
                      key={idx}
                      style={{
                        display: "flex",
                        gap: 10,
                        fontSize: 13,
                        color: SR.ink2,
                      }}
                    >
                      <span style={{ color: SR.amber, fontWeight: 700 }}>!</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div>
              {/* Approach cards */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 16,
                }}
              >
                {[
                  {
                    title: "Lead with Impact",
                    description:
                      "Open with quantified wins: user growth, team scaling, revenue impact.",
                    recommended: true,
                  },
                  {
                    title: "Show Fintech Readiness",
                    description:
                      "Highlight how payment and merchant platforms map to your background.",
                    recommended: false,
                  },
                  {
                    title: "Emphasize Culture Fit",
                    description:
                      "Stripe values autonomy and craftsmanship—tie to your philosophy.",
                    recommended: false,
                  },
                ].map((approach, idx) => (
                  <div
                    key={idx}
                    style={{
                      ...cardStyle,
                      position: "relative",
                      paddingTop: approach.recommended ? 40 : 20,
                    } as React.CSSProperties}
                  >
                    {approach.recommended && (
                      <div
                        style={{
                          position: "absolute",
                          top: 10,
                          right: 10,
                          background: SR.green,
                          color: "#fff",
                          fontSize: 10,
                          fontWeight: 700,
                          padding: "3px 8px",
                          borderRadius: 4,
                        }}
                      >
                        Recommended
                      </div>
                    )}
                    <h4
                      style={{
                        fontSize: 14,
                        fontWeight: 700,
                        color: SR.ink,
                        margin: "0 0 8px",
                      }}
                    >
                      {approach.title}
                    </h4>
                    <p
                      style={{
                        fontSize: 13,
                        color: SR.ink2,
                        margin: 0,
                        lineHeight: 1.5,
                      }}
                    >
                      {approach.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Interview Tab */}
        {activeTab === "interview" && (
          <div>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 24,
              }}
            >
              {[
                {
                  round: 1,
                  stage: "Recruiter Screen",
                  format: "30 min call, exploratory",
                  questions: [
                    "Walk through your background and key wins",
                    "Why are you interested in Stripe?",
                    "What attracted you to this role?",
                  ],
                },
                {
                  round: 2,
                  stage: "Hiring Manager",
                  format: "45 min, technical PM depth",
                  questions: [
                    "Tell us about a complex product decision",
                    "How do you approach cross-functional alignment?",
                    "Describe your approach to metrics and success",
                  ],
                },
                {
                  round: 3,
                  stage: "Take-home Exercise",
                  format: "2-3 hours, case study",
                  questions: [
                    "Design a new feature for merchant dashboard",
                    "Define success metrics and tradeoffs",
                    "Present your thinking",
                  ],
                },
                {
                  round: 4,
                  stage: "Final / Onsite",
                  format: "4 hours, 3-4 interviewers",
                  questions: [
                    "Deep dive on strategy and leadership",
                    "Culture and values alignment",
                    "Round-robin with team leads",
                  ],
                },
              ].map((round, idx) => (
                <div
                  key={idx}
                  style={{
                    ...cardStyle,
                    paddingLeft: 24,
                    borderLeft: `3px solid ${stageColor}`,
                  } as React.CSSProperties}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      marginBottom: 12,
                    }}
                  >
                    <div>
                      <h4
                        style={{
                          fontSize: 14,
                          fontWeight: 700,
                          color: SR.ink,
                          margin: 0,
                        }}
                      >
                        Round {round.round}: {round.stage}
                      </h4>
                      <p
                        style={{
                          fontSize: 12,
                          color: SR.ink3,
                          margin: "4px 0 0",
                        }}
                      >
                        {round.format}
                      </p>
                    </div>
                  </div>
                  <div>
                    <p
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: SR.ink,
                        margin: "12px 0 8px",
                      }}
                    >
                      Expected Questions:
                    </p>
                    <ul
                      style={{
                        listStyle: "none",
                        margin: 0,
                        padding: 0,
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
                      }}
                    >
                      {round.questions.map((q, qIdx) => (
                        <li
                          key={qIdx}
                          style={{
                            fontSize: 13,
                            color: SR.ink2,
                            paddingLeft: 20,
                            position: "relative",
                          }}
                        >
                          <span
                            style={{
                              position: "absolute",
                              left: 0,
                              color: SR.ink4,
                            }}
                          >
                            •
                          </span>
                          {q}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Way-In Tab */}
        {activeTab === "way-in" && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
              gap: 20,
            }}
          >
            {contacts.map((contact, idx) => (
              <div
                key={idx}
                style={cardStyle as React.CSSProperties}
              >
                <div style={{ marginBottom: 16 }}>
                  <h4
                    style={{
                      fontSize: 14,
                      fontWeight: 700,
                      color: SR.ink,
                      margin: "0 0 2px",
                    }}
                  >
                    {contact.name}
                  </h4>
                  <p
                    style={{
                      fontSize: 12,
                      color: SR.ink2,
                      margin: "0 0 8px",
                    }}
                  >
                    {contact.title}
                  </p>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      fontSize: 11,
                      color: SR.ink3,
                    }}
                  >
                    <span
                      style={{
                        display: "inline-block",
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        background: warmthColor(contact.warmth),
                      }}
                    />
                    <span style={{ textTransform: "capitalize" }}>
                      {contact.warmth}
                    </span>
                    {contact.mutualConnections > 0 && (
                      <>
                        <span>·</span>
                        <span>
                          {contact.mutualConnections} mutual
                          {contact.mutualConnections === 1
                            ? " connection"
                            : " connections"}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                <div style={{ marginBottom: 12 }}>
                  <p
                    style={{
                      fontSize: 12,
                      color: SR.ink2,
                      lineHeight: 1.5,
                      margin: 0,
                    }}
                  >
                    {contact.degree === "1st"
                      ? "Direct connection. Strong relationship potential."
                      : "Mutual connection. Room to warm up the relationship."}
                  </p>
                </div>

                <button
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    background: SR.brand,
                    color: "#fff",
                    border: "none",
                    borderRadius: 6,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                    transition: "background 0.2s",
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background =
                      "#4754E8";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background =
                      SR.brand;
                  }}
                >
                  Draft Outreach
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
