"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { SR } from "@/lib/constants";

/* ── Mock timeline data (replaced by API when credits active) ── */
const TIMELINE_ITEMS = [
  {
    n: 1,
    when: "TODAY",
    title: "Review new matches",
    sub: "Scout found 3 new roles",
    why: "Fresh roles matching your profile landed overnight. Early movers get recruiter attention.",
    impact: { label: "HIGHEST IMPACT", color: SR.green },
    primary: { label: "Open Scout", href: "/scout", icon: "→" },
    secondary: { label: "View matches" },
    pinColor: SR.green,
  },
  {
    n: 2,
    when: "TODAY",
    title: "Complete your profile",
    sub: "Profile strength: 60%",
    why: "A complete profile powers better matches, stronger packs, and smarter Scout recommendations.",
    impact: { label: "HIGH IMPACT", color: SR.brand },
    primary: { label: "Open profile", href: "/profile", icon: "⚡" },
    secondary: { label: "Why this matters" },
    pinColor: SR.brand,
  },
  {
    n: 3,
    when: "THIS WEEK",
    title: "Upload your CV",
    sub: "Train the Scout on your background",
    why: "The Scout needs your CV to understand your experience and generate tailored application packs.",
    impact: { label: "MEDIUM IMPACT", color: SR.violet },
    primary: { label: "Upload CV", href: "/profile", icon: "✎" },
    secondary: { label: "Learn more" },
    pinColor: SR.violet,
  },
  {
    n: 4,
    when: "NEXT WEEK",
    title: "Explore the hidden market",
    sub: "Hiring signals before public postings",
    why: "Scout monitors funding rounds, leadership changes, and expansion signals to predict roles before they go live.",
    impact: { label: "WATCH", color: SR.amber },
    primary: { label: "Open Scout", href: "/scout", icon: "+" },
    secondary: { label: "How it works" },
    pinColor: SR.amber,
  },
];

const SCOUTS_READ = {
  headline: "Get started by completing your profile.",
  body: "The Scout works best when it knows you. Upload your CV, fill in your experience, and set your target criteria. Once your profile is complete, the Scout will start surfacing roles, signals, and warm intro paths tailored to you.",
  bullets: [
    { l: "Profile strength", v: "60%" },
    { l: "CV uploaded", v: "Not yet" },
    { l: "Target set", v: "Partial" },
    { l: "Scout status", v: "Waiting" },
  ],
  secondary: [
    "Upload your CV to unlock AI-powered pack generation.",
    "Set your target criteria to start receiving matched roles.",
  ],
};

