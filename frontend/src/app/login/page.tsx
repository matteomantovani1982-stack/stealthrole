"use client";

import { FormEvent, useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

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
      setError(err instanceof Error ? err.message : `${provider} login failed`);
      setSocialLoading("");
    }
  }

  return (
    <>
      <style jsx global>{`
        @keyframes scanLine{0%{top:-5%}100%{top:105%}}
        @keyframes pulseRing{0%{opacity:.4;transform:translate(-50%,-50%) scale(.8)}100%{opacity:0;transform:translate(-50%,-50%) scale(1.3)}}
        @keyframes logoFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-12px)}}
        @keyframes particleUp{0%{transform:translateY(0);opacity:.7}100%{transform:translateY(-110vh);opacity:0}}
        @keyframes cardFloat{0%{opacity:0;transform:translateY(20px)}10%{opacity:.7;transform:translateY(0)}80%{opacity:.7;transform:translateY(-30px)}100%{opacity:0;transform:translateY(-50px)}}
        @keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
        @keyframes cursorBlink{0%,100%{opacity:1}50%{opacity:0}}
        @keyframes barGrow{from{width:0}to{width:var(--w)}}
        @media (max-width: 768px) {
          .login-left-panel { display: none !important; }
        }
      `}</style>

      <div style={{ display: "flex", minHeight: "100vh", fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif", flexWrap: "wrap" as const }}>

        {/* ═══ LEFT PANEL ═══ */}
        <div className="login-left-panel" style={{
          flex: 1, minWidth: "320px", background: "#07091a", display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center", padding: "40px 30px",
          position: "relative", overflow: "hidden",
          backgroundImage: "url('/images/sr-logo.png')",
          backgroundSize: "cover", backgroundPosition: "center", backgroundRepeat: "no-repeat",
        }}>
          {/* Dark overlay over background logo */}
          <div style={{ position: "absolute", inset: 0, background: "linear-gradient(to bottom, rgba(7,9,28,0.4) 0%, rgba(7,9,28,0.85) 45%, rgba(7,9,28,0.95) 100%)", zIndex: 1 }} />

          {/* Scan line */}
          <div style={{ position: "absolute", top: "-100%", left: 0, right: 0, height: 2, background: "linear-gradient(90deg,transparent,rgba(77,142,245,.12),transparent)", animation: "scanLine 6s linear infinite", zIndex: 2 }} />

          {/* Particles */}
          {[
            { left: "15%", dur: "8s", delay: "0s", size: 3 },
            { left: "30%", dur: "10s", delay: "1.5s", size: 5, opacity: 0.7 },
            { left: "55%", dur: "7s", delay: ".5s", size: 4 },
            { left: "70%", dur: "9s", delay: "2s", size: 3, opacity: 0.5 },
            { left: "85%", dur: "11s", delay: "3s", size: 6, opacity: 0.4 },
            { left: "42%", dur: "8.5s", delay: "1s", size: 3 },
          ].map((p, i) => (
            <div key={i} style={{
              position: "absolute", bottom: "-10%", left: p.left,
              width: p.size, height: p.size, borderRadius: "50%",
              background: "rgba(77,142,245,.6)", opacity: p.opacity ?? 0.7,
              animation: `particleUp ${p.dur} linear infinite`, animationDelay: p.delay,
              pointerEvents: "none",
            }} />
          ))}

          {/* Floating job cards */}
          {[
            { text: "Head of Growth", match: "91% match", pos: { left: "8%", top: "18%" }, delay: "0s" },
            { text: "VP Operations", match: "87%", pos: { right: "10%", top: "30%" }, delay: "4s" },
            { text: "Strategy Director", match: "84%", pos: { left: "15%", bottom: "22%" }, delay: "8s" },
          ].map((card, i) => (
            <div key={i} style={{
              position: "absolute", ...card.pos,
              background: "rgba(7,9,28,.85)", border: "1px solid rgba(77,142,245,.3)",
              borderRadius: 10, padding: "10px 16px", fontSize: 12, color: "rgba(255,255,255,.9)",
              backdropFilter: "blur(4px)", animation: `cardFloat 12s ease-in-out infinite`,
              animationDelay: card.delay, pointerEvents: "none", whiteSpace: "nowrap",
            }}>
              {card.text}<span style={{ color: "#4d8ef5", fontWeight: 600, marginLeft: 6 }}>{card.match}</span>
            </div>
          ))}

          {/* Spacer — logo is now the background */}
          <div style={{ height: 40, zIndex: 3 }} />

          <div style={{ fontSize: 22, fontWeight: 700, textAlign: "center", lineHeight: 1.4, marginBottom: 8, maxWidth: 380, color: "#fff", position: "relative", zIndex: 3 }}>
            Stop applying. <span style={{ color: "#4d8ef5" }}>Start leading.</span>
          </div>
          <div style={{ fontSize: 13, color: "rgba(255,255,255,.45)", textAlign: "center", maxWidth: 340, lineHeight: 1.5, marginBottom: 28, position: "relative", zIndex: 3 }}>
            StealthRole. Always one step ahead.
          </div>

          {/* AI Panel */}
          <div style={{ background: "rgba(7,9,28,.8)", border: "1px solid rgba(77,142,245,.2)", borderRadius: 14, padding: "18px 20px", maxWidth: 380, width: "100%", position: "relative", zIndex: 3, backdropFilter: "blur(12px)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, fontWeight: 600, color: "rgba(255,255,255,.7)", marginBottom: 14, letterSpacing: .5, textTransform: "uppercase" }}>
              <span style={{ width: 7, height: 7, background: "#4d8ef5", borderRadius: "50%", animation: "blink 1.5s infinite" }} />
              AI scanning live
              <span style={{ display: "inline-block", width: 1, height: 12, background: "#4d8ef5", marginLeft: 4, animation: "cursorBlink 1s step-end infinite" }} />
            </div>

            {[
              { color: "#4d8ef5", title: "Detect hiring signals", desc: "Funding rounds, leadership changes, expansion moves", w: "82%" },
              { color: "#22c55e", title: "Find hidden roles", desc: "Before they are posted on job boards", w: "67%" },
              { color: "#f59e0b", title: "Map your network path", desc: "Find connections who can get you in the door", w: "54%" },
            ].map((s, i) => (
              <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 12 }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", marginTop: 5, flexShrink: 0, background: s.color }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "rgba(255,255,255,.8)" }}>{s.title}</div>
                  <div style={{ fontSize: 10, color: "rgba(255,255,255,.4)", marginTop: 1 }}>{s.desc}</div>
                  <div style={{ height: 3, background: "rgba(255,255,255,.06)", borderRadius: 2, marginTop: 5, overflow: "hidden" }}>
                    <div style={{ height: "100%", borderRadius: 2, background: s.color, animation: "barGrow 2s ease-out forwards", "--w": s.w } as any} />
                  </div>
                </div>
              </div>
            ))}

            <div style={{ height: 1, background: "rgba(255,255,255,.06)", margin: "14px 0" }} />
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 11, color: "rgba(255,255,255,.45)", lineHeight: 1.4 }}>Roles detected<br /><span style={{ color: "#4d8ef5", fontWeight: 600 }}>across MENA</span></div>
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 11, color: "rgba(255,255,255,.45)", lineHeight: 1.4 }}>Signals scanned<br /><span style={{ color: "#4d8ef5", fontWeight: 600 }}>every week</span></div>
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 11, color: "rgba(255,255,255,.45)", lineHeight: 1.4 }}>Before roles<br /><span style={{ color: "#4d8ef5", fontWeight: 600 }}>are posted</span></div>
              </div>
            </div>
          </div>
        </div>

        {/* ═══ RIGHT PANEL ═══ */}
        <div style={{
          flex: 1, minWidth: "340px", maxWidth: 480, background: "#0f1225", display: "flex",
          flexDirection: "column", justifyContent: "center", padding: "40px 48px",
        }}>
          {/* Brand */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 32 }}>
            <img src="/images/sr-logo.png" alt="" style={{ width: 48, height: 48, borderRadius: 8, mixBlendMode: "screen", filter: "drop-shadow(0 0 10px rgba(77,142,245,.2))" }} />
            <span style={{ fontSize: 24, fontWeight: 700, color: "rgba(255,255,255,.9)" }}>
              Stealth<span style={{ color: "#4d8ef5" }}>Role</span>
            </span>
          </div>

          <div style={{ fontSize: 24, fontWeight: 700, color: "#fff", marginBottom: 6 }}>Your next role is already out there</div>
          <div style={{ fontSize: 13, color: "rgba(255,255,255,.4)", marginBottom: 24, lineHeight: 1.5 }}>Sign in to discover hidden opportunities before they are posted.</div>

          {/* Teaser card */}
          <div style={{ background: "rgba(77,142,245,.04)", border: "1px solid rgba(77,142,245,.2)", borderRadius: 12, padding: 16, marginBottom: 24 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "rgba(255,255,255,.5)", marginBottom: 10 }}>
              <span style={{ width: 6, height: 6, background: "#4d8ef5", borderRadius: "50%", animation: "blink 2s infinite" }} />
              Hidden match found for your profile
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: "#fff" }}>Head of Growth</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#22c55e" }}>91%</div>
            </div>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,.4)", marginBottom: 4 }}>Fast-growing fintech · Dubai · Not posted publicly</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: "rgba(255,255,255,.6)", filter: "blur(5px)", userSelect: "none", marginBottom: 8 }}>Confidential Company</div>
            <div style={{ fontSize: 11, color: "#4d8ef5", fontWeight: 500 }}>Sign up free to unlock the company name and apply →</div>
          </div>

          {/* Form */}
          <form onSubmit={handleContinue}>
            {isRegister && step === "password" && (
              <input
                type="text" placeholder="Full name" value={name}
                onChange={(e) => setName(e.target.value)}
                style={{ width: "100%", padding: "13px 16px", background: "rgba(255,255,255,.05)", border: "1px solid rgba(255,255,255,.08)", borderRadius: 10, color: "#fff", fontSize: 14, outline: "none", marginBottom: 8 }}
              />
            )}

            <input
              type="email" placeholder="Your email" required value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{ width: "100%", padding: "13px 16px", background: "rgba(255,255,255,.05)", border: "1px solid rgba(255,255,255,.08)", borderRadius: 10, color: "#fff", fontSize: 14, outline: "none" }}
            />

            {step === "password" && (
              <input
                type="password" placeholder="Password" required minLength={8}
                value={password} onChange={(e) => setPassword(e.target.value)} autoFocus
                style={{ width: "100%", padding: "13px 16px", background: "rgba(255,255,255,.05)", border: "1px solid rgba(255,255,255,.08)", borderRadius: 10, color: "#fff", fontSize: 14, outline: "none", marginTop: 8 }}
              />
            )}

            {error && (
              <div style={{ fontSize: 13, color: error.includes("coming soon") ? "#60a5fa" : "#f87171", background: error.includes("coming soon") ? "rgba(96,165,250,.1)" : "rgba(248,113,113,.1)", border: error.includes("coming soon") ? "1px solid rgba(96,165,250,.15)" : "1px solid rgba(248,113,113,.15)", borderRadius: 10, padding: "10px 16px", marginTop: 8 }}>
                {error}
              </div>
            )}

            <button type="submit" disabled={loading} style={{
              width: "100%", padding: 13, background: "#4d8ef5", color: "#fff", border: "none",
              borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: "pointer", marginTop: 10,
              opacity: loading ? 0.5 : 1,
            }}>
              {loading ? "..." : "Continue"}
            </button>
          </form>

          {/* Divider */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "20px 0", fontSize: 12, color: "rgba(255,255,255,.25)" }}>
            <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,.06)" }} />
            or continue with
            <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,.06)" }} />
          </div>

          {/* Social buttons */}
          {[
            { provider: "google", label: "Continue with Google", icon: <svg width="16" height="16" viewBox="0 0 18 18"><path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/><path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z" fill="#34A853"/><path d="M3.964 10.71A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.997 8.997 0 000 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/><path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 6.29C4.672 4.163 6.656 2.58 9 2.58z" fill="#EA4335"/></svg> },
            { provider: "facebook", label: "Continue with Facebook", icon: <svg width="16" height="16" viewBox="0 0 18 18"><circle cx="9" cy="9" r="9" fill="#1877F2"/><path d="M12.5 9.75h-2v5.25H8v-5.25H6.25v-2.5H8V5.75c0-1.5.9-2.75 2.75-2.75h1.75v2.5h-1.25c-.5 0-.75.25-.75.75v1h2l-.25 2.5h-1.75z" fill="white"/></svg> },
            { provider: "apple", label: "Continue with Apple", icon: <svg width="16" height="16" viewBox="0 0 18 18" fill="white"><path d="M15.1 6.05c-.09.07-1.68.97-1.68 2.96 0 2.31 2.03 3.13 2.09 3.15-.01.05-.32 1.12-1.07 2.21-.65.94-1.32 1.88-2.38 1.88s-1.31-.62-2.51-.62c-1.17 0-1.58.64-2.57.64s-1.62-.87-2.38-1.94C3.42 12.73 2.7 10.61 2.7 8.6c0-3.23 2.1-4.94 4.17-4.94 1.1 0 2.01.72 2.7.72.66 0 1.69-.76 2.94-.76.47 0 2.17.04 3.29 1.64l.3-.01zM11.85 2.3c.47-.56.8-1.34.8-2.12 0-.11-.01-.22-.03-.3-.76.03-1.67.51-2.22 1.14-.43.48-.83 1.27-.83 2.06 0 .12.02.24.03.28.05.01.14.02.22.02.69 0 1.54-.46 2.03-1.08z"/></svg> },
            { provider: "linkedin", label: "Continue with LinkedIn", icon: <svg width="16" height="16" viewBox="0 0 18 18"><path d="M15.335 1.5H2.665A1.165 1.165 0 001.5 2.665v12.67A1.165 1.165 0 002.665 16.5h12.67a1.165 1.165 0 001.165-1.165V2.665A1.165 1.165 0 0015.335 1.5zM6.5 13.5H4.25V7.25H6.5V13.5zM5.375 6.313a1.313 1.313 0 110-2.625 1.313 1.313 0 010 2.625zM14.25 13.5H12V10.5c0-.75-.015-1.714-1.044-1.714-1.046 0-1.206.817-1.206 1.661V13.5H7.5V7.25h2.159v.854h.03c.3-.57 1.035-1.17 2.13-1.17 2.278 0 2.7 1.5 2.7 3.45V13.5z" fill="#0A66C2"/></svg> },
          ].map(({ provider, label, icon }) => (
            <button key={provider} type="button"
              onClick={() => handleSocialLogin(provider)}
              disabled={!!socialLoading}
              style={{
                width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
                padding: 11, background: "rgba(255,255,255,.04)", border: "1px solid rgba(255,255,255,.08)",
                borderRadius: 10, color: "rgba(255,255,255,.7)", fontSize: 13, fontWeight: 500,
                cursor: "pointer", marginBottom: 8, opacity: socialLoading ? 0.5 : 1,
              }}
            >
              {icon} {socialLoading === provider ? "..." : label}
            </button>
          ))}

          {/* Sign up / Sign in toggle */}
          <div style={{ textAlign: "center", marginTop: 20, fontSize: 13, color: "rgba(255,255,255,.35)" }}>
            {isRegister ? "Already have an account? " : "Don\u2019t have an account? "}
            <button type="button"
              onClick={() => { setIsRegister(!isRegister); setError(""); setStep("email"); }}
              style={{ background: "none", border: "none", color: "#4d8ef5", fontSize: 13, fontWeight: 500, cursor: "pointer" }}
            >
              {isRegister ? "Sign in" : "Sign up"}
            </button>
          </div>

          <div style={{ display: "flex", justifyContent: "center", gap: 16, marginTop: 20, fontSize: 11 }}>
            <a href="/terms" style={{ color: "rgba(255,255,255,.2)", textDecoration: "none" }}>Terms</a>
            <a href="/privacy" style={{ color: "rgba(255,255,255,.2)", textDecoration: "none" }}>Privacy</a>
            <a href="mailto:support@stealthrole.com" style={{ color: "rgba(255,255,255,.2)", textDecoration: "none" }}>Support</a>
          </div>
        </div>
      </div>
    </>
  );
}
