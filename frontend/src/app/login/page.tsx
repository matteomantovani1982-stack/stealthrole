"use client";

import { FormEvent, useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

/* ── design tokens (from sr-login.jsx / sr-app-shell.jsx) ── */
const SR = {
  bg: "#03040f",
  brand: "#7F8CFF",
  brand2: "#5B6CFF",
  brand3: "#9F7AEA",
  ink: "rgba(255,255,255,0.92)",
  ink3: "rgba(255,255,255,0.62)",
  ink4: "rgba(255,255,255,0.32)",
  ink5: "rgba(255,255,255,0.18)",
  border: "rgba(255,255,255,0.06)",
  border2: "rgba(255,255,255,0.10)",
};

const MONO = "'JetBrains Mono', ui-monospace, monospace";
const INTER = "Inter, system-ui, -apple-system, sans-serif";

/* ── useCycle hook — cycles through items at interval ── */
function useCycle(length: number, ms: number, offset = 0) {
  const [i, setI] = useState(offset % Math.max(1, length));
  useEffect(() => {
    if (length <= 1) return;
    const id = setInterval(() => setI((x) => (x + 1) % length), ms);
    return () => clearInterval(id);
  }, [length, ms]);
  return i;
}

/* ── CycleFrame — cross-fade wrapper ── */
function CycleFrame({
  idx,
  frames,
}: {
  idx: number;
  frames: React.ReactNode[];
}) {
  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      {frames.map((f, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            inset: 0,
            opacity: i === idx ? 1 : 0,
            transition: "opacity .55s ease",
            pointerEvents: i === idx ? "auto" : "none",
          }}
        >
          {f}
        </div>
      ))}
    </div>
  );
}

/* ── MonitorFrame ── */
function MonitorFrame({
  label,
  accent = "#7F8CFF",
  glow,
  children,
  style,
}: {
  label: string;
  accent?: string;
  glow?: boolean;
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div
      style={{
        position: "absolute",
        background: "#0a0d2a",
        border: "1px solid rgba(255,255,255,0.10)",
        borderRadius: 6,
        overflow: "hidden",
        boxShadow: glow
          ? "0 0 0 1px rgba(127,140,255,.18), 0 12px 40px rgba(0,0,0,.55), 0 0 24px rgba(91,108,255,.18)"
          : "0 12px 40px rgba(0,0,0,.55)",
        ...style,
      }}
    >
      <div
        style={{
          height: 18,
          padding: "0 8px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          background: "rgba(0,0,0,0.35)",
          fontFamily: MONO,
          fontSize: 8,
          letterSpacing: 1,
          color: accent,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              background: accent,
              animation: "sr-pulse 1.6s ease-in-out infinite",
            }}
          />
          {label}
        </div>
        <div style={{ color: "rgba(255,255,255,0.32)" }}>● ● ●</div>
      </div>
      <div
        style={{
          position: "relative",
          height: "calc(100% - 18px)",
          overflow: "hidden",
        }}
      >
        {children}
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            height: 1,
            background:
              "linear-gradient(90deg, transparent, rgba(127,140,255,.4), transparent)",
            animation: "sr-scan-vert 5s linear infinite",
            pointerEvents: "none",
            zIndex: 5,
          }}
        />
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   SITE MOCKUPS — rich cycling content like the designer prototype
   ═══════════════════════════════════════════════════════════════ */