export default function HomePage() {
  const { user } = useAuth();
  const [active, setActive] = useState(0);

  const now = new Date();
  const dayName = now.toLocaleDateString("en-US", { weekday: "long" }).toUpperCase();
  const dateStr = now.toLocaleDateString("en-US", { day: "2-digit", month: "short" }).toUpperCase();
  const timeStr = now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
  const firstName = user?.full_name?.split(" ")[0] || user?.email?.split("@")[0] || "there";

  const greetingText =
    now.getHours() < 12 ? "Good morning" : now.getHours() < 18 ? "Good afternoon" : "Good evening";

  return (
    <div
      style={{
        height: "100vh",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        fontFamily: "Inter, system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Greeting row */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "22px 32px 14px",
        }}
      >
        <div>
          <div
            style={{
              fontFamily: "'JetBrains Mono', ui-monospace, monospace",
              fontSize: 10,
              color: SR.ink4,
              letterSpacing: 1.4,
              fontWeight: 600,
              marginBottom: 4,
            }}
          >
            {dayName} &middot; {dateStr} &middot; {timeStr}
          </div>
          <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: -0.5, lineHeight: 1.1, color: SR.ink }}>
            {greetingText}, {firstName}.
          </div>
          <div style={{ fontSize: 13, color: SR.ink3, marginTop: 2 }}>
            Here is your career action timeline.
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "4px 11px",
              borderRadius: 999,
              background: "rgba(34,197,94,0.10)",
              border: "1px solid rgba(34,197,94,0.25)",
              color: SR.green,
              fontSize: 11.5,
              fontWeight: 500,
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: SR.green }} />
            Sweep active
          </span>
        </div>
      </div>

      {/* Two shortcut cards */}
      <div style={{ padding: "0 32px 18px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        {/* Unleash the Scout */}
        <Link href="/scout" style={{ textDecoration: "none", display: "block" }}>
          <div
            style={{
              position: "relative",
              padding: "18px 22px",
              borderRadius: 14,
              overflow: "hidden",
              background: `linear-gradient(135deg, ${SR.brandDeep} 0%, ${SR.brand} 50%, ${SR.violet} 100%)`,
              boxShadow: "0 14px 32px rgba(91,108,255,0.32), inset 0 1px 0 rgba(255,255,255,0.18)",
              cursor: "pointer",
              color: "#fff",
            }}
          >
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
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                    fontSize: 9.5,
                    letterSpacing: 1.4,
                    opacity: 0.78,
                    fontWeight: 700,
                    marginBottom: 8,
                  }}
                >
                  JOB SCOUT
                </div>
                <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: -0.4, lineHeight: 1.15, marginBottom: 5 }}>
                  Unleash the Scout
                </div>
                <div style={{ fontSize: 12.5, lineHeight: 1.45, opacity: 0.88, maxWidth: 380 }}>
                  Discover open, predicted, and hidden roles before others.
                </div>
              </div>
              <div
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 10,
                  background: "rgba(255,255,255,0.16)",
                  border: "1px solid rgba(255,255,255,0.25)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 18,
                  fontWeight: 600,
                }}
              >
                &rarr;
              </div>
            </div>
          </div>
        </Link>

        {/* Applications */}
        <Link href="/applications" style={{ textDecoration: "none", display: "block" }}>
          <div
            style={{
              position: "relative",
              padding: "18px 22px",
              borderRadius: 14,
              overflow: "hidden",
              background: SR.panel,
              border: `1px solid ${SR.border2}`,
              boxShadow: "0 6px 18px rgba(15,18,40,0.06)",
              cursor: "pointer",
              borderLeft: `4px solid ${SR.brand}`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                    fontSize: 9.5,
                    letterSpacing: 1.4,
                    color: SR.brand,
                    fontWeight: 700,
                    marginBottom: 8,
                  }}
                >
                  APPLICATIONS
                </div>
                <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: -0.4, lineHeight: 1.15, marginBottom: 5, color: SR.ink }}>
                  Open my pipeline
                </div>
                <div style={{ fontSize: 12.5, lineHeight: 1.45, color: SR.ink3, maxWidth: 380 }}>
                  Track applications, interviews, packs, and next actions.
                </div>
              </div>
              <div
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 10,
                  background: SR.brandTint2,
                  color: SR.brand,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 18,
                  fontWeight: 600,
                }}
              >
                &rarr;
              </div>
            </div>
          </div>
        </Link>
      </div>

      {/* Main: timeline + scout's read */}
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
        {/* TIMELINE panel */}
        <div
          style={{
            background: SR.panel,
            border: `1px solid ${SR.border}`,
            borderRadius: 14,
            boxShadow: "0 1px 2px rgba(15,18,40,0.03)",
            padding: "20px 22px 22px",
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 18 }}>
            <div>
              <div
                style={{
                  fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                  fontSize: 9.5,
                  color: SR.ink4,
                  letterSpacing: 1.4,
                  fontWeight: 600,
                  marginBottom: 5,
                }}
              >
                YOUR ACTION TIMELINE
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, color: SR.ink, letterSpacing: -0.3 }}>
                {TIMELINE_ITEMS.length} moves ranked for you
              </div>
            </div>
          </div>

          {/* Track with pins */}
          <div style={{ position: "relative", marginBottom: 14 }}>
            <div
              style={{
                position: "absolute",
                left: 18,
                right: 18,
                top: 11,
                height: 2,
                background: `linear-gradient(90deg, ${SR.green} 0%, ${SR.brand} 35%, ${SR.violet} 65%, ${SR.amber} 100%)`,
                borderRadius: 2,
                opacity: 0.45,
              }}
            />
            <div style={{ display: "grid", gridTemplateColumns: `repeat(${TIMELINE_ITEMS.length}, 1fr)`, position: "relative" }}>
              {TIMELINE_ITEMS.map((it, i) => (
                <div
                  key={i}
                  onClick={() => setActive(i)}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    cursor: "pointer",
                    position: "relative",
                    zIndex: 1,
                  }}
                >
                  <div
                    style={{
                      width: 24,
                      height: 24,
                      borderRadius: "50%",
                      background: SR.panel,
                      border: `2px solid ${it.pinColor}`,
                      boxShadow: active === i ? `0 0 0 5px ${it.pinColor}26, 0 6px 14px rgba(15,18,40,0.10)` : "none",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 11,
                      fontWeight: 700,
                      color: it.pinColor,
                      fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                      transition: "all .15s",
                    }}
                  >
                    {it.n}
                  </div>
                  <div
                    style={{
                      fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                      fontSize: 9.5,
                      color: active === i ? it.pinColor : SR.ink4,
                      letterSpacing: 1.1,
                      fontWeight: 600,
                      marginTop: 7,
                      textAlign: "center",
                    }}
                  >
                    {it.when}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Item cards */}
          <div style={{ flex: 1, display: "grid", gridTemplateColumns: `repeat(${TIMELINE_ITEMS.length}, 1fr)`, gap: 12, minHeight: 0 }}>
            {TIMELINE_ITEMS.map((it, i) => {
              const sel = active === i;
              return (
                <div
                  key={i}
                  onClick={() => setActive(i)}
                  style={{
                    position: "relative",
                    display: "flex",
                    flexDirection: "column",
                    background: sel ? SR.panel : SR.panelSoft,
                    border: `1px solid ${sel ? "rgba(91,108,255,0.32)" : SR.border}`,
                    borderRadius: 11,
                    padding: "14px 14px 14px",
                    boxShadow: sel ? `0 8px 22px rgba(91,108,255,0.12), inset 0 0 0 1px rgba(91,108,255,0.10)` : "none",
                    cursor: "pointer",
                    transition: "all .15s",
                  }}
                >
                  {/* Impact badge */}
                  <div
                    style={{
                      display: "inline-flex",
                      alignSelf: "flex-start",
                      alignItems: "center",
                      gap: 5,
                      padding: "2.5px 8px",
                      borderRadius: 4,
                      background: `${it.impact.color}1A`,
                      color: it.impact.color,
                      fontSize: 9.5,
                      fontWeight: 700,
                      letterSpacing: 0.7,
                      marginBottom: 9,
                    }}
                  >
                    <span style={{ width: 5, height: 5, borderRadius: "50%", background: it.impact.color }} />
                    {it.impact.label}
                  </div>

                  <div style={{ fontSize: 14.5, fontWeight: 700, color: SR.ink, lineHeight: 1.25, letterSpacing: -0.2, marginBottom: 3 }}>
                    {it.title}
                  </div>
                  <div style={{ fontSize: 11.5, color: SR.ink3, marginBottom: 9 }}>{it.sub}</div>

                  <div style={{ fontSize: 11.5, color: SR.ink2, lineHeight: 1.5, marginBottom: 12, flex: 1 }}>
                    <span
                      style={{
                        fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                        fontSize: 9.5,
                        color: SR.ink4,
                        letterSpacing: 0.8,
                        fontWeight: 700,
                        marginRight: 4,
                      }}
                    >
                      WHY
                    </span>
                    {it.why}
                  </div>

                  {/* Actions */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                    <Link
                      href={it.primary.href}
                      style={{
                        width: "100%",
                        padding: "9px 12px",
                        borderRadius: 8,
                        border: "none",
                        background: `linear-gradient(135deg, ${SR.brandDeep}, ${SR.violet})`,
                        color: "#fff",
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                        boxShadow: "0 6px 14px rgba(91,108,255,0.25)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 6,
                        textDecoration: "none",
                      }}
                    >
                      <span>{it.primary.label}</span>
                      <span style={{ opacity: 0.85 }}>{it.primary.icon}</span>
                    </Link>
                    <button
                      style={{
                        width: "100%",
                        padding: "8px 12px",
                        borderRadius: 8,
                        border: `1px solid ${SR.border2}`,
                        background: SR.panel,
                        color: SR.ink2,
                        fontSize: 11.5,
                        fontWeight: 500,
                        cursor: "pointer",
                      }}
                    >
                      {it.secondary.label}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* SCOUT'S READ panel */}
        <div
          style={{
            background: SR.panel,
            border: `1px solid ${SR.border}`,
            borderRadius: 14,
            boxShadow: "0 1px 2px rgba(15,18,40,0.03)",
            padding: "20px 20px 20px",
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
            overflow: "hidden",
          }}
        >
          {/* Heading */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <span
              style={{
                width: 18,
                height: 18,
                borderRadius: 5,
                background: `linear-gradient(135deg, ${SR.brandDeep}, ${SR.violet})`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
                fontSize: 10,
                fontWeight: 700,
                fontFamily: "'JetBrains Mono', ui-monospace, monospace",
              }}
            >
              S
            </span>
            <div
              style={{
                fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                fontSize: 10,
                color: SR.ink4,
                letterSpacing: 1.4,
                fontWeight: 700,
              }}
            >
              SCOUT&apos;S READ
            </div>
            <div
              style={{
                marginLeft: "auto",
                fontSize: 9.5,
                color: SR.green,
                fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                fontWeight: 700,
                letterSpacing: 0.8,
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              <span style={{ width: 5, height: 5, borderRadius: "50%", background: SR.green }} />
              LIVE
            </div>
          </div>

          <div style={{ fontSize: 16, fontWeight: 700, color: SR.ink, letterSpacing: -0.3, lineHeight: 1.25, marginBottom: 10 }}>
            {SCOUTS_READ.headline}
          </div>

          <div style={{ fontSize: 12.5, color: SR.ink2, lineHeight: 1.6, marginBottom: 14 }}>
            {SCOUTS_READ.body}
          </div>

          {/* Key facts */}
          <div
            style={{
              background: SR.brandTint,
              border: "1px solid rgba(91,108,255,0.18)",
              borderRadius: 10,
              padding: "11px 13px",
              marginBottom: 14,
            }}
          >
            {SCOUTS_READ.bullets.map((b, i, arr) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  padding: "5px 0",
                  borderBottom: i === arr.length - 1 ? "none" : "1px solid rgba(91,108,255,0.12)",
                }}
              >
                <span style={{ fontSize: 11, color: SR.ink3 }}>{b.l}</span>
                <span
                  style={{
                    fontSize: 11.5,
                    color: SR.brand,
                    fontWeight: 600,
                    fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {b.v}
                </span>
              </div>
            ))}
          </div>

          {/* Secondary reads */}
          <div
            style={{
              fontFamily: "'JetBrains Mono', ui-monospace, monospace",
              fontSize: 9.5,
              color: SR.ink4,
              letterSpacing: 1.2,
              fontWeight: 700,
              marginBottom: 7,
            }}
          >
            NEXT STEPS
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 9, flex: 1 }}>
            {SCOUTS_READ.secondary.map((s, i) => (
              <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <span style={{ width: 5, height: 5, borderRadius: "50%", background: SR.violet, marginTop: 7, flexShrink: 0 }} />
                <span style={{ fontSize: 11.5, color: SR.ink2, lineHeight: 1.5 }}>{s}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
