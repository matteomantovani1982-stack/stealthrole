"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

/* ── Design tokens (sr-home-timeline) ── */
const HT = {
  bg: "#f4f5fb",
  panel: "#ffffff",
  panelSoft: "#fafbff",
  border: "rgba(15,18,40,0.08)",
  border2: "rgba(15,18,40,0.14)",
  divider: "rgba(15,18,40,0.06)",
  ink: "#0c1030",
  ink2: "rgba(12,16,48,0.82)",
  ink3: "rgba(12,16,48,0.62)",
  ink4: "rgba(12,16,48,0.45)",
  ink5: "rgba(12,16,48,0.30)",
  brand: "#5B6CFF",
  brand2: "#7F8CFF",
  brandDeep: "#4754E8",
  violet: "#9F7AEA",
  brandTint: "rgba(91,108,255,0.08)",
  brandTint2: "rgba(91,108,255,0.14)",
  green: "#22c55e",
  amber: "#fbbf24",
  red: "#ef4444",
};

/* ── Mock timeline data ── */
const TIMELINE_ITEMS = [
  {
    n: 1,
    when: "TODAY · ~9h window",
    title: "Contact Maya Patel",
    sub: "Linear · Head of Talent",
    why: "Series C just closed + leadership hiring + warm intro path through Tom Moor.",
    impact: { label: "HIGHEST IMPACT", color: HT.green },
    primary: { label: "Open LinkedIn message", icon: "→" },
    secondary: { label: "View warm intro path" },
    pinColor: HT.green,
  },
  {
    n: 2,
    when: "TODAY · before 6pm",
    title: "Build CV pack for Stripe",
    sub: "Stripe · Director of Product, Atlas",
    why: "Old manager Will recommended you directly. Posting opens Wed; pack-first applicants get the call.",
    impact: { label: "HIGH IMPACT", color: HT.brand },
    primary: { label: "Generate pack", icon: "⚡" },
    secondary: { label: "Open dossier" },
    pinColor: HT.brand,
  },
  {
    n: 3,
    when: "TOMORROW",
    title: "Follow up with recruiter",
    sub: "Sarah Chen · Sequoia Talent",
    why: "Replied 3 days ago about three stealth portcos. Window closes if you wait the week.",
    impact: { label: "MEDIUM IMPACT", color: HT.violet },
    primary: { label: "Draft reply", icon: "✎" },
    secondary: { label: "View thread" },
    pinColor: HT.violet,
  },
  {
    n: 4,
    when: "THIS WEEK",
    title: "Monitor Careem expansion",
    sub: "Careem · NYC bureau opening",
    why: "Expansion signal detected — PM hires expected within 2–4 weeks. Not active yet, just watch.",
    impact: { label: "LOW · WATCH", color: HT.amber },
    primary: { label: "Add to watchlist", icon: "+" },
    secondary: { label: "Open intel" },
    pinColor: HT.amber,
  },
];

/* ── Scout's Read data ── */
const SCOUTS_READ = {
  headline: "Linear is your move this week.",
  body: "Three signals stack: a Series C close, a Head of Product req opened, and Karri asked Maya to reach out to you specifically. Your match is the strongest in the radar (94). Move on Maya before the public posting goes live.",
  bullets: [
    { l: "Strongest match", v: "Linear · 94" },
    { l: "Warm path", v: "Tom Moor · 1° · ⭑⭑⭑" },
    { l: "Window closes", v: "~9h" },
    { l: "Predicted by Scout", v: "3 days early" },
  ],
  secondary: [
    "Stripe Atlas Director req is opening Wed — start the pack today.",
    "Ramp NYC expansion is real but slow; no action this week.",
  ],
};