function SiteFT() {
  const stories = [
    {
      kicker: "CORPORATE · EXCLUSIVE",
      title:
        "Ramp CFO departs; senior finance seat opens at hyper-growth fintech",
      desc: "The speed-management unicorn is said to be moving quickly on a replacement, with three candidates in late-stage discussions.",
      tags: ["RAMP", "CFO", "EXEC"],
    },
    {
      kicker: "M&A · TECHNOLOGY",
      title: "Stripe in advanced talks for $5B secondary share sale",
      desc: "Tiger Global and Sequoia tipped as principal buyers; transaction implies a slight valuation reset.",
      tags: ["STRIPE", "SECONDARY", "FINTECH"],
    },
    {
      kicker: "AI · FUNDING",
      title: "Anthropic close to $2B Series E led by Google, sources say",
      desc: "Round expected to value the AI lab at $40B post-money; talent acquisition seen as a key use of proceeds.",
      tags: ["ANTHROPIC", "AI", "SERIES E"],
    },
  ];
  const idx = useCycle(stories.length, 5000, 0);
  return (
    <div
      style={{
        height: "100%",
        background: "#fff1e5",
        color: "#1a1a1a",
        fontFamily: "Georgia, 'Times New Roman', serif",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          padding: "6px 10px",
          borderBottom: "1px solid #d8c9b3",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          background: "#f5e3cf",
        }}
      >
        <div style={{ fontWeight: 900, fontSize: 11, letterSpacing: 0.2 }}>
          FINANCIAL TIMES
        </div>
        <div
          style={{
            fontSize: 7,
            color: "#6b5a44",
            fontFamily: MONO,
            letterSpacing: 1,
          }}
        >
          APRIL 24, 2026 · LIVE
        </div>
      </div>
      <div style={{ flex: 1, position: "relative" }}>
        <CycleFrame
          idx={idx}
          frames={stories.map((s, i) => (
            <div key={i} style={{ padding: "8px 10px" }}>
              <div
                style={{
                  fontSize: 7,
                  color: "#a04040",
                  fontFamily: MONO,
                  letterSpacing: 1.2,
                  marginBottom: 3,
                }}
              >
                {s.kicker}
              </div>
              <div
                style={{
                  fontWeight: 700,
                  fontSize: 12,
                  lineHeight: 1.2,
                  color: "#0a0a0a",
                  marginBottom: 5,
                }}
              >
                {s.title}
              </div>
              <div
                style={{
                  fontSize: 8.5,
                  color: "#3a3a3a",
                  lineHeight: 1.4,
                  marginBottom: 6,
                }}
              >
                {s.desc}
              </div>
              <div style={{ display: "flex", gap: 4 }}>
                {s.tags.map((t, j) => (
                  <span
                    key={j}
                    style={{
                      fontFamily: MONO,
                      fontSize: 7,
                      padding: "1px 5px",
                      border: "1px solid #b08060",
                      color: "#a04040",
                      borderRadius: 2,
                      letterSpacing: 0.8,
                    }}
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          ))}
        />
      </div>
    </div>
  );
}

function SiteReuters() {
  const stories = [
    {
      tag: "BREAKING",
      cat: "M&A",
      title: "Stripe in advanced talks for $5B secondary, sources say",
      desc: "Tiger Global, Sequoia tipped as buyers; valuation reset implied.",
      time: "09:14 GMT",
    },
    {
      tag: "EXCLUSIVE",
      cat: "FUNDING",
      title: "Anthropic raising $2B Series E led by Google, sources say",
      desc: "Round values AI lab at $40B post; talent acquisition plans accelerate.",
      time: "08:42 GMT",
    },
    {
      tag: "WIRE",
      cat: "PEOPLE",
      title: "Ramp CFO to depart, plans new fintech venture",
      desc: "Search for replacement underway; founder confirms internal memo.",
      time: "07:55 GMT",
    },
  ];
  const idx = useCycle(stories.length, 4200, 0);
  return (
    <div
      style={{
        height: "100%",
        background: "#fff",
        color: "#0a0a0a",
        fontFamily: INTER,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          padding: "5px 8px",
          background: "#fa6400",
          color: "#000",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div
          style={{
            fontWeight: 900,
            fontSize: 11,
            letterSpacing: -0.3,
            fontFamily: "'Times New Roman', serif",
          }}
        >
          REUTERS
        </div>
        <div style={{ fontFamily: MONO, fontSize: 7, letterSpacing: 0.8 }}>
          ● LIVE WIRE
        </div>
      </div>
      <div style={{ flex: 1, position: "relative" }}>
        <CycleFrame
          idx={idx}
          frames={stories.map((s, i) => (
            <div key={i} style={{ padding: "7px 9px" }}>
              <div
                style={{
                  display: "flex",
                  gap: 5,
                  marginBottom: 4,
                  alignItems: "center",
                }}
              >
                <span
                  style={{
                    fontFamily: MONO,
                    fontSize: 6.5,
                    padding: "1px 4px",
                    background: "#fa6400",
                    color: "#000",
                    fontWeight: 800,
                    letterSpacing: 0.6,
                  }}
                >
                  {s.tag}
                </span>
                <span
                  style={{
                    fontFamily: MONO,
                    fontSize: 6.5,
                    color: "#fa6400",
                    letterSpacing: 0.8,
                    fontWeight: 700,
                  }}
                >
                  {s.cat}
                </span>
                <span
                  style={{
                    marginLeft: "auto",
                    fontFamily: MONO,
                    fontSize: 6.5,
                    color: "#999",
                  }}
                >
                  {s.time}
                </span>
              </div>
              <div
                style={{
                  fontWeight: 800,
                  fontSize: 11,
                  lineHeight: 1.2,
                  color: "#000",
                  marginBottom: 4,
                  letterSpacing: -0.3,
                }}
              >
                {s.title}
              </div>
              <div style={{ fontSize: 8, color: "#444", lineHeight: 1.4 }}>
                {s.desc}
              </div>
            </div>
          ))}
        />
      </div>
      <div
        style={{
          padding: "3px 8px",
          background: "#000",
          color: "#fa6400",
          display: "flex",
          justifyContent: "space-between",
          fontFamily: MONO,
          fontSize: 6.5,
          letterSpacing: 0.6,
        }}
      >
        <span>
          WIRE · {idx + 1}/{stories.length}
        </span>
        <span style={{ color: "#fff" }}>RTRS · LIVE</span>
      </div>
    </div>
  );
}

function SiteBloomberg() {
  const stories = [
    {
      time: "14:18 UTC",
      kicker: "EXCLUSIVE",
      title: "Anthropic Lifts Series E Ahead of Schedule, Sources Say",
      rows: [
        ["ANTH:US", "+8.2%", "#22c55e"],
        ["GOOGL:US", "+1.1%", "#22c55e"],
        ["MSFT:US", "+0.8%", "#22c55e"],
        ["NVDA:US", "+2.3%", "#22c55e"],
      ],
    },
    {
      time: "13:42 UTC",
      kicker: "BREAKING",
      title: "Stripe Said to Tap Banks for Direct Listing Path in 2026",
      rows: [
        ["V:US", "-0.4%", "#ef4444"],
        ["MA:US", "+0.2%", "#22c55e"],
        ["ADYEY:US", "-1.1%", "#ef4444"],
        ["AFRM:US", "+3.4%", "#22c55e"],
      ],
    },
    {
      time: "12:55 UTC",
      kicker: "FIRST WORD",
      title: "Databricks Boosts Hiring; 240 New Reqs Posted Quietly",
      rows: [
        ["MDB:US", "+1.7%", "#22c55e"],
        ["SNOW:US", "-0.6%", "#ef4444"],
        ["DDOG:US", "+2.1%", "#22c55e"],
        ["NET:US", "+0.9%", "#22c55e"],
      ],
    },
  ];
  const idx = useCycle(stories.length, 4500, 2);
  return (
    <div
      style={{
        height: "100%",
        background: "#0d0d0d",
        color: "#fff",
        fontFamily: "Georgia, serif",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          padding: "5px 8px",
          borderBottom: "2px solid #ff7a00",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div
          style={{
            fontWeight: 900,
            fontSize: 10,
            letterSpacing: 0.5,
            fontFamily: "Helvetica, Arial, sans-serif",
          }}
        >
          <span style={{ color: "#ff7a00" }}>Bloomberg</span>{" "}
          <span style={{ color: "#999", fontSize: 7, fontWeight: 600 }}>
            TERMINAL
          </span>
        </div>
        <div
          style={{
            fontFamily: MONO,
            fontSize: 7,
            color: "#ff7a00",
            letterSpacing: 1,
          }}
        >
          ● LIVE
        </div>
      </div>
      <div style={{ flex: 1, position: "relative" }}>
        <CycleFrame
          idx={idx}
          frames={stories.map((s, i) => (
            <div key={i} style={{ padding: "8px 10px" }}>
              <div
                style={{
                  fontFamily: MONO,
                  fontSize: 7,
                  color: "#ff7a00",
                  letterSpacing: 1,
                  marginBottom: 3,
                }}
              >
                {s.kicker} · {s.time}
              </div>
              <div
                style={{
                  fontWeight: 700,
                  fontSize: 11,
                  lineHeight: 1.2,
                  marginBottom: 6,
                  color: "#fff",
                }}
              >
                {s.title}
              </div>
              <div
                style={{
                  fontFamily: MONO,
                  fontSize: 8,
                  color: "#bbb",
                  lineHeight: 1.6,
                }}
              >
                {s.rows.map((r, j) => (
                  <div key={j}>
                    {r[0]} <span style={{ color: r[2] }}>{r[1]}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        />
      </div>
    </div>
  );
}

function SiteCrunchbase() {
  const watchlists = [
    {
      title: "RECENT FUNDING · LAST 7D",
      deals: [
        {
          logo: "R",
          logoBg: "#000",
          name: "Revolut",
          sector: "Fintech · London",
          round: "Series F",
          amt: "$420M",
          lead: "Tiger Global",
        },
        {
          logo: "S",
          logoBg: "#635bff",
          name: "Stripe",
          sector: "Payments · SF",
          round: "Secondary",
          amt: "$6.5B",
          lead: "Sequoia",
        },
        {
          logo: "A",
          logoBg: "#d4a373",
          name: "Anthropic",
          sector: "AI · SF",
          round: "Series E",
          amt: "$2.0B",
          lead: "Google",
        },
        {
          logo: "D",
          logoBg: "#774aef",
          name: "Databricks",
          sector: "Data · SF",
          round: "Series J",
          amt: "$10B",
          lead: "Thrive",
        },
        {
          logo: "P",
          logoBg: "#0d9488",
          name: "Perplexity",
          sector: "AI Search · SF",
          round: "Series C",
          amt: "$520M",
          lead: "IVP",
        },
        {
          logo: "H",
          logoBg: "#f97316",
          name: "Hex",
          sector: "Analytics · SF",
          round: "Series C",
          amt: "$150M",
          lead: "Iconiq",
        },
      ],
    },
    {
      title: "AI INFRA · TRENDING",
      deals: [
        {
          logo: "T",
          logoBg: "#0d9488",
          name: "Together",
          sector: "GPU Infra · SF",
          round: "Series B",
          amt: "$120M",
          lead: "Salesforce",
        },
        {
          logo: "F",
          logoBg: "#ef4444",
          name: "Fireworks",
          sector: "Inference · SF",
          round: "Series A",
          amt: "$52M",
          lead: "Benchmark",
        },
        {
          logo: "M",
          logoBg: "#7F8CFF",
          name: "Modal Labs",
          sector: "Compute · NYC",
          round: "Seed+",
          amt: "$16M",
          lead: "Redpoint",
        },
        {
          logo: "L",
          logoBg: "#a78bfa",
          name: "Lambda Labs",
          sector: "Cloud GPU · SF",
          round: "Series C",
          amt: "$320M",
          lead: "USIT",
        },
        {
          logo: "R",
          logoBg: "#22c55e",
          name: "Replicate",
          sector: "Model Hosting · SF",
          round: "Series B",
          amt: "$40M",
          lead: "a16z",
        },
        {
          logo: "O",
          logoBg: "#fbbf24",
          name: "Octo AI",
          sector: "Inference · SEA",
          round: "Series B",
          amt: "$85M",
          lead: "Tiger",
        },
      ],
    },
  ];
  const idx = useCycle(watchlists.length, 6000, 0);
  return (
    <div
      style={{
        height: "100%",
        background: "#f5f7fa",
        color: "#0a0a0a",
        fontFamily: INTER,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          padding: "5px 8px",
          background: "#0288d1",
          color: "#fff",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ fontWeight: 800, fontSize: 10, letterSpacing: 0.3 }}>
          crunchbase
        </div>
        <div style={{ fontFamily: MONO, fontSize: 7, opacity: 0.85 }}>
          {watchlists[idx].title}
        </div>
      </div>
      <div
        style={{
          padding: "4px 8px",
          background: "#e8eef3",
          borderBottom: "1px solid #d6dde4",
          display: "flex",
          justifyContent: "space-between",
          fontFamily: MONO,
          fontSize: 6.5,
          color: "#5a6470",
          letterSpacing: 0.8,
          fontWeight: 700,
        }}
      >
        <span style={{ width: "42%" }}>COMPANY</span>
        <span style={{ width: "22%" }}>ROUND</span>
        <span style={{ width: "18%" }}>AMOUNT</span>
        <span style={{ width: "18%", textAlign: "right" }}>LEAD</span>
      </div>
      <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        <CycleFrame
          idx={idx}
          frames={watchlists.map((wl, i) => (
            <div key={i}>
              {wl.deals.map((d, j) => (
                <div
                  key={j}
                  style={{
                    padding: "4px 8px",
                    display: "flex",
                    alignItems: "center",
                    borderBottom: "1px solid #e0e6ec",
                    background: j % 2 ? "#f9fafb" : "#fff",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 5,
                      width: "42%",
                      minWidth: 0,
                    }}
                  >
                    <div
                      style={{
                        width: 16,
                        height: 16,
                        borderRadius: 3,
                        background: d.logoBg,
                        color: "#fff",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontWeight: 900,
                        fontSize: 8,
                        flexShrink: 0,
                      }}
                    >
                      {d.logo}
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div
                        style={{
                          fontWeight: 700,
                          fontSize: 8.5,
                          lineHeight: 1.1,
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {d.name}
                      </div>
                      <div
                        style={{
                          fontSize: 6.5,
                          color: "#7a8290",
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {d.sector}
                      </div>
                    </div>
                  </div>
                  <div
                    style={{
                      width: "22%",
                      fontSize: 7.5,
                      color: "#0288d1",
                      fontWeight: 600,
                    }}
                  >
                    {d.round}
                  </div>
                  <div
                    style={{
                      width: "18%",
                      fontSize: 8.5,
                      fontWeight: 800,
                      color: "#0a0a0a",
                      fontFamily: MONO,
                    }}
                  >
                    {d.amt}
                  </div>
                  <div
                    style={{
                      width: "18%",
                      fontSize: 7,
                      color: "#5a6470",
                      textAlign: "right",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {d.lead}
                  </div>
                </div>
              ))}
            </div>
          ))}
        />
      </div>
    </div>
  );
}

function SiteLinkedIn() {
  const posts = [
    {
      initials: "NS",
      name: "Nikolay Storonsky",
      role: "CEO · Revolut · 1d",
      body: "Huge week ahead. We're launching Revolut Wealth and building out the team. Top talent: let's talk.",
      tags: ["#hiring", "#fintech", "#london"],
    },
    {
      initials: "DK",
      name: "Dario Kerkez",
      role: "VP Engineering · Stripe · 6h",
      body: "São Paulo office officially opens Monday. Hiring 200+ engineers and risk leaders across LATAM. DMs open.",
      tags: ["#stripe", "#latam", "#hiring"],
    },
    {
      initials: "AS",
      name: "Avlok Kohli",
      role: "CEO · AngelList · 2d",
      body: "The hidden market is real — 62% of senior roles never get posted publicly. Here's what we saw last quarter.",
      tags: ["#hiring", "#talent", "#data"],
    },
  ];
  const idx = useCycle(posts.length, 4400, 1);
  return (
    <div
      style={{
        height: "100%",
        background: "#f3f2ef",
        color: "#0a0a0a",
        fontFamily: INTER,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          padding: "4px 8px",
          background: "#fff",
          borderBottom: "1px solid #e0e0e0",
          display: "flex",
          alignItems: "center",
          gap: 5,
        }}
      >
        <span
          style={{
            background: "#0a66c2",
            color: "#fff",
            fontWeight: 900,
            fontSize: 10,
            padding: "1px 4px",
            borderRadius: 2,
            fontFamily: "Helvetica, Arial, sans-serif",
          }}
        >
          in
        </span>
        <span style={{ fontWeight: 700, fontSize: 9, color: "#0a66c2" }}>
          LinkedIn
        </span>
        <span
          style={{
            marginLeft: "auto",
            fontSize: 7,
            color: "#888",
            fontFamily: MONO,
          }}
        >
          POST {idx + 1}/{posts.length}
        </span>
      </div>
      <div style={{ flex: 1, position: "relative", padding: 6 }}>
        <CycleFrame
          idx={idx}
          frames={posts.map((p, i) => (
            <div
              key={i}
              style={{
                background: "#fff",
                borderRadius: 6,
                border: "1px solid #e0e0e0",
                padding: 8,
                height: "calc(100% - 0px)",
                boxSizing: "border-box",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  marginBottom: 6,
                }}
              >
                <div
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: "50%",
                    background:
                      "linear-gradient(135deg,#7F8CFF,#9F7AEA)",
                    color: "#fff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 700,
                    fontSize: 9,
                  }}
                >
                  {p.initials}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 9,
                      fontWeight: 700,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {p.name}
                  </div>
                  <div style={{ fontSize: 7, color: "#666" }}>{p.role}</div>
                </div>
              </div>
              <div
                style={{ fontSize: 8.5, lineHeight: 1.4, color: "#0a0a0a" }}
              >
                {p.body}
              </div>
              <div style={{ display: "flex", gap: 4, marginTop: 5 }}>
                {p.tags.map((t, j) => (
                  <span
                    key={j}
                    style={{
                      fontSize: 7,
                      padding: "1px 4px",
                      background: "#eef3fb",
                      color: "#0a66c2",
                      borderRadius: 2,
                    }}
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          ))}
        />
      </div>
    </div>
  );
}

function SiteLayoffs() {
  const events = [
    {
      co: "Twilio",
      n: 120,
      pct: 6,
      team: "Sales · Customer Success",
      date: "Apr 23",
    },
    {
      co: "Cruise",
      n: 900,
      pct: 24,
      team: "Robotaxi Ops · Eng",
      date: "Apr 21",
    },
    {
      co: "Klarna",
      n: 500,
      pct: 10,
      team: "Risk · Compliance",
      date: "Apr 19",
    },
  ];
  const idx = useCycle(events.length, 3500, 1);
  return (
    <div
      style={{
        height: "100%",
        background: "#fafafa",
        color: "#0a0a0a",
        fontFamily: INTER,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          padding: "5px 8px",
          background: "#000",
          color: "#fff",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "2px solid #ef4444",
        }}
      >
        <div style={{ fontWeight: 900, fontSize: 10, letterSpacing: -0.3 }}>
          layoffs.fyi
        </div>
        <div
          style={{
            fontFamily: MONO,
            fontSize: 7,
            color: "#ef4444",
            letterSpacing: 0.8,
          }}
        >
          ● TRACKING · 2026
        </div>
      </div>
      <div style={{ flex: 1, position: "relative" }}>
        <CycleFrame
          idx={idx}
          frames={events.map((ev, i) => (
            <div key={i} style={{ padding: "7px 9px" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  marginBottom: 3,
                }}
              >
                <div
                  style={{
                    fontWeight: 800,
                    fontSize: 13,
                    color: "#000",
                    letterSpacing: -0.3,
                  }}
                >
                  {ev.co}
                </div>
                <div style={{ fontFamily: MONO, fontSize: 7, color: "#888" }}>
                  {ev.date}
                </div>
              </div>
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-end",
                  gap: 8,
                  marginBottom: 5,
                }}
              >
                <div>
                  <div
                    style={{
                      fontFamily: MONO,
                      fontSize: 6.5,
                      color: "#888",
                      letterSpacing: 0.6,
                    }}
                  >
                    LAID OFF
                  </div>
                  <div
                    style={{
                      fontSize: 18,
                      fontWeight: 900,
                      color: "#ef4444",
                      letterSpacing: -0.6,
                      fontFamily: MONO,
                      lineHeight: 1,
                    }}
                  >
                    {ev.n}
                  </div>
                </div>
                <div style={{ paddingBottom: 1 }}>
                  <div
                    style={{
                      fontFamily: MONO,
                      fontSize: 6.5,
                      color: "#888",
                      letterSpacing: 0.6,
                    }}
                  >
                    OF TOTAL
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 800,
                      color: "#000",
                      fontFamily: MONO,
                    }}
                  >
                    {ev.pct}%
                  </div>
                </div>
              </div>
              <div style={{ fontSize: 7.5, color: "#444", lineHeight: 1.4 }}>
                <div>
                  <span style={{ color: "#888" }}>Teams:</span> {ev.team}
                </div>
              </div>
            </div>
          ))}
        />
      </div>
    </div>
  );
}

function SiteSecureTerminal() {
  const lines = [
    { c: "#a78bfa", t: "$ scout --mode=stealth" },
    { c: "rgba(255,255,255,.6)", t: "connecting…" },
    { c: "#22c55e", t: "✓ certificate verified" },
    { c: "#22c55e", t: "✓ tunnel established" },
    { c: "#22c55e", t: "✓ watching 142 companies" },
    { c: "rgba(255,255,255,.5)", t: "47 new signals" },
    { c: "#7F8CFF", t: "$ _" },
  ];
  return (
    <div
      style={{
        height: "100%",
        background: "#0a0d2a",
        padding: "10px 12px",
        color: "#fff",
      }}
    >
      <div
        style={{
          fontFamily: MONO,
          fontSize: 8,
          color: "#22c55e",
          letterSpacing: 1.5,
          marginBottom: 4,
        }}
      >
        STEALTH ROLE · SCOUT
      </div>
      <div
        style={{
          height: 1,
          background: "rgba(127,140,255,0.18)",
          marginBottom: 6,
        }}
      />
      <div style={{ fontFamily: MONO, fontSize: 9, lineHeight: 1.5 }}>
        {lines.map((l, i) => (
          <div
            key={i}
            style={{
              color: l.c,
              animation:
                i === lines.length - 1
                  ? "sr-blink 1.2s steps(2) infinite"
                  : "none",
            }}
          >
            {l.t}
          </div>
        ))}
      </div>
      <button
        style={{
          marginTop: 6,
          width: "100%",
          padding: "5px 8px",
          border: "none",
          background: `linear-gradient(135deg, ${SR.brand2}, ${SR.brand3})`,
          color: "#fff",
          fontFamily: INTER,
          fontSize: 9,
          letterSpacing: 0.2,
          fontWeight: 600,
          borderRadius: 3,
          cursor: "pointer",
          boxShadow: "0 4px 10px rgba(91,108,255,.3)",
        }}
      >
        Sign in →
      </button>
    </div>
  );
}

function SiteHiringBars() {
  const bars = [42, 28, 56, 38, 64, 50, 72, 44, 58, 36, 68, 48, 62, 40];
  return (
    <div
      style={{
        height: "100%",
        background: "#0a0d2a",
        padding: "10px 12px",
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <div
          style={{
            fontFamily: INTER,
            fontSize: 18,
            fontWeight: 700,
            color: "#fff",
            letterSpacing: -0.5,
          }}
        >
          +34%
        </div>
        <div
          style={{
            fontFamily: MONO,
            fontSize: 7,
            color: "rgba(255,255,255,.5)",
            letterSpacing: 1,
          }}
        >
          WoW · 12 COS
        </div>
      </div>
      <div
        style={{ flex: 1, display: "flex", gap: 3, alignItems: "flex-end" }}
      >
        {bars.map((b, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: `${b}%`,
              borderRadius: "2px 2px 0 0",
              background: "linear-gradient(180deg, #7F8CFF, #5B6CFF)",
              opacity: 0.45 + (b / 100) * 0.55,
              transformOrigin: "bottom",
              animation: `sr-bar 2.${(i % 9) + 1}s ease-in-out ${i * 0.07}s infinite`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

function SiteTechCrunch() {
  const features = [
    {
      tag: "EXCLUSIVE",
      cat: "VENTURE",
      title: "Scale AI quietly closes $1B at $14B valuation",
      lede: "Round led by Accel; funds expected to drive go-to-market and applied research hiring.",
    },
    {
      tag: "BREAKING",
      cat: "FINTECH",
      title: "Ramp's CFO exits to launch a new fintech venture",
      lede: "The departure caps a six-month strategy review; founders confirm internal memo.",
    },
    {
      tag: "SCOOP",
      cat: "ENTERPRISE",
      title: "Datadog in late talks to recruit VP Eng from AWS",
      lede: "Two sources say an offer is expected within two weeks; comp package said to be substantial.",
    },
  ];
  const idx = useCycle(features.length, 4800, 0);
  return (
    <div
      style={{
        height: "100%",
        background: "#fff",
        color: "#0a0a0a",
        fontFamily: INTER,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          padding: "5px 8px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid #e5e5e5",
          background: "#0f9b56",
        }}
      >
        <div
          style={{
            fontWeight: 900,
            fontSize: 12,
            letterSpacing: -0.4,
            color: "#fff",
          }}
        >
          TechCrunch
        </div>
        <div
          style={{
            fontFamily: MONO,
            fontSize: 6.5,
            color: "rgba(255,255,255,.85)",
            letterSpacing: 0.6,
          }}
        >
          · LIVE
        </div>
      </div>
      <div style={{ flex: 1, position: "relative" }}>
        <CycleFrame
          idx={idx}
          frames={features.map((f, i) => (
            <div key={i} style={{ padding: "7px 9px 5px" }}>
              <div
                style={{
                  fontFamily: MONO,
                  fontSize: 6.5,
                  color: "#0f9b56",
                  letterSpacing: 1.2,
                  marginBottom: 3,
                  fontWeight: 800,
                }}
              >
                {f.tag} · {f.cat}
              </div>
              <div
                style={{
                  fontWeight: 800,
                  fontSize: 11,
                  lineHeight: 1.2,
                  marginBottom: 3,
                  letterSpacing: -0.3,
                  color: "#0a0a0a",
                }}
              >
                {f.title}
              </div>
              <div
                style={{ fontSize: 7.5, color: "#5a5a5a", lineHeight: 1.35 }}
              >
                {f.lede}
              </div>
            </div>
          ))}
        />
      </div>
    </div>
  );
}

/* ── HUD top bar ── */
function HudTop() {
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: 0,
        height: 34,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 22px",
        borderBottom: `1px solid ${SR.border}`,
        background:
          "linear-gradient(180deg, rgba(11,15,42,.7), rgba(11,15,42,.3))",
        fontFamily: MONO,
        fontSize: 9,
        letterSpacing: 1.6,
        color: "rgba(255,255,255,.5)",
        zIndex: 20,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            color: "#7F8CFF",
          }}
        >
          <span
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              background: "#22c55e",
              animation: "sr-pulse 1.6s ease-in-out infinite",
            }}
          />
          STEALTH ROLE
        </span>
        <span style={{ color: "rgba(255,255,255,.32)" }}>·</span>
        <span>SCOUT · LIVE</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <span>4,128 COMPANIES</span>
        <span>1,267 SIGNALS / 24H</span>
        <span style={{ color: "rgba(255,255,255,.78)" }}>APR 24, 2026</span>
      </div>
    </div>
  );
}

/* ── HUD bottom ticker ── */
function HudBottomTicker() {
  const items = [
    "● RAMP · CFO wire +180M",
    "VP GROWTH FORMING",
    "ETA 9D",
    "CONF 94%",
    "● KLARNA · Chief of Staff req opened (unposted)",
    "ETA 4D",
    "● REVOLUT · GM Wealth confirmed",
    "ETA 7D",
    "CONF 90%",
    "● DATADOG · VP Eng poach window open",
    "● STRIPE · LATAM hiring spree forming",
  ];
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 0,
        height: 32,
        borderTop: `1px solid ${SR.border}`,
        background:
          "linear-gradient(0deg, rgba(11,15,42,.85), rgba(11,15,42,.4))",
        display: "flex",
        alignItems: "center",
        overflow: "hidden",
        fontFamily: MONO,
        fontSize: 9,
        letterSpacing: 1.4,
        zIndex: 20,
      }}
    >
      <div
        style={{
          flexShrink: 0,
          padding: "0 12px",
          height: "100%",
          display: "flex",
          alignItems: "center",
          background: "rgba(127,140,255,.12)",
          color: "#7F8CFF",
          borderRight: `1px solid ${SR.border}`,
        }}
      >
        ALERTS
      </div>
      <div
        style={{
          display: "flex",
          whiteSpace: "nowrap",
          animation: "sr-tick-left 60s linear infinite",
          paddingLeft: 18,
          color: "rgba(255,255,255,.62)",
        }}
      >
        {[0, 1].map((k) => (
          <span
            key={k}
            style={{ display: "inline-flex", gap: 24, paddingRight: 24 }}
          >
            {items.map((t, i) => (
              <span key={i}>{t}</span>
            ))}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ── Monitor wall ── */
function MonitorWall() {
  /* Monitors positioned using the designer's exact pixel coordinates
     on a 1440×900 canvas, scaled via percentage positioning */
  const monitors: {
    x: number;
    y: number;
    w: number;
    h: number;
    label: string;
    comp: React.ReactNode;
    accent: string;
    glow?: boolean;
  }[] = [
    // top row
    {
      x: 20,
      y: 56,
      w: 320,
      h: 220,
      label: "FT.COM · LIVE",
      comp: <SiteFT />,
      accent: "#a04040",
    },
    {
      x: 360,
      y: 56,
      w: 290,
      h: 200,
      label: "CRUNCHBASE · NEW",
      comp: <SiteCrunchbase />,
      accent: "#0288d1",
    },
    {
      x: 670,
      y: 46,
      w: 270,
      h: 180,
      label: "BLOOMBERG · TERMINAL",
      comp: <SiteBloomberg />,
      accent: "#ff7a00",
    },
    {
      x: 960,
      y: 56,
      w: 320,
      h: 250,
      label: "SECURE TERMINAL · CH.07",
      comp: <SiteSecureTerminal />,
      accent: "#22c55e",
      glow: true,
    },

    // middle row
    {
      x: 60,
      y: 296,
      w: 240,
      h: 180,
      label: "LINKEDIN · FEED",
      comp: <SiteLinkedIn />,
      accent: "#0a66c2",
    },
    {
      x: 320,
      y: 276,
      w: 240,
      h: 200,
      label: "REUTERS · BREAKING",
      comp: <SiteReuters />,
      accent: "#ff8000",
    },
    {
      x: 670,
      y: 246,
      w: 270,
      h: 170,
      label: "TECHCRUNCH · LIVE",
      comp: <SiteTechCrunch />,
      accent: "#0f9b56",
    },

    // bottom row
    {
      x: 60,
      y: 496,
      w: 250,
      h: 200,
      label: "LAYOFFS.FYI",
      comp: <SiteLayoffs />,
      accent: "#ef4444",
    },
    {
      x: 330,
      y: 496,
      w: 220,
      h: 180,
      label: "CRUNCHBASE · WATCHLIST",
      comp: <SiteCrunchbase />,
      accent: "#0288d1",
    },
    {
      x: 960,
      y: 326,
      w: 320,
      h: 190,
      label: "HIRING VELOCITY",
      comp: <SiteHiringBars />,
      accent: "#7F8CFF",
    },
  ];

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      {/* Background */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse 80% 80% at 50% 50%, rgba(20,18,52,.55) 0%, rgba(3,4,15,.85) 70%)",
        }}
      />
      {/* Dot grid */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.16,
          backgroundImage:
            "radial-gradient(rgba(127,140,255,.5) 1px, transparent 1px)",
          backgroundSize: "22px 22px",
        }}
      />

      {/* Monitors — scaled to fill viewport width */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          /* Scale monitors designed for 1440×900 to fill viewport */
        }}
      >
        {monitors.map((m, i) => (
          <MonitorFrame
            key={i}
            label={m.label}
            accent={m.accent}
            glow={m.glow}
            style={{
              left: `${(m.x / 1440) * 100}%`,
              top: `${(m.y / 900) * 100}%`,
              width: `${(m.w / 1440) * 100}%`,
              height: `${(m.h / 900) * 100}%`,
              minWidth: 180,
              minHeight: 120,
              opacity: 0.96,
            }}
          >
            {m.comp}
          </MonitorFrame>
        ))}
      </div>

      {/* glass haze */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(180deg, rgba(3,4,15,.18) 0%, rgba(3,4,15,.06) 35%, rgba(3,4,15,.42) 100%)",
          pointerEvents: "none",
        }}
      />
      {/* Indigo glow center */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse 60% 70% at 50% 60%, rgba(91,108,255,.10) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />
      {/* Heavy radial veil to push center forward (from designer SRLoginB) */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse 42% 50% at 50% 52%, rgba(3,4,15,.92) 0%, rgba(3,4,15,.72) 35%, rgba(3,4,15,.38) 60%, rgba(3,4,15,.05) 85%)",
          pointerEvents: "none",
        }}
      />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   LOGIN PAGE — Command Deck (from Claude Designer sr-login.jsx)
   ═══════════════════════════════════════════════════════════════ */
export default function LoginPage() {
  const { login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [step, setStep] = useState<"email" | "password">("email");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [socialLoading, setSocialLoading] = useState("");

  async function handleContinue(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (step === "email") {
      if (!email) return;
      setStep("password");
      return;
    }
    setLoading(true);
    try {
      if (isRegister) {
        await register(email, password, name || undefined);
      } else {
        await login(email, password);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function handleSocialLogin(provider: string) {
    setError("");
    setSocialLoading(provider);
    try {
      if (provider === "google") {
        const res = await fetch("/api/v1/auth/google/url");
        if (!res.ok) throw new Error("Google login not available");
        const data = await res.json();
        window.location.href = data.auth_url;
      } else {
        setError(`${provider} login coming soon`);
        setSocialLoading("");
      }
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : `${provider} login failed`
      );
      setSocialLoading("");
    }
  }

  const fieldStyle: React.CSSProperties = {
    width: "100%",
    boxSizing: "border-box",
    padding: "13px 14px",
    background: "rgba(255,255,255,.04)",
    border: `1px solid ${SR.border2}`,
    borderRadius: 10,
    fontSize: 13.5,
    color: SR.ink,
    fontFamily: INTER,
    outline: "none",
  };

  const socialBtnStyle: React.CSSProperties = {
    width: "100%",
    padding: "11px 14px",
    background: "rgba(255,255,255,.04)",
    border: `1px solid ${SR.border2}`,
    borderRadius: 10,
    color: SR.ink,
    fontSize: 13,
    fontWeight: 500,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    opacity: socialLoading ? 0.5 : 1,
  };

  return (
    <>
      <style jsx global>{`
        @keyframes sr-pulse {
          0%,
          100% {
            opacity: 0.45;
          }
          50% {
            opacity: 1;
          }
        }
        @keyframes sr-scan-vert {
          0% {
            top: -2%;
          }
          100% {
            top: 102%;
          }
        }
        @keyframes sr-tick-left {
          0% {
            transform: translateX(0);
          }
          100% {
            transform: translateX(-50%);
          }
        }
        @keyframes sr-glow-breath {
          0%,
          100% {
            opacity: 0.55;
          }
          50% {
            opacity: 0.95;
          }
        }
        @keyframes sr-blink {
          0%,
          90%,
          100% {
            opacity: 1;
          }
          95% {
            opacity: 0.2;
          }
        }
        @keyframes sr-bar {
          0%,
          100% {
            transform: scaleY(0.4);
          }
          50% {
            transform: scaleY(1);
          }
        }
        @media (max-width: 900px) {
          .sr-monitor-wall {
            display: none !important;
          }
          .sr-login-tagline {
            display: none !important;
          }
          .sr-login-panel {
            position: relative !important;
            right: auto !important;
            top: auto !important;
            bottom: auto !important;
            width: 100% !important;
            max-width: 420px !important;
            margin: 60px auto !important;
          }
        }
      `}</style>

      <div
        style={{
          width: "100%",
          minHeight: "100vh",
          position: "relative",
          overflow: "hidden",
          background: SR.bg,
          color: SR.ink,
          fontFamily: INTER,
        }}
      >
        {/* Monitor wall background */}
        <div className="sr-monitor-wall">
          <MonitorWall />
        </div>

        {/* HUD chrome */}
        <HudTop />
        <HudBottomTicker />

        {/* Brand mark — top-left */}
        <div
          style={{
            position: "absolute",
            left: 36,
            top: 54,
            zIndex: 8,
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <img
            src="/images/sr-logo.png"
            alt=""
            style={{
              width: 30,
              height: 30,
              objectFit: "contain",
              filter: "drop-shadow(0 0 8px rgba(127,140,255,.55))",
            }}
          />
          <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: -0.3 }}>
            Stealth<span style={{ color: SR.brand }}>Role</span>
          </div>
        </div>

        {/* Tagline — bottom-left */}
        <div
          className="sr-login-tagline"
          style={{
            position: "absolute",
            left: 36,
            bottom: 74,
            maxWidth: 420,
            zIndex: 8,
          }}
        >
          <div
            style={{
              fontFamily: MONO,
              fontSize: 10,
              letterSpacing: 2,
              color: SR.brand,
              marginBottom: 12,
            }}
          >
            THE HIDDEN MARKET
          </div>
          <div
            style={{
              fontSize: 36,
              fontWeight: 600,
              letterSpacing: -1.2,
              lineHeight: 1.04,
            }}
          >
            See the roles before
            <br />
            they&apos;re posted.
          </div>
          <div
            style={{
              fontSize: 13.5,
              color: SR.ink3,
              marginTop: 14,
              lineHeight: 1.55,
              maxWidth: 380,
            }}
          >
            Stealth Role watches 4,128 companies for funding rounds, leadership
            moves, and quiet hiring — and brings the matches to you.
          </div>
        </div>

        {/* Login panel — right rail */}
        <div
          className="sr-login-panel"
          style={{
            position: "absolute",
            right: 48,
            top: 84,
            bottom: 64,
            width: 380,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            zIndex: 10,
          }}
        >
          <div
            style={{
              position: "relative",
              padding: "28px 28px 26px",
              background: "rgba(11,15,42,.82)",
              backdropFilter: "blur(14px)",
              border: "1px solid rgba(127,140,255,.22)",
              borderRadius: 14,
              boxShadow:
                "0 28px 70px rgba(0,0,0,.55), 0 0 0 1px rgba(255,255,255,.04), 0 0 50px rgba(91,108,255,.16)",
              overflow: "hidden",
            }}
          >
            {/* Hooded silhouette watermark */}
            <div
              style={{
                position: "absolute",
                inset: 0,
                pointerEvents: "none",
                overflow: "hidden",
                borderRadius: 14,
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: "50%",
                  top: "48%",
                  transform: "translate(-50%, -50%)",
                  width: "130%",
                  height: "130%",
                  WebkitMaskImage:
                    "radial-gradient(ellipse 55% 60% at 50% 50%, rgba(0,0,0,.85) 25%, rgba(0,0,0,.45) 55%, transparent 85%)",
                  maskImage:
                    "radial-gradient(ellipse 55% 60% at 50% 50%, rgba(0,0,0,.85) 25%, rgba(0,0,0,.45) 55%, transparent 85%)",
                  opacity: 0.18,
                  mixBlendMode: "screen",
                  filter: "saturate(1.4) contrast(1.1)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <img
                  src="/images/sr-logo.png"
                  alt=""
                  style={{
                    width: "100%",
                    height: "100%",
                    objectFit: "contain",
                  }}
                />
              </div>
              {/* Glow halo */}
              <div
                style={{
                  position: "absolute",
                  left: "50%",
                  top: "45%",
                  transform: "translate(-50%, -50%)",
                  width: 280,
                  height: 280,
                  borderRadius: "50%",
                  background:
                    "radial-gradient(circle, rgba(91,108,255,.18), rgba(159,122,234,.08) 45%, transparent 75%)",
                  filter: "blur(20px)",
                }}
              />
            </div>

            {/* Header */}
            <div style={{ position: "relative", marginBottom: 20 }}>
              <div
                style={{ fontSize: 22, fontWeight: 600, letterSpacing: -0.5 }}
              >
                {isRegister ? "Create your account" : "Welcome back"}
              </div>
              <div style={{ fontSize: 13, color: SR.ink3, marginTop: 5 }}>
                {isRegister
                  ? "Join the hidden market."
                  : "Sign in to continue scouting."}
              </div>
            </div>

            {/* Form */}
            <form
              onSubmit={handleContinue}
              style={{ position: "relative" }}
            >
              {isRegister && step === "password" && (
                <>
                  <label
                    style={{
                      fontSize: 11,
                      fontWeight: 500,
                      color: SR.ink3,
                      marginBottom: 7,
                      display: "block",
                    }}
                  >
                    Full name
                  </label>
                  <input
                    type="text"
                    placeholder="Your name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    style={{ ...fieldStyle, marginBottom: 14 }}
                  />
                </>
              )}

              <label
                style={{
                  fontSize: 11,
                  fontWeight: 500,
                  color: SR.ink3,
                  marginBottom: 7,
                  display: "block",
                }}
              >
                Email
              </label>
              <input
                type="email"
                placeholder="you@company.com"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={fieldStyle}
              />

              {step === "password" && (
                <>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginTop: 14,
                      marginBottom: 7,
                    }}
                  >
                    <label
                      style={{
                        fontSize: 11,
                        fontWeight: 500,
                        color: SR.ink3,
                      }}
                    >
                      Password
                    </label>
                    <a
                      style={{
                        fontSize: 12,
                        color: SR.brand,
                        cursor: "pointer",
                        textDecoration: "none",
                      }}
                    >
                      Forgot?
                    </a>
                  </div>
                  <input
                    type="password"
                    placeholder="••••••••••••"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoFocus
                    style={{ ...fieldStyle, letterSpacing: 2 }}
                  />
                </>
              )}

              {error && (
                <div
                  style={{
                    fontSize: 13,
                    color: error.includes("coming soon")
                      ? "#60a5fa"
                      : "#f87171",
                    background: error.includes("coming soon")
                      ? "rgba(96,165,250,.1)"
                      : "rgba(248,113,113,.1)",
                    border: error.includes("coming soon")
                      ? "1px solid rgba(96,165,250,.15)"
                      : "1px solid rgba(248,113,113,.15)",
                    borderRadius: 10,
                    padding: "10px 16px",
                    marginTop: 10,
                  }}
                >
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                style={{
                  width: "100%",
                  marginTop: 18,
                  padding: "13px 18px",
                  border: "none",
                  cursor: "pointer",
                  background: `linear-gradient(135deg, ${SR.brand2}, ${SR.brand3})`,
                  color: "#fff",
                  fontWeight: 600,
                  fontSize: 14,
                  fontFamily: INTER,
                  borderRadius: 11,
                  boxShadow:
                    "0 8px 22px rgba(91,108,255,.32), inset 0 1px 0 rgba(255,255,255,.18)",
                  opacity: loading ? 0.5 : 1,
                }}
              >
                {loading
                  ? "..."
                  : step === "email"
                  ? "Continue"
                  : isRegister
                  ? "Create account"
                  : "Sign in"}
              </button>
            </form>

            {/* Divider */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                margin: "22px 0 16px",
                color: SR.ink5,
                fontSize: 11,
              }}
            >
              <div
                style={{ flex: 1, height: 1, background: SR.border }}
              />
              <span>or continue with</span>
              <div
                style={{ flex: 1, height: 1, background: SR.border }}
              />
            </div>

            {/* Social buttons */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 8,
                position: "relative",
              }}
            >
              <button
                type="button"
                onClick={() => handleSocialLogin("google")}
                disabled={!!socialLoading}
                style={socialBtnStyle}
              >
                <svg width="15" height="15" viewBox="0 0 18 18">
                  <path
                    d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.79 2.71v2.26h2.9c1.7-1.56 2.69-3.87 2.69-6.61z"
                    fill="#4285F4"
                  />
                  <path
                    d="M9 18c2.43 0 4.47-.81 5.96-2.18l-2.9-2.26c-.8.54-1.84.86-3.06.86-2.36 0-4.36-1.59-5.07-3.74H.95v2.32A9 9 0 0 0 9 18z"
                    fill="#34A853"
                  />
                  <path
                    d="M3.93 10.68A5.4 5.4 0 0 1 3.64 9c0-.59.1-1.16.29-1.68V4.99H.95A9 9 0 0 0 0 9c0 1.45.35 2.83.95 4.04l2.98-2.36z"
                    fill="#FBBC05"
                  />
                  <path
                    d="M9 3.58c1.32 0 2.51.45 3.44 1.34l2.58-2.58A9 9 0 0 0 9 0 9 9 0 0 0 .95 4.99l2.98 2.32C4.64 5.17 6.64 3.58 9 3.58z"
                    fill="#EA4335"
                  />
                </svg>
                {socialLoading === "google"
                  ? "..."
                  : "Continue with Google"}
              </button>

              <button
                type="button"
                onClick={() => handleSocialLogin("linkedin")}
                disabled={!!socialLoading}
                style={socialBtnStyle}
              >
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="#0A66C2"
                >
                  <path d="M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.13 1.45-2.13 2.94v5.67H9.36V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12zM7.12 20.45H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.72v20.56C0 23.23.79 24 1.77 24h20.45C23.2 24 24 23.23 24 22.28V1.72C24 .77 23.2 0 22.22 0z" />
                </svg>
                {socialLoading === "linkedin"
                  ? "..."
                  : "Continue with LinkedIn"}
              </button>

              <button
                type="button"
                onClick={() => handleSocialLogin("apple")}
                disabled={!!socialLoading}
                style={socialBtnStyle}
              >
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="#fff"
                >
                  <path d="M17.05 12.04c-.03-2.85 2.33-4.22 2.43-4.29-1.32-1.94-3.39-2.2-4.13-2.23-1.76-.18-3.43 1.04-4.32 1.04-.9 0-2.27-1.02-3.74-.99-1.92.03-3.7 1.12-4.69 2.84-2.01 3.48-.51 8.62 1.43 11.45.95 1.39 2.08 2.95 3.55 2.89 1.43-.06 1.97-.92 3.7-.92 1.72 0 2.21.92 3.72.89 1.54-.03 2.51-1.41 3.45-2.81 1.09-1.61 1.54-3.18 1.56-3.26-.03-.01-2.97-1.14-3-4.51zM14.34 3.93c.79-.96 1.32-2.29 1.17-3.61-1.13.05-2.5.75-3.32 1.7-.73.84-1.37 2.2-1.2 3.5 1.26.1 2.55-.64 3.35-1.59z" />
                </svg>
                {socialLoading === "apple"
                  ? "..."
                  : "Continue with Apple"}
              </button>
            </div>

            {/* Toggle sign in / sign up */}
            <div
              style={{
                marginTop: 22,
                fontSize: 12,
                color: SR.ink3,
                textAlign: "center",
              }}
            >
              {isRegister
                ? "Already have an account? "
                : "New here? "}
              <button
                type="button"
                onClick={() => {
                  setIsRegister(!isRegister);
                  setError("");
                  setStep("email");
                }}
                style={{
                  background: "none",
                  border: "none",
                  color: SR.brand,
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                {isRegister ? "Sign in" : "Request an invite"}
              </button>
            </div>
          </div>

          {/* Privacy note */}
          <div
            style={{
              marginTop: 14,
              fontSize: 11,
              color: SR.ink5,
              textAlign: "center",
              letterSpacing: 0.3,
            }}
          >
            Private by default · Your current employer never sees you here.
          </div>
        </div>
      </div>
    </>
  );
}
