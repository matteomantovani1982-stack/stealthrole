"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { clearAllUserData, setCurrentUserId, getMe } from "@/lib/api";

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-surface-50"><div className="w-6 h-6 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" /></div>}>
      <AuthCallbackInner />
    </Suspense>
  );
}

function AuthCallbackInner() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState("Processing...");

  useEffect(() => {
    const code = searchParams.get("code");
    const rawState = searchParams.get("state") || "";

    if (!code) {
      setStatus("No authorization code received. Please try again.");
      return;
    }

    // Determine if this is a Google login or email integration callback
    if (rawState === "google_login") {
      handleGoogleLogin(code);
    } else {
      handleEmailIntegration(code, rawState);
    }
  }, [searchParams]);

  async function handleGoogleLogin(code: string) {
    try {
      // SECURITY: clear ALL prior user data before storing new tokens
      clearAllUserData();
      const res = await fetch("/api/v1/auth/google", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });

      if (res.ok) {
        const data = await res.json();
        localStorage.setItem("sr_token", data.access_token);
        if (data.refresh_token) localStorage.setItem("sr_refresh", data.refresh_token);
        // Fetch the new user's identity and pin it
        try {
          const me = await getMe();
          if (me?.id) setCurrentUserId(me.id);
        } catch {}
        setStatus(data.is_new_user ? "Account created! Redirecting..." : "Signed in! Redirecting...");
        setTimeout(() => {
          window.location.href = data.is_new_user ? "/profile" : "/applications";
        }, 1000);
      } else {
        const body = await res.json().catch(() => ({}));
        setStatus(`Login failed: ${body.detail || "Unknown error"}`);
      }
    } catch (err: unknown) {
      setStatus(`Error: ${err instanceof Error ? err.message : "Unknown"}`);
    }
  }

  async function handleEmailIntegration(code: string, rawState: string) {
    const stateParts = rawState.split(":");
    const provider = stateParts.length >= 2 ? stateParts[stateParts.length - 1] : (window.location.href.includes("google") ? "gmail" : "outlook");

    const token = localStorage.getItem("sr_token");
    try {
      const res = await fetch("/api/v1/email-integration/callback", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ provider, code, state: rawState }),
      });

      if (res.ok) {
        const data = await res.json();
        setStatus(`Connected ${data.email_address}! Redirecting...`);
        setTimeout(() => {
          window.location.href = "/settings";
        }, 2000);
      } else {
        const body = await res.json().catch(() => ({}));
        setStatus(`Connection failed: ${body.detail || "Unknown error"}`);
      }
    } catch (err: unknown) {
      setStatus(`Error: ${err instanceof Error ? err.message : "Unknown"}`);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-50">
      <div className="bg-white rounded-xl border border-surface-200 p-8 text-center max-w-md">
        <div className="text-2xl mb-3">🔐</div>
        <div className="text-lg font-semibold text-ink-900 mb-2">Authentication</div>
        <div className="text-sm text-ink-500">{status}</div>
      </div>
    </div>
  );
}
