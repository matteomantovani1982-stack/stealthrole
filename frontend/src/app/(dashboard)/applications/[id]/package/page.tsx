"use client";

import { useState } from "react";
import Link from "next/link";

type Tab = "overview" | "strategy" | "interview" | "way-in";

// Color tokens matching sr-application-light.jsx
const AL = {
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
  watching: "#4d8ef5",
  applied: "#a78bfa",
  interview: "#22c55e",
  offer: "#fbbf24",
  rejected: "#ef4444",
  funding: "#22c55e",
  leadership: "#4d8ef5",
  hiring: "#a78bfa",
  product: "#ec4899",
  velocity: "#fb923c",
};

// Mock interview data
const interviewRounds = [
  {
    round: "Recruiter screen",
    who: "Maya Patel · Head of Talent",
    when: "30 min · video",
    eta: "Week 1",
    color: AL.watching,
    questions: [
      "Walk me through your career",
      "Why are you leaving now?",
      "What comp range?",
      "Timeline — other companies?",
    ],
    prep: [
      "90-second narrative: Notion API → Figma platform → Linear",
      "Have $280k number ready",
      "Mention late stages elsewhere",
    ],
  },
  {
    round: "Hiring manager deep-dive",
    who: "Karri Saarinen · Co-founder & CEO",
    when: "60 min · video",
    eta: "Week 1–2",
    color: AL.applied,
    questions: [
      "Describe a 0→1 product you shipped",
      "How do you prioritize with limited eng?",
      "What would you do in your first 90 days?",
      "How do you handle disagreement with founders?",
    ],
    prep: [
      "Prepare Notion AI 0→1 case study",
      "Framework: Impact · Effort · Confidence",
      "90-day plan: listen → quick wins → roadmap",
      "Use Figma founder disagreement as positive example",
    ],
  },
  {
    round: "System design / case study",
    who: "Panel (2 engineers + 1 designer)",
    when: "90 min · onsite or video",
    eta: "Week 2",
    color: AL.interview,
    questions: [
      "Design a feature from scratch for Linear",
      "Walk through your technical decision-making",
      "How do you write specs engineers love?",
      "Whiteboard an analytics pipeline",
    ],
    prep: [
      "Study Linear's issue tracker deeply",
      "Bring FigJam plugins API spec as artifact",
      "Practice whiteboard explanation of event pipelines",
      "Prepare 'spec template' you've used before",
    ],
  },
  {
    round: "Cross-functional / culture",
    who: "Product team (3 PMs)",
    when: "45 min · video",
    eta: "Week 2–3",
    color: AL.offer,
    questions: [
      "Tell us about a launch that failed",
      "How do you give feedback to engineers?",
      "What's your approach to user research?",
      "How do you handle scope creep?",
    ],
    prep: [
      "Prepare 'Figma growth funnel' failure story with lessons",
      "Framework: direct + kind + specific",
      "Notion AI user research methodology example",
      "Show scope management with data-driven trade-offs",
    ],
  },
  {
    round: "Final / founder close",
    who: "Karri Saarinen",
    when: "30 min · video",
    eta: "Week 3",
    color: AL.interview,
    questions: [
      "Why Linear specifically?",
      "Where do you see yourself in 3 years?",
      "What questions do you have for me?",
      "Are you ready to move forward?",
    ],
    prep: [
      "Be genuine about why Linear's craft culture matters to you",
      "Connect 3-year vision to Linear's roadmap",
      "Prepare 3 sharp questions about product vision",
      "Signal enthusiasm and readiness to commit",
    ],
  },
];

