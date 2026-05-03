"use client";

import { useState } from "react";
import { SR } from "@/lib/constants";
import { useAuth } from "@/lib/auth-context";

// Mock data
const MOCK_EXPERIENCES = [
  {
    id: "exp1",
    company: "TechCorp",
    role: "Senior Product Manager",
    dates: "2021 - Present",
    bullets: [
      "Led product roadmap that increased user retention by 42%",
      "Managed cross-functional teams of 8 engineers and 3 designers"
    ]
  },
  {
    id: "exp2",
    company: "StartupXYZ",
    role: "Product Manager",
    dates: "2019 - 2021",
    bullets: [
      "Grew user base from 10K to 500K in 18 months",
      "Launched 3 major product initiatives"
    ]
  },
  {
    id: "exp3",
    company: "ConsultCo",
    role: "Strategy Consultant",
    dates: "2018 - 2019",
    bullets: [
      "Advised Fortune 500 companies on digital transformation",
      "Delivered 12 client engagements with avg satisfaction 9.2/10"
    ]
  }
];

const MOCK_SKILLS = [
  "Product Strategy",
  "SaaS",
  "Go-to-market",
  "Team Leadership",
  "User Research",
  "Roadmapping",
  "Analytics",
  "B2B Sales",
  "Data Analysis",
  "Communication",
  "AI/ML",
  "Mobile"
];

const MOCK_TARGET_TITLES = ["VP Product", "Director of Product", "Chief Product Officer"];
const MOCK_SENIORITY = "Manager";
const MOCK_WORK_MODES = ["Remote", "Hybrid"];
const MOCK_INDUSTRIES = ["SaaS", "Fintech", "Healthcare"];

