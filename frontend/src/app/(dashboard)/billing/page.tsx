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

const PLANS = [
  {
    id: "recon",
    name: "Recon",
    price: "$0",
    tag: "Free",
    features: ["Up to 50 scans/month", "2 packs/month", "Basic company signals", "No team access"]
  },
  {
    id: "operator",
    name: "Operator",
    price: "$48",
    tag: "CURRENT",
    period: "/mo",
    features: ["Unlimited scans", "Unlimited packs", "Full signals + predictions", "Warm intro requests", "Unlimited team members"]
  },
  {
    id: "command",
    name: "Command",
    price: "$148",
    tag: "For pros",
    period: "/mo",
    features: ["Everything in Operator", "Priority API support", "Custom integrations", "Dedicated onboarding", "SLA guarantees"]
  }
];

const USAGE = [
  { label: "Scan credits", used: 3140, total: 5000, color: AC.brand },
  { label: "Watched companies", used: 142, total: 250, color: AC.good },
  { label: "Packs built", used: 14, total: 50, color: AC.warn },
  { label: "Warm-intro requests", used: 2, total: 5, color: "#7F60E8" }
];

const INVOICES = [
  { date: "Apr 12, 2026", invoice: "INV-2026-004", amount: "$48", status: "Paid", method: "Visa •••• 4242", pdf: "PDF" },
  { date: "Mar 12, 2026", invoice: "INV-2026-003", amount: "$48", status: "Paid", method: "Visa •••• 4242", pdf: "PDF" },
  { date: "Feb 12, 2026", invoice: "INV-2026-002", amount: "$48", status: "Paid", method: "Visa •••• 4242", pdf: "PDF" },
  { date: "Jan 12, 2026", invoice: "INV-2026-001", amount: "$48", status: "Paid", method: "Visa •••• 4242", pdf: "PDF" },
  { date: "Dec 12, 2025", invoice: "INV-2025-012", amount: "$48", status: "Paid", method: "Visa •••• 4242", pdf: "PDF" },
  { date: "Nov 12, 2025", invoice: "INV-2025-011", amount: "$48", status: "Refunded", method: "Visa •••• 4242", pdf: "PDF" }
];

const ADDONS = [
  { label: "+100 companies", price: "$10/mo" },
  { label: "+2000 scans", price: "$15/mo" },
  { label: "Pack ghostwriting", price: "$25/mo" },
  { label: "Priority intros", price: "$30/mo" }
];

