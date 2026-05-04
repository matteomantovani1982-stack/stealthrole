"use client";

import { useState } from "react";

const AC = {
  bg: "#f6f7fb",
  panel: "#ffffff",
  panel2: "#fafbfd",
  border: "rgba(15,18,40,0.08)",
  border2: "rgba(15,18,40,0.14)",
  divider: "rgba(15,18,40,0.06)",
  ink: "#0c1030",
  ink2: "rgba(12,16,48,0.82)",
  ink3: "rgba(12,16,48,0.58)",
  ink4: "rgba(12,16,48,0.40)",
  ink5: "rgba(12,16,48,0.22)",
  brand: "#5B6CFF",
  brand2: "#4754E8",
  brand3: "#7F60E8",
  brandTint: "rgba(91,108,255,0.08)",
  brandTint2: "rgba(91,108,255,0.14)",
  good: "#16a34a",
  warn: "#ca8a04",
  bad: "#dc2626",
};

const EXPERIENCES = [
  {
    id: "exp1",
    company: "Notion",
    logo: "🔗",
    role: "Senior Product Manager",
    dates: "2023 – present",
    bullets: ["Led Notion AI MVP", "Owned editor surfaces"]
  },
  {
    id: "exp2",
    company: "Figma",
    logo: "◆",
    role: "Product Manager, Platform",
    dates: "2020 – 2023",
    bullets: ["Shipped FigJam plugins API", "Ran growth funnel rewrite"]
  },
  {
    id: "exp3",
    company: "Stripe",
    logo: "₪",
    role: "Associate PM, Atlas",
    dates: "2017 – 2020",
    bullets: ["First PM hire on Atlas"]
  },
  {
    id: "exp4",
    company: "McKinsey",
    logo: "⟡",
    role: "Business Analyst",
    dates: "2015 – 2017",
    bullets: []
  }
];

const SKILLS = [
  { name: "B2B SaaS", weight: 5 },
  { name: "Editor surfaces", weight: 5 },
  { name: "Growth PM", weight: 4 },
  { name: "AI/ML products", weight: 4 },
  { name: "DevTools", weight: 4 },
  { name: "Series A→C scale", weight: 4 },
  { name: "Roadmap strategy", weight: 5 },
  { name: "User research", weight: 3 },
  { name: "Pricing & packaging", weight: 3 },
  { name: "Platform PM", weight: 3 },
  { name: "Mobile", weight: 2 },
  { name: "Marketplaces", weight: 2 },
  { name: "Fintech adjacent", weight: 3 },
  { name: "0→1", weight: 5 },
  { name: "Hiring & team building", weight: 4 }
];

const DOCUMENTS = [
  { name: "Resume_2024.pdf", type: "PDF", size: "2.4 MB", status: "Ready" },
  { name: "Cover_Letter.docx", type: "DOCX", size: "1.1 MB", status: "Ready" },
  { name: "Portfolio.pdf", type: "PDF", size: "5.8 MB", status: "Ready" },
  { name: "Certificates.zip", type: "ZIP", size: "3.2 MB", status: "Archived" }
];

const STATS = [
  { label: "Packs built", value: "14" },
  { label: "Applications sent", value: "8" },
  { label: "Replies", value: "5" },
  { label: "Interviews", value: "3" },
  { label: "Offers", value: "1" },
  { label: "Hidden roles", value: "3" },
  { label: "Avg time-to-pack", value: "4.2 min" }
];

const SOURCES = [
  { name: "LinkedIn", status: "connected" },
  { name: "Greenhouse", status: "connected" },
  { name: "Lever", status: "connected" },
  { name: "Workday", status: "connected" },
  { name: "Calendar", status: "connected" },
  { name: "Email", status: "reauthorize" },
  { name: "GitHub", status: "disconnected" }
];

