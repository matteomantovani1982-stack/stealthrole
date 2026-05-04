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

type TabId = "integrations" | "notifications" | "privacy" | "account" | "security";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabId>("integrations");
  const [integrationStates, setIntegrationStates] = useState({
    linkedin: true,
    gmail: true,
    calendar: true,
    whatsapp: false,
  });
  const [notifyStates, setNotifyStates] = useState({
    fundingEvents: true,
    leadershipChanges: true,
    realestate: true,
    hiringBoom: true,
    productLaunches: true,
    velocityChanges: false,
    distressSignals: false,
  });
  const [frequencyState, setFrequencyState] = useState("4h");
  const [privacyStates, setPrivacyStates] = useState({
    blockEmployer: true,
    anonRecruiters: true,
    publicProfile: false,
    hideLocation: true,
    allowExport: true,
  });
  const [addOnStates, setAddOnStates] = useState({
    companies: false,
    scans: false,
    ghostwriting: false,
    intros: false,
  });

  const cardStyle = {
    background: AC.panel,
    border: `1px solid ${AC.border}`,
    borderRadius: 12,
    boxShadow: "0 1px 2px rgba(15,18,40,0.03)"
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

  const renderToggle = (enabled: boolean, onChange: () => void) => (
    <button
      onClick={onChange}
      style={{
        width: 34,
        height: 20,
        borderRadius: 999,
        background: enabled ? `linear-gradient(90deg, ${AC.brand2} 0%, ${AC.brand3} 100%)` : AC.border2,
        border: "none",
        cursor: "pointer",
        position: "relative",
        transition: "all 0.2s"
      }}
    >
      <div
        style={{
          width: 16,
          height: 16,
          borderRadius: "50%",
          background: "#fff",
          position: "absolute",
          top: 2,
          right: enabled ? 2 : "auto",
          left: enabled ? "auto" : 2,
          transition: "all 0.2s",
          boxShadow: "0 1px 3px rgba(0,0,0,0.1)"
        }}
      />
    </button>
  );

  return (
    <div style={{ background: AC.bg, minHeight: "100vh", fontFamily: '"Inter, system-ui, sans-serif"' }}>
      {/* Header */}
      <div style={{
        padding: "28px 36px 22px",
        background: `linear-gradient(135deg, ${AC.brand} 0%, ${AC.brand3} 100%)`
      }}>
        <div style={{ maxWidth: 1440, margin: "0 auto" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.7)", letterSpacing: 1, marginBottom: 12, fontFamily: "'JetBrains Mono', monospace" }}>
            SETTINGS · INTEGRATIONS
          </div>
          <h1 style={{ fontSize: 28, fontWeight: 600, color: "#fff", margin: "0 0 4px 0" }}>
            Settings
          </h1>
          <p style={{ fontSize: 13, color: "rgba(255,255,255,0.8)", margin: 0 }}>
            Manage integrations, privacy, and account.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ maxWidth: 1440, margin: "0 auto", padding: "0 36px", borderBottom: `1px solid ${AC.border}`, display: "flex", gap: 32 }}>
        {(["integrations", "notifications", "privacy", "account", "security"] as TabId[]).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: "12px 0",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: 12,
              fontWeight: 600,
              color: activeTab === tab ? AC.brand : AC.ink4,
              borderBottom: activeTab === tab ? `2px solid ${AC.brand}` : "none",
              transition: "all 0.2s",
              textTransform: "capitalize"
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ maxWidth: 1440, margin: "0 auto", padding: "24px 36px 32px" }}>

        {/* INTEGRATIONS TAB */}
        {activeTab === "integrations" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            <div style={cardStyle}>
              <div style={titleBarStyle}>Integrations</div>
              <div style={contentStyle}>
                {[
                  { id: "linkedin", name: "LinkedIn Extension", desc: "Sync connections & insights", icon: "in", bg: "#0A66C2" },
                  { id: "gmail", name: "Gmail & Outlook", desc: "Email sync & detection", icon: "✉", bg: "#EA4335" },
                  { id: "calendar", name: "Calendar", desc: "Interview scheduling", icon: "📅", bg: "#4F46E5" },
                  { id: "whatsapp", name: "WhatsApp", desc: "Opportunity alerts", icon: "💬", bg: "#25D366" }
                ].map((int: any) => (
                  <div key={int.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: 12, marginBottom: 12, borderBottom: `1px solid ${AC.divider}` }}>
                    <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                      <div style={{
                        width: 36,
                        height: 36,
                        borderRadius: 8,
                        background: int.bg,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        color: "#fff",
                        fontSize: 16
                      }}>
                        {int.icon}
                      </div>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: AC.ink }}>{int.name}</div>
                        <div style={{ fontSize: 11, color: AC.ink4 }}>{int.desc}</div>
                      </div>
                    </div>
                    {renderToggle(integrationStates[int.id as keyof typeof integrationStates], () => { const key = int.id as keyof typeof integrationStates; setIntegrationStates(prev => ({ ...prev, [key]: !prev[key] })); })}
                  </div>
                ))}
              </div>
            </div>

            <div style={cardStyle}>
              <div style={titleBarStyle}>Scan & Precog</div>
              <div style={contentStyle}>
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: AC.ink4, marginBottom: 8, textTransform: "uppercase" }}>Frequency</div>
                  <div style={{ display: "flex", gap: 8 }}>
                    {[
                      { id: "12h", label: "Every 12h" },
                      { id: "4h", label: "Every 4h" },
                      { id: "1h", label: "Hourly" },
                      { id: "rt", label: "Real-time" }
                    ].map(opt => (
                      <button
                        key={opt.id}
                        onClick={() => setFrequencyState(opt.id)}
                        style={{
                          padding: "6px 12px",
                          border: `1px solid ${frequencyState === opt.id ? AC.brand : AC.border}`,
                          background: frequencyState === opt.id ? AC.brandTint : "transparent",
                          color: frequencyState === opt.id ? AC.brand : AC.ink4,
                          borderRadius: 6,
                          fontSize: 11,
                          fontWeight: 600,
                          cursor: "pointer",
                          transition: "all 0.2s"
                        }}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div style={{ fontSize: 11, fontWeight: 600, color: AC.ink4, marginBottom: 8, textTransform: "uppercase" }}>Active Triggers</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {[
                    { id: "fundingEvents", label: "Funding events" },
                    { id: "leadershipChanges", label: "Leadership changes" },
                    { id: "realestate", label: "Real-estate signals" },
                    { id: "hiringBoom", label: "Hiring surges" },
                    { id: "productLaunches", label: "Product launches" },
                    { id: "velocityChanges", label: "Velocity changes" },
                    { id: "distressSignals", label: "Distress signals" }
                  ].map(trigger => (
                    <div key={trigger.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ fontSize: 12, color: AC.ink }}>{trigger.label}</div>
                      {renderToggle(notifyStates[trigger.id as keyof typeof notifyStates], () => { const key = trigger.id as keyof typeof notifyStates; setNotifyStates(prev => ({ ...prev, [key]: !prev[key] })); })}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* NOTIFICATIONS TAB */}
        {activeTab === "notifications" && (
          <div style={cardStyle}>
            <div style={titleBarStyle}>Notifications</div>
            <div style={contentStyle}>
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: AC.ink4, marginBottom: 12, textTransform: "uppercase" }}>Daily Briefing</div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{ fontSize: 20 }}>📧</div>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: AC.ink }}>Email at 8:00 AM</div>
                      <div style={{ fontSize: 11, color: AC.ink4 }}>Daily briefing digest</div>
                    </div>
                  </div>
                  {renderToggle(true, () => {})}
                </div>
              </div>

              <div style={{ borderTop: `1px solid ${AC.divider}`, paddingTop: 20 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: AC.ink4, marginBottom: 12, textTransform: "uppercase" }}>Real-time Alerts</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
                  {[
                    { label: "New opportunities matching profile" },
                    { label: "Application status changes" },
                    { label: "Recruiter outreach" },
                    { label: "Network activity"}
                  ].map((alert, idx) => (
                    <div key={idx} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ fontSize: 12, color: AC.ink }}>{alert.label}</div>
                      {renderToggle(idx < 2, () => {})}
                    </div>
                  ))}
                </div>

                <div style={{ fontSize: 11, fontWeight: 600, color: AC.ink4, marginBottom: 12, textTransform: "uppercase" }}>Channels</div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {["Email", "Push", "SMS", "Slack", "Webhook"].map(ch => (
                    <span key={ch} style={{
                      padding: "5px 10px",
                      borderRadius: 6,
                      fontSize: 11,
                      fontWeight: 600,
                      background: AC.brandTint,
                      color: AC.brand,
                      cursor: "pointer"
                    }}>
                      {ch}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* PRIVACY TAB */}
        {activeTab === "privacy" && (
          <div style={cardStyle}>
            <div style={titleBarStyle}>Stealth & Privacy</div>
            <div style={{ ...contentStyle, borderTop: `1px solid ${AC.divider}`, marginTop: 0, paddingTop: 14 }}>
              <div style={{ background: AC.brandTint2, border: `1px solid ${AC.brand}`, borderRadius: 6, padding: 10, marginBottom: 16, fontSize: 11, color: AC.brand, fontWeight: 500 }}>
                Stealth mode is on — your current employer cannot see your activity.
              </div>
              {[
                { id: "blockEmployer", label: "Block current employer" },
                { id: "anonRecruiters", label: "Anonymous to recruiters" },
                { id: "publicProfile", label: "Public profile" },
                { id: "hideLocation", label: "Hide location precision" },
                { id: "allowExport", label: "Allow data export" }
              ].map(priv => (
                <div key={priv.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: 10, marginBottom: 10, borderBottom: `1px solid ${AC.divider}` }}>
                  <div style={{ fontSize: 12, color: AC.ink }}>{priv.label}</div>
                  {renderToggle(privacyStates[priv.id as keyof typeof privacyStates], () => { const key = priv.id as keyof typeof privacyStates; setPrivacyStates(prev => ({ ...prev, [key]: !prev[key] })); })}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ACCOUNT TAB */}
        {activeTab === "account" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <div style={cardStyle}>
              <div style={titleBarStyle}>Account</div>
              <div style={contentStyle}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: AC.ink4, marginBottom: 6, textTransform: "uppercase" }}>Email</div>
                    <input type="text" placeholder="alex@notion.com" style={{ width: "100%", padding: "8px 12px", border: `1px solid ${AC.border}`, borderRadius: 6, fontSize: 12, background: AC.panel2 }} />
                  </div>
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: AC.ink4, marginBottom: 6, textTransform: "uppercase" }}>Password</div>
                    <input type="password" placeholder="••••••••" style={{ width: "100%", padding: "8px 12px", border: `1px solid ${AC.border}`, borderRadius: 6, fontSize: 12, background: AC.panel2 }} />
                  </div>
                </div>
              </div>
            </div>

            <div style={cardStyle}>
              <div style={titleBarStyle}>Two-Factor Authentication</div>
              <div style={contentStyle}>
                {[
                  { id: "auth", label: "Authenticator app", status: true },
                  { id: "sms", label: "SMS backup codes", status: false },
                  { id: "hw", label: "Hardware security key", status: false }
                ].map(twofa => (
                  <div key={twofa.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: 10, marginBottom: 10, borderBottom: `1px solid ${AC.divider}` }}>
                    <div style={{ fontSize: 12, color: AC.ink }}>{twofa.label}</div>
                    {renderToggle(twofa.status, () => {})}
                  </div>
                ))}
              </div>
            </div>

            <div style={cardStyle}>
              <div style={titleBarStyle}>Active Sessions</div>
              <div style={contentStyle}>
                {[
                  { device: "Chrome on macOS", browser: "Chrome · 95.0", lastActive: "Today at 2:45 PM" },
                  { device: "Safari on iPhone", browser: "Safari · iOS 15", lastActive: "Yesterday at 9:30 AM" },
                  { device: "Firefox on Windows", browser: "Firefox · 96.0", lastActive: "3 days ago" }
                ].map((sess, idx) => (
                  <div key={idx} style={{ paddingBottom: 10, marginBottom: 10, borderBottom: idx < 2 ? `1px solid ${AC.divider}` : "none" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: AC.ink }}>{sess.device}</div>
                        <div style={{ fontSize: 11, color: AC.ink4 }}>{sess.browser}</div>
                        <div style={{ fontSize: 10, color: AC.ink4, marginTop: 2 }}>{sess.lastActive}</div>
                      </div>
                      <button style={{ fontSize: 11, color: AC.bad, cursor: "pointer", background: "none", border: "none", fontWeight: 600 }}>Sign out</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* SECURITY TAB */}
        {activeTab === "security" && (
          <div style={cardStyle}>
            <div style={titleBarStyle}>Security</div>
            <div style={contentStyle}>
              <div style={{ background: AC.brandTint, border: `1px solid ${AC.brand}`, borderRadius: 6, padding: 12, marginBottom: 16, fontSize: 11, color: AC.brand }}>
                Your account security level: Strong
              </div>
              <div style={{ fontSize: 11, fontWeight: 600, color: AC.ink4, marginBottom: 12, textTransform: "uppercase" }}>Last Password Change</div>
              <div style={{ fontSize: 12, color: AC.ink, marginBottom: 20 }}>2 months ago</div>
              <button style={{ padding: "10px 16px", background: AC.brand, color: "#fff", border: "none", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                Change password
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