// Mock contact data
const contactData = [
  {
    name: "Tom Moor",
    title: "Co-founder, Linear (prev. Notion)",
    degree: 1,
    warmth: "warm",
    why: "Tom knows your Notion work. He's the warmest path to Karri.",
    draft: {
      subject: "Quick question about Linear",
      body: "Hey Tom — saw Linear just closed the C round, congrats. I've been watching the Head of Product opening and it lines up well with my background (Notion AI, Figma platform). Would you be open to a 15-min chat?",
    },
  },
  {
    name: "Maya Patel",
    title: "Head of Talent, Linear",
    degree: 1,
    warmth: "warm",
    why: "Maya is the hiring gatekeeper. She reached out to you 2 days ago.",
    draft: {
      subject: "Re: Head of Product",
      body: "Hi Maya — thanks for reaching out. I'd love to learn more about the Head of Product role. I've spent the last 3 years shipping AI products at Notion and platform tools at Figma. When works for a quick call?",
    },
  },
  {
    name: "Sarah Chen",
    title: "Partner, Sequoia",
    degree: 2,
    warmth: "weak",
    why: "Sarah co-led Linear's C round. She has hiring influence.",
    mutuals: [
      {
        name: "James Park",
        title: "Principal, Sequoia",
        note: "Worked with you at Stripe",
        strength: "strong",
      },
    ],
  },
  {
    name: "Karri Saarinen",
    title: "CEO & Co-founder, Linear",
    degree: 2,
    warmth: "cold",
    why: "Karri is the final decision-maker. Don't reach out cold — go through Tom or Maya.",
    mutuals: [
      {
        name: "Tom Moor",
        title: "Co-founder, Linear",
        note: "Direct colleague",
        strength: "strong",
      },
      {
        name: "Ellie Zhang",
        title: "VP Design, Figma (prev. Linear)",
        note: "Former Linear team",
        strength: "medium",
      },
    ],
  },
];

