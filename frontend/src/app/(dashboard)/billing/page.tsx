// @ts-nocheck
"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";

const PLANS = [
  {
    id: "free",
    name: "Free",
    price: 0,
    annual: 0,
    credits: 5,
    features: ["5 credits/month", "Profile + tracker (50 jobs)", "1 Intelligence Pack", "LinkedIn import"],
    cta: "Current Plan",
    popular: false,
  },
  {
    id: "pro",
    name: "Pro",
    price: 29,
    annual: 199,
    credits: 30,
    monthlyPriceId: "price_1TFK4M2NSvovIMwbAL0xrYLW",
    annualPriceId: "price_1TFK4N2NSvovIMwbxnrto73i",
    features: ["30 credits/month", "Full Intelligence Packs", "Email integration (Gmail/Outlook)", "LinkedIn integration", "Auto-apply (25/month)", "Hidden market signals"],
    cta: "Upgrade to Pro",
    popular: true,
  },
  {
    id: "elite",
    name: "Elite",
    price: 59,
    annual: 399,
    credits: 100,
    monthlyPriceId: "price_1TFK4O2NSvovIMwb49XsXfAk",
    annualPriceId: "price_1TFK4O2NSvovIMwbIiYVJ14b",
    features: ["100 credits/month", "Everything in Pro", "Unlimited Intelligence Packs", "100 auto-applies/month", "Priority processing", "WhatsApp alerts", "API access"],
    cta: "Upgrade to Elite",
    popular: false,
  },
];

const CREDIT_PACKS = [
  { name: "10 Credits", price: 5, credits: 10, priceId: "price_1TFK4Q2NSvovIMwbsOc7tNyt" },
  { name: "40 Credits", price: 15, credits: 40, priceId: "price_1TFK4R2NSvovIMwbRRxwYjGC" },
  { name: "100 Credits", price: 35, credits: 100, priceId: "price_1TFK4S2NSvovIMwbvd5Iljsm" },
];

const CREDIT_COSTS = [
  { action: "CV Tailoring", credits: 1 },
  { action: "Intelligence Pack", credits: 3 },
  { action: "Outreach Messages", credits: 1 },
  { action: "Shadow Application", credits: 3 },
  { action: "Auto-Apply", credits: 2 },
  { action: "Deep Email Scan", credits: 2 },
  { action: "Conversation Reply", credits: 1 },
];

