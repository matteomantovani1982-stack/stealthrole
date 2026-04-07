"use client";

import { FormEvent, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import Image from "next/image";

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
    <div
      className="min-h-screen flex flex-col"
      style={{
        background: "radial-gradient(ellipse at 60% 50%, #1B2350 0%, #141A3A 40%, #0B0F2A 100%)",
      }}
    >
      {/* Top-left logo */}
      <div className="p-6 flex items-center gap-2">
        <Image src="/images/sr-logo.png" alt="" width={28} height={28} className="rounded-md" />
        <span className="text-base font-bold text-white/90 tracking-tight">
          Stealth<span className="text-[#7F8CFF]">Role</span>
        </span>
      </div>

      {/* Centered content */}
      <div className="flex-1 flex items-center justify-center px-4 -mt-10">
        <div className="w-full max-w-[420px] flex flex-col items-center">
          {/* Hooded figure */}
          <Image
            src="/images/sr-logo.png"
            alt=""
            width={120}
            height={120}
            className="mb-6 drop-shadow-[0_0_40px_rgba(91,108,255,0.25)]"
            priority
          />

          {/* Title */}
          <h1 className="text-[28px] font-bold text-white mb-1.5 text-center">
            Welcome back
          </h1>
          <p className="text-[13px] text-[#8B92B0] mb-7 text-center leading-relaxed">
            Sign in to discover hidden opportunities before they are posted.
          </p>

          {/* Form */}
          <form onSubmit={handleContinue} className="w-full space-y-3">
            {isRegister && step === "password" && (
              <input
                type="text"
                placeholder="Full name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                style={{ height: 48, borderRadius: 10, background: "rgba(255,255,255,0.05)" }}
                className="w-full px-4 text-[14px] text-white placeholder-[#555C7A] border border-white/[0.08] focus:outline-none focus:border-[#5B6CFF]/50 transition-colors"
              />
            )}

            <input
              type="email"
              placeholder="Your email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{ height: 48, borderRadius: 10, background: "rgba(255,255,255,0.05)" }}
              className="w-full px-4 text-[14px] text-white placeholder-[#555C7A] border border-white/[0.08] focus:outline-none focus:border-[#5B6CFF]/50 transition-colors"
            />

            {step === "password" && (
              <input
                type="password"
                placeholder="Password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoFocus
                style={{ height: 48, borderRadius: 10, background: "rgba(255,255,255,0.05)" }}
                className="w-full px-4 text-[14px] text-white placeholder-[#555C7A] border border-white/[0.08] focus:outline-none focus:border-[#5B6CFF]/50 transition-colors"
              />
            )}

            {error && (
              <div className="text-[13px] text-red-400 bg-red-500/10 border border-red-500/15 px-4 py-2.5" style={{ borderRadius: 10 }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{ height: 48, borderRadius: 10, background: "linear-gradient(135deg, #5B6CFF 0%, #7F8CFF 100%)" }}
              className="w-full text-white text-[14px] font-semibold disabled:opacity-50 transition-opacity"
            >
              {loading ? "..." : "Continue"}
            </button>
          </form>

          {/* Divider */}
          <div className="w-full relative my-5">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-white/[0.06]" />
            </div>
            <div className="relative flex justify-center">
              <span className="px-3 text-[12px] text-[#555C7A]" style={{ backgroundColor: "#111735" }}>
                or continue with
              </span>
            </div>
          </div>

          {/* Social buttons */}
          <div className="w-full space-y-2.5">
            <button
              type="button"
              onClick={() => handleSocialLogin("google")}
              disabled={!!socialLoading}
              style={{ height: 44, borderRadius: 10, background: "rgba(255,255,255,0.04)" }}
              className="w-full flex items-center justify-center gap-2.5 border border-white/[0.08] text-[13px] font-medium text-white/75 hover:bg-white/[0.07] disabled:opacity-50 transition-colors"
            >
              <svg width="16" height="16" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
                <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
                <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z" fill="#34A853"/>
                <path d="M3.964 10.71A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.997 8.997 0 000 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
                <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 6.29C4.672 4.163 6.656 2.58 9 2.58z" fill="#EA4335"/>
              </svg>
              Continue with Google
            </button>

            <button
              type="button"
              onClick={() => handleSocialLogin("facebook")}
              disabled={!!socialLoading}
              style={{ height: 44, borderRadius: 10, background: "rgba(255,255,255,0.04)" }}
              className="w-full flex items-center justify-center gap-2.5 border border-white/[0.08] text-[13px] font-medium text-white/75 hover:bg-white/[0.07] disabled:opacity-50 transition-colors"
            >
              <svg width="16" height="16" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
                <circle cx="9" cy="9" r="9" fill="#1877F2"/>
                <path d="M12.5 9.75h-2v5.25H8v-5.25H6.25v-2.5H8V5.75c0-1.5.9-2.75 2.75-2.75h1.75v2.5h-1.25c-.5 0-.75.25-.75.75v1h2l-.25 2.5h-1.75z" fill="white"/>
              </svg>
              Continue with Facebook
            </button>

            <button
              type="button"
              onClick={() => handleSocialLogin("apple")}
              disabled={!!socialLoading}
              style={{ height: 44, borderRadius: 10, background: "rgba(255,255,255,0.04)" }}
              className="w-full flex items-center justify-center gap-2.5 border border-white/[0.08] text-[13px] font-medium text-white/75 hover:bg-white/[0.07] disabled:opacity-50 transition-colors"
            >
              <svg width="16" height="16" viewBox="0 0 18 18" fill="white" xmlns="http://www.w3.org/2000/svg">
                <path d="M15.1 6.05c-.09.07-1.68.97-1.68 2.96 0 2.31 2.03 3.13 2.09 3.15-.01.05-.32 1.12-1.07 2.21-.65.94-1.32 1.88-2.38 1.88s-1.31-.62-2.51-.62c-1.17 0-1.58.64-2.57.64s-1.62-.87-2.38-1.94C3.42 12.73 2.7 10.61 2.7 8.6c0-3.23 2.1-4.94 4.17-4.94 1.1 0 2.01.72 2.7.72.66 0 1.69-.76 2.94-.76.47 0 2.17.04 3.29 1.64l.3-.01zM11.85 2.3c.47-.56.8-1.34.8-2.12 0-.11-.01-.22-.03-.3-.76.03-1.67.51-2.22 1.14-.43.48-.83 1.27-.83 2.06 0 .12.02.24.03.28.05.01.14.02.22.02.69 0 1.54-.46 2.03-1.08z"/>
              </svg>
              Continue with Apple
            </button>
          </div>

          {/* Sign up link */}
          <div className="mt-6 text-center">
            <span className="text-[13px] text-[#555C7A]">
              {isRegister ? "Already have an account? " : "Don\u2019t have an account? "}
            </span>
            <button
              type="button"
              onClick={() => { setIsRegister(!isRegister); setError(""); setStep("email"); }}
              className="text-[13px] text-[#7F8CFF] hover:text-[#99A5FF] font-medium transition-colors"
            >
              {isRegister ? "Sign in" : "Sign up"}
            </button>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="pb-6 flex items-center justify-center gap-3 text-[11px] text-[#3D4260]">
        <a href="#" className="hover:text-[#555C7A] transition-colors">Terms</a>
        <span>|</span>
        <a href="#" className="hover:text-[#555C7A] transition-colors">Privacy</a>
        <span>|</span>
        <a href="#" className="hover:text-[#555C7A] transition-colors">Support</a>
      </div>
    </div>
  );
}
