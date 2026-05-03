"use client";

import { useState } from "react";
import { SR } from "@/lib/constants";

const PLANS = [
  {
    id: "recon",
    name: "Recon",
    label: "Free",
    features: ["5 scout scans/month", "2 application packs", "Basic signals"],
  },
  {
    id: "operator",
    name: "Operator",
    price: "$29/mo",
    features: ["Unlimited scans", "20 packs/month", "Full signals + predictions", "Way-In contacts"],
  },
  {
    id: "command",
    name: "Command",
    price: "$79/mo",
    features: ["Everything in Operator", "Priority Scout", "Unlimited packs", "API access", "Dedicated support"],
  },
];

const USAGE_ITEMS = [
  { label: "Scout scans", used: 3, total: 5, color: "#6366f1" },
  { label: "Application packs", used: 1, total: 2, color: "#a855f7" },
  { label: "API calls", used: 0, total: 100, color: "#d1d5db" },
];

const INVOICES = [
  { date: "Apr 2026", description: "Free plan", amount: "$0", status: "Paid" },
  { date: "Mar 2026", description: "Free plan", amount: "$0", status: "Paid" },
  { date: "Feb 2026", description: "Free plan", amount: "$0", status: "Paid" },
];

export default function BillingPage() {
  const [currentPlan] = useState("recon");

  return (
    <div style={{ padding: "40px 0" }}>
      {/* Header */}
      <div style={{ marginBottom: "32px" }}>
        <h1 style={{ fontSize: "28px", fontWeight: "700", color: "#0a0a0a", margin: "0 0 8px 0" }}>Billing</h1>
        <p style={{ fontSize: "14px", color: "#666666", margin: "0" }}>Manage your plan, credits, and usage.</p>
      </div>

      {/* 2-column layout */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "32px" }}>
        {/* Left column (~60%) */}
        <div style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
          {/* Plans Section */}
          <div>
            <h2 style={{ fontSize: "16px", fontWeight: "700", color: "#0a0a0a", margin: "0 0 16px 0" }}>Plans</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px" }}>
              {PLANS.map((plan) => {
                const isActive = currentPlan === plan.id;
                return (
                  <div
                    key={plan.id}
                    style={{
                      background: "#ffffff",
                      border: `2px solid ${isActive ? SR.brand : SR.border}`,
                      borderRadius: "14px",
                      padding: "20px",
                      backgroundColor: isActive ? `${SR.brand}10` : "#ffffff",
                    }}
                  >
                    {isActive && (
                      <div
                        style={{
                          display: "inline-block",
                          fontSize: "11px",
                          fontWeight: "700",
                          color: SR.brand,
                          background: `${SR.brand}20`,
                          padding: "4px 8px",
                          borderRadius: "4px",
                          marginBottom: "12px",
                        }}
                      >
                        Current plan
                      </div>
                    )}
                    <h3 style={{ fontSize: "16px", fontWeight: "700", color: "#0a0a0a", margin: "0 0 8px 0" }}>
                      {plan.name}
                    </h3>
                    {plan.label && (
                      <p style={{ fontSize: "13px", color: "#666666", margin: "0 0 12px 0" }}>{plan.label}</p>
                    )}
                    {plan.price && (
                      <p style={{ fontSize: "14px", fontWeight: "700", color: "#0a0a0a", margin: "0 0 12px 0" }}>
                        {plan.price}
                      </p>
                    )}
                    <ul style={{ margin: "0 0 16px 0", padding: "0", listStyle: "none" }}>
                      {plan.features.map((feature, idx) => (
                        <li
                          key={idx}
                          style={{
                            fontSize: "13px",
                            color: "#444444",
                            margin: "0 0 8px 0",
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                          }}
                        >
                          <span style={{ color: SR.brand, fontWeight: "700" }}>✓</span>
                          {feature}
                        </li>
                      ))}
                    </ul>
                    {!isActive && (
                      <button
                        style={{
                          width: "100%",
                          padding: "10px 12px",
                          background: SR.brand,
                          color: "#ffffff",
                          border: "none",
                          borderRadius: "8px",
                          fontSize: "13px",
                          fontWeight: "600",
                          cursor: "pointer",
                          transition: "opacity 0.2s",
                        }}
                        onMouseEnter={(e) => ((e.target as HTMLElement).style.opacity = "0.9")}
                        onMouseLeave={(e) => ((e.target as HTMLElement).style.opacity = "1")}
                      >
                        Upgrade
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Usage Section */}
          <div>
            <h2 style={{ fontSize: "16px", fontWeight: "700", color: "#0a0a0a", margin: "0 0 16px 0" }}>Usage</h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {USAGE_ITEMS.map((item) => {
                const percentage = (item.used / item.total) * 100;
                return (
                  <div key={item.label}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        marginBottom: "8px",
                      }}
                    >
                      <label style={{ fontSize: "13px", fontWeight: "600", color: "#0a0a0a" }}>
                        {item.label}
                      </label>
                      <span style={{ fontSize: "12px", color: "#666666" }}>
                        {item.used} of {item.total} used
                      </span>
                    </div>
                    <div
                      style={{
                        background: SR.border,
                        height: "6px",
                        borderRadius: "3px",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          background: item.color,
                          height: "100%",
                          width: `${percentage}%`,
                          borderRadius: "3px",
                          transition: "width 0.3s",
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Invoice History */}
          <div>
            <h2 style={{ fontSize: "16px", fontWeight: "700", color: "#0a0a0a", margin: "0 0 16px 0" }}>
              Invoice History
            </h2>
            <div style={{ border: `1px solid ${SR.border}`, borderRadius: "8px", overflow: "hidden" }}>
              <table
                style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  fontSize: "13px",
                }}
              >
                <thead>
                  <tr style={{ background: "#f9f9f9", borderBottom: `1px solid ${SR.border}` }}>
                    <th
                      style={{
                        padding: "12px",
                        textAlign: "left",
                        fontWeight: "600",
                        color: "#0a0a0a",
                      }}
                    >
                      Date
                    </th>
                    <th
                      style={{
                        padding: "12px",
                        textAlign: "left",
                        fontWeight: "600",
                        color: "#0a0a0a",
                      }}
                    >
                      Description
                    </th>
                    <th
                      style={{
                        padding: "12px",
                        textAlign: "left",
                        fontWeight: "600",
                        color: "#0a0a0a",
                      }}
                    >
                      Amount
                    </th>
                    <th
                      style={{
                        padding: "12px",
                        textAlign: "left",
                        fontWeight: "600",
                        color: "#0a0a0a",
                      }}
                    >
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {INVOICES.map((invoice, idx) => (
                    <tr
                      key={idx}
                      style={{
                        borderBottom: idx < INVOICES.length - 1 ? `1px solid ${SR.border}` : "none",
                      }}
                    >
                      <td style={{ padding: "12px", color: "#444444" }}>{invoice.date}</td>
                      <td style={{ padding: "12px", color: "#444444" }}>{invoice.description}</td>
                      <td style={{ padding: "12px", color: "#444444" }}>{invoice.amount}</td>
                      <td style={{ padding: "12px" }}>
                        <span
                          style={{
                            display: "inline-block",
                            padding: "4px 8px",
                            background: "#dcfce7",
                            color: "#166534",
                            borderRadius: "4px",
                            fontSize: "12px",
                            fontWeight: "600",
                          }}
                        >
                          {invoice.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right column (~40%) */}
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          {/* Payment Methods */}
          <div
            style={{
              background: "#ffffff",
              border: `1px solid ${SR.border}`,
              borderRadius: "8px",
              padding: "20px",
            }}
          >
            <h3 style={{ fontSize: "15px", fontWeight: "700", color: "#0a0a0a", margin: "0 0 16px 0" }}>
              Payment Methods
            </h3>
            <p style={{ fontSize: "13px", color: "#666666", margin: "0 0 16px 0" }}>No payment method</p>
            <button
              style={{
                width: "100%",
                padding: "10px 12px",
                background: SR.brand,
                color: "#ffffff",
                border: "none",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: "600",
                cursor: "pointer",
                transition: "opacity 0.2s",
              }}
              onMouseEnter={(e) => ((e.target as HTMLElement).style.opacity = "0.9")}
              onMouseLeave={(e) => ((e.target as HTMLElement).style.opacity = "1")}
            >
              + Add payment method
            </button>
          </div>

          {/* Billing Details */}
          <div
            style={{
              background: "#ffffff",
              border: `1px solid ${SR.border}`,
              borderRadius: "8px",
              padding: "20px",
            }}
          >
            <h3 style={{ fontSize: "15px", fontWeight: "700", color: "#0a0a0a", margin: "0 0 16px 0" }}>
              Billing Details
            </h3>
            <p style={{ fontSize: "13px", color: "#666666", margin: "0 0 16px 0" }}>No billing address on file</p>
            <button
              style={{
                width: "100%",
                padding: "10px 12px",
                background: "#ffffff",
                color: SR.brand,
                border: `1px solid ${SR.border}`,
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: "600",
                cursor: "pointer",
                transition: "background-color 0.2s, color 0.2s",
              }}
              onMouseEnter={(e) => {
                (e.target as HTMLElement).style.background = `${SR.brand}10`;
              }}
              onMouseLeave={(e) => {
                (e.target as HTMLElement).style.background = "#ffffff";
              }}
            >
              Add billing details
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