export default function ProfilePage() {
  const [expandedExp, setExpandedExp] = useState<string | null>(null);

  const cardStyle = {
    background: AC.panel,
    border: `1px solid ${AC.border}`,
    borderRadius: 12,
    boxShadow: "0 1px 2px rgba(15,18,40,0.03)",
    marginBottom: 18
  };

  const titleBarStyle = {
    background: AC.panel2,
    padding: "12px 16px",
    borderBottom: `1px solid ${AC.divider}`,
    fontSize: 11,
    fontWeight: 600,
    color: AC.ink3,
    textTransform: "uppercase" as const,
    letterSpacing: 0.4
  };

  const contentStyle = { padding: 18 };

  return (
    <div style={{ background: AC.bg, minHeight: "100vh", fontFamily: '"Inter, system-ui, sans-serif"' }}>
      {/* Header */}
      <div style={{
        padding: "28px 36px 22px",
        background: `linear-gradient(135deg, ${AC.brand} 0%, ${AC.brand3} 100%)`
      }}>
        <div style={{ maxWidth: 1440, margin: "0 auto" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.7)", letterSpacing: 1, marginBottom: 12, fontFamily: "'JetBrains Mono', monospace" }}>
            PROFILE · TRAIN THE SYSTEM
          </div>
          <h1 style={{ fontSize: 28, fontWeight: 600, color: "#fff", margin: "0 0 4px 0" }}>
            Alex Moreno
          </h1>
          <p style={{ fontSize: 13, color: "rgba(255,255,255,0.8)", margin: 0 }}>
            Product leader · 9 years
          </p>
        </div>
      </div>

      {/* Main content */}
      <div style={{ maxWidth: 1440, margin: "0 auto", padding: "0 36px 32px", display: "grid", gridTemplateColumns: "1fr 320px", gap: 18 }}>

        {/* LEFT COLUMN */}
        <div>

          {/* Identity Card */}
          <div style={cardStyle}>
            <div style={titleBarStyle}>Identity</div>
            <div style={{ ...contentStyle, display: "flex", gap: 18, alignItems: "flex-start" }}>
              <div style={{
                width: 88,
                height: 88,
                borderRadius: "50%",
                background: `linear-gradient(135deg, ${AC.brand} 0%, ${AC.brand3} 100%)`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
                fontSize: 28,
                fontWeight: 600,
                flexShrink: 0,
                fontFamily: "'JetBrains Mono', monospace"
              }}>
                AM
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", gap: 8, marginBottom: 12, alignItems: "center" }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: AC.ink }}>Senior Product Manager</div>
                  <span style={{ fontSize: 9, fontWeight: 700, background: AC.brandTint2, color: AC.brand, padding: "2px 6px", borderRadius: 4 }}>OPERATOR</span>
                  <span style={{ fontSize: 9, fontWeight: 700, background: "rgba(22,163,74,0.12)", color: AC.good, padding: "2px 6px", borderRadius: 4 }}>VERIFIED</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: 13 }}>
                  <div><div style={{ fontSize: 11, color: AC.ink4, fontWeight: 600, marginBottom: 2 }}>NAME</div><div style={{ color: AC.ink }}>Alex Moreno</div></div>
                  <div><div style={{ fontSize: 11, color: AC.ink4, fontWeight: 600, marginBottom: 2 }}>TITLE</div><div style={{ color: AC.ink }}>Senior Product Manager</div></div>
                  <div><div style={{ fontSize: 11, color: AC.ink4, fontWeight: 600, marginBottom: 2 }}>LOCATION</div><div style={{ color: AC.ink }}>San Francisco, CA</div></div>
                  <div><div style={{ fontSize: 11, color: AC.ink4, fontWeight: 600, marginBottom: 2 }}>EMAIL</div><div style={{ color: AC.ink }}>alex@notion.com</div></div>
                  <div><div style={{ fontSize: 11, color: AC.ink4, fontWeight: 600, marginBottom: 2 }}>PHONE</div><div style={{ color: AC.ink }}>+1 (415) 555-1234</div></div>
                  <div><div style={{ fontSize: 11, color: AC.ink4, fontWeight: 600, marginBottom: 2 }}>LINKEDIN</div><div style={{ color: AC.brand }}>linkedin.com/in/amoreno</div></div>
                </div>
              </div>
            </div>
          </div>

          {/* Experience Card */}
          <div style={cardStyle}>
            <div style={titleBarStyle}>Experience</div>
            <div style={{ ...contentStyle, position: "relative" }}>
              <div style={{ display: "flex", position: "relative" }}>
                <div style={{ width: 2, background: AC.divider, marginRight: 20 }} />
                <div style={{ flex: 1 }}>
                  {EXPERIENCES.map((exp, idx) => (
                    <div key={exp.id} style={{ marginBottom: idx < EXPERIENCES.length - 1 ? 24 : 0 }}>
                      <div style={{ display: "flex", gap: 16, position: "relative" }}>
                        <div style={{
                          width: 11,
                          height: 11,
                          borderRadius: "50%",
                          border: `2px solid ${AC.brand}`,
                          background: "#fff",
                          position: "absolute",
                          left: -26.5,
                          top: 3,
                          flexShrink: 0
                        }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 13, fontWeight: 600, color: AC.ink, marginBottom: 2 }}>{exp.role}</div>
                          <div style={{ fontSize: 12, color: AC.ink3, marginBottom: 1 }}>{exp.company}</div>
                          <div style={{ fontSize: 11, color: AC.ink4, marginBottom: 6 }}>{exp.dates}</div>
                          {exp.bullets.length > 0 && (
                            <ul style={{ margin: 0, padding: "0 0 0 16px", fontSize: 12, color: AC.ink3 }}>
                              {exp.bullets.map((bullet, bidx) => (
                                <li key={bidx} style={{ marginBottom: 2 }}>{bullet}</li>
                              ))}
                            </ul>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Skills Card */}
          <div style={cardStyle}>
            <div style={titleBarStyle}>Skills</div>
            <div style={{ ...contentStyle, display: "flex", flexWrap: "wrap", gap: 8 }}>
              {SKILLS.map((skill) => (
                <span key={skill.name} style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  padding: "5px 10px",
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 500,
                  background: skill.weight >= 4 ? AC.brandTint2 : AC.brandTint,
                  color: skill.weight >= 4 ? AC.brand2 : AC.brand,
                  whiteSpace: "nowrap"
                }}>
                  <span style={{ fontSize: 5, fontWeight: 700 }}>{"●".repeat(skill.weight)}</span>
                  {skill.name}
                </span>
              ))}
            </div>
          </div>

          {/* Target Search Card */}
          <div style={cardStyle}>
            <div style={titleBarStyle}>Target Search</div>
            <div style={contentStyle}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {[
                  { label: "Roles", value: "VP Product, Director of Product, Chief Product Officer" },
                  { label: "Work mode", value: "Remote, Hybrid" },
                  { label: "Industries", value: "SaaS, Fintech, Healthcare" },
                  { label: "Seniority", value: "Manager, Senior Manager" },
                  { label: "Company size", value: "Series A–C" },
                  { label: "Avoid", value: "Recruiting, Consulting" },
                  { label: "Stage", value: "Funded (Series A+)" },
                  { label: "Salary floor", value: "$200k + equity" },
                  { label: "Equity floor", value: "0.1%" },
                ].map((item, idx) => (
                  <div key={idx}>
                    <div style={{ fontSize: 11, color: AC.ink4, fontWeight: 600, marginBottom: 4, textTransform: "uppercase" }}>{item.label}</div>
                    <div style={{ fontSize: 12, color: AC.ink3 }}>{item.value}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Documents Card */}
          <div style={cardStyle}>
            <div style={titleBarStyle}>Documents</div>
            <div style={contentStyle}>
              <div style={{
                border: `2px dashed ${AC.border2}`,
                borderRadius: 8,
                padding: 24,
                textAlign: "center",
                marginBottom: 16,
                background: AC.panel2,
                cursor: "pointer"
              }}>
                <div style={{ fontSize: 20, marginBottom: 8 }}>📄</div>
                <div style={{ fontSize: 13, fontWeight: 500, color: AC.ink, marginBottom: 2 }}>Drop documents here or click to upload</div>
                <div style={{ fontSize: 11, color: AC.ink4 }}>PDF, DOC, DOCX up to 10MB</div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {DOCUMENTS.map((doc, idx) => (
                  <div key={idx} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px", borderRadius: 6, background: AC.panel2 }}>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 500, color: AC.ink }}>{doc.name}</div>
                      <div style={{ fontSize: 11, color: AC.ink4 }}>{doc.type} · {doc.size}</div>
                    </div>
                    <span style={{ fontSize: 9, fontWeight: 700, background: AC.brandTint, color: AC.brand, padding: "2px 6px", borderRadius: 4 }}>{doc.status}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

        </div>

        {/* RIGHT COLUMN (STICKY) */}
        <div style={{ position: "sticky", top: 18, height: "fit-content", display: "flex", flexDirection: "column", gap: 18 }}>

          {/* Live Summary Card */}
          <div style={cardStyle}>
            <div style={titleBarStyle}>Live Summary</div>
            <div style={contentStyle}>
              <div style={{ fontSize: 11, fontWeight: 600, color: AC.ink4, marginBottom: 8 }}>TARGET ROLES</div>
              <div style={{ fontSize: 12, color: AC.ink, marginBottom: 12 }}>VP Product, Director of Product</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: AC.ink4, marginBottom: 8 }}>SENIORITY</div>
              <div style={{ fontSize: 12, color: AC.ink, marginBottom: 12 }}>Manager · 9 years experience</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: AC.ink4, marginBottom: 8 }}>INDUSTRIES</div>
              <div style={{ fontSize: 12, color: AC.ink }}>SaaS, Fintech, Healthcare</div>
            </div>
          </div>

          {/* Operator Stats Card */}
          <div style={cardStyle}>
            <div style={titleBarStyle}>Operator Stats</div>
            <div style={contentStyle}>
              {STATS.map((stat, idx) => (
                <div key={idx} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 8, paddingBottom: 8, borderBottom: `1px solid ${AC.divider}` }}>
                  <div style={{ color: AC.ink4 }}>{stat.label}</div>
                  <div style={{ fontWeight: 600, color: AC.ink, fontFamily: "'JetBrains Mono', monospace" }}>{stat.value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Connected Sources Card */}
          <div style={cardStyle}>
            <div style={titleBarStyle}>Connected Sources</div>
            <div style={contentStyle}>
              {SOURCES.map((source, idx) => (
                <div key={idx} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12, marginBottom: 8, paddingBottom: 8, borderBottom: idx < SOURCES.length - 1 ? `1px solid ${AC.divider}` : "none" }}>
                  <div style={{ color: AC.ink }}>{source.name}</div>
                  <span style={{
                    fontSize: 9,
                    fontWeight: 700,
                    padding: "2px 6px",
                    borderRadius: 4,
                    background: source.status === "connected" ? "rgba(22,163,74,0.12)" : source.status === "reauthorize" ? "rgba(202,138,4,0.12)" : "rgba(12,16,48,0.08)",
                    color: source.status === "connected" ? AC.good : source.status === "reauthorize" ? AC.warn : AC.ink4,
                    textTransform: "capitalize"
                  }}>
                    {source.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
