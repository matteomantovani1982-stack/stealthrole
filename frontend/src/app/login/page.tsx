"use client";

import { FormEvent, useState } from "react";
import { useAuth } from "@/lib/auth-context";

/* ── design tokens (matching sr-login.jsx from Claude Designer) ── */
const SR = {
  bg: "#03040f",
  brand: "#7F8CFF",
  brand2: "#5B6CFF",
  brand3: "#9F7AEA",
  ink: "rgba(255,255,255,0.92)",
  ink3: "rgba(255,255,255,0.62)",
  ink5: "rgba(255,255,255,0.32)",
  border: "rgba(255,255,255,0.06)",
  border2: "rgba(255,255,255,0.10)",
};

/* ── Monitor frame ── */
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
          fontFamily: "'JetBrains Mono', monospace",
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

/* ── Simplified site mockups ── */
function SiteFT() {
  return (
    <div
      style={{
        height: "100%",
        background: "#fff1e5",
        color: "#1a1a1a",
        fontFamily: "Georgia, 'Times New Roman', serif",
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
            fontFamily: "'JetBrains Mono', monospace",
            letterSpacing: 1,
          }}
        >
          LIVE
        </div>
      </div>
      <div style={{ padding: "8px 10px" }}>
        <div
          style={{
            fontSize: 7,
            color: "#a04040",
            fontFamily: "'JetBrains Mono', monospace",
            letterSpacing: 1.2,
            marginBottom: 3,
          }}
        >
          CORPORATE · EXCLUSIVE
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
          Ramp CFO departs; senior finance seat opens at hyper-growth fintech
        </div>
        <div
          style={{ fontSize: 8.5, color: "#3a3a3a", lineHeight: 1.4, marginBottom: 6 }}
        >
          The speed-management unicorn is said to be moving quickly on a replacement.
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {["RAMP", "CFO", "EXEC"].map((t) => (
            <span
              key={t}
              style={{
                fontFamily: "'JetBrains Mono', monospace",
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
    </div>
  );
}

function SiteBloomberg() {
  return (
    <div
      style={{
        height: "100%",
        background: "#000",
        color: "#ff7a00",
        fontFamily: "'JetBrains Mono', monospace",
      }}
    >
      <div
        style={{
          padding: "4px 8px",
          borderBottom: "1px solid #333",
          display: "flex",
          justifyContent: "space-between",
          fontSize: 9,
          fontWeight: 900,
        }}
      >
        <span>BLOOMBERG</span>
        <span style={{ color: "#22c55e", fontSize: 7 }}>● LIVE</span>
      </div>
      <div style={{ padding: "6px 8px", fontSize: 8 }}>
        <div style={{ color: "#ff7a00", fontWeight: 700, fontSize: 11, marginBottom: 4 }}>
          MARKETS
        </div>
        {[
          { sym: "SPX", val: "5,248.32", chg: "+0.41%", up: true },
          { sym: "AAPL", val: "198.12", chg: "+1.2%", up: true },
          { sym: "TSLA", val: "174.88", chg: "-2.1%", up: false },
          { sym: "NVDA", val: "892.14", chg: "+3.8%", up: true },
        ].map((s) => (
          <div
            key={s.sym}
            style={{
              display: "flex",
              justifyContent: "space-between",
              padding: "3px 0",
              borderBottom: "1px solid #222",
              fontSize: 8,
            }}
          >
            <span style={{ color: "#ccc", fontWeight: 600 }}>{s.sym}</span>
            <span style={{ color: "#999" }}>{s.val}</span>
            <span style={{ color: s.up ? "#22c55e" : "#ef4444" }}>{s.chg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SiteLinkedIn() {
  return (
    <div
      style={{
        height: "100%",
        background: "#fff",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <div
        style={{
          padding: "4px 8px",
          background: "#0a66c2",
          color: "#fff",
          fontSize: 10,
          fontWeight: 700,
        }}
      >
        LinkedIn
      </div>
      <div style={{ padding: "8px" }}>
        {[
          { title: "VP of Growth", co: "Stripe", loc: "San Francisco" },
          { title: "Head of Strategy", co: "Revolut", loc: "London" },
        ].map((j, i) => (
          <div
            key={i}
            style={{
              padding: "6px 0",
              borderBottom: "1px solid #eee",
              fontSize: 9,
              color: "#333",
            }}
          >
            <div style={{ fontWeight: 700, color: "#0a66c2", fontSize: 10 }}>
              {j.title}
            </div>
            <div style={{ color: "#666", marginTop: 1 }}>
              {j.co} · {j.loc}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SiteReuters() {
  return (
    <div
      style={{
        height: "100%",
        background: "#fff",
        fontFamily: "system-ui, sans-serif",
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
            fontFamily: "'Times New Roman', serif",
          }}
        >
          REUTERS
        </div>
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 7,
            letterSpacing: 0.8,
          }}
        >
          ● LIVE WIRE
        </div>
      </div>
      <div style={{ padding: "7px 9px" }}>
        <div
          style={{
            display: "flex",
            gap: 6,
            fontSize: 7,
            fontFamily: "'JetBrains Mono', monospace",
            marginBottom: 4,
          }}
        >
          <span
            style={{
              background: "#fa6400",
              color: "#fff",
              padding: "1px 5px",
              borderRadius: 2,
              fontWeight: 700,
            }}
          >
            BREAKING
          </span>
          <span style={{ color: "#666" }}>M&A</span>
        </div>
        <div
          style={{
            fontWeight: 700,
            fontSize: 11,
            lineHeight: 1.2,
            marginBottom: 4,
            color: "#0a0a0a",
          }}
        >
          Stripe in advanced talks for $5B secondary, sources say
        </div>
        <div style={{ fontSize: 8.5, color: "#555", lineHeight: 1.4 }}>
          Tiger Global, Sequoia tipped as buyers; valuation reset implied.
        </div>
      </div>
    </div>
  );
}

function SiteTerminal() {
  return (
    <div
      style={{
        height: "100%",
        background: "#0b1120",
        fontFamily: "'JetBrains Mono', monospace",
        color: "#22c55e",
        fontSize: 8,
        padding: "8px",
        lineHeight: 1.6,
      }}
    >
      <div style={{ color: "#7F8CFF", marginBottom: 4 }}>
        ▸ SR.SCOUT — SIGNAL INTERCEPT
      </div>
      <div>RAMP · CFO wire +180M · ETA 9D</div>
      <div style={{ color: "#fbbf24" }}>CONF 94% · HIRING SIGNAL CONFIRMED</div>
      <div style={{ marginTop: 4 }}>KLARNA · Chief of Staff (unposted)</div>
      <div style={{ color: "#fbbf24" }}>CONF 88% · FUNDING ROUND → HIRING</div>
      <div style={{ marginTop: 4 }}>REVOLUT · GM Wealth confirmed</div>
      <div style={{ color: "#ef4444" }}>PRIORITY · NETWORK MATCH FOUND</div>
      <div style={{ marginTop: 6, color: "#7F8CFF" }}>
        ▸ 1,267 SIGNALS / 24H
      </div>
    </div>
  );
}

function SiteLayoffs() {
  return (
    <div
      style={{
        height: "100%",
        background: "#fff",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <div
        style={{
          padding: "5px 8px",
          borderBottom: "1px solid #eee",
          fontSize: 10,
          fontWeight: 700,
          color: "#ef4444",
        }}
      >
        LAYOFFS.FYI
      </div>
      <div style={{ padding: "6px 8px", fontSize: 8 }}>
        {[
          { co: "Meta", n: "210", date: "Apr 22" },
          { co: "Snap", n: "180", date: "Apr 20" },
          { co: "Lyft", n: "120", date: "Apr 18" },
        ].map((l, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              justifyContent: "space-between",
              padding: "4px 0",
              borderBottom: "1px solid #f5f5f5",
              color: "#333",
            }}
          >
            <span style={{ fontWeight: 600 }}>{l.co}</span>
            <span style={{ color: "#ef4444" }}>{l.n}</span>
            <span style={{ color: "#999" }}>{l.date}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SiteCrunchbase() {
  return (
    <div
      style={{
        height: "100%",
        background: "#fff",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <div
        style={{
          padding: "5px 8px",
          borderBottom: "1px solid #eee",
          fontSize: 10,
          fontWeight: 700,
          color: "#0288d1",
        }}
      >
        CRUNCHBASE
      </div>
      <div style={{ padding: "6px 8px" }}>
        {[
          { co: "Anthropic", round: "Series E", amt: "$2B", stage: "AI" },
          { co: "Wiz", round: "Series D", amt: "$1B", stage: "Security" },
        ].map((f, i) => (
          <div
            key={i}
            style={{
              padding: "5px 0",
              borderBottom: "1px solid #f5f5f5",
              fontSize: 9,
              color: "#333",
            }}
          >
            <div style={{ fontWeight: 700, color: "#0288d1" }}>{f.co}</div>
            <div style={{ display: "flex", gap: 8, color: "#666", marginTop: 2, fontSize: 8 }}>
              <span>{f.round}</span>
              <span style={{ fontWeight: 600, color: "#0288d1" }}>{f.amt}</span>
              <span>{f.stage}</span>
            </div>
          </div>
        ))}
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
        fontFamily: "'JetBrains Mono', monospace",
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
        fontFamily: "'JetBrains Mono', monospace",
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

/* ── Monitor wall background ── */
function MonitorWall() {
  return (
    <div style={{ position: "absolute", inset: 0, opacity: 1 }}>
      {/* Background gradient */}
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

      {/* Monitor frames */}
      <MonitorFrame
        label="FT.COM · LIVE"
        accent="#a04040"
        style={{ left: "2%", top: "8%", width: "22%", height: "28%" }}
      >
        <SiteFT />
      </MonitorFrame>

      <MonitorFrame
        label="CRUNCHBASE · NEW"
        accent="#0288d1"
        style={{ left: "26%", top: "8%", width: "18%", height: "25%" }}
      >
        <SiteCrunchbase />
      </MonitorFrame>

      <MonitorFrame
        label="BLOOMBERG · TERMINAL"
        accent="#ff7a00"
        style={{ left: "46%", top: "6%", width: "18%", height: "24%" }}
      >
        <SiteBloomberg />
      </MonitorFrame>

      <MonitorFrame
        label="SECURE TERMINAL · CH.07"
        accent="#22c55e"
        glow
        style={{ left: "66%", top: "8%", width: "22%", height: "30%" }}
      >
        <SiteTerminal />
      </MonitorFrame>

      <MonitorFrame
        label="LINKEDIN · FEED"
        accent="#0a66c2"
        style={{ left: "5%", top: "40%", width: "16%", height: "24%" }}
      >
        <SiteLinkedIn />
      </MonitorFrame>

      <MonitorFrame
        label="REUTERS · BREAKING"
        accent="#ff8000"
        style={{ left: "23%", top: "37%", width: "18%", height: "26%" }}
      >
        <SiteReuters />
      </MonitorFrame>

      <MonitorFrame
        label="LAYOFFS.FYI"
        accent="#ef4444"
        style={{ left: "5%", top: "68%", width: "17%", height: "24%" }}
      >
        <SiteLayoffs />
      </MonitorFrame>

      <MonitorFrame
        label="CRUNCHBASE · WATCHLIST"
        accent="#0288d1"
        style={{ left: "46%", top: "56%", width: "18%", height: "22%" }}
      >
        <SiteCrunchbase />
      </MonitorFrame>

      {/* Glass haze overlay */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(180deg, rgba(3,4,15,.18) 0%, rgba(3,4,15,.06) 35%, rgba(3,4,15,.42) 100%)",
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse 60% 70% at 50% 60%, rgba(91,108,255,.10) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   LOGIN PAGE — Command Deck (Variation A from Claude Designer)
   ═══════════════════════════════════════════════════════════════════ */
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
    fontFamily: "Inter, system-ui, sans-serif",
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
          fontFamily: "Inter, system-ui, sans-serif",
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
              fontFamily: "'JetBrains Mono', monospace",
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
                  fontFamily: "Inter, system-ui, sans-serif",
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
