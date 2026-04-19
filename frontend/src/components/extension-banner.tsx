// @ts-nocheck
"use client";

import { useEffect, useState } from "react";
import { getAuthHeaders } from "@/lib/utils";

// Chrome Web Store URL — update when extension is published
const CHROME_STORE_URL = "https://chrome.google.com/webstore/detail/stealthrole";
// For now, link to the GitHub instructions
const INSTALL_URL = "https://github.com/matteomantovani1982-stack/stealthrole#extension";

export default function ExtensionBanner() {
  const [dismissed, setDismissed] = useState(true); // hidden by default
  const [extensionDetected, setExtensionDetected] = useState(false);

  useEffect(() => {
    // Check if banner was already dismissed
    const wasDismissed = localStorage.getItem("sr_ext_banner_dismissed");
    if (wasDismissed) {
      setDismissed(true);
      return;
    }

    // Try to detect if extension is installed by checking for its injected element
    // or by sending a message. If not detected after 2s, show banner.
    const timer = setTimeout(() => {
      // Check if extension content script injected its marker
      const marker = document.getElementById("sr-extension-marker");
      if (marker) {
        setExtensionDetected(true);
        setDismissed(true);
      } else {
        setDismissed(false);
      }
    }, 2000);

    return () => clearTimeout(timer);
  }, []);

  // Sync token to extension whenever it changes
  useEffect(() => {
    function syncToken() {
      const headers = getAuthHeaders(false);
      const token = headers["Authorization"]?.replace("Bearer ", "");
      if (token) {
        // Dispatch a custom event that the extension content script can listen for
        window.dispatchEvent(new CustomEvent("sr-token-sync", { detail: { token } }));
      }
    }

    // Sync on mount
    syncToken();

    // Sync whenever localStorage changes (login/logout)
    window.addEventListener("storage", syncToken);
    // Also sync on focus (user might have just logged in on another tab)
    window.addEventListener("focus", syncToken);

    return () => {
      window.removeEventListener("storage", syncToken);
      window.removeEventListener("focus", syncToken);
    };
  }, []);

  if (dismissed) return null;

  return (
    <div style={{
      position: "fixed", bottom: 24, right: 24, zIndex: 1000,
      width: 380, borderRadius: 16, overflow: "hidden",
      background: "linear-gradient(160deg, #0a1a3a, #060e22)",
      border: "1px solid rgba(77,142,245,0.3)",
      boxShadow: "0 20px 60px rgba(0,0,0,0.5), 0 0 40px rgba(77,142,245,0.1)",
    }}>
      {/* Top band */}
      <div style={{ height: 3, background: "linear-gradient(90deg, transparent, #4d8ef5, transparent)" }} />

      <div style={{ padding: "18px 20px" }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              background: "linear-gradient(135deg, #4d8ef5, #7c6aff)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
              </svg>
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#fff" }}>Install StealthRole Extension</div>
              <div style={{ fontSize: 11, color: "rgba(255,255,255,0.45)" }}>Required for LinkedIn integration</div>
            </div>
          </div>
          <button onClick={() => { setDismissed(true); localStorage.setItem("sr_ext_banner_dismissed", "7d"); }}
            style={{ background: "none", border: "none", color: "rgba(255,255,255,0.3)", cursor: "pointer", fontSize: 18, lineHeight: 1, padding: 4 }}>
            ×
          </button>
        </div>

        {/* Benefits */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 14 }}>
          {[
            { icon: "🔗", text: "Auto-map your LinkedIn connections to opportunities" },
            { icon: "🤝", text: "Find warm intro paths to hiring managers" },
            { icon: "📊", text: "Save profiles and track mutual connections" },
          ].map((b, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "rgba(255,255,255,0.6)" }}>
              <span>{b.icon}</span>
              <span>{b.text}</span>
            </div>
          ))}
        </div>

        {/* Buttons */}
        <div style={{ display: "flex", gap: 8 }}>
          <a href={INSTALL_URL} target="_blank" rel="noopener"
            style={{
              flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              background: "#4d8ef5", color: "#fff", border: "none", borderRadius: 10,
              padding: "10px 16px", fontSize: 12, fontWeight: 600, textDecoration: "none", cursor: "pointer",
            }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="white"><circle cx="12" cy="12" r="10" fill="none" stroke="white" strokeWidth="2"/><path d="M12 8v8m-4-4h8" stroke="white" strokeWidth="2" strokeLinecap="round"/></svg>
            Install for Chrome
          </a>
          <button onClick={() => { setDismissed(true); localStorage.setItem("sr_ext_banner_dismissed", "7d"); }}
            style={{
              background: "rgba(255,255,255,0.05)", color: "rgba(255,255,255,0.5)",
              border: "0.5px solid rgba(255,255,255,0.1)", borderRadius: 10,
              padding: "10px 16px", fontSize: 12, fontWeight: 500, cursor: "pointer",
            }}>
            Later
          </button>
        </div>

        <div style={{ fontSize: 9, color: "rgba(255,255,255,0.25)", textAlign: "center", marginTop: 10 }}>
          Works with Chrome, Brave, and Edge
        </div>
      </div>
    </div>
  );
}
