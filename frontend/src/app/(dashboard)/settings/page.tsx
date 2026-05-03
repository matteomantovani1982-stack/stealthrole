"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { SR } from "@/lib/constants";

type TabId = "integrations" | "notifications" | "privacy" | "account" | "security";

interface Session {
  device: string;
  lastActive: string;
  location: string;
}

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<TabId>("integrations");

  // Notification states
  const [notificationStates, setNotificationStates] = useState({
    newMatches: true,
    applicationStatus: true,
    scoutDigest: true,
    marketing: false,
  });
  const [notificationChannel, setNotificationChannel] = useState<"email" | "push" | "both">("email");

  // Privacy states
  const [privacyStates, setPrivacyStates] = useState({
    stealthMode: true,
    shareData: false,
    contactSuggestions: true,
  });

  // Account data
  const [createdDate] = useState("February 14, 2024");

  // Security states
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false);
  const [sessions] = useState<Session[]>([
    { device: "Chrome on macOS", lastActive: "Today at 2:45 PM", location: "San Francisco, CA" },
    { device: "Safari on iPhone", lastActive: "Yesterday at 9:30 AM", location: "San Francisco, CA" },
  ]);

  const toggleNotification = (key: keyof typeof notificationStates) => {
    setNotificationStates(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const togglePrivacy = (key: keyof typeof privacyStates) => {
    setPrivacyStates(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const renderToggle = (enabled: boolean, onChange: () => void) => (
    <button
      onClick={onChange}
      style={{
        width: 40,
        height: 22,
        borderRadius: 11,
        backgroundColor: enabled ? "#4D8EF5" : "#E5E7EB",
        border: "none",
        cursor: "pointer",
        transition: "background-color 0.2s",
        position: "relative",
        display: "flex",
        alignItems: "center",
        paddingLeft: enabled ? 2 : 0,
        paddingRight: enabled ? 0 : 2,
      }}
    >
      <div
        style={{
          width: 18,
          height: 18,
          borderRadius: 9,
          backgroundColor: "white",
          marginLeft: enabled ? "auto" : 0,
          marginRight: enabled ? 0 : "auto",
          transition: "margin 0.2s",
        }}
      />
    </button>
  );

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#FFFFFF", color: "#1F2937", padding: "48px 40px" }}>
      {/* Header */}
      <div style={{ marginBottom: 48 }}>
        <h1 style={{ fontSize: 28, fontWeight: 600, marginBottom: 8 }}>Settings</h1>
        <p style={{ fontSize: 14, color: "#6B7280" }}>Manage integrations and preferences.</p>
      </div>

      {/* Tabs */}
      <div style={{ borderBottom: `1px solid ${SR.border}`, marginBottom: 32, display: "flex", gap: 32 }}>
        {(["integrations", "notifications", "privacy", "account", "security"] as TabId[]).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: "12px 0",
              border: "none",
              backgroundColor: "transparent",
              cursor: "pointer",
              fontSize: 14,
              fontWeight: 500,
              color: activeTab === tab ? "#4D8EF5" : "#9CA3AF",
              borderBottom: activeTab === tab ? "2px solid #4D8EF5" : "none",
              transition: "all 0.2s",
              textTransform: "capitalize",
            }}
          >
            {tab === "integrations" && "Integrations"}
            {tab === "notifications" && "Notifications"}
            {tab === "privacy" && "Privacy"}
            {tab === "account" && "Account"}
            {tab === "security" && "Security"}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div style={{
        backgroundColor: "#FFFFFF",
        border: `1px solid ${SR.border}`,
        borderRadius: 14,
        padding: 24,
      }}>

        {/* INTEGRATIONS TAB */}
        {activeTab === "integrations" && (
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
              {/* LinkedIn Extension */}
              <div style={{
                border: `1px solid ${SR.border}`,
                borderRadius: 12,
                padding: 20,
                display: "flex",
                flexDirection: "column",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                  <div style={{
                    width: 48,
                    height: 48,
                    borderRadius: 8,
                    backgroundColor: "#0A66C2",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "white",
                    fontSize: 20,
                  }}>
                    in
                  </div>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>LinkedIn Extension</h3>
                    <p style={{ fontSize: 12, color: "#6B7280", margin: "4px 0 0 0" }}>Sync connections & insights</p>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: "auto", paddingTop: 12 }}>
                  <span style={{
                    backgroundColor: "#D1FAE5",
                    color: "#065F46",
                    padding: "4px 12px",
                    borderRadius: 20,
                    fontSize: 12,
                    fontWeight: 500,
                  }}>
                    Connected
                  </span>
                  <button style={{
                    marginLeft: "auto",
                    padding: "8px 16px",
                    backgroundColor: "transparent",
                    border: `1px solid #EF4444`,
                    color: "#EF4444",
                    borderRadius: 8,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                    transition: "background-color 0.2s",
                  }}
                  onMouseOver={e => (e.currentTarget.style.backgroundColor = "rgba(239, 68, 68, 0.05)")}
                  onMouseOut={e => (e.currentTarget.style.backgroundColor = "transparent")}
                  >
                    Disconnect
                  </button>
                </div>
              </div>

              {/* Gmail */}
              <div style={{
                border: `1px solid ${SR.border}`,
                borderRadius: 12,
                padding: 20,
                display: "flex",
                flexDirection: "column",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                  <div style={{
                    width: 48,
                    height: 48,
                    borderRadius: 8,
                    backgroundColor: "#EA4335",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "white",
                    fontSize: 20,
                  }}>
                    G
                  </div>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Gmail</h3>
                    <p style={{ fontSize: 12, color: "#6B7280", margin: "4px 0 0 0" }}>Email sync & detection</p>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: "auto", paddingTop: 12 }}>
                  <span style={{
                    backgroundColor: "#F3F4F6",
                    color: "#6B7280",
                    padding: "4px 12px",
                    borderRadius: 20,
                    fontSize: 12,
                    fontWeight: 500,
                  }}>
                    Not connected
                  </span>
                  <button style={{
                    marginLeft: "auto",
                    padding: "8px 16px",
                    backgroundColor: "#EA4335",
                    color: "white",
                    border: "none",
                    borderRadius: 8,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                    transition: "background-color 0.2s",
                  }}
                  onMouseOver={e => (e.currentTarget.style.backgroundColor = "#D33B27")}
                  onMouseOut={e => (e.currentTarget.style.backgroundColor = "#EA4335")}
                  >
                    Connect
                  </button>
                </div>
              </div>

              {/* Outlook */}
              <div style={{
                border: `1px solid ${SR.border}`,
                borderRadius: 12,
                padding: 20,
                display: "flex",
                flexDirection: "column",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                  <div style={{
                    width: 48,
                    height: 48,
                    borderRadius: 8,
                    backgroundColor: "#0078D4",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "white",
                    fontSize: 20,
                  }}>
                    O
                  </div>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Outlook</h3>
                    <p style={{ fontSize: 12, color: "#6B7280", margin: "4px 0 0 0" }}>Email sync & detection</p>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: "auto", paddingTop: 12 }}>
                  <span style={{
                    backgroundColor: "#F3F4F6",
                    color: "#6B7280",
                    padding: "4px 12px",
                    borderRadius: 20,
                    fontSize: 12,
                    fontWeight: 500,
                  }}>
                    Not connected
                  </span>
                  <button style={{
                    marginLeft: "auto",
                    padding: "8px 16px",
                    backgroundColor: "#0078D4",
                    color: "white",
                    border: "none",
                    borderRadius: 8,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                    transition: "background-color 0.2s",
                  }}
                  onMouseOver={e => (e.currentTarget.style.backgroundColor = "#005A9E")}
                  onMouseOut={e => (e.currentTarget.style.backgroundColor = "#0078D4")}
                  >
                    Connect
                  </button>
                </div>
              </div>

              {/* Calendar */}
              <div style={{
                border: `1px solid ${SR.border}`,
                borderRadius: 12,
                padding: 20,
                display: "flex",
                flexDirection: "column",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                  <div style={{
                    width: 48,
                    height: 48,
                    borderRadius: 8,
                    backgroundColor: "#4F46E5",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "white",
                    fontSize: 20,
                  }}>
                    📅
                  </div>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Calendar</h3>
                    <p style={{ fontSize: 12, color: "#6B7280", margin: "4px 0 0 0" }}>Interview scheduling</p>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: "auto", paddingTop: 12 }}>
                  <span style={{
                    backgroundColor: "#F3F4F6",
                    color: "#6B7280",
                    padding: "4px 12px",
                    borderRadius: 20,
                    fontSize: 12,
                    fontWeight: 500,
                  }}>
                    Not connected
                  </span>
                  <button style={{
                    marginLeft: "auto",
                    padding: "8px 16px",
                    backgroundColor: "#4F46E5",
                    color: "white",
                    border: "none",
                    borderRadius: 8,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                    transition: "background-color 0.2s",
                  }}
                  onMouseOver={e => (e.currentTarget.style.backgroundColor = "#4338CA")}
                  onMouseOut={e => (e.currentTarget.style.backgroundColor = "#4F46E5")}
                  >
                    Connect
                  </button>
                </div>
              </div>

              {/* WhatsApp */}
              <div style={{
                border: `1px solid ${SR.border}`,
                borderRadius: 12,
                padding: 20,
                display: "flex",
                flexDirection: "column",
                gridColumn: "span 2",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                  <div style={{
                    width: 48,
                    height: 48,
                    borderRadius: 8,
                    backgroundColor: "#25D366",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "white",
                    fontSize: 20,
                  }}>
                    💬
                  </div>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>WhatsApp</h3>
                    <p style={{ fontSize: 12, color: "#6B7280", margin: "4px 0 0 0" }}>Opportunity alerts</p>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: "auto", paddingTop: 12 }}>
                  <span style={{
                    backgroundColor: "#F3F4F6",
                    color: "#6B7280",
                    padding: "4px 12px",
                    borderRadius: 20,
                    fontSize: 12,
                    fontWeight: 500,
                  }}>
                    Coming soon
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* NOTIFICATIONS TAB */}
        {activeTab === "notifications" && (
          <div style={{ maxWidth: 500 }}>
            <div style={{ marginBottom: 32 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Email Notifications</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <p style={{ fontSize: 14, fontWeight: 500, margin: 0, marginBottom: 4 }}>New matches found</p>
                    <p style={{ fontSize: 12, color: "#6B7280", margin: 0 }}>When relevant opportunities appear</p>
                  </div>
                  {renderToggle(notificationStates.newMatches, () => toggleNotification("newMatches"))}
                </div>
                <div style={{ height: 1, backgroundColor: SR.border }} />
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <p style={{ fontSize: 14, fontWeight: 500, margin: 0, marginBottom: 4 }}>Application status changes</p>
                    <p style={{ fontSize: 12, color: "#6B7280", margin: 0 }}>Updates on your applications</p>
                  </div>
                  {renderToggle(notificationStates.applicationStatus, () => toggleNotification("applicationStatus"))}
                </div>
                <div style={{ height: 1, backgroundColor: SR.border }} />
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <p style={{ fontSize: 14, fontWeight: 500, margin: 0, marginBottom: 4 }}>Scout weekly digest</p>
                    <p style={{ fontSize: 12, color: "#6B7280", margin: 0 }}>Summary of your network activity</p>
                  </div>
                  {renderToggle(notificationStates.scoutDigest, () => toggleNotification("scoutDigest"))}
                </div>
                <div style={{ height: 1, backgroundColor: SR.border }} />
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <p style={{ fontSize: 14, fontWeight: 500, margin: 0, marginBottom: 4 }}>Marketing emails</p>
                    <p style={{ fontSize: 12, color: "#6B7280", margin: 0 }}>New features and updates</p>
                  </div>
                  {renderToggle(notificationStates.marketing, () => toggleNotification("marketing"))}
                </div>
              </div>
            </div>

            <div>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Notification Channel</h3>
              <div style={{ display: "flex", gap: 8 }}>
                {(["email", "push", "both"] as const).map(channel => (
                  <button
                    key={channel}
                    onClick={() => setNotificationChannel(channel)}
                    style={{
                      padding: "8px 16px",
                      border: `1px solid ${notificationChannel === channel ? "#4D8EF5" : SR.border}`,
                      borderRadius: 8,
                      backgroundColor: notificationChannel === channel ? "#DBEAFE" : "#FFFFFF",
                      color: notificationChannel === channel ? "#4D8EF5" : "#6B7280",
                      fontSize: 12,
                      fontWeight: 500,
                      cursor: "pointer",
                      transition: "all 0.2s",
                      textTransform: "capitalize",
                    }}
                  >
                    {channel}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* PRIVACY TAB */}
        {activeTab === "privacy" && (
          <div style={{ maxWidth: 500 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: 14, fontWeight: 500, margin: 0, marginBottom: 4 }}>Stealth mode</p>
                  <p style={{ fontSize: 12, color: "#6B7280", margin: 0 }}>Your profile won't appear in public searches</p>
                </div>
                {renderToggle(privacyStates.stealthMode, () => togglePrivacy("stealthMode"))}
              </div>
              <div style={{ height: 1, backgroundColor: SR.border }} />
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: 14, fontWeight: 500, margin: 0, marginBottom: 4 }}>Share anonymized data for Scout improvements</p>
                  <p style={{ fontSize: 12, color: "#6B7280", margin: 0 }}>Help us improve recommendations</p>
                </div>
                {renderToggle(privacyStates.shareData, () => togglePrivacy("shareData"))}
              </div>
              <div style={{ height: 1, backgroundColor: SR.border }} />
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: 14, fontWeight: 500, margin: 0, marginBottom: 4 }}>Allow contact suggestions</p>
                  <p style={{ fontSize: 12, color: "#6B7280", margin: 0 }}>Recommend people to connect with</p>
                </div>
                {renderToggle(privacyStates.contactSuggestions, () => togglePrivacy("contactSuggestions"))}
              </div>
            </div>
          </div>
        )}

        {/* ACCOUNT TAB */}
        {activeTab === "account" && (
          <div style={{ maxWidth: 500 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: "#6B7280", display: "block", marginBottom: 8 }}>EMAIL</label>
                <p style={{ fontSize: 14, margin: 0 }}>{user?.email || "—"}</p>
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: "#6B7280", display: "block", marginBottom: 8 }}>FULL NAME</label>
                <p style={{ fontSize: 14, margin: 0 }}>{user?.full_name || "—"}</p>
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: "#6B7280", display: "block", marginBottom: 8 }}>CREATED DATE</label>
                <p style={{ fontSize: 14, margin: 0 }}>{createdDate}</p>
              </div>
              <div style={{ marginTop: 24 }}>
                <button
                  onClick={() => {
                    if (confirm("Are you sure? This cannot be undone.")) {
                      logout();
                    }
                  }}
                  style={{
                    padding: "10px 16px",
                    backgroundColor: "#FEE2E2",
                    color: "#DC2626",
                    border: `1px solid #FECACA`,
                    borderRadius: 8,
                    fontSize: 14,
                    fontWeight: 600,
                    cursor: "pointer",
                    transition: "background-color 0.2s",
                  }}
                  onMouseOver={e => (e.currentTarget.style.backgroundColor = "#FCA5A5")}
                  onMouseOut={e => (e.currentTarget.style.backgroundColor = "#FEE2E2")}
                >
                  Delete Account
                </button>
              </div>
            </div>
          </div>
        )}

        {/* SECURITY TAB */}
        {activeTab === "security" && (
          <div>
            <div style={{ marginBottom: 32 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Two-Factor Authentication</h3>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <p style={{ fontSize: 14, fontWeight: 500, margin: 0, marginBottom: 4 }}>
                    {twoFactorEnabled ? "Enabled" : "Not enabled"}
                  </p>
                  <p style={{ fontSize: 12, color: "#6B7280", margin: 0 }}>Add an extra security layer</p>
                </div>
                <button
                  onClick={() => setTwoFactorEnabled(!twoFactorEnabled)}
                  style={{
                    padding: "10px 16px",
                    backgroundColor: twoFactorEnabled ? "#FEE2E2" : "#DBEAFE",
                    color: twoFactorEnabled ? "#DC2626" : "#4D8EF5",
                    border: `1px solid ${twoFactorEnabled ? "#FECACA" : "#BFDBFE"}`,
                    borderRadius: 8,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                    transition: "all 0.2s",
                  }}
                  onMouseOver={e => {
                    e.currentTarget.style.backgroundColor = twoFactorEnabled ? "#FCA5A5" : "#93C5FD";
                  }}
                  onMouseOut={e => {
                    e.currentTarget.style.backgroundColor = twoFactorEnabled ? "#FEE2E2" : "#DBEAFE";
                  }}
                >
                  {twoFactorEnabled ? "Disable" : "Enable"}
                </button>
              </div>
            </div>

            <div style={{ marginBottom: 32 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Active Sessions</h3>
              <div style={{ border: `1px solid ${SR.border}`, borderRadius: 8, overflow: "hidden" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ backgroundColor: "#F9FAFB" }}>
                      <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 12, fontWeight: 600, color: "#6B7280", borderBottom: `1px solid ${SR.border}` }}>Device</th>
                      <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 12, fontWeight: 600, color: "#6B7280", borderBottom: `1px solid ${SR.border}` }}>Last Active</th>
                      <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 12, fontWeight: 600, color: "#6B7280", borderBottom: `1px solid ${SR.border}` }}>Location</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sessions.map((session, idx) => (
                      <tr key={idx} style={{ borderBottom: idx < sessions.length - 1 ? `1px solid ${SR.border}` : "none" }}>
                        <td style={{ padding: "12px 16px", fontSize: 13 }}>{session.device}</td>
                        <td style={{ padding: "12px 16px", fontSize: 13, color: "#6B7280" }}>{session.lastActive}</td>
                        <td style={{ padding: "12px 16px", fontSize: 13, color: "#6B7280" }}>{session.location}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <button
              onClick={() => {
                if (confirm("Sign out all sessions?")) {
                  logout();
                }
              }}
              style={{
                padding: "10px 16px",
                backgroundColor: "#FEE2E2",
                color: "#DC2626",
                border: `1px solid #FECACA`,
                borderRadius: 8,
                fontSize: 14,
                fontWeight: 600,
                cursor: "pointer",
                transition: "background-color 0.2s",
              }}
              onMouseOver={e => (e.currentTarget.style.backgroundColor = "#FCA5A5")}
              onMouseOut={e => (e.currentTarget.style.backgroundColor = "#FEE2E2")}
            >
              Sign Out All Sessions
            </button>
          </div>
        )}

      </div>
    </div>
  );
}