export default function BillingPage() {
  const { user } = useAuth();
  const [annual, setAnnual] = useState(true);
  const [loading, setLoading] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  async function handleCheckout(priceId: string) {
    if (!priceId) return;
    setLoading(priceId);
    try {
      const token = localStorage.getItem("sr_token");
      const res = await fetch("/api/v1/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({
          price_id: priceId,
          success_url: `${window.location.origin}/billing?success=true`,
          cancel_url: `${window.location.origin}/billing?canceled=true`,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Checkout failed");
      }
      const data = await res.json();
      window.location.href = data.checkout_url;
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Checkout failed");
      setLoading(null);
    }
  }

  return (
    <div className="max-w-4xl space-y-8">
      <div className="text-center">
        <h1 className="text-3xl font-bold text-ink-900">Choose Your Plan</h1>
        <p className="text-sm text-ink-400 mt-2">Scale your job search with AI-powered intelligence</p>
      </div>

      {message && <div className="px-4 py-3 rounded-lg bg-brand-50 text-brand-700 text-sm text-center">{message}</div>}

      {/* Annual toggle */}
      <div className="flex items-center justify-center gap-3">
        <span className={`text-sm ${!annual ? "text-ink-900 font-medium" : "text-ink-400"}`}>Monthly</span>
        <button onClick={() => setAnnual(!annual)} className={`relative w-12 h-6 rounded-full transition-colors ${annual ? "bg-brand-600" : "bg-surface-300"}`}>
          <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${annual ? "translate-x-6" : "translate-x-0.5"}`} />
        </button>
        <span className={`text-sm ${annual ? "text-ink-900 font-medium" : "text-ink-400"}`}>Annual</span>
        {annual && <span className="text-[11px] px-2 py-0.5 rounded-full bg-green-50 text-green-700 font-medium">Save 30%+</span>}
      </div>

      {/* Plan cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {PLANS.map((plan) => (
          <div key={plan.id} className={`bg-white rounded-xl border p-6 flex flex-col ${plan.popular ? "border-brand-600 ring-1 ring-brand-600" : "border-surface-200"}`}>
            {plan.popular && <div className="text-[11px] font-bold text-brand-600 uppercase mb-2">Most Popular</div>}
            <h3 className="text-lg font-bold text-ink-900">{plan.name}</h3>
            <div className="mt-2 mb-4">
              {plan.price === 0 ? (
                <span className="text-3xl font-bold text-ink-900">Free</span>
              ) : (
                <>
                  <span className="text-3xl font-bold text-ink-900">${annual ? Math.round(plan.annual / 12) : plan.price}</span>
                  <span className="text-sm text-ink-400">/mo</span>
                  {annual && <div className="text-[12px] text-green-600 mt-1">${plan.annual}/year (billed annually)</div>}
                </>
              )}
            </div>
            <div className="text-sm font-semibold text-brand-600 mb-3">{plan.credits} credits/month</div>
            <ul className="flex-1 space-y-2 mb-5">
              {plan.features.map((f, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-ink-700">
                  <span className="text-green-600 shrink-0 mt-0.5">✓</span>
                  {f}
                </li>
              ))}
            </ul>
            <button
              onClick={() => {
                const priceId = annual ? plan.annualPriceId : plan.monthlyPriceId;
                if (priceId) handleCheckout(priceId);
              }}
              disabled={plan.id === "free" || loading !== null}
              className={`w-full py-2.5 rounded-lg text-sm font-semibold transition-colors ${
                plan.id === "free"
                  ? "bg-surface-100 text-ink-400 cursor-default"
                  : plan.popular
                  ? "bg-brand-600 text-white hover:bg-brand-700"
                  : "bg-ink-900 text-white hover:bg-ink-700"
              } ${loading ? "opacity-50" : ""}`}
            >
              {loading === (annual ? plan.annualPriceId : plan.monthlyPriceId) ? "Redirecting..." : plan.cta}
            </button>
          </div>
        ))}
      </div>

      {/* Credit packs */}
      <div>
        <h2 className="text-xl font-bold text-ink-900 text-center mb-2">Need More Credits?</h2>
        <p className="text-sm text-ink-400 text-center mb-4">Top up anytime — credits never expire</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {CREDIT_PACKS.map((pack) => (
            <div key={pack.name} className="bg-white rounded-xl border border-surface-200 p-5 text-center">
              <div className="text-2xl font-bold text-brand-600 mb-1">{pack.credits}</div>
              <div className="text-sm text-ink-400 mb-3">credits</div>
              <div className="text-lg font-bold text-ink-900 mb-4">${pack.price}</div>
              <button
                onClick={() => handleCheckout(pack.priceId)}
                disabled={loading !== null}
                className="w-full py-2 bg-surface-100 text-ink-700 text-sm font-semibold rounded-lg hover:bg-surface-200 transition-colors"
              >
                {loading === pack.priceId ? "Redirecting..." : "Buy Credits"}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Credit costs table */}
      <div className="bg-white rounded-xl border border-surface-200 p-6">
        <h3 className="text-base font-bold text-ink-900 mb-4">What Credits Buy</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {CREDIT_COSTS.map((item) => (
            <div key={item.action} className="bg-surface-50 rounded-lg px-3 py-2.5 flex items-center justify-between">
              <span className="text-sm text-ink-700">{item.action}</span>
              <span className="text-sm font-bold text-brand-600">{item.credits}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