export default function BillingPage() {
  const [addOnStates, setAddOnStates] = useState({ companies: false, scans: false, ghostwriting: false, intros: false });

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
            BILLING · CREDITS & USAGE
          </div>
          <h1 style={{ fontSize: 28, fontWeight: 600, color: "#fff", margin: "0 0 4px 0" }}>
            Billing
          </h1>
          <p style={{ fontSize: 13, color: "rgba(255,255,255,0.8)", margin: 0 }}>
            Manage your plan, usage, and payment methods.
          </p>
        </div>
      </div>

      {/* Main content */}
      <div style={{ maxWidth: 1440, margin: "0 auto", padding: "0 36px 32px", display: "grid", gridTemplateColumns: "1fr 340px", gap: 18 }}>

        {/* LEFT COLUMN */}
        <div>

          {/* Plans */}
          <div style={{ marginBottom: 18 }}>
            <h2 style={{ fontSize: 14, fontWeight: 600, color: AC.ink, marginBottom: 12, padding: "0 0 0 0" }}>Plans</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
              {PLANS.map(plan => (
                <div key={plan.id} style={{
                  ...cardStyle,
                  position: "relative",
                  background: plan.id === "operator" ? AC.brandTint : AC.panel,
                  overflow: "hidden"
                }}>
                  {plan.id === "operator" && (
                    <div style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      right: 0,
                      height: 3,
                      background: `linear-gradient(90deg, ${AC.brand} 0%, ${AC.brand3} 100%)`
                    }} />
                  )}
                  <div style={{ ...titleBarStyle, borderTop: plan.id === "operator" ? `3px solid ${AC.brand2}` : "none" }}>
                    {plan.tag === "CURRENT" ? (
                      <span style={{ background: AC.brandTint2, color: AC.brand, padding: "2px 6px", borderRadius: 4, fontSize: 9, fontWeight: 700 }}>CURRENT PLAN</span>
                    ) : (
                      <span style={{ fontSize: 9, fontWeight: 700, color: AC.ink4 }}>{plan.tag}</span>
                    )}
                  </div>
                  <div style={contentStyle}>
                    <h3 style={{ fontSize: 14, fontWeight: 600, color: AC.ink, margin: "0 0 4px 0" }}>{plan.name}</h3>
                    <div style={{ fontSize: 18, fontWeight: 700, color: AC.brand, marginBottom: 12 }}>
                      {plan.price}
                      {plan.period && <span style={{ fontSize: 12, color: AC.ink4, fontWeight: 500 }}>{plan.period}</span>}
                    </div>
                    <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6, marginBottom: 16 }}>
                      {plan.features.map((feat, idx) => (
                        <li key={idx} style={{ display: "flex", gap: 6, fontSize: 12, color: AC.ink3 }}>
                          <span style={{ color: AC.good, fontWeight: 700 }}>✓</span>
                          {feat}
                        </li>
                      ))}
                    </ul>
                    <button style={{
                      width: "100%",
                      padding: "10px 12px",
                      background: plan.id === "operator" ? "transparent" : AC.brand,
                      color: plan.id === "operator" ? AC.ink4 : "#fff",
                      border: plan.id === "operator" ? `1px solid ${AC.border}` : "none",
                      borderRadius: 6,
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: plan.id === "operator" ? "default" : "pointer"
                    }}>
                      {plan.id === "operator" ? "Current plan" : plan.id === "recon" ? "Downgrade" : "Upgrade"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Usage This Period */}
          <div style={{ ...cardStyle, marginBottom: 18 }}>
            <div style={titleBarStyle}>Usage This Period</div>
            <div style={contentStyle}>
              {USAGE.map((item, idx) => {
                const pct = (item.used / item.total) * 100;
                return (
                  <div key={idx} style={{ marginBottom: idx < USAGE.length - 1 ? 16 : 0 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 12 }}>
                      <div style={{ color: AC.ink4, fontWeight: 600 }}>{item.label}</div>
                      <div style={{ color: AC.ink3, fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>{item.used}/{item.total}</div>
                    </div>
                    <div style={{ height: 5, background: AC.panel2, borderRadius: 3, overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${pct}%`, background: item.color, borderRadius: 3 }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Invoice History */}
          <div style={cardStyle}>
            <div style={titleBarStyle}>Invoice History</div>
            <div style={contentStyle}>
              <div style={{ overflow: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left", padding: "8px 0", borderBottom: `1px solid ${AC.divider}`, fontWeight: 600, color: AC.ink4, fontSize: 11 }}>Date</th>
                      <th style={{ textAlign: "left", padding: "8px 0", borderBottom: `1px solid ${AC.divider}`, fontWeight: 600, color: AC.ink4, fontSize: 11 }}>Invoice</th>
                      <th style={{ textAlign: "right", padding: "8px 0", borderBottom: `1px solid ${AC.divider}`, fontWeight: 600, color: AC.ink4, fontSize: 11 }}>Amount</th>
                      <th style={{ textAlign: "left", padding: "8px 0", borderBottom: `1px solid ${AC.divider}`, fontWeight: 600, color: AC.ink4, fontSize: 11 }}>Status</th>
                      <th style={{ textAlign: "left", padding: "8px 0", borderBottom: `1px solid ${AC.divider}`, fontWeight: 600, color: AC.ink4, fontSize: 11 }}>Method</th>
                      <th style={{ textAlign: "center", padding: "8px 0", borderBottom: `1px solid ${AC.divider}`, fontWeight: 600, color: AC.ink4, fontSize: 11 }}>PDF</th>
                    </tr>
                  </thead>
                  <tbody>
                    {INVOICES.map((inv, idx) => (
                      <tr key={idx} style={{ borderBottom: `1px solid ${AC.divider}` }}>
                        <td style={{ padding: "10px 0", color: AC.ink }}>{inv.date}</td>
                        <td style={{ padding: "10px 0", color: AC.ink, fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>{inv.invoice}</td>
                        <td style={{ padding: "10px 0", color: AC.ink, textAlign: "right", fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>{inv.amount}</td>
                        <td style={{ padding: "10px 0" }}>
                          <span style={{
                            fontSize: 9,
                            fontWeight: 700,
                            padding: "2px 6px",
                            borderRadius: 4,
                            background: inv.status === "Paid" ? "rgba(22,163,74,0.12)" : "rgba(202,138,4,0.12)",
                            color: inv.status === "Paid" ? AC.good : AC.warn
                          }}>
                            {inv.status}
                          </span>
                        </td>
                        <td style={{ padding: "10px 0", color: AC.ink3, fontSize: 11 }}>{inv.method}</td>
                        <td style={{ padding: "10px 0", textAlign: "center" }}>
                          <a href="#" style={{ color: AC.brand, textDecoration: "none", fontWeight: 600, fontSize: 10 }}>↓</a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

        </div>

        {/* RIGHT COLUMN (STICKY) */}
        <div style={{ position: "sticky", top: 18, height: "fit-content", display: "flex", flexDirection: "column", gap: 18 }}>

          {/* Payment Methods */}
          <div style={cardStyle}>
            <div style={titleBarStyle}>Payment Methods</div>
            <div style={contentStyle}>
              <div style={{
                background: `linear-gradient(135deg, ${AC.brand} 0%, ${AC.brand3} 100%)`,
                borderRadius: 8,
                padding: 12,
                color: "#fff",
                marginBottom: 12,
                position: "relative"
              }}>
                <div style={{ fontSize: 9, fontWeight: 700, opacity: 0.7, marginBottom: 8 }}>PRIMARY</div>
                <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>Visa •••• 4242</div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, opacity: 0.8 }}>
                  <span>Alex Moreno</span>
                  <span>08/28</span>
                </div>
              </div>
              <div style={{
                background: AC.panel2,
                border: `1px solid ${AC.border}`,
                borderRadius: 8,
                padding: 12,
                marginBottom: 12
              }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: AC.ink, marginBottom: 4 }}>Mastercard •••• 8821</div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: AC.ink4 }}>
                  <span>Backup card</span>
                  <span>11/27</span>
                </div>
              </div>
              <button style={{
                width: "100%",
                padding: "8px 12px",
                border: `1px solid ${AC.border}`,
                background: AC.panel,
                borderRadius: 6,
                fontSize: 11,
                fontWeight: 600,
                color: AC.brand,
                cursor: "pointer"
              }}>
                + Add card
              </button>
            </div>
          </div>

          {/* Billing Details */}
          <div style={cardStyle}>
            <div style={titleBarStyle}>Billing Details</div>
            <div style={contentStyle}>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {[
                  { label: "Billed to", value: "Alex Moreno" },
                  { label: "Address", value: "123 Market St" },
                  { label: "Country", value: "United States" },
                  { label: "Tax ID", value: "12-3456789" },
                  { label: "Email", value: "alex@notion.com" }
                ].map((item, idx) => (
                  <div key={idx}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: AC.ink4, marginBottom: 2, textTransform: "uppercase" }}>{item.label}</div>
                    <div style={{ fontSize: 12, color: AC.ink }}>{item.value}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Add-ons */}
          <div style={cardStyle}>
            <div style={titleBarStyle}>Add-ons</div>
            <div style={contentStyle}>
              {ADDONS.map((addon, idx) => (
                <div key={idx} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: 10, marginBottom: 10, borderBottom: idx < ADDONS.length - 1 ? `1px solid ${AC.divider}` : "none" }}>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 500, color: AC.ink }}>{addon.label}</div>
                    <div style={{ fontSize: 10, color: AC.ink4 }}>{addon.price}</div>
                  </div>
                  {renderToggle(false, () => {})}
                </div>
              ))}
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