export default function ProfilePage() {
  const { user } = useAuth();
  const [expandedExp, setExpandedExp] = useState<string | null>(null);

  // Get initials from user name
  const getInitials = (name: string | undefined): string => {
    if (!name) return "U";
    const parts = name.split(" ");
    return (parts[0][0] + (parts[1]?.[0] || "")).toUpperCase();
  };

  const panelStyle = {
    background: SR.panel,
    border: `1px solid ${SR.border}`,
    borderRadius: 14,
    padding: 24,
    marginBottom: 18
  };

  const chipStyle = (active: boolean) => ({
    borderRadius: 999,
    padding: "4px 12px",
    fontSize: 12,
    fontWeight: 500,
    backgroundColor: active ? SR.brandTint : "transparent",
    color: active ? SR.brand : SR.ink4,
    border: `1px solid ${active ? SR.brand : SR.border2}`,
    cursor: "pointer",
    display: "inline-block",
    marginRight: 8,
    marginBottom: 8
  });

  return (
    <div style={{ background: SR.bg, minHeight: "100vh", paddingTop: 24, paddingBottom: 40 }}>
      {/* Main container */}
      <div style={{ maxWidth: 1200, margin: "0 auto", paddingLeft: 24, paddingRight: 24 }}>
        {/* Header section */}
        <div style={{ marginBottom: 32 }}>
          <h1 style={{ fontSize: 28, fontWeight: 600, color: SR.ink, margin: 0, marginBottom: 8 }}>
            Profile
          </h1>
          <p style={{ fontSize: 14, color: SR.ink3, margin: 0 }}>
            Train the Scout on your background.
          </p>
        </div>

        {/* 2-column layout wrapper */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          {/* LEFT COLUMN - Main content (~65%) */}
          <div style={{ gridColumn: "1 / 2" }}>

            {/* 1. Identity Card */}
            <div style={panelStyle}>
              <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
                {/* Avatar circle */}
                <div
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: "50%",
                    background: SR.brand,
                    color: "#fff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 24,
                    fontWeight: 600,
                    flexShrink: 0
                  }}
                >
                  {getInitials(user?.full_name ?? undefined)}
                </div>

                {/* User info */}
                <div style={{ flex: 1 }}>
                  <h2 style={{ fontSize: 16, fontWeight: 600, color: SR.ink, margin: 0, marginBottom: 4 }}>
                    {user?.full_name || "User"}
                  </h2>
                  <p style={{ fontSize: 13, color: SR.ink3, margin: 0, marginBottom: 4 }}>
                    {user?.email || "email@example.com"}
                  </p>
                  <p style={{ fontSize: 13, color: SR.ink4, margin: 0 }}>
                    Senior Product Manager
                  </p>
                </div>
              </div>
            </div>

            {/* 2. Experience Section */}
            <div style={panelStyle}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: SR.ink, margin: 0, marginBottom: 16 }}>
                Experience
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {MOCK_EXPERIENCES.map((exp) => (
                  <div
                    key={exp.id}
                    onClick={() => setExpandedExp(expandedExp === exp.id ? null : exp.id)}
                    style={{
                      border: `1px solid ${SR.border}`,
                      borderRadius: 8,
                      padding: 12,
                      cursor: "pointer",
                      transition: "background 0.2s",
                      background: expandedExp === exp.id ? SR.panelSoft : "transparent"
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: SR.ink }}>
                          {exp.role}
                        </div>
                        <div style={{ fontSize: 12, color: SR.ink3, marginTop: 2 }}>
                          {exp.company}
                        </div>
                        <div style={{ fontSize: 11, color: SR.ink4, marginTop: 2 }}>
                          {exp.dates}
                        </div>
                      </div>
                      <div style={{ fontSize: 12, color: SR.ink4 }}>
                        {expandedExp === exp.id ? "▾" : "▸"}
                      </div>
                    </div>

                    {expandedExp === exp.id && (
                      <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${SR.border}` }}>
                        {exp.bullets.map((bullet, idx) => (
                          <div key={idx} style={{ fontSize: 12, color: SR.ink3, marginBottom: 6, paddingLeft: 16, position: "relative" }}>
                            <span style={{ position: "absolute", left: 0 }}>•</span>
                            {bullet}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              <button
                style={{
                  marginTop: 16,
                  padding: "8px 12px",
                  background: "transparent",
                  border: `1px solid ${SR.border}`,
                  borderRadius: 6,
                  color: SR.brand,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer"
                }}
              >
                + Add Experience
              </button>
            </div>

            {/* 3. Skills Section */}
            <div style={panelStyle}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: SR.ink, margin: 0, marginBottom: 16 }}>
                Skills & Expertise
              </h3>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {MOCK_SKILLS.map((skill) => (
                  <span
                    key={skill}
                    style={{
                      ...chipStyle(true),
                      marginRight: 0,
                      marginBottom: 8
                    }}
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>

            {/* 4. Target Search Section */}
            <div style={panelStyle}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: SR.ink, margin: 0, marginBottom: 16 }}>
                Target Criteria
              </h3>

              {/* Target Titles */}
              <div style={{ marginBottom: 20 }}>
                <label style={{ fontSize: 11, fontWeight: 600, color: SR.ink4, textTransform: "uppercase", display: "block", marginBottom: 8 }}>
                  Target Titles
                </label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {MOCK_TARGET_TITLES.map((title) => (
                    <span key={title} style={chipStyle(true)}>
                      {title}
                    </span>
                  ))}
                </div>
              </div>

              {/* Seniority Level */}
              <div style={{ marginBottom: 20 }}>
                <label style={{ fontSize: 11, fontWeight: 600, color: SR.ink4, textTransform: "uppercase", display: "block", marginBottom: 8 }}>
                  Seniority Level
                </label>
                <div style={chipStyle(true)}>
                  {MOCK_SENIORITY}
                </div>
              </div>

              {/* Work Modes */}
              <div style={{ marginBottom: 20 }}>
                <label style={{ fontSize: 11, fontWeight: 600, color: SR.ink4, textTransform: "uppercase", display: "block", marginBottom: 8 }}>
                  Work Modes
                </label>
                <div style={{ display: "flex", gap: 8 }}>
                  {MOCK_WORK_MODES.map((mode) => (
                    <span key={mode} style={chipStyle(true)}>
                      {mode}
                    </span>
                  ))}
                </div>
              </div>

              {/* Industries */}
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: SR.ink4, textTransform: "uppercase", display: "block", marginBottom: 8 }}>
                  Industries
                </label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {MOCK_INDUSTRIES.map((ind) => (
                    <span key={ind} style={chipStyle(true)}>
                      {ind}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* 5. Resume & Documents Section */}
            <div style={panelStyle}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: SR.ink, margin: 0, marginBottom: 16 }}>
                Documents
              </h3>

              {/* Upload dropzone */}
              <div
                style={{
                  border: `2px dashed ${SR.border2}`,
                  borderRadius: 8,
                  padding: 32,
                  textAlign: "center",
                  marginBottom: 16,
                  cursor: "pointer"
                }}
              >
                <div style={{ fontSize: 24, marginBottom: 8 }}>📄</div>
                <div style={{ fontSize: 13, fontWeight: 500, color: SR.ink }}>
                  Drop your CV here or click to upload
                </div>
                <div style={{ fontSize: 12, color: SR.ink4, marginTop: 4 }}>
                  PDF, DOC, DOCX up to 10MB
                </div>
              </div>

              {/* Documents table */}
              <div style={{ borderTop: `1px solid ${SR.border}`, paddingTop: 16 }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr auto auto auto", gap: 12, fontSize: 12, marginBottom: 8 }}>
                  <div style={{ fontWeight: 600, color: SR.ink4 }}>Filename</div>
                  <div style={{ fontWeight: 600, color: SR.ink4 }}>Type</div>
                  <div style={{ fontWeight: 600, color: SR.ink4 }}>Date</div>
                  <div style={{ fontWeight: 600, color: SR.ink4 }}>Status</div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr auto auto auto", gap: 12, fontSize: 12, paddingTop: 8, borderTop: `1px solid ${SR.border}` }}>
                  <div style={{ color: SR.ink }}>resume_2024.pdf</div>
                  <div style={{ color: SR.ink3 }}>PDF</div>
                  <div style={{ color: SR.ink3 }}>Jan 15, 2024</div>
                  <span style={{
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontSize: 11,
                    backgroundColor: "rgba(34, 197, 94, 0.08)",
                    color: "#22c55e",
                    fontWeight: 500
                  }}>
                    Ready
                  </span>
                </div>
              </div>
            </div>

          </div>

          {/* RIGHT COLUMN - Sticky summary rail (~35%) */}
          <div style={{ position: "sticky", top: 24, height: "fit-content" }}>

            {/* Profile Completeness Card */}
            <div style={panelStyle}>
              <h4 style={{ fontSize: 12, fontWeight: 600, color: SR.ink4, textTransform: "uppercase", margin: 0, marginBottom: 16 }}>
                Profile Completeness
              </h4>

              {/* Circular gauge */}
              <div style={{ display: "flex", justifyContent: "center", marginBottom: 20 }}>
                <div
                  style={{
                    width: 100,
                    height: 100,
                    borderRadius: "50%",
                    background: `conic-gradient(${SR.brand} 0deg 216deg, ${SR.border} 216deg 360deg)`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center"
                  }}
                >
                  <div
                    style={{
                      width: 90,
                      height: 90,
                      borderRadius: "50%",
                      background: SR.panel,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexDirection: "column"
                    }}
                  >
                    <div style={{ fontSize: 24, fontWeight: 700, color: SR.brand }}>60%</div>
                  </div>
                </div>
              </div>

              {/* Completion items */}
              <div style={{ fontSize: 12 }}>
                <div style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}>
                  <span style={{ color: "#22c55e" }}>✓</span>
                  <span style={{ color: SR.ink }}>Profile photo</span>
                </div>
                <div style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}>
                  <span style={{ color: "#22c55e" }}>✓</span>
                  <span style={{ color: SR.ink }}>Experience added</span>
                </div>
                <div style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}>
                  <span style={{ color: "#22c55e" }}>✓</span>
                  <span style={{ color: SR.ink }}>Skills listed</span>
                </div>
                <div style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}>
                  <span style={{ color: SR.ink4 }}>✕</span>
                  <span style={{ color: SR.ink4 }}>Education</span>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{ color: SR.ink4 }}>✕</span>
                  <span style={{ color: SR.ink4 }}>Certifications</span>
                </div>
              </div>
            </div>

            {/* Connected Sources Card */}
            <div style={panelStyle}>
              <h4 style={{ fontSize: 12, fontWeight: 600, color: SR.ink4, textTransform: "uppercase", margin: 0, marginBottom: 16 }}>
                Connected Sources
              </h4>

              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {/* LinkedIn - Connected */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <span style={{ fontSize: 18 }}>in</span>
                    <span style={{ fontSize: 13, fontWeight: 500, color: SR.ink }}>LinkedIn</span>
                  </div>
                  <span style={{
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontSize: 11,
                    backgroundColor: "rgba(34, 197, 94, 0.08)",
                    color: "#22c55e",
                    fontWeight: 500
                  }}>
                    Connected
                  </span>
                </div>

                {/* Gmail - Not Connected */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <span style={{ fontSize: 18 }}>✉</span>
                    <span style={{ fontSize: 13, fontWeight: 500, color: SR.ink }}>Gmail</span>
                  </div>
                  <button
                    style={{
                      padding: "2px 8px",
                      borderRadius: 4,
                      fontSize: 11,
                      backgroundColor: SR.border,
                      color: SR.ink4,
                      fontWeight: 500,
                      border: "none",
                      cursor: "pointer"
                    }}
                  >
                    Connect
                  </button>
                </div>

                {/* Calendar - Not Connected */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <span style={{ fontSize: 18 }}>📅</span>
                    <span style={{ fontSize: 13, fontWeight: 500, color: SR.ink }}>Calendar</span>
                  </div>
                  <button
                    style={{
                      padding: "2px 8px",
                      borderRadius: 4,
                      fontSize: 11,
                      backgroundColor: SR.border,
                      color: SR.ink4,
                      fontWeight: 500,
                      border: "none",
                      cursor: "pointer"
                    }}
                  >
                    Connect
                  </button>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