export default function ApplicationPackagePage() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [expandedContact, setExpandedContact] = useState<number | null>(null);

  // Mock application data
  const role = "Head of Product";
  const company = "Linear";
  const logoChar = "L";
  const logoColor = "#5E6AD2";
  const match = 94;
  const salary = "$240–$290k";
  const mode = "Remote";
  const stage = "watching";
  const stageColor = AL[stage as keyof typeof AL] || AL.watching;

  const warmthColor = (warmth: string) => {
    switch (warmth) {
      case "warm":
        return AL.good;
      case "weak":
        return AL.warn;
      case "cold":
        return AL.bad;
      default:
        return AL.ink4;
    }
  };

  const degreeLabel = (degree: number) => (degree === 1 ? "1st degree" : "2nd degree");

  return (
    <div style={{ minHeight: "100vh", background: AL.bg }}>
      {/* HERO SECTION */}
      <div style={{ padding: "28px 36px 0", background: AL.panel }}>
        {/* Back link */}
        <Link
          href="/applications"
          style={{
            fontSize: 12,
            color: AL.brand,
            textDecoration: "none",
            cursor: "pointer",
            display: "inline-block",
          }}
        >
          ← Applications
        </Link>

        {/* Main row */}
        <div style={{ display: "flex", gap: 24, marginTop: 14, alignItems: "flex-start" }}>
          {/* Company logo */}
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 13,
              background: logoColor,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#ffffff",
              fontSize: 27,
              fontWeight: 700,
              flexShrink: 0,
              boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
            }}
          >
            {logoChar}
          </div>

          {/* Info section */}
          <div style={{ flex: 1 }}>
            {/* Role name */}
            <h1
              style={{
                fontSize: 28,
                fontWeight: 700,
                letterSpacing: -0.8,
                margin: 0,
                color: AL.ink,
              }}
            >
              {role}
            </h1>

            {/* Company + mode + salary */}
            <p style={{ fontSize: 13, color: AL.ink3, margin: "8px 0 16px" }}>
              {company} · {mode} · {salary}
            </p>

            {/* Stage progression row */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 11,
                color: AL.ink3,
              }}
            >
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: AL.watching,
                }}
              />
              <span>Watching</span>
              <div style={{ color: AL.ink4 }}>→</div>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: AL.ink5,
                }}
              />
              <span>Applied</span>
              <div style={{ color: AL.ink4 }}>→</div>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: AL.ink5,
                }}
              />
              <span>Interview</span>
              <div style={{ color: AL.ink4 }}>→</div>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: AL.ink5,
                }}
              />
              <span>Offer</span>
            </div>
          </div>

          {/* Match gauge - SVG circle */}
          <div style={{ position: "relative", width: 80, height: 80, flexShrink: 0 }}>
            <svg
              viewBox="0 0 80 80"
              style={{ width: "100%", height: "100%" }}
            >
              {/* Background circle */}
              <circle
                cx="40"
                cy="40"
                r="36"
                fill="none"
                stroke={AL.border}
                strokeWidth="3"
              />
              {/* Progress arc */}
              <circle
                cx="40"
                cy="40"
                r="36"
                fill="none"
                stroke={stageColor}
                strokeWidth="3"
                strokeDasharray={`${(match / 100) * 2 * Math.PI * 36} ${
                  2 * Math.PI * 36
                }`}
                strokeLinecap="round"
                style={{
                  transform: "rotate(-90deg)",
                  transformOrigin: "40px 40px",
                }}
              />
            </svg>
            {/* Center text */}
            <div
              style={{
                position: "absolute",
                top: "50%",
                left: "50%",
                transform: "translate(-50%, -50%)",
                textAlign: "center",
              }}
            >
              <div style={{ fontSize: 22, fontWeight: 700, color: AL.ink }}>
                {match}%
              </div>
              <div style={{ fontSize: 10, color: AL.ink3, fontWeight: 600 }}>
                Match
              </div>
            </div>
          </div>
        </div>

        {/* Divider */}
        <div
          style={{
            marginTop: 24,
            borderBottom: `1px solid ${AL.divider}`,
          }}
        />
      </div>

      {/* TAB BAR */}
      <div
        style={{
          padding: "0 36px",
          marginTop: 18,
          borderBottom: `1px solid ${AL.border}`,
          display: "flex",
          gap: 0,
          background: AL.panel,
        }}
      >
        {[
          { key: "overview" as Tab, label: "Overview" },
          { key: "strategy" as Tab, label: "Strategy" },
          { key: "interview" as Tab, label: "Interview" },
          { key: "way-in" as Tab, label: "Way-In" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: "12px 16px",
              fontSize: 14,
              fontWeight: activeTab === tab.key ? 600 : 500,
              backgroundColor: "transparent",
              border: "none",
              borderBottom: activeTab === tab.key ? `2px solid ${AL.brand}` : "2px solid transparent",
              color: activeTab === tab.key ? AL.ink : AL.ink3,
              cursor: "pointer",
              transition: "all 0.2s",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* TAB CONTENT */}
      <div style={{ padding: "22px 36px 32px" }}>
        {/* OVERVIEW TAB */}
        {activeTab === "overview" && (
          <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 18 }}>
            {/* Left column */}
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              {/* Executive Summary */}
              <div
                style={{
                  background: AL.panel,
                  border: `1px solid ${AL.border}`,
                  borderRadius: 12,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    background: AL.panel2,
                    padding: "12px 16px",
                    borderBottom: `1px solid ${AL.divider}`,
                    fontSize: 11,
                    fontWeight: 600,
                    color: AL.ink3,
                    textTransform: "uppercase",
                    letterSpacing: 0.4,
                  }}
                >
                  Executive Summary
                </div>
                <div style={{ padding: "16px" }}>
                  <ol
                    style={{
                      margin: 0,
                      paddingLeft: 20,
                      display: "flex",
                      flexDirection: "column",
                      gap: 10,
                    }}
                  >
                    <li
                      style={{
                        fontSize: 13,
                        color: AL.ink2,
                        lineHeight: 1.6,
                      }}
                    >
                      You've led AI product initiatives at Notion and scaling design systems at Figma.
                      Linear's CPD role is a natural next step.
                    </li>
                    <li
                      style={{
                        fontSize: 13,
                        color: AL.ink2,
                        lineHeight: 1.6,
                      }}
                    >
                      Strong fit: 0→1 product shipping, platform thinking, and eng team partnership.
                    </li>
                    <li
                      style={{
                        fontSize: 13,
                        color: AL.ink2,
                        lineHeight: 1.6,
                      }}
                    >
                      Gap to address: haven't led a P&L, but your impact metrics are strong.
                    </li>
                  </ol>
                </div>
              </div>

              {/* Why This Role · Why Now */}
              <div
                style={{
                  background: AL.panel,
                  border: `1px solid ${AL.border}`,
                  borderRadius: 12,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    background: AL.panel2,
                    padding: "12px 16px",
                    borderBottom: `1px solid ${AL.divider}`,
                    fontSize: 11,
                    fontWeight: 600,
                    color: AL.brand,
                    textTransform: "uppercase",
                    letterSpacing: 0.4,
                  }}
                >
                  Why This Role · Why Now
                </div>
                <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: 12 }}>
                  {[
                    {
                      title: "Product-market fit",
                      desc: "Linear dominates the dev tools space. Issue tracking is still unsolved.",
                    },
                    {
                      title: "Timing",
                      desc: "Series C just closed. They're hiring for scale, not rescue.",
                    },
                    {
                      title: "Culture alignment",
                      desc: "Karri's design-first ethos matches your philosophy.",
                    },
                  ].map((item, idx) => (
                    <div key={idx}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: AL.ink }}>
                        {item.title}
                      </div>
                      <div style={{ fontSize: 12, color: AL.ink3, marginTop: 4 }}>
                        {item.desc}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Salary Intelligence */}
              <div
                style={{
                  background: AL.panel,
                  border: `1px solid ${AL.border}`,
                  borderRadius: 12,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    background: AL.panel2,
                    padding: "12px 16px",
                    borderBottom: `1px solid ${AL.divider}`,
                    fontSize: 11,
                    fontWeight: 600,
                    color: AL.ink3,
                    textTransform: "uppercase",
                    letterSpacing: 0.4,
                  }}
                >
                  Salary Intelligence
                </div>
                <div style={{ padding: "16px" }}>
                  <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", marginBottom: 12 }}>
                    <div
                      style={{
                        flex: "0 0 20%",
                        background: AL.ink5,
                      }}
                    />
                    <div
                      style={{
                        flex: "0 0 60%",
                        background: stageColor,
                      }}
                    />
                    <div
                      style={{
                        flex: "0 0 20%",
                        background: AL.ink5,
                      }}
                    />
                  </div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 11,
                      color: AL.ink3,
                    }}
                  >
                    <span>$210k</span>
                    <span style={{ fontWeight: 600 }}>$265k (yours)</span>
                    <span>$320k</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right column */}
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              {/* Company Intel */}
              <div
                style={{
                  background: AL.panel,
                  border: `1px solid ${AL.border}`,
                  borderRadius: 12,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    background: AL.panel2,
                    padding: "12px 16px",
                    borderBottom: `1px solid ${AL.divider}`,
                    fontSize: 11,
                    fontWeight: 600,
                    color: AL.ink3,
                    textTransform: "uppercase",
                    letterSpacing: 0.4,
                  }}
                >
                  Company Intel
                </div>
                <div style={{ padding: "16px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  {[
                    { label: "Founded", value: "2023" },
                    { label: "Stage", value: "Series C" },
                    { label: "Headcount", value: "~45" },
                    { label: "HQ", value: "San Francisco" },
                    { label: "Growth", value: "2x YoY" },
                    { label: "Glassdoor", value: "4.8 ⭐" },
                  ].map((field, idx) => (
                    <div key={idx}>
                      <div style={{ fontSize: 11, color: AL.ink3, marginBottom: 4 }}>
                        {field.label}
                      </div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: AL.ink }}>
                        {field.value}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Timeline */}
              <div
                style={{
                  background: AL.panel,
                  border: `1px solid ${AL.border}`,
                  borderRadius: 12,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    background: AL.panel2,
                    padding: "12px 16px",
                    borderBottom: `1px solid ${AL.divider}`,
                    fontSize: 11,
                    fontWeight: 600,
                    color: AL.ink3,
                    textTransform: "uppercase",
                    letterSpacing: 0.4,
                  }}
                >
                  Timeline
                </div>
                <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: 14 }}>
                  {[
                    { date: "May 3", event: "Applied via YC founders intro" },
                    { date: "May 4", event: "Maya reached out for recruiter screen" },
                    { date: "Expected", event: "Screen with Karri (1–2 wks)" },
                    { date: "Expected", event: "Final round (2–3 wks)" },
                  ].map((item, idx) => (
                    <div key={idx} style={{ display: "flex", gap: 12 }}>
                      <div
                        style={{
                          width: 4,
                          height: 4,
                          borderRadius: "50%",
                          background: AL.brand,
                          marginTop: 6,
                          flexShrink: 0,
                        }}
                      />
                      <div>
                        <div style={{ fontSize: 11, color: AL.ink3, fontWeight: 600 }}>
                          {item.date}
                        </div>
                        <div style={{ fontSize: 12, color: AL.ink2 }}>{item.event}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* STRATEGY TAB */}
        {activeTab === "strategy" && (
          <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 18 }}>
            {/* Left column */}
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              {/* Your Strengths */}
              <div
                style={{
                  background: AL.panel,
                  border: `1px solid ${AL.border}`,
                  borderRadius: 12,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    background: AL.panel2,
                    padding: "12px 16px",
                    borderBottom: `1px solid ${AL.divider}`,
                    fontSize: 11,
                    fontWeight: 600,
                    color: AL.good,
                    textTransform: "uppercase",
                    letterSpacing: 0.4,
                  }}
                >
                  Your Strengths
                </div>
                <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: 12 }}>
                  {[
                    { title: "0→1 product vision", desc: "Shipped Notion AI and Figma plugins from concept to adoption." },
                    { title: "Eng partnership", desc: "Deep collab with API teams. Understand backend constraints." },
                    { title: "Design systems thinking", desc: "Platform-first mentality. Built tools for tools." },
                    { title: "Maker mindset", desc: "You ship, you iterate, you listen to users directly." },
                  ].map((item, idx) => (
                    <div key={idx}>
                      <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                        <div
                          style={{
                            color: AL.good,
                            fontWeight: 700,
                            fontSize: 14,
                            marginTop: -2,
                          }}
                        >
                          ✓
                        </div>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 600, color: AL.ink }}>
                            {item.title}
                          </div>
                          <div style={{ fontSize: 12, color: AL.ink3, marginTop: 2 }}>
                            {item.desc}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Gaps to Address */}
              <div
                style={{
                  background: AL.panel,
                  border: `1px solid ${AL.border}`,
                  borderRadius: 12,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    background: AL.panel2,
                    padding: "12px 16px",
                    borderBottom: `1px solid ${AL.divider}`,
                    fontSize: 11,
                    fontWeight: 600,
                    color: AL.warn,
                    textTransform: "uppercase",
                    letterSpacing: 0.4,
                  }}
                >
                  Gaps to Address
                </div>
                <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: 12 }}>
                  {[
                    { title: "No go-to-market lead", fix: "Frame your Notion adoption curve and Figma pricing research." },
                    { title: "No hiring manager experience", fix: "Highlight PM coaching at Figma (3 reported PMs)." },
                    { title: "Startup only", fix: "Own the fact — but show you're comfortable with fast iteration." },
                  ].map((item, idx) => (
                    <div key={idx}>
                      <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                        <div
                          style={{
                            color: AL.warn,
                            fontWeight: 700,
                            fontSize: 14,
                            marginTop: -2,
                          }}
                        >
                          ⚠
                        </div>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 600, color: AL.ink }}>
                            {item.title}
                          </div>
                          <div style={{ fontSize: 12, color: AL.ink3, marginTop: 2 }}>
                            {item.fix}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right column */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {/* Recommended Approach */}
              {[
                {
                  num: 1,
                  title: "Lead with user obsession",
                  desc: "Karri prizes craft and taste. Open with how you approach user feedback loops.",
                  recommended: true,
                },
                {
                  num: 2,
                  title: "Show taste in product design",
                  desc: "Bring examples of Linear-like products you'd build. Be specific.",
                  recommended: true,
                },
                {
                  num: 3,
                  title: "Own the startup context",
                  desc: "Lean into speed and iteration. Contrast with your thinking on scale.",
                  recommended: false,
                },
                {
                  num: 4,
                  title: "Ask about their roadmap",
                  desc: "Show you've read their CEO updates. Ask about AI direction.",
                  recommended: false,
                },
              ].map((play, idx) => (
                <div
                  key={idx}
                  style={{
                    background: AL.panel,
                    border: `1px solid ${AL.border}`,
                    borderRadius: 12,
                    padding: "12px 16px",
                    position: "relative",
                    borderLeft: play.recommended ? `3px solid ${AL.brand}` : "3px solid transparent",
                  }}
                >
                  {play.recommended && (
                    <div
                      style={{
                        position: "absolute",
                        top: 8,
                        right: 8,
                        background: AL.brandTint,
                        color: AL.brand,
                        fontSize: 10,
                        fontWeight: 600,
                        padding: "3px 8px",
                        borderRadius: 4,
                      }}
                    >
                      Recommended
                    </div>
                  )}
                  <div style={{ display: "flex", gap: 10 }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 700,
                        color: AL.ink,
                        minWidth: 20,
                      }}
                    >
                      {play.num}.
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: AL.ink }}>
                        {play.title}
                      </div>
                      <div style={{ fontSize: 12, color: AL.ink3, marginTop: 2 }}>
                        {play.desc}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* INTERVIEW TAB */}
        {activeTab === "interview" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            {interviewRounds.map((interview, idx) => (
              <div
                key={idx}
                style={{
                  background: AL.panel,
                  border: `1px solid ${AL.border}`,
                  borderRadius: 12,
                  overflow: "hidden",
                }}
              >
                {/* Round header */}
                <div
                  style={{
                    background: AL.panel2,
                    padding: "12px 16px",
                    borderBottom: `1px solid ${AL.divider}`,
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                  }}
                >
                  <div
                    style={{
                      width: 38,
                      height: 38,
                      borderRadius: "50%",
                      border: `2px solid ${interview.color}`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 14,
                      fontWeight: 700,
                      color: interview.color,
                      flexShrink: 0,
                    }}
                  >
                    {idx + 1}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: AL.ink }}>
                      {interview.round}
                    </div>
                    <div style={{ fontSize: 11, color: AL.ink3, marginTop: 2 }}>
                      {interview.who}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 11, color: AL.ink3 }}>{interview.when}</div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: AL.ink, marginTop: 2 }}>
                      {interview.eta}
                    </div>
                  </div>
                </div>

                {/* Content: 2 columns */}
                <div
                  style={{
                    padding: "16px",
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: 16,
                  }}
                >
                  {/* Left: Questions */}
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: AL.ink3, marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.4 }}>
                      Likely Questions
                    </div>
                    <ol
                      style={{
                        margin: 0,
                        paddingLeft: 20,
                        display: "flex",
                        flexDirection: "column",
                        gap: 8,
                      }}
                    >
                      {interview.questions.map((q, qIdx) => (
                        <li
                          key={qIdx}
                          style={{
                            fontSize: 12,
                            color: AL.ink2,
                            lineHeight: 1.5,
                          }}
                        >
                          {q}
                        </li>
                      ))}
                    </ol>
                  </div>

                  {/* Right: Prep tips */}
                  <div>
                    <div
                      style={{
                        fontSize: 11,
                        fontWeight: 600,
                        color: AL.ink3,
                        marginBottom: 10,
                        textTransform: "uppercase",
                        letterSpacing: 0.4,
                      }}
                    >
                      Prep Tips
                    </div>
                    <ul
                      style={{
                        margin: 0,
                        paddingLeft: 20,
                        display: "flex",
                        flexDirection: "column",
                        gap: 8,
                      }}
                    >
                      {interview.prep.map((tip, tipIdx) => (
                        <li
                          key={tipIdx}
                          style={{
                            fontSize: 12,
                            color: AL.ink2,
                            lineHeight: 1.5,
                            background: AL.brandTint,
                            padding: "8px 12px",
                            borderRadius: 6,
                            listStyle: "none",
                          }}
                        >
                          {tip}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* WAY-IN TAB */}
        {activeTab === "way-in" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {contactData.map((contact, idx) => (
              <div
                key={idx}
                style={{
                  background: AL.panel,
                  border: `1px solid ${AL.border}`,
                  borderRadius: 12,
                  overflow: "hidden",
                }}
              >
                {/* Header row */}
                <div
                  style={{
                    padding: "14px 16px",
                    borderBottom:
                      expandedContact === idx ? `1px solid ${AL.divider}` : "none",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                  }}
                  onClick={() =>
                    setExpandedContact(expandedContact === idx ? null : idx)
                  }
                >
                  {/* Avatar */}
                  <div
                    style={{
                      width: 42,
                      height: 42,
                      borderRadius: "50%",
                      background: AL.brandTint,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 14,
                      fontWeight: 700,
                      color: AL.brand,
                      flexShrink: 0,
                    }}
                  >
                    {contact.name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")}
                  </div>

                  {/* Info */}
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: AL.ink }}>
                      {contact.name}
                    </div>
                    <div style={{ fontSize: 12, color: AL.ink3, marginTop: 2 }}>
                      {contact.title}
                    </div>
                  </div>

                  {/* Warmth badge */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      fontSize: 11,
                      color: AL.ink3,
                    }}
                  >
                    <div
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        background: warmthColor(contact.warmth),
                      }}
                    />
                    <span style={{ textTransform: "capitalize" }}>
                      {contact.warmth === "weak" ? "Weak" : contact.warmth}
                    </span>
                  </div>

                  {/* Degree badge */}
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      background: AL.brandTint,
                      color: AL.brand,
                      padding: "4px 8px",
                      borderRadius: 4,
                    }}
                  >
                    {degreeLabel(contact.degree)}
                  </div>
                </div>

                {/* Expanded content */}
                {expandedContact === idx && (
                  <div
                    style={{
                      padding: "16px",
                      background: AL.bg,
                      display: "flex",
                      flexDirection: "column",
                      gap: 14,
                    }}
                  >
                    {/* Why reach out */}
                    <div>
                      <div
                        style={{
                          fontSize: 11,
                          fontWeight: 600,
                          color: AL.ink3,
                          marginBottom: 8,
                          textTransform: "uppercase",
                          letterSpacing: 0.4,
                        }}
                      >
                        Why Reach Out
                      </div>
                      <div style={{ fontSize: 12, color: AL.ink2, lineHeight: 1.6 }}>
                        {contact.why}
                      </div>
                    </div>

                    {/* Draft message (if direct connection) */}
                    {contact.draft && (
                      <div>
                        <div
                          style={{
                            fontSize: 11,
                            fontWeight: 600,
                            color: AL.ink3,
                            marginBottom: 8,
                            textTransform: "uppercase",
                            letterSpacing: 0.4,
                          }}
                        >
                          Draft Message
                        </div>
                        <div
                          style={{
                            background: AL.ink,
                            color: AL.panel,
                            padding: "12px 14px",
                            borderRadius: 6,
                            fontSize: 12,
                            lineHeight: 1.5,
                            fontFamily: "monospace",
                          }}
                        >
                          <div style={{ marginBottom: 8 }}>
                            <strong>Subject:</strong> {contact.draft.subject}
                          </div>
                          <div>{contact.draft.body}</div>
                        </div>
                      </div>
                    )}

                    {/* Mutual connections */}
                    {contact.mutuals && contact.mutuals.length > 0 && (
                      <div>
                        <div
                          style={{
                            fontSize: 11,
                            fontWeight: 600,
                            color: AL.ink3,
                            marginBottom: 8,
                            textTransform: "uppercase",
                            letterSpacing: 0.4,
                          }}
                        >
                          Mutual Connections
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                          {contact.mutuals.map((mutual, midx) => (
                            <div
                              key={midx}
                              style={{
                                background: AL.panel,
                                padding: "12px 14px",
                                borderRadius: 6,
                                border: `1px solid ${AL.border}`,
                              }}
                            >
                              <div style={{ fontSize: 12, fontWeight: 600, color: AL.ink }}>
                                {mutual.name}
                              </div>
                              <div style={{ fontSize: 11, color: AL.ink3, marginTop: 2 }}>
                                {mutual.title}
                              </div>
                              {mutual.note && (
                                <div style={{ fontSize: 11, color: AL.ink3, marginTop: 4 }}>
                                  {mutual.note}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Action buttons */}
                    <div style={{ display: "flex", gap: 8 }}>
                      <button
                        style={{
                          flex: 1,
                          padding: "8px 12px",
                          background: AL.brand,
                          color: "#ffffff",
                          border: "none",
                          borderRadius: 6,
                          fontSize: 12,
                          fontWeight: 600,
                          cursor: "pointer",
                          transition: "background 0.2s",
                        }}
                        onMouseEnter={(e) => {
                          (e.currentTarget as HTMLButtonElement).style.background =
                            AL.brand2;
                        }}
                        onMouseLeave={(e) => {
                          (e.currentTarget as HTMLButtonElement).style.background =
                            AL.brand;
                        }}
                      >
                        Copy Draft
                      </button>
                      {contact.draft && (
                        <button
                          style={{
                            flex: 1,
                            padding: "8px 12px",
                            background: AL.brandTint,
                            color: AL.brand,
                            border: `1px solid ${AL.brandTint2}`,
                            borderRadius: 6,
                            fontSize: 12,
                            fontWeight: 600,
                            cursor: "pointer",
                            transition: "all 0.2s",
                          }}
                          onMouseEnter={(e) => {
                            (e.currentTarget as HTMLButtonElement).style.background =
                              AL.brandTint2;
                          }}
                          onMouseLeave={(e) => {
                            (e.currentTarget as HTMLButtonElement).style.background =
                              AL.brandTint;
                          }}
                        >
                          Send on LinkedIn
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