export default function HomePage() {
  const { user } = useAuth();
  const [active, setActive] = useState(0);

  const now = new Date();
  const dayName = now.toLocaleDateString("en-US", { weekday: "long" }).toUpperCase();
  const dateStr = now.toLocaleDateString("en-US", { day: "2-digit", month: "short" }).toUpperCase();
  const timeStr = now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
  const firstName = user?.full_name?.split(" ")[0] || user?.email?.split("@")[0] || "Alex";

  const greetingText =
    now.getHours() < 12 ? "Good morning" : now.getHours() < 18 ? "Good afternoon" : "Good evening";

  return (
    <div
      style={{
        height: "100vh",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        fontFamily: "Inter, system-ui, sans-serif",
        backgroundColor: HT.bg,
      }}
    >
      {/* ── GREETING ROW ── */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          padding: "22px 32px 14px",
        }}
      >
        <div>
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 10,
              color: HT.ink4,
              letterSpacing: 1.4,
              fontWeight: 600,
              marginBottom: 4,
            }}
          >
            {dayName} · {dateStr} · {timeStr}
          </div>
          <div
            style={{
              fontSize: 24,
              fontWeight: 700,
              letterSpacing: -0.5,
              lineHeight: 1.1,
              color: HT.ink,
              marginBottom: 2,
            }}
          >
            {greetingText}, {firstName}.
          </div>
          <div style={{ fontSize: 13, color: HT.ink3 }}>Here is your career action timeline.</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 2 }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 12px",
              borderRadius: 999,
              backgroundColor: "rgba(34,197,94,0.10)",
              border: `1px solid ${HT.green}40`,
              color: HT.green,
              fontSize: 11.5,
              fontWeight: 600,
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: HT.green }} />
            Sweep active
          </span>
          <span
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 11,
              color: HT.ink5,
              letterSpacing: 0.6,
            }}
          >
            last sweep · 6m ago
          </span>
        </div>
      </div>

      {/* ── SHORTCUT CARDS (2-column grid) ── */}
      <div
        style={{
          padding: "0 32px 18px",
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 14,
        }}
      >
        {/* Card 1: Unleash the Scout (gradient) */}
        <Link href="/scout" style={{ textDecoration: "none", display: "block" }}>
          <div
            style={{
              position: "relative",
              padding: "18px 22px",
              borderRadius: 14,
              overflow: "hidden",
              background: `linear-gradient(135deg, ${HT.brandDeep} 0%, ${HT.brand} 50%, ${HT.violet} 100%)`,
              boxShadow: `0 14px 32px rgba(91,108,255,0.32), inset 0 1px 0 rgba(255,255,255,0.18)`,
              cursor: "pointer",
              color: "#fff",
            }}
          >
            {/* Radial glow circle */}
            <div
              style={{
                position: "absolute",
                top: -40,
                right: -30,
                width: 160,
                height: 160,
                borderRadius: "50%",
                background: "radial-gradient(circle, rgba(255,255,255,0.20), transparent 70%)",
              }}
            />
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", position: "relative", zIndex: 1 }}>
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 9.5,
                    letterSpacing: 1.4,
                    opacity: 0.78,
                    fontWeight: 700,
                    marginBottom: 8,
                  }}
                >
                  JOB SCOUT
                </div>
                <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: -0.4, lineHeight: 1.15, marginBottom: 6 }}>
                  Unleash the Scout
                </div>
                <div style={{ fontSize: 12.5, lineHeight: 1.45, opacity: 0.88 }}>
                  Discover open, predicted, and hidden roles before others.
                </div>
              </div>
              <div
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 10,
                  backgroundColor: "rgba(255,255,255,0.16)",
                  border: "1px solid rgba(255,255,255,0.25)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 18,
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                →
              </div>
            </div>
          </div>
        </Link>

        {/* Card 2: Open my pipeline (white) */}
        <Link href="/applications" style={{ textDecoration: "none", display: "block" }}>
          <div
            style={{
              position: "relative",
              padding: "18px 22px",
              borderRadius: 14,
              backgroundColor: HT.panel,
              border: `1px solid ${HT.border2}`,
              boxShadow: "0 6px 18px rgba(15,18,40,0.06)",
              cursor: "pointer",
              borderLeft: `4px solid ${HT.brand}`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 9.5,
                    letterSpacing: 1.4,
                    color: HT.brand,
                    fontWeight: 700,
                    marginBottom: 8,
                  }}
                >
                  APPLICATIONS
                </div>
                <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: -0.4, lineHeight: 1.15, marginBottom: 6, color: HT.ink }}>
                  Open my pipeline
                </div>
                <div style={{ fontSize: 12.5, lineHeight: 1.45, color: HT.ink3 }}>Track applications, interviews, packs, and next actions.</div>
              </div>
              <div
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 10,
                  backgroundColor: HT.brandTint2,
                  color: HT.brand,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 18,
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                →
              </div>
            </div>
          </div>
        </Link>
      </div>

      {/* ── MAIN AREA: Timeline (left) + Scout's Read (right) ── */}
      <div
        style={{
          flex: 1,
          padding: "0 32px 24px",
          display: "grid",
          gridTemplateColumns: "1fr 360px",
          gap: 18,
          minHeight: 0,
        }}
      >
        {/* LEFT: ACTION TIMELINE PANEL */}
        <div
          style={{
            backgroundColor: HT.panel,
            border: `1px solid ${HT.border}`,
            borderRadius: 14,
            boxShadow: "0 1px 2px rgba(15,18,40,0.03)",
            padding: "20px 22px",
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
          }}
        >
          {/* Header */}
          <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 18 }}>
            <div>
              <div
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 9.5,
                  color: HT.ink4,
                  letterSpacing: 1.4,
                  fontWeight: 700,
                  marginBottom: 5,
                }}
              >
                YOUR ACTION TIMELINE · MAY 03 → MAY 09
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: -0.3, color: HT.ink }}>
                4 moves the Scout ranked for this week
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                style={{
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: `1px solid ${HT.border2}`,
                  backgroundColor: HT.panel,
                  color: HT.ink3,
                  fontSize: 11.5,
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                This week
              </button>
              <button
                style={{
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: `1px solid ${HT.border2}`,
                  backgroundColor: HT.panelSoft,
                  color: HT.ink4,
                  fontSize: 11.5,
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                Next week
              </button>
            </div>
          </div>

          {/* GRADIENT TRACK */}
          <div
            style={{
              height: 3,
              borderRadius: 2,
              background: `linear-gradient(90deg, ${HT.green} 0%, ${HT.brand} 35%, ${HT.violet} 65%, ${HT.amber} 100%)`,
              marginBottom: 24,
            }}
          />

          {/* PIN ROW */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: `repeat(${TIMELINE_ITEMS.length}, 1fr)`,
              gap: 0,
              marginBottom: 14,
            }}
          >
            {TIMELINE_ITEMS.map((it, i) => (
              <div
                key={i}
                onClick={() => setActive(i)}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  cursor: "pointer",
                }}
              >
                <div
                  style={{
                    width: 24,
                    height: 24,
                    borderRadius: "50%",
                    backgroundColor: active === i ? it.pinColor : HT.panel,
                    border: `2px solid ${it.pinColor}`,
                    boxShadow:
                      active === i
                        ? `0 0 0 5px ${it.pinColor}26, 0 6px 14px rgba(15,18,40,0.10)`
                        : "none",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 11,
                    fontWeight: 700,
                    color: active === i ? HT.panel : it.pinColor,
                    fontFamily: "'JetBrains Mono', monospace",
                    transition: "all 0.15s ease",
                  }}
                >
                  {it.n}
                </div>
                <div
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 9.5,
                    color: active === i ? it.pinColor : HT.ink5,
                    letterSpacing: 1.1,
                    fontWeight: 600,
                    marginTop: 7,
                    textAlign: "center",
                  }}
                >
                  {it.when.split(" · ")[0]}
                </div>
              </div>
            ))}
          </div>

          {/* CARDS ROW */}
          <div
            style={{
              flex: 1,
              display: "grid",
              gridTemplateColumns: `repeat(${TIMELINE_ITEMS.length}, 1fr)`,
              gap: 10,
              minHeight: 0,
            }}
          >
            {TIMELINE_ITEMS.map((it, i) => {
              const isActive = active === i;
              return (
                <div
                  key={i}
                  onClick={() => setActive(i)}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    backgroundColor: isActive ? HT.panel : HT.panelSoft,
                    border: isActive ? `1px solid rgba(91,108,255,0.32)` : `1px solid ${HT.border}`,
                    borderRadius: 10,
                    padding: "14px 14px 16px",
                    boxShadow: isActive ? `0 8px 22px rgba(91,108,255,0.12), inset 0 0 0 1px rgba(91,108,255,0.10)` : "none",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  {/* Impact badge */}
                  <div
                    style={{
                      display: "inline-flex",
                      alignSelf: "flex-start",
                      alignItems: "center",
                      gap: 5,
                      padding: "3px 8px",
                      borderRadius: 4,
                      backgroundColor: `${it.impact.color}24`,
                      color: it.impact.color,
                      fontSize: 9,
                      fontWeight: 700,
                      letterSpacing: 0.6,
                      textTransform: "uppercase",
                      marginBottom: 9,
                    }}
                  >
                    <span
                      style={{
                        width: 5,
                        height: 5,
                        borderRadius: "50%",
                        backgroundColor: it.impact.color,
                      }}
                    />
                    {it.impact.label}
                  </div>

                  {/* Title */}
                  <div
                    style={{
                      fontSize: 14,
                      fontWeight: 600,
                      letterSpacing: -0.2,
                      color: HT.ink,
                      marginBottom: 3,
                    }}
                  >
                    {it.title}
                  </div>

                  {/* Subtitle */}
                  <div
                    style={{
                      fontSize: 11.5,
                      color: HT.ink3,
                      marginBottom: 9,
                    }}
                  >
                    {it.sub}
                  </div>

                  {/* WHY section */}
                  <div
                    style={{
                      flex: 1,
                      marginBottom: 12,
                      paddingTop: 8,
                      borderTop: `1px solid ${HT.divider}`,
                    }}
                  >
                    <div
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 8.5,
                        letterSpacing: 1,
                        color: HT.ink5,
                        fontWeight: 700,
                        marginBottom: 4,
                      }}
                    >
                      WHY NOW
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: HT.ink3,
                        lineHeight: 1.5,
                      }}
                    >
                      {it.why}
                    </div>
                  </div>

                  {/* Primary button */}
                  <button
                    style={{
                      width: "100%",
                      padding: "7px 10px",
                      borderRadius: 7,
                      border: `1px solid ${it.impact.color}`,
                      backgroundColor: `${it.impact.color}20`,
                      color: it.impact.color,
                      fontSize: 11.5,
                      fontWeight: 600,
                      cursor: "pointer",
                      marginBottom: 8,
                      transition: "all 0.15s ease",
                    }}
                  >
                    {it.primary.label} {it.primary.icon}
                  </button>

                  {/* Secondary button */}
                  <button
                    style={{
                      width: "100%",
                      padding: "7px 10px",
                      borderRadius: 7,
                      border: "none",
                      backgroundColor: "transparent",
                      color: HT.ink4,
                      fontSize: 11,
                      fontWeight: 500,
                      cursor: "pointer",
                    }}
                  >
                    {it.secondary.label}
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* RIGHT: SCOUT'S READ PANEL */}
        <div
          style={{
            backgroundColor: HT.panel,
            border: `1px solid ${HT.border}`,
            borderRadius: 14,
            boxShadow: "0 1px 2px rgba(15,18,40,0.03)",
            padding: "22px 20px",
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
            overflow: "auto",
          }}
        >
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 12 }}>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 9,
                color: HT.brand,
                letterSpacing: 1.6,
                fontWeight: 700,
              }}
            >
              SCOUT'S READ
            </span>
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                backgroundColor: HT.green,
              }}
            />
          </div>

          {/* Headline */}
          <div
            style={{
              fontSize: 20,
              fontWeight: 700,
              letterSpacing: -0.4,
              color: HT.ink,
              marginBottom: 12,
              lineHeight: 1.3,
            }}
          >
            {SCOUTS_READ.headline}
          </div>

          {/* Body text */}
          <div
            style={{
              fontSize: 13,
              color: HT.ink3,
              lineHeight: 1.6,
              marginBottom: 16,
            }}
          >
            {SCOUTS_READ.body}
          </div>

          {/* Key facts grid */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 8,
              marginBottom: 16,
              paddingBottom: 16,
              borderBottom: `1px solid ${HT.divider}`,
            }}
          >
            {SCOUTS_READ.bullets.map((b, i) => (
              <div key={i}>
                <div
                  style={{
                    fontSize: 10,
                    color: HT.ink4,
                    fontWeight: 500,
                    marginBottom: 2,
                  }}
                >
                  {b.l}
                </div>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: HT.ink,
                  }}
                >
                  {b.v}
                </div>
              </div>
            ))}
          </div>

          {/* Next steps */}
          <div>
            <div
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 9,
                color: HT.ink5,
                letterSpacing: 1.6,
                fontWeight: 700,
                marginBottom: 10,
              }}
            >
              NEXT STEPS
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {SCOUTS_READ.secondary.map((s, i) => (
                <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                  <span
                    style={{
                      width: 5,
                      height: 5,
                      borderRadius: "50%",
                      backgroundColor: HT.brand,
                      marginTop: 5,
                      flexShrink: 0,
                    }}
                  />
                  <span
                    style={{
                      fontSize: 11.5,
                      color: HT.ink3,
                      lineHeight: 1.5,
                    }}
                  >
                    {s}
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
