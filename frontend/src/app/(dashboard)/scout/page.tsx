"use client";

import { useState } from "react";
import Link from "next/link";
import { SR, STAGE_COLORS, TRIGGER_COLORS } from "@/lib/constants";

export default function ScoutPage() {
  const [activeTab, setActiveTab] = useState("open-roles");

  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        backgroundColor: SR.bg,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div style={{ padding: "32px 32px 24px", borderBottom: `1px solid ${SR.border}` }}>
        <h1 style={{ margin: "0 0 8px 0", fontSize: 28, fontWeight: 600, color: SR.ink }}>
          Job Scout
        </h1>
        <p style={{ margin: 0, fontSize: 14, color: SR.ink3 }}>
          Discover opportunities before they go public.
        </p>
      </div>

      {/* Tab Bar */}
      <div
        style={{
          display: "flex",
          gap: 8,
          padding: "16px 32px",
          borderBottom: `1px solid ${SR.border}`,
          backgroundColor: SR.panel,
        }}
      >
        {[
          { id: "open-roles", label: "Open Roles" },
          { id: "predicted-roles", label: "Predicted Roles" },
          { id: "hiring-signals", label: "Hiring Signals" },
          { id: "advisory-freelance", label: "Advisory / Freelance" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "8px 16px",
              borderRadius: 20,
              fontSize: 13,
              fontWeight: 500,
              border: "none",
              cursor: "pointer",
              backgroundColor:
                activeTab === tab.id ? SR.brandTint2 : "transparent",
              color: activeTab === tab.id ? SR.brand : SR.ink3,
              transition: "all 0.2s ease",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "24px 32px",
          backgroundColor: SR.bg,
        }}
      >
        {activeTab === "open-roles" && <OpenRolesTab />}
        {activeTab === "predicted-roles" && <PredictedRolesTab />}
        {activeTab === "hiring-signals" && <HiringSignalsTab />}
        {activeTab === "advisory-freelance" && <AdvisoryFreelanceTab />}
      </div>
    </div>
  );
}

// Mock data for Open Roles
const mockOpenRoles = [
  {
    id: 1,
    company: "TechFlow Inc.",
    role: "Senior Product Designer",
    match: 92,
    salary: "$120k - $160k",
    mode: "Remote",
    location: "San Francisco, CA",
    tags: ["Design Systems", "UX Research", "Figma"],
  },
  {
    id: 2,
    company: "DataCore Systems",
    role: "Machine Learning Engineer",
    match: 88,
    salary: "$140k - $180k",
    mode: "Hybrid",
    location: "New York, NY",
    tags: ["Python", "TensorFlow", "MLOps"],
  },
  {
    id: 3,
    company: "CloudScale Ventures",
    role: "Full Stack Engineer",
    match: 85,
    salary: "$130k - $170k",
    mode: "Remote",
    location: "Austin, TX",
    tags: ["React", "Node.js", "PostgreSQL"],
  },
  {
    id: 4,
    company: "SecureVault Ltd.",
    role: "Security Architect",
    match: 78,
    salary: "$150k - $200k",
    mode: "On-site",
    location: "Boston, MA",
    tags: ["Cybersecurity", "Cloud Security", "CISO"],
  },
  {
    id: 5,
    company: "AnalyticsPro",
    role: "Analytics Lead",
    match: 72,
    salary: "$110k - $150k",
    mode: "Hybrid",
    location: "Chicago, IL",
    tags: ["SQL", "Tableau", "Data Strategy"],
  },
  {
    id: 6,
    company: "VentureLabs",
    role: "Product Manager",
    match: 68,
    salary: "$130k - $160k",
    mode: "Remote",
    location: "Los Angeles, CA",
    tags: ["B2B SaaS", "Roadmapping", "Agile"],
  },
];

function OpenRolesTab() {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
        gap: 20,
      }}
    >
      {mockOpenRoles.map((role) => (
        <RoleCard key={role.id} role={role} />
      ))}
    </div>
  );
}

