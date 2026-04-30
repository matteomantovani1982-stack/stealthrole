"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { connectEmail, listEmailAccounts, getCreditBalance, getCreditPricing, getActiveProfile, importLinkedIn, applyImportToProfile } from "@/lib/api";
import { getAuthHeaders } from "@/lib/utils";

interface EmailAccount {
  id: string;
  provider: string;
  email_address: string;
  sync_status: string;
  last_synced_at: string | null;
  total_scanned: number;
  total_signals: number;
  is_active: boolean;
}

interface LinkedInStats {
  total_connections: number;
  recruiters: number;
  unique_companies: number;
}

const NAV_ITEMS = [
  { id: "account", label: "Account" },
  { id: "credits", label: "Credits" },
  { id: "email", label: "Email" },
  { id: "linkedin", label: "LinkedIn" },
  { id: "whatsapp", label: "WhatsApp" },
  { id: "danger-zone", label: "Danger zone" },
];

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const [credits, setCredits] = useState<{ balance: number; lifetime_purchased: number; lifetime_spent: number } | null>(null);
  const [pricing, setPricing] = useState<{ action: string; credits: number; display: string }[]>([]);
  const [emailAccounts, setEmailAccounts] = useState<EmailAccount[]>([]);
  const [linkedinStats, setLinkedinStats] = useState<LinkedInStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [connectingEmail, setConnectingEmail] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [linkedinImporting, setLinkedinImporting] = useState(false);
  const [extensionSync, setExtensionSync] = useState<{ status: "idle" | "scanning" | "done" | "error"; count: number; error?: string }>({ status: "idle", count: 0 });
  const [extensionInstalled, setExtensionInstalled] = useState(false);
  const syncStartedAckRef = useRef(false);

  useEffect(() => {
    const headers = getAuthHeaders(false);
    Promise.allSettled([
      getCreditBalance().then(setCredits),
      getCreditPricing().then(setPricing),
      listEmailAccounts().then((d) => setEmailAccounts((d?.accounts || []) as EmailAccount[])),
      fetch("/api/v1/linkedin/stats", { headers }).then((r) => r.ok ? r.json() : null).then(setLinkedinStats),
    ]).finally(() => setLoading(false));
  }, []);

  // ── Chrome extension detection + live sync progress ───────────────────────
  useEffect(() => {
    // Extension injects <div id="sr-extension-marker" data-version="..."> on load
    const check = () => {
      const el = document.getElementById("sr-extension-marker");
      setExtensionInstalled(!!el);
    };
    check();
    const t = setTimeout(check, 800);

    const handler = (event: MessageEvent) => {
      if (event.source !== window || !event.data) return;
      const msg = event.data;
      if (msg.type === "SR_SYNC_PROGRESS" && msg.payload?.feature === "connections") {
        const p = msg.payload;
        setExtensionSync({ status: p.status, count: p.count || 0, error: p.error });
        // On done, refresh the imported count
        if (p.status === "done") {
          const headers = getAuthHeaders(false);
          fetch("/api/v1/linkedin/stats", { headers }).then((r) => r.ok ? r.json() : null).then(setLinkedinStats);
        }
      }
      if (msg.type === "SR_SYNC_STARTED") {
        syncStartedAckRef.current = true;
        if (!msg.ok) setExtensionSync({ status: "error", count: 0, error: msg.error || "Could not start sync" });
      }
    };
    window.addEventListener("message", handler);
    return () => { clearTimeout(t); window.removeEventListener("message", handler); };
  }, []);

  function startExtensionSync() {
    syncStartedAckRef.current = false;
    setExtensionSync({ status: "scanning", count: 0 });
    window.postMessage({ type: "SR_START_CONNECTIONS_SYNC" }, "*");
    // Guard: if extension bridge doesn't ack quickly, show actionable error.
    window.setTimeout(() => {
      setExtensionSync((prev) => {
        if (prev.status !== "scanning") return prev;
        if (syncStartedAckRef.current) return prev;
        return {
          status: "error",
          count: 0,
          error: "Extension bridge not responding. Reload extension and page, then try again.",
        };
      });
    }, 8000);
  }

  async function handleConnectEmail(provider: "gmail" | "outlook") {
    setConnectingEmail(provider);
    setMessage("");
    try {
      const data = await connectEmail(provider);
      // Redirect to OAuth URL
      window.location.href = data.auth_url;
      setMessage(`${provider === "gmail" ? "Google" : "Microsoft"} authorization opened in a new tab. Complete the login there, then refresh this page.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Connect failed";
      if (msg.includes("not configured")) {
        setMessage(`${provider === "gmail" ? "Gmail" : "Outlook"} integration not configured yet. The API key needs to be set up in production.`);
      } else {
        setMessage(msg);
      }
    } finally {
      setConnectingEmail(null);
    }
  }

  return (
    <div className="flex min-h-full">
      {/* Left navigation panel */}
      <nav className="w-[200px] shrink-0 border-r border-[rgba(255,255,255,0.06)] bg-[#070920] py-6 px-4 sticky top-0 h-screen">
        <ul className="space-y-1">
          {NAV_ITEMS.map((item) => (
            <li key={item.id}>
              <a
                href={`#${item.id}`}
                className="block px-3 py-2 rounded-lg text-sm text-[rgba(255,255,255,0.45)] hover:text-white hover:bg-[rgba(255,255,255,0.06)] transition-colors"
              >
                {item.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      {/* Main content */}
      <div className="flex-1 space-y-6 max-w-2xl py-6 px-8">
        <h1 className="text-[20px] font-medium text-white">Settings</h1>

        {message && (
          <div className="px-4 py-3 rounded-lg bg-[rgba(77,142,245,0.08)] text-[#4d8ef5] text-sm">{message}</div>
        )}

        {/* Account */}
        <section id="account" className="bg-[rgba(255,255,255,0.06)] rounded-xl border border-[rgba(255,255,255,0.1)] p-6 scroll-mt-6">
          <h2 className="text-base font-semibold text-white mb-4">Account</h2>
          <div className="grid grid-cols-2 gap-4 text-sm mb-4">
            <div>
              <div className="text-[11px] text-[rgba(255,255,255,0.4)] uppercase">Name</div>
              <div className="font-medium text-white">{user?.full_name || "—"}</div>
            </div>
            <div>
              <div className="text-[11px] text-[rgba(255,255,255,0.4)] uppercase">Email</div>
              <div className="font-medium text-white">{user?.email || "—"}</div>
            </div>
          </div>
          <button onClick={logout} className="px-4 py-2 text-sm text-red-400 border border-red-400/20 rounded-lg hover:bg-red-400/10 transition-colors">
            Sign out
          </button>
        </section>

        {/* Credits */}
        <section id="credits" className="bg-[rgba(255,255,255,0.06)] rounded-xl border border-[rgba(255,255,255,0.1)] p-6 scroll-mt-6">
          <h2 className="text-base font-semibold text-white mb-4">Credits</h2>
          {credits ? (
            <>
              <div className="grid grid-cols-3 gap-4 text-sm mb-5">
                <div>
                  <div className="text-[11px] text-[rgba(255,255,255,0.4)] uppercase">Balance</div>
                  <div className="text-2xl font-bold text-[#4d8ef5]">{credits.balance}</div>
                </div>
                <div>
                  <div className="text-[11px] text-[rgba(255,255,255,0.4)] uppercase">Purchased</div>
                  <div className="font-medium text-white">{credits.lifetime_purchased}</div>
                </div>
                <div>
                  <div className="text-[11px] text-[rgba(255,255,255,0.4)] uppercase">Spent</div>
                  <div className="font-medium text-white">{credits.lifetime_spent}</div>
                </div>
              </div>
              {pricing.length > 0 && (
                <div>
                  <div className="text-[12px] font-medium text-[rgba(255,255,255,0.45)] uppercase mb-2">Credit Costs</div>
                  <div className="grid grid-cols-2 gap-2">
                    {pricing.map((p) => (
                      <div key={p.action} className="flex items-center justify-between bg-[rgba(255,255,255,0.04)] rounded-lg px-3 py-2 text-sm">
                        <span className="text-[rgba(255,255,255,0.7)]">{p.display}</span>
                        <span className="font-bold text-[#4d8ef5]">{p.credits}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="text-sm text-[rgba(255,255,255,0.4)]">{loading ? "Loading..." : "—"}</div>
          )}
        </section>

        {/* Email Integration */}
        <section id="email" className="bg-[rgba(255,255,255,0.06)] rounded-xl border border-[rgba(255,255,255,0.1)] p-6 scroll-mt-6">
          <h2 className="text-base font-semibold text-white mb-4">Email Integration</h2>
          <p className="text-sm text-[rgba(255,255,255,0.4)] mb-4">Connect your email to auto-detect applications, interviews, and follow-ups.</p>

          {emailAccounts.length > 0 && (
            <div className="space-y-2 mb-4">
              {emailAccounts.map((acc) => (
                <div key={acc.id} className="flex items-center justify-between bg-[rgba(255,255,255,0.04)] rounded-lg px-4 py-3">
                  <div className="text-sm">
                    <span className="font-medium text-white">{acc.email_address}</span>
                    <span className="text-[rgba(255,255,255,0.4)] ml-2 text-[12px]">({acc.provider})</span>
                    {acc.last_synced_at && <span className="text-[rgba(255,255,255,0.4)] ml-2 text-[11px]">Last sync: {new Date(acc.last_synced_at).toLocaleDateString()}</span>}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-[11px] px-2 py-0.5 rounded-full ${acc.is_active ? "bg-green-500/10 text-green-400" : "bg-[rgba(255,255,255,0.04)] text-[rgba(255,255,255,0.4)]"}`}>
                      {acc.is_active ? `${acc.total_signals} signals · ${acc.total_scanned} scanned` : "Disconnected"}
                    </span>
                    {acc.is_active && (
                      <button id={`sync-btn-${acc.id}`} onClick={async () => {
                        const btn = document.getElementById(`sync-btn-${acc.id}`) as HTMLButtonElement;
                        if (btn) { btn.textContent = "Syncing your emails..."; btn.disabled = true; btn.style.opacity = "0.5"; btn.style.cursor = "not-allowed"; }
                        try {
                          await fetch(`/api/v1/email-integration/accounts/${acc.id}/sync`, {
                            method: "POST",
                            headers: getAuthHeaders(false),
                          });
                          setMessage("Email sync started! Results will appear shortly.");
                          if (btn) { btn.textContent = "Sync Now"; btn.disabled = false; btn.style.opacity = "1"; btn.style.cursor = "pointer"; }
                        } catch {
                          setMessage("Sync failed");
                          if (btn) { btn.textContent = "Sync Now"; btn.disabled = false; btn.style.opacity = "1"; btn.style.cursor = "pointer"; }
                        }
                      }} className="text-[11px] px-2 py-0.5 rounded bg-[rgba(77,142,245,0.08)] text-[#4d8ef5] hover:bg-[rgba(77,142,245,0.15)] font-medium disabled:opacity-50 disabled:cursor-not-allowed">Sync Now</button>
                    )}
                    <button onClick={async () => {
                      try {
                        await fetch(`/api/v1/email-integration/accounts/${acc.id}`, {
                          method: "DELETE",
                          headers: getAuthHeaders(false),
                        });
                        setEmailAccounts((prev) => prev.filter((a) => a.id !== acc.id));
                        setMessage("Account removed.");
                      } catch { setMessage("Remove failed"); }
                    }} className="text-[11px] px-2 py-0.5 rounded bg-red-400/10 text-red-400 hover:bg-red-400/20 font-medium">Remove</button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={() => handleConnectEmail("gmail")}
              disabled={connectingEmail === "gmail"}
              className="flex items-center gap-2 px-4 py-2.5 border border-[rgba(255,255,255,0.1)] text-[rgba(255,255,255,0.7)] text-sm font-semibold rounded-lg hover:bg-[rgba(255,255,255,0.04)] disabled:opacity-50 transition-colors"
            >
              <svg width="16" height="16" viewBox="0 0 16 16"><path d="M14 3H2l6 4.5L14 3z" fill="#EA4335"/><path d="M14 3v10H2V3l6 4.5L14 3z" fill="none" stroke="#4285F4" strokeWidth="1.2"/></svg>
              {connectingEmail === "gmail" ? "Connecting..." : "Connect Gmail"}
            </button>
            <button
              onClick={() => handleConnectEmail("outlook")}
              disabled={connectingEmail === "outlook"}
              className="flex items-center gap-2 px-4 py-2.5 border border-[rgba(255,255,255,0.1)] text-[rgba(255,255,255,0.7)] text-sm font-semibold rounded-lg hover:bg-[rgba(255,255,255,0.04)] disabled:opacity-50 transition-colors"
            >
              <svg width="16" height="16" viewBox="0 0 16 16"><rect x="1" y="3" width="14" height="10" rx="1" fill="none" stroke="#0078D4" strokeWidth="1.2"/><path d="M1 3l7 5 7-5" fill="none" stroke="#0078D4" strokeWidth="1.2"/></svg>
              {connectingEmail === "outlook" ? "Connecting..." : "Connect Outlook"}
            </button>
          </div>
        </section>

        {/* LinkedIn */}
        <section id="linkedin" className="bg-[rgba(255,255,255,0.06)] rounded-xl border border-[rgba(255,255,255,0.1)] p-6 scroll-mt-6">
          <h2 className="text-base font-semibold text-white mb-4">LinkedIn</h2>

          {linkedinStats && linkedinStats.total_connections > 0 && (
            <div className="bg-[rgba(255,255,255,0.04)] rounded-lg px-4 py-3 text-sm mb-4">
              <span className="font-bold text-[#4d8ef5]">{linkedinStats.total_connections}</span> <span className="text-white">connections imported</span>
              <span className="text-[rgba(255,255,255,0.4)] ml-2">({linkedinStats.recruiters} recruiters, {linkedinStats.unique_companies} companies)</span>
            </div>
          )}

          {/* Sync via Chrome extension */}
          <div className="mb-4">
            <label className="text-sm font-medium text-[rgba(255,255,255,0.7)] block mb-2">Sync with Chrome extension</label>
            <p className="text-[12px] text-[rgba(255,255,255,0.4)] mb-2">
              The fastest way — opens LinkedIn, scrolls automatically, imports everything in batches. Runs in the background.
            </p>
            {!extensionInstalled && (
              <div className="text-[12px] text-amber-400 mb-2">
                Chrome extension not detected. <a href="https://stealthrole.com/extension" className="underline" target="_blank" rel="noreferrer">Install it</a>, reload this page, and try again.
              </div>
            )}
            <button
              onClick={startExtensionSync}
              disabled={!extensionInstalled || extensionSync.status === "scanning"}
              className="px-4 py-2.5 bg-[#7F8CFF] text-white text-sm font-semibold rounded-lg hover:bg-[#6B7CFF] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {extensionSync.status === "scanning" ? `Scanning… ${extensionSync.count}` : "🔄 Sync now via extension"}
            </button>
            {extensionSync.status === "scanning" && (
              <div className="mt-3">
                <div className="h-1.5 bg-[rgba(255,255,255,0.08)] rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-[#5B6CFF] to-[#7F8CFF] animate-pulse" style={{ width: "40%" }} />
                </div>
                <div className="text-[11px] text-[rgba(255,255,255,0.5)] mt-1">
                  {extensionSync.count} connections found so far — keep this tab open
                </div>
              </div>
            )}
            {extensionSync.status === "done" && (
              <div className="text-[12px] text-green-400 mt-2">✓ Imported {extensionSync.count} connections</div>
            )}
            {extensionSync.status === "error" && (
              <div className="text-[12px] text-red-400 mt-2">⚠ {extensionSync.error || "Sync failed"}</div>
            )}
          </div>

          {/* Direct URL import */}
          <div className="mb-4">
            <label className="text-sm font-medium text-[rgba(255,255,255,0.7)] block mb-2">Import your LinkedIn profile</label>
            <p className="text-[12px] text-[rgba(255,255,255,0.4)] mb-2">Paste your LinkedIn URL to import experiences, skills, and connections.</p>
            <div className="flex gap-2">
              <input
                type="url"
                value={linkedinUrl}
                onChange={(e) => setLinkedinUrl(e.target.value)}
                placeholder="https://www.linkedin.com/in/your-profile"
                className="flex-1 px-3 py-2.5 rounded-lg border border-[rgba(255,255,255,0.1)] bg-[rgba(255,255,255,0.04)] text-white text-sm placeholder:text-[rgba(255,255,255,0.3)] focus:outline-none focus:ring-2 focus:ring-[#4d8ef5]/20"
              />
              <button
                onClick={async () => {
                  if (!linkedinUrl.trim()) return;
                  setLinkedinImporting(true);
                  setMessage("");
                  try {
                    const profile = await getActiveProfile();
                    if (!profile) { setMessage("Create a profile first (go to Profile page)"); return; }
                    const imported = await importLinkedIn(profile.id, linkedinUrl.trim());
                    if (imported) {
                      await applyImportToProfile(profile.id, imported, true);
                    }
                    setMessage("LinkedIn profile imported and applied!");
                    setLinkedinUrl("");
                  } catch (err: unknown) {
                    setMessage(err instanceof Error ? err.message : "Import failed");
                  } finally { setLinkedinImporting(false); }
                }}
                disabled={linkedinImporting || !linkedinUrl.trim()}
                className="px-4 py-2.5 bg-[#4d8ef5] text-white text-sm font-semibold rounded-lg hover:bg-[#3b7de0] disabled:opacity-50 transition-colors shrink-0"
              >
                {linkedinImporting ? "Importing..." : "Import"}
              </button>
            </div>
          </div>

          {/* CSV Import */}
          <div className="border-t border-[rgba(255,255,255,0.1)] pt-4 mt-4">
            <label className="text-sm font-medium text-[rgba(255,255,255,0.7)] block mb-2">Import connections from CSV</label>
            <p className="text-[12px] text-[rgba(255,255,255,0.4)] mb-2">
              Go to LinkedIn &rarr; Settings &rarr; Data Privacy &rarr; Get a copy of your data &rarr; download Connections.csv &rarr; upload it here.
            </p>
            <label className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#4d8ef5] text-white text-sm font-semibold rounded-lg hover:bg-[#3b7de0] cursor-pointer transition-colors">
              Upload Connections.csv
              <input type="file" accept=".csv,.txt" onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) { setMessage("No file selected"); return; }
                setMessage(`Importing ${file.name}...`);
                const form = new FormData();
                form.append("file", file);
                try {
                  const res = await fetch("/api/v1/linkedin/import-csv", {
                    method: "POST",
                    headers: getAuthHeaders(false),
                    body: form,
                  });
                  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Import failed");
                  const data = await res.json();
                  setMessage(`Imported ${data.created} new connections (${data.recruiters_detected} recruiters detected, ${data.applications_matched} matched to applications)`);
                  // Refresh stats
                  const headers2 = getAuthHeaders(false);
                  fetch("/api/v1/linkedin/stats", { headers: headers2 }).then((r) => r.ok ? r.json() : null).then(setLinkedinStats);
                } catch (err) {
                  setMessage(err instanceof Error ? err.message : "CSV import failed");
                }
              }} className="hidden" />
            </label>
          </div>

          {/* Message Analysis */}
          <div className="border-t border-[rgba(255,255,255,0.1)] pt-4 mt-4">
            <label className="text-sm font-medium text-[rgba(255,255,255,0.7)] block mb-2">Analyze conversation + draft reply</label>
            <p className="text-[12px] text-[rgba(255,255,255,0.4)] mb-2">Paste a LinkedIn conversation with a recruiter or contact. We&apos;ll analyze it and draft a reply.</p>
            <textarea
              id="convo-text"
              placeholder="Paste the conversation here..."
              rows={4}
              className="w-full px-3 py-2.5 rounded-lg border border-[rgba(255,255,255,0.1)] bg-[rgba(255,255,255,0.04)] text-white text-sm placeholder:text-[rgba(255,255,255,0.3)] resize-none mb-2 focus:outline-none focus:ring-2 focus:ring-[#4d8ef5]/20"
            />
            <button onClick={async () => {
              const text = (document.getElementById("convo-text") as HTMLTextAreaElement)?.value;
              if (!text?.trim()) return;
              setMessage("Analyzing conversation...");
              try {
                const res = await fetch("/api/v1/linkedin/analyze-conversation", {
                  method: "POST",
                  headers: getAuthHeaders(),
                  body: JSON.stringify({ messages: text, tone: "professional" }),
                });
                if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Analysis failed");
                const data = await res.json();
                setMessage("");
                // Show result in a simple way
                const resultDiv = document.getElementById("convo-result");
                if (resultDiv) {
                  resultDiv.innerHTML = `
                    <div class="space-y-3">
                      <div><span class="text-[11px] font-medium text-[rgba(255,255,255,0.4)] uppercase">Intent</span><div class="text-sm font-medium text-white">${data.intent || "unknown"}</div></div>
                      <div><span class="text-[11px] font-medium text-[rgba(255,255,255,0.4)] uppercase">Analysis</span><div class="text-sm text-[rgba(255,255,255,0.7)]">${data.analysis || ""}</div></div>
                      <div><span class="text-[11px] font-medium text-[rgba(255,255,255,0.4)] uppercase">Suggested Reply</span><div class="text-sm text-white bg-[rgba(77,142,245,0.08)] rounded-lg p-3 whitespace-pre-wrap">${data.suggested_reply || "No reply generated"}</div></div>
                      ${data.alternative_reply ? `<div><span class="text-[11px] font-medium text-[rgba(255,255,255,0.4)] uppercase">Alternative</span><div class="text-sm text-[rgba(255,255,255,0.7)] bg-[rgba(255,255,255,0.04)] rounded-lg p-3 whitespace-pre-wrap">${data.alternative_reply}</div></div>` : ""}
                      ${data.next_steps ? `<div><span class="text-[11px] font-medium text-[rgba(255,255,255,0.4)] uppercase">Next Steps</span><ul class="text-sm text-[rgba(255,255,255,0.7)] list-disc list-inside">${data.next_steps.map((s: string) => `<li>${s}</li>`).join("")}</ul></div>` : ""}
                    </div>
                  `;
                }
              } catch (err) {
                setMessage(err instanceof Error ? err.message : "Analysis failed");
              }
            }} className="px-4 py-2.5 bg-[#4d8ef5] text-white text-sm font-semibold rounded-lg hover:bg-[#3b7de0] transition-colors">
              Analyze & Draft Reply
            </button>
            <div id="convo-result" className="mt-3" />
          </div>
        </section>

        {/* WhatsApp Alerts */}
        <section id="whatsapp" className="bg-[rgba(255,255,255,0.06)] rounded-xl border border-[rgba(255,255,255,0.1)] p-6 scroll-mt-6">
          <h2 className="text-base font-semibold text-white mb-4">WhatsApp Alerts</h2>
          <p className="text-sm text-[rgba(255,255,255,0.4)] mb-4">Get daily alerts for new opportunities, follow-up reminders, and pack completions via WhatsApp.</p>

          {/* Status badge */}
          {(user as any)?.whatsapp_verified ? (
            <div className="flex items-center gap-2 mb-4 px-3 py-2 rounded-lg bg-green-500/10 border border-green-500/20">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <span className="text-sm text-green-400 font-medium">WhatsApp verified: {(user as any)?.whatsapp_number}</span>
              <span className="text-xs text-[rgba(255,255,255,0.3)] ml-auto">Mode: {(user as any)?.whatsapp_alert_mode || "CASUAL"}</span>
            </div>
          ) : (user as any)?.whatsapp_number ? (
            <div className="flex items-center gap-2 mb-4 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
              <span className="w-2 h-2 rounded-full bg-amber-500" />
              <span className="text-sm text-amber-400 font-medium">Pending verification: {(user as any)?.whatsapp_number}</span>
            </div>
          ) : null}

          {/* Sandbox instructions */}
          <div className="bg-[rgba(77,142,245,0.06)] border border-[rgba(77,142,245,0.15)] rounded-lg p-4 mb-4">
            <div className="text-xs font-semibold text-[#93c5fd] uppercase mb-2">Required first step</div>
            <div className="text-sm text-[rgba(255,255,255,0.6)] leading-relaxed">
              Before you can receive messages, you must opt in to the WhatsApp sandbox:<br />
              1. Open WhatsApp on your phone<br />
              2. Send the message <span className="font-mono bg-[rgba(255,255,255,0.08)] px-1.5 py-0.5 rounded text-white">join center-affect</span> to <span className="font-mono bg-[rgba(255,255,255,0.08)] px-1.5 py-0.5 rounded text-white">+1 415 523 8886</span><br />
              3. Wait for the confirmation reply, then enter your number below
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <label className="text-[12px] font-medium text-[rgba(255,255,255,0.45)] uppercase block mb-1">WhatsApp Number</label>
              <div className="flex gap-2">
                <input
                  id="wa-number"
                  type="tel"
                  defaultValue={(user as any)?.whatsapp_number || ""}
                  placeholder="+971501234567"
                  className="flex-1 px-3 py-2.5 rounded-lg border border-[rgba(255,255,255,0.1)] bg-[rgba(255,255,255,0.04)] text-white text-sm placeholder:text-[rgba(255,255,255,0.3)] focus:outline-none focus:ring-2 focus:ring-[#4d8ef5]/20"
                />
                <button onClick={async () => {
                  const number = (document.getElementById("wa-number") as HTMLInputElement)?.value;
                  if (!number?.trim()) return;
                  setMessage("Sending verification code to WhatsApp...");
                  try {
                    const res = await fetch("/api/v1/whatsapp/verify", {
                      method: "POST",
                      headers: getAuthHeaders(),
                      body: JSON.stringify({ whatsapp_number: number.replace(/\s/g, "").trim() }),
                    });
                    if (res.ok) {
                      setMessage("Verification code sent! Check your WhatsApp and enter the 6-digit code below.");
                    } else {
                      const body = await res.json().catch(() => ({}));
                      if (res.status === 503) {
                        setMessage("WhatsApp service not configured. Check Twilio credentials.");
                      } else if (res.status === 502) {
                        setMessage("Could not send message. Did you send 'join center-affect' to +14155238886 first?");
                      } else {
                        setMessage(body.detail || "Failed — use format +971501234567 (no spaces)");
                      }
                    }
                  } catch (err) {
                    setMessage(err instanceof Error ? err.message : "Failed");
                  }
                }} className="px-4 py-2.5 bg-green-600 text-white text-sm font-semibold rounded-lg hover:bg-green-700 transition-colors shrink-0">
                  Send Code
                </button>
              </div>
              <div className="text-xs text-[rgba(255,255,255,0.25)] mt-1">Format: +971501234567 (country code, no spaces)</div>
              {/* Verification code input */}
              <div className="flex gap-2 mt-2">
                <input id="wa-code" type="text" maxLength={6} placeholder="6-digit code" className="flex-1 px-3 py-2.5 rounded-lg border border-[rgba(255,255,255,0.1)] bg-[rgba(255,255,255,0.04)] text-white text-sm placeholder:text-[rgba(255,255,255,0.3)] focus:outline-none focus:ring-2 focus:ring-[#4d8ef5]/20 font-mono tracking-widest" />
                <button onClick={async () => {
                  const code = (document.getElementById("wa-code") as HTMLInputElement)?.value;
                  const number = (document.getElementById("wa-number") as HTMLInputElement)?.value;
                  if (!code?.trim() || !number?.trim()) { setMessage("Enter both number and code"); return; }
                  setMessage("Verifying...");
                  try {
                    const res = await fetch("/api/v1/whatsapp/confirm", {
                      method: "POST",
                      headers: getAuthHeaders(),
                      body: JSON.stringify({ whatsapp_number: number.replace(/\s/g, "").trim(), code: code.trim() }),
                    });
                    if (res.ok) {
                      setMessage("WhatsApp verified! You will now receive opportunity alerts.");
                      // Reload page to update status badge
                      setTimeout(() => window.location.reload(), 1500);
                    } else {
                      const body = await res.json().catch(() => ({}));
                      setMessage(body.detail || "Invalid code — check and try again");
                    }
                  } catch (err) { setMessage("Verification failed"); }
                }} className="px-4 py-2.5 bg-green-600 text-white text-sm font-semibold rounded-lg hover:bg-green-700 transition-colors shrink-0">
                  Verify
                </button>
              </div>
            </div>

            {/* Send test message button — only if verified */}
            {(user as any)?.whatsapp_verified && (
              <button onClick={async () => {
                setMessage("Sending test message...");
                try {
                  const res = await fetch("/api/v1/whatsapp/send-test", {
                    method: "POST",
                    headers: getAuthHeaders(),
                  });
                  if (res.ok) {
                    setMessage("Test message sent! Check your WhatsApp.");
                  } else {
                    const body = await res.json().catch(() => ({}));
                    setMessage(body.detail || "Test failed");
                  }
                } catch { setMessage("Test failed"); }
              }} className="w-full py-2.5 bg-[rgba(255,255,255,0.04)] text-[rgba(255,255,255,0.6)] text-sm font-medium rounded-lg border border-[rgba(255,255,255,0.1)] hover:bg-[rgba(255,255,255,0.08)] transition-colors">
                Send Test Message
              </button>
            )}

            <div>
              <label className="text-[12px] font-medium text-[rgba(255,255,255,0.45)] uppercase block mb-2">Alert Types</label>
              <div className="space-y-2">
                {[
                  { id: "new_opportunities", label: "New hidden market opportunities", desc: "Daily digest of jobs found before they are posted" },
                  { id: "follow_up_reminders", label: "Follow-up reminders", desc: "Nudge when it is time to follow up on an application" },
                  { id: "pack_ready", label: "Pack completion", desc: "Notify when an Intelligence Pack is ready" },
                  { id: "interview_prep", label: "Interview reminders", desc: "Prep reminders before scheduled interviews" },
                ].map((alert) => (
                  <label key={alert.id} className="flex items-start gap-3 bg-[rgba(255,255,255,0.04)] rounded-lg p-3 cursor-pointer hover:bg-[rgba(255,255,255,0.06)] transition-colors">
                    <input type="checkbox" defaultChecked className="mt-0.5 rounded border-[rgba(255,255,255,0.3)] text-[#4d8ef5] focus:ring-[#4d8ef5]" />
                    <div>
                      <div className="text-sm font-medium text-white">{alert.label}</div>
                      <div className="text-[12px] text-[rgba(255,255,255,0.4)]">{alert.desc}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Danger zone */}
        <section id="danger-zone" className="bg-[rgba(255,255,255,0.06)] rounded-xl border border-red-400/20 p-6 scroll-mt-6">
          <h2 className="text-base font-semibold text-red-400 mb-4">Danger zone</h2>
          <p className="text-sm text-[rgba(255,255,255,0.4)] mb-4">Permanently delete your account and all associated data. This action cannot be undone.</p>
          <button onClick={logout} className="px-4 py-2 text-sm text-red-400 border border-red-400/20 rounded-lg hover:bg-red-400/10 transition-colors">
            Delete Account
          </button>
        </section>
      </div>
    </div>
  );
}