function RoleCard({ role }: { role: (typeof mockOpenRoles)[0] }) {
  const gaugeColor =
    role.match >= 85 ? SR.brand : role.match >= 70 ? "#22c55e" : "#f59e0b";

  return (
    <div
      style={{
        backgroundColor: SR.panel,
        border: `1px solid ${SR.border}`,
        borderRadius: 12,
        padding: 18,
        display: "flex",
        flexDirection: "column",
        gap: 12,
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      {/* Company & Role */}
      <div>
        <p style={{ margin: "0 0 4px 0", fontSize: 12, color: SR.ink3 }}>
          {role.company}
        </p>
        <h3 style={{ margin: "0 0 8px 0", fontSize: 16, fontWeight: 600, color: SR.ink }}>
          {role.role}
        </h3>
      </div>

      {/* Match Gauge */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div
          style={{
            width: 60,
            height: 60,
            borderRadius: "50%",
            backgroundColor: SR.panelSoft,
            border: `3px solid ${gaugeColor}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <span style={{ fontSize: 20, fontWeight: 600, color: gaugeColor }}>
            {role.match}%
          </span>
        </div>
        <div style={{ flex: 1 }}>
          <p style={{ margin: "0 0 4px 0", fontSize: 11, color: SR.ink3 }}>
            Match Score
          </p>
          <p style={{ margin: 0, fontSize: 13, fontWeight: 500, color: SR.ink }}>
            {role.salary}
          </p>
          <p style={{ margin: "4px 0 0 0", fontSize: 11, color: SR.ink3 }}>
            {role.mode} · {role.location}
          </p>
        </div>
      </div>

      {/* Tags */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {role.tags.slice(0, 3).map((tag, idx) => (
          <span
            key={idx}
            style={{
              fontSize: 11,
              padding: "4px 8px",
              borderRadius: 6,
              backgroundColor: SR.brandTint,
              color: SR.brand,
            }}
          >
            {tag}
          </span>
        ))}
      </div>

      {/* Action Button */}
      <Link
        href={`/applications`}
        style={{
          marginTop: 8,
          padding: "10px 16px",
          borderRadius: 8,
          backgroundColor: SR.brand,
          color: "#ffffff",
          fontSize: 12,
          fontWeight: 600,
          textDecoration: "none",
          textAlign: "center",
          border: "none",
          cursor: "pointer",
          transition: "background-color 0.2s ease",
        }}
      >
        View Dossier
      </Link>
    </div>
  );
}

// Mock data for Predicted Roles
const mockPredictedRoles = [
  {
    id: 1,
    company: "Stripe",
    role: "Director of Engineering",
    confidence: 87,
    trigger: "Funding Round",
    basis: "Series F funding announced, expanding product teams.",
  },
  {
    id: 2,
    company: "Figma",
    role: "Principal Designer",
    confidence: 79,
    trigger: "Leadership Change",
    basis: "New SVP of Design hired to lead expansion.",
  },
  {
    id: 3,
    company: "Notion",
    role: "Head of Sales",
    confidence: 74,
    trigger: "Market Expansion",
    basis: "Targeting enterprise segment in APAC region.",
  },
  {
    id: 4,
    company: "Anthropic",
    role: "Research Scientist",
    confidence: 68,
    trigger: "Product Launch",
    basis: "New research division being established.",
  },
];

function PredictedRolesTab() {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
        gap: 20,
      }}
    >
      {mockPredictedRoles.map((pred) => (
        <PredictionCard key={pred.id} prediction={pred} />
      ))}
    </div>
  );
}

function PredictionCard({
  prediction,
}: {
  prediction: (typeof mockPredictedRoles)[0];
}) {
  return (
    <div
      style={{
        backgroundColor: SR.panel,
        border: `1px solid ${SR.border}`,
        borderRadius: 12,
        padding: 18,
        display: "flex",
        flexDirection: "column",
        gap: 12,
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      {/* Header */}
      <div>
        <p style={{ margin: "0 0 4px 0", fontSize: 12, color: SR.ink3 }}>
          {prediction.company}
        </p>
        <h3 style={{ margin: "0 0 8px 0", fontSize: 16, fontWeight: 600, color: SR.ink }}>
          {prediction.role}
        </h3>
      </div>

      {/* Confidence & Trigger */}
      <div style={{ display: "flex", gap: 12 }}>
        <div
          style={{
            flex: 1,
            padding: 10,
            borderRadius: 8,
            backgroundColor: SR.brandTint,
          }}
        >
          <p style={{ margin: "0 0 4px 0", fontSize: 10, color: SR.ink3 }}>
            Confidence
          </p>
          <p style={{ margin: 0, fontSize: 18, fontWeight: 600, color: SR.brand }}>
            {prediction.confidence}%
          </p>
        </div>
        <div
          style={{
            flex: 1,
            padding: 10,
            borderRadius: 8,
            backgroundColor: SR.panelSoft,
          }}
        >
          <p style={{ margin: "0 0 4px 0", fontSize: 10, color: SR.ink3 }}>
            Trigger
          </p>
          <p
            style={{
              margin: 0,
              fontSize: 12,
              fontWeight: 500,
              color: SR.ink,
            }}
          >
            {prediction.trigger}
          </p>
        </div>
      </div>

      {/* Basis Text */}
      <p style={{ margin: 0, fontSize: 13, color: SR.ink2, lineHeight: 1.5 }}>
        {prediction.basis}
      </p>

      {/* Action Button */}
      <Link
        href={`/applications`}
        style={{
          marginTop: 8,
          padding: "10px 16px",
          borderRadius: 8,
          backgroundColor: SR.brand,
          color: "#ffffff",
          fontSize: 12,
          fontWeight: 600,
          textDecoration: "none",
          textAlign: "center",
          border: "none",
          cursor: "pointer",
          transition: "background-color 0.2s ease",
        }}
      >
        View Details
      </Link>
    </div>
  );
}

// Mock data for Hiring Signals
const mockHiringSignals = [
  {
    id: 1,
    headline: "Seed Round Closed",
    source: "TechCrunch",
    trigger: "Funding",
    impact: "High",
    text: "Acme Corp raised $50M to expand product and sales teams.",
  },
  {
    id: 2,
    headline: "New CTO Announced",
    source: "LinkedIn",
    trigger: "Leadership",
    impact: "High",
    text: "Former Google VP joins as CTO, leading tech modernization.",
  },
  {
    id: 3,
    headline: "Acquisition Completed",
    source: "PitchBook",
    trigger: "M&A",
    impact: "Very High",
    text: "Acquired rival startup to consolidate market position.",
  },
  {
    id: 4,
    headline: "Office Expansion",
    source: "Built In",
    trigger: "Expansion",
    impact: "Medium",
    text: "Opening new engineering hub in Austin with 150 headcount.",
  },
  {
    id: 5,
    headline: "Funding Milestone",
    source: "Crunchbase",
    trigger: "Funding",
    impact: "High",
    text: "Series C raised at $2B valuation, 3x growth in headcount.",
  },
  {
    id: 6,
    headline: "Partnership Announced",
    source: "Official Blog",
    trigger: "Strategic",
    impact: "Medium",
    text: "Strategic partnership with Fortune 500 customer.",
  },
];

function HiringSignalsTab() {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
        gap: 20,
      }}
    >
      {mockHiringSignals.map((signal) => (
        <SignalCard key={signal.id} signal={signal} />
      ))}
    </div>
  );
}

function SignalCard({ signal }: { signal: (typeof mockHiringSignals)[0] }) {
  const tc = TRIGGER_COLORS[signal.trigger as keyof typeof TRIGGER_COLORS];
  const triggerColor = tc ? tc.dot : "#999";
  const triggerBg = tc ? tc.bg : "rgba(0,0,0,0.04)";
  const impactColor =
    signal.impact === "Very High"
      ? "#ef4444"
      : signal.impact === "High"
        ? "#f59e0b"
        : "#10b981";

  return (
    <div
      style={{
        backgroundColor: SR.panel,
        border: `1px solid ${SR.border}`,
        borderRadius: 12,
        padding: 18,
        display: "flex",
        flexDirection: "column",
        gap: 12,
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      {/* Headline */}
      <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: SR.ink }}>
        {signal.headline}
      </h3>

      {/* Source & Trigger */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <p style={{ margin: 0, fontSize: 11, color: SR.ink3 }}>
          {signal.source}
        </p>
        <span
          style={{
            padding: "3px 8px",
            borderRadius: 4,
            backgroundColor: triggerBg,
            color: triggerColor,
            fontSize: 10,
            fontWeight: 500,
          }}
        >
          {signal.trigger}
        </span>
      </div>

      {/* Impact Badge */}
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 10px",
          borderRadius: 6,
          backgroundColor: impactColor + "15",
          width: "fit-content",
        }}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            backgroundColor: impactColor,
          }}
        />
        <span style={{ fontSize: 11, fontWeight: 500, color: impactColor }}>
          {signal.impact}
        </span>
      </div>

      {/* Text */}
      <p style={{ margin: 0, fontSize: 13, color: SR.ink2, lineHeight: 1.5 }}>
        {signal.text}
      </p>
    </div>
  );
}

// Mock data for Advisory / Freelance
const mockGigs = [
  {
    id: 1,
    title: "Growth Strategy Advisor",
    platform: "Toptal",
    fit: 94,
    rate: "$250/hr",
    commitment: "10 hrs/week",
    duration: "3 months",
  },
  {
    id: 2,
    title: "Product Design Consultant",
    platform: "Gun.io",
    fit: 89,
    rate: "$200/hr",
    commitment: "Flexible",
    duration: "Ongoing",
  },
  {
    id: 3,
    title: "Technical Due Diligence",
    platform: "GLG",
    fit: 85,
    rate: "$350/hr",
    commitment: "Ad-hoc",
    duration: "Project-based",
  },
  {
    id: 4,
    title: "Executive Coach",
    platform: "Andela",
    fit: 76,
    rate: "$300/session",
    commitment: "2 hrs/month",
    duration: "6 months",
  },
];

function AdvisoryFreelanceTab() {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
        gap: 20,
      }}
    >
      {mockGigs.map((gig) => (
        <GigCard key={gig.id} gig={gig} />
      ))}
    </div>
  );
}

function GigCard({ gig }: { gig: (typeof mockGigs)[0] }) {
  return (
    <div
      style={{
        backgroundColor: SR.panel,
        border: `1px solid ${SR.border}`,
        borderRadius: 12,
        padding: 18,
        display: "flex",
        flexDirection: "column",
        gap: 12,
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      {/* Header */}
      <div>
        <h3 style={{ margin: "0 0 4px 0", fontSize: 15, fontWeight: 600, color: SR.ink }}>
          {gig.title}
        </h3>
        <p style={{ margin: 0, fontSize: 12, color: SR.ink3 }}>
          {gig.platform}
        </p>
      </div>

      {/* Fit & Rate */}
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <div
          style={{
            width: 50,
            height: 50,
            borderRadius: "50%",
            backgroundColor: SR.brandTint,
            border: `2px solid ${SR.brand}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <span style={{ fontSize: 18, fontWeight: 600, color: SR.brand }}>
            {gig.fit}%
          </span>
        </div>
        <div>
          <p style={{ margin: "0 0 4px 0", fontSize: 10, color: SR.ink3 }}>
            Rate
          </p>
          <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: SR.ink }}>
            {gig.rate}
          </p>
        </div>
      </div>

      {/* Commitment & Duration */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <div style={{ padding: 10, borderRadius: 8, backgroundColor: SR.panelSoft }}>
          <p style={{ margin: "0 0 4px 0", fontSize: 10, color: SR.ink3 }}>
            Commitment
          </p>
          <p style={{ margin: 0, fontSize: 12, fontWeight: 500, color: SR.ink }}>
            {gig.commitment}
          </p>
        </div>
        <div style={{ padding: 10, borderRadius: 8, backgroundColor: SR.panelSoft }}>
          <p style={{ margin: "0 0 4px 0", fontSize: 10, color: SR.ink3 }}>
            Duration
          </p>
          <p style={{ margin: 0, fontSize: 12, fontWeight: 500, color: SR.ink }}>
            {gig.duration}
          </p>
        </div>
      </div>

      {/* Action Button */}
      <Link
        href={`/applications`}
        style={{
          marginTop: 8,
          padding: "10px 16px",
          borderRadius: 8,
          backgroundColor: SR.brand,
          color: "#ffffff",
          fontSize: 12,
          fontWeight: 600,
          textDecoration: "none",
          textAlign: "center",
          border: "none",
          cursor: "pointer",
          transition: "background-color 0.2s ease",
        }}
      >
        Learn More
      </Link>
    </div>
  );
}
