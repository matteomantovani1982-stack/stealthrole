// @ts-nocheck
"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { getAuthHeaders } from "@/lib/utils";
import {
  getActiveProfile,
  createProfile,
  listCVs,
  importLinkedIn,
  uploadAndPopulateProfile,
  updateProfilePreferences,
  updateProfile,
  addExperience,
  updateExperience,
  deleteExperience,
  type CandidateProfile,
  type ExperienceEntry,
} from "@/lib/api";
import Modal from "@/components/modal";
import EmailIntelligenceTab from "@/components/email-intelligence-tab";
import LinkedInIntelligenceTab from "@/components/linkedin-intelligence-tab";

const REGIONS = ["UAE", "KSA", "Qatar", "Bahrain", "EU", "UK", "US", "APAC", "MENA", "Remote", "Global"];
const SECTORS = ["Tech", "Fintech", "SaaS", "Healthcare", "E-commerce", "Consulting", "Energy", "Logistics", "Education", "Media", "Real Estate", "Government"];
const SENIORITY = ["Individual Contributor", "Manager", "Senior Manager", "Director", "VP", "C-Level"];
const ROLE_SUGGESTIONS = [
  "CEO", "COO", "CFO", "CTO", "CMO", "CPO",
  "VP Operations", "VP Engineering", "VP Sales", "VP Product",
  "Director of Strategy", "Director of Engineering", "Director of Product",
  "Head of Operations", "Head of Growth", "Head of People", "Head of Data",
  "General Manager", "Country Manager", "Product Manager", "Engineering Manager",
  "Principal Engineer", "Staff Engineer", "Solutions Architect",
  "Management Consultant", "Strategy Consultant",
];

function parseGlobalContext(raw: string | null): Record<string, unknown> {
  if (!raw) return {};
  try { return JSON.parse(raw); } catch { return {}; }
}

const EMPTY_EXP = {
  role_title: "",
  company_name: "",
  start_date: "",
  end_date: "",
  location: "",
  context: "",
  contribution: "",
  outcomes: "",
  methods: "",
};

export default function ProfilePage() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [cvs, setCvs] = useState<{ id: string; original_filename: string; status: string; quality_score: number | null }[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<"profile" | "email" | "linkedin">("profile");
  const [showLinkedIn, setShowLinkedIn] = useState(false);
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [linkedinLoading, setLinkedinLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [expandedExps, setExpandedExps] = useState<Set<string>>(new Set());
  const [selectedRegions, setSelectedRegions] = useState<string[]>([]);
  const [selectedSectors, setSelectedSectors] = useState<string[]>([]);
  const [selectedSeniority, setSelectedSeniority] = useState("");
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [customRole, setCustomRole] = useState("");
  const [salaryMin, setSalaryMin] = useState("");
  const [salaryMax, setSalaryMax] = useState("");

  // Edit mode states
  const [editingHeadline, setEditingHeadline] = useState(false);
  const [editingHeadlineVal, setEditingHeadlineVal] = useState("");
  const [editingSummary, setEditingSummary] = useState(false);
  const [editingSummaryVal, setEditingSummaryVal] = useState("");
  const [editingPersonal, setEditingPersonal] = useState(false);
  const [personalDraft, setPersonalDraft] = useState({ full_name: "", email: "", phone: "", location: "", nationality: "", linkedin_url: "" });
  const [editingSkills, setEditingSkills] = useState(false);
  const [skillsDraft, setSkillsDraft] = useState<string[]>([]);
  const [newSkill, setNewSkill] = useState("");
  const [editingLanguages, setEditingLanguages] = useState(false);
  const [languagesDraft, setLanguagesDraft] = useState<string[]>([]);
  const [newLanguage, setNewLanguage] = useState("");
  const [editingEducation, setEditingEducation] = useState(false);
  const [educationDraft, setEducationDraft] = useState<Record<string, string>[]>([]);
  const [editingExpId, setEditingExpId] = useState<string | null>(null);
  const [expDraft, setExpDraft] = useState({ ...EMPTY_EXP });
  const [addingExp, setAddingExp] = useState(false);
  const [newExpDraft, setNewExpDraft] = useState({ ...EMPTY_EXP });
  const [sectionSaving, setSectionSaving] = useState("");

  // For creating a profile when none exists
  const [createName, setCreateName] = useState("");
  const [createHeadline, setCreateHeadline] = useState("");

  const refresh = useCallback(() => {
    Promise.allSettled([
      getActiveProfile().then((p) => {
        setProfile(p);
        if (p?.preferences) {
          const prefs = p.preferences as Record<string, unknown>;
          setSelectedRegions((prefs.regions as string[]) || []);
          setSelectedSectors((prefs.sectors as string[]) || []);
          const seniorityVal = prefs.seniority;
          setSelectedSeniority(Array.isArray(seniorityVal) ? (seniorityVal[0] as string || "") : (seniorityVal as string || ""));
          setSelectedRoles((prefs.roles as string[]) || []);
          setSalaryMin(String(prefs.salaryMin || prefs.salary_min || ""));
          setSalaryMax(String(prefs.salary_max || ""));
        }
      }),
      listCVs().then(setCvs).catch(() => setCvs([])),
    ]).finally(() => setLoading(false));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Auto-clear messages after 4 seconds
  useEffect(() => {
    if (message && !message.includes("Uploading")) {
      const t = setTimeout(() => setMessage(""), 4000);
      return () => clearTimeout(t);
    }
  }, [message]);

  // Auto-save preferences on change (debounced 800ms)
  useEffect(() => {
    if (!profile) return;
    // Skip on initial mount before user interaction
    if (selectedRegions.length === 0 && selectedSectors.length === 0 && selectedRoles.length === 0 && !selectedSeniority && !salaryMin && !salaryMax) return;
    const timer = setTimeout(() => {
      handleSavePreferences().catch(() => {});
    }, 800);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRegions, selectedSectors, selectedRoles, selectedSeniority, salaryMin, salaryMax]);

  const ctx = parseGlobalContext(profile?.global_context ?? null);
  const skills = (ctx.skills as string[]) || [];
  const languages = (ctx.languages as string[]) || [];
  const education = (ctx.education as Record<string, string>[]) || [];
  const completeCount = profile?.experiences?.filter((e) => e.is_complete).length ?? 0;

  // Helper: update global_context fields
  async function saveGlobalContextFields(updates: Record<string, unknown>) {
    if (!profile) return;
    const currentCtx = parseGlobalContext(profile.global_context ?? null);
    const newCtx = { ...currentCtx, ...updates };
    const newGc = JSON.stringify(newCtx);
    const updated = await updateProfile(profile.id, { global_context: newGc });
    setProfile(updated);
  }

  // Helper: update profile-level fields
  async function saveProfileFields(updates: Record<string, unknown>) {
    if (!profile) return;
    const updated = await updateProfile(profile.id, updates);
    setProfile(updated);
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setMessage("Uploading and extracting your profile... this takes 30-60 seconds");
    try {
      const result = await uploadAndPopulateProfile(file);
      setMessage(`Profile populated! ${(result.extracted as Record<string,unknown>)?.experiences_count || 0} experiences extracted.`);
      setLoading(true);
      await new Promise((r) => setTimeout(r, 1000));
      const p = await getActiveProfile();
      setProfile(p);
      if (p?.preferences) {
        const prefs = p.preferences as Record<string, unknown>;
        setSelectedRegions((prefs.regions as string[]) || []);
        setSelectedSectors((prefs.sectors as string[]) || []);
        setSelectedSeniority((prefs.seniority as string) || "");
        setSelectedRoles((prefs.roles as string[]) || []);
      }
      const cvList = await listCVs().catch(() => []);
      setCvs(cvList || []);
      setLoading(false);
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : "Upload failed");
    } finally { setUploading(false); }
  }

  async function handleCreateProfile() {
    try {
      const gc: Record<string, unknown> = {};
      if (createName.trim()) gc.full_name = createName.trim();
      const body: Record<string, unknown> = { headline: createHeadline.trim() || user?.full_name || "" };
      if (Object.keys(gc).length > 0) body.global_context = JSON.stringify(gc);
      const p = await createProfile(body);
      setProfile(p);
      setMessage("Profile created! Upload a CV or fill in your details manually.");
      setCreateName("");
      setCreateHeadline("");
    } catch (err: unknown) { setMessage(err instanceof Error ? err.message : "Failed"); }
  }

  async function handleLinkedInImport() {
    if (!profile || !linkedinUrl.trim()) return;
    setLinkedinLoading(true);
    setMessage("");
    try {
      await importLinkedIn(profile.id, linkedinUrl.trim());
      setMessage("LinkedIn imported!");
      setShowLinkedIn(false);
      setLinkedinUrl("");
      setTimeout(refresh, 2000);
    } catch (err: unknown) { setMessage(err instanceof Error ? err.message : "Import failed"); }
    finally { setLinkedinLoading(false); }
  }

  async function handleSavePreferences() {
    if (!profile) return;
    setSaving(true);
    setMessage("");
    try {
      await updateProfilePreferences(profile.id, {
        regions: selectedRegions,
        sectors: selectedSectors,
        roles: selectedRoles,
        seniority: selectedSeniority ? [selectedSeniority] : [],
        salaryMin: salaryMin || undefined,
        salary_max: salaryMax || undefined,
      } as any);
      setMessage("Preferences saved!");
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : "Save failed");
    } finally { setSaving(false); }
  }

  // --- Section save handlers ---

  async function handleSaveHeadline() {
    setSectionSaving("headline");
    try {
      await saveProfileFields({ headline: editingHeadlineVal });
      setEditingHeadline(false);
      setMessage("Headline saved!");
    } catch (err: unknown) { setMessage(err instanceof Error ? err.message : "Save failed"); }
    finally { setSectionSaving(""); }
  }

  async function handleSaveSummary() {
    setSectionSaving("summary");
    try {
      await saveGlobalContextFields({ summary: editingSummaryVal });
      setEditingSummary(false);
      setMessage("Summary saved!");
    } catch (err: unknown) { setMessage(err instanceof Error ? err.message : "Save failed"); }
    finally { setSectionSaving(""); }
  }

  async function handleSavePersonal() {
    setSectionSaving("personal");
    try {
      await saveGlobalContextFields({
        full_name: personalDraft.full_name,
        email: personalDraft.email,
        phone: personalDraft.phone,
        nationality: personalDraft.nationality,
        linkedin_url: personalDraft.linkedin_url,
      });
      // location is a profile-level field
      await saveProfileFields({ location: personalDraft.location });
      setEditingPersonal(false);
      setMessage("Personal details saved!");
    } catch (err: unknown) { setMessage(err instanceof Error ? err.message : "Save failed"); }
    finally { setSectionSaving(""); }
  }

  async function handleSaveSkills() {
    setSectionSaving("skills");
    try {
      await saveGlobalContextFields({ skills: skillsDraft });
      setEditingSkills(false);
      setMessage("Skills saved!");
    } catch (err: unknown) { setMessage(err instanceof Error ? err.message : "Save failed"); }
    finally { setSectionSaving(""); }
  }

  async function handleSaveLanguages() {
    setSectionSaving("languages");
    try {
      await saveGlobalContextFields({ languages: languagesDraft });
      setEditingLanguages(false);
      setMessage("Languages saved!");
    } catch (err: unknown) { setMessage(err instanceof Error ? err.message : "Save failed"); }
    finally { setSectionSaving(""); }
  }

  async function handleSaveEducation() {
    setSectionSaving("education");
    try {
      await saveGlobalContextFields({ education: educationDraft });
      setEditingEducation(false);
      setMessage("Education saved!");
    } catch (err: unknown) { setMessage(err instanceof Error ? err.message : "Save failed"); }
    finally { setSectionSaving(""); }
  }

  async function handleSaveExperience() {
    if (!profile || !editingExpId) return;
    setSectionSaving("exp-" + editingExpId);
    try {
      await updateExperience(profile.id, editingExpId, expDraft);
      setEditingExpId(null);
      setMessage("Experience updated!");
      // Refresh to get updated data
      const p = await getActiveProfile();
      setProfile(p);
    } catch (err: unknown) { setMessage(err instanceof Error ? err.message : "Save failed"); }
    finally { setSectionSaving(""); }
  }

  async function handleAddExperience() {
    if (!profile) return;
    setSectionSaving("new-exp");
    try {
      await addExperience(profile.id, newExpDraft);
      setAddingExp(false);
      setNewExpDraft({ ...EMPTY_EXP });
      setMessage("Experience added!");
      const p = await getActiveProfile();
      setProfile(p);
    } catch (err: unknown) { setMessage(err instanceof Error ? err.message : "Save failed"); }
    finally { setSectionSaving(""); }
  }

  async function handleDeleteExperience(expId: string) {
    if (!profile || !confirm("Delete this experience?")) return;
    setSectionSaving("del-" + expId);
    try {
      await deleteExperience(profile.id, expId);
      setMessage("Experience deleted.");
      const p = await getActiveProfile();
      setProfile(p);
    } catch (err: unknown) { setMessage(err instanceof Error ? err.message : "Save failed"); }
    finally { setSectionSaving(""); }
  }

  function toggleItem(list: string[], item: string, setter: (v: string[]) => void) {
    setter(list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);
  }
  function toggleExp(id: string) {
    setExpandedExps((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-32 bg-[rgba(255,255,255,0.06)] rounded-xl animate-pulse" />)}</div>;

  return (
    <div className="space-y-6 max-w-3xl" style={{ color: "#fff" }}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 style={{ fontSize: 20, fontWeight: 500, color: "#fff", margin: 0 }}>Profile</h1>
          {profile && (
            <span style={{ fontSize: 10, padding: "4px 10px", borderRadius: 14, background: "rgba(34,197,94,0.1)", border: "0.5px solid rgba(34,197,94,0.2)", color: "#22c55e" }}>
              {profile.headline ? "87" : "40"}% complete
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <label style={{ padding: "8px 14px", background: "#4d8ef5", color: "#fff", fontSize: 11, fontWeight: 600, borderRadius: 10, cursor: "pointer" }}>
            {uploading ? "Processing..." : "Upload CV"}
            <input type="file" accept=".pdf,.docx,.doc" onChange={handleUpload} disabled={uploading} className="hidden" />
          </label>
          {profile && <>
            <button id="dl-cv-btn" onClick={async () => {
              const btn = document.getElementById("dl-cv-btn");
              if (btn) btn.textContent = "Generating...";
              try {
                const res = await fetch("/api/v1/cv-builder/generate", { method: "POST", headers: getAuthHeaders() });
                if (res.ok) {
                  const blob = await res.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a"); a.href = url; a.download = "StealthRole_CV.docx"; a.click(); URL.revokeObjectURL(url);
                }
              } catch {}
              if (btn) btn.textContent = "Download CV";
            }} style={{ padding: "8px 14px", background: "rgba(34,197,94,0.15)", color: "#86efac", fontSize: 11, fontWeight: 600, borderRadius: 10, border: "0.5px solid rgba(34,197,94,0.25)", cursor: "pointer" }}>Download CV</button>
            <button onClick={() => setShowLinkedIn(true)} style={{ padding: "8px 14px", background: "rgba(255,255,255,0.04)", color: "rgba(255,255,255,0.6)", fontSize: 11, fontWeight: 500, borderRadius: 10, border: "0.5px solid rgba(255,255,255,0.1)", cursor: "pointer" }}>Import LinkedIn</button>
          </>}
        </div>
      </div>

      {/* Tab bar */}
      <div style={{ display: "flex", gap: 4, borderBottom: "0.5px solid rgba(255,255,255,0.08)", marginBottom: 4 }}>
        {([
          { id: "profile", label: "Resume" },
          { id: "email", label: "Email Intelligence" },
          { id: "linkedin", label: "Contacts" },
        ] as const).map((tab) => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "10px 16px", fontSize: 13, fontWeight: 500, cursor: "pointer",
              borderBottom: activeTab === tab.id ? "2px solid #4d8ef5" : "2px solid transparent",
              color: activeTab === tab.id ? "#fff" : "rgba(255,255,255,0.35)",
              background: "transparent", border: "none",
              borderBottomWidth: 2, borderBottomStyle: "solid",
              borderBottomColor: activeTab === tab.id ? "#4d8ef5" : "transparent",
            }}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Email Intelligence tab */}
      {activeTab === "email" && <EmailIntelligenceTab />}

      {/* LinkedIn Intelligence tab */}
      {activeTab === "linkedin" && <LinkedInIntelligenceTab />}

      {/* PROFILE TAB CONTENT */}
      {activeTab === "profile" && <>

      {message && <div className="px-4 py-3 rounded-lg bg-[rgba(77,142,245,0.08)] text-[#4d8ef5] text-sm">{message}</div>}

      {/* No profile - creation form */}
      {!profile && (
        <div className="bg-[rgba(255,255,255,0.06)] rounded-xl border border-[rgba(255,255,255,0.1)] p-8 text-center">
          <div className="text-4xl mb-3">&#128100;</div>
          <div className="text-lg font-semibold text-white mb-2">Set up your profile</div>
          <div className="text-sm text-[rgba(255,255,255,0.4)] mb-4">Upload your CV or create a profile manually.</div>
          <div className="max-w-sm mx-auto space-y-3 mb-4">
            <input
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
              placeholder="Full Name"
              className="w-full px-3 py-2.5 rounded-lg border border-[rgba(255,255,255,0.1)] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
            <input
              value={createHeadline}
              onChange={(e) => setCreateHeadline(e.target.value)}
              placeholder="Headline (e.g. Senior Product Manager)"
              className="w-full px-3 py-2.5 rounded-lg border border-[rgba(255,255,255,0.1)] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>
          <div className="flex justify-center gap-3">
            <button onClick={handleCreateProfile} className="px-5 py-2.5 bg-[#4d8ef5] text-white text-sm font-semibold rounded-lg hover:bg-[#3b7de0]">Create Profile</button>
            <label className="px-5 py-2.5 border border-[rgba(255,255,255,0.12)] text-[rgba(255,255,255,0.7)] text-sm font-semibold rounded-lg hover:bg-[rgba(255,255,255,0.06)] cursor-pointer">Upload CV<input type="file" accept=".pdf,.docx,.doc" onChange={handleUpload} className="hidden" /></label>
          </div>
        </div>
      )}

      {/* Headline + Summary */}
      {profile && (
        <section className="bg-[rgba(255,255,255,0.06)] rounded-xl border border-[rgba(255,255,255,0.1)] p-5">
          {/* Headline */}
          <div className="flex items-start justify-between mb-2">
            {editingHeadline ? (
              <div className="flex-1 mr-3">
                <input
                  value={editingHeadlineVal}
                  onChange={(e) => setEditingHeadlineVal(e.target.value)}
                  className="w-full text-lg font-semibold text-white px-3 py-1.5 rounded-lg border border-[rgba(255,255,255,0.12)] focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                  placeholder="Your headline"
                />
              </div>
            ) : (
              <div className="text-lg font-semibold text-white">{profile.headline || <span className="text-ink-300 italic">No headline set</span>}</div>
            )}
            <div className="flex gap-1.5 shrink-0">
              {editingHeadline ? (
                <>
                  <button onClick={handleSaveHeadline} disabled={sectionSaving === "headline"} className="px-3 py-1 bg-[#4d8ef5] text-white text-xs font-semibold rounded-lg hover:bg-[#3b7de0] disabled:opacity-50">{sectionSaving === "headline" ? "Saving..." : "Save"}</button>
                  <button onClick={() => setEditingHeadline(false)} className="px-3 py-1 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.55)] text-xs font-semibold rounded-lg hover:bg-surface-200">Cancel</button>
                </>
              ) : (
                <button onClick={() => { setEditingHeadlineVal(profile.headline || ""); setEditingHeadline(true); }} className="px-3 py-1 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.55)] text-xs font-semibold rounded-lg hover:bg-surface-200">Edit</button>
              )}
            </div>
          </div>

          {/* Summary */}
          <div className="flex items-start justify-between">
            {editingSummary ? (
              <div className="flex-1 mr-3">
                <textarea
                  value={editingSummaryVal}
                  onChange={(e) => setEditingSummaryVal(e.target.value)}
                  rows={4}
                  className="w-full text-sm text-[rgba(255,255,255,0.7)] px-3 py-2 rounded-lg border border-[rgba(255,255,255,0.12)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 leading-relaxed"
                  placeholder="Write a summary about yourself..."
                />
              </div>
            ) : (
              <div className="text-sm text-[rgba(255,255,255,0.45)] leading-relaxed flex-1">{typeof ctx.summary === "string" && ctx.summary ? ctx.summary : <span className="text-ink-300 italic">No summary</span>}</div>
            )}
            <div className="flex gap-1.5 shrink-0 ml-3">
              {editingSummary ? (
                <>
                  <button onClick={handleSaveSummary} disabled={sectionSaving === "summary"} className="px-3 py-1 bg-[#4d8ef5] text-white text-xs font-semibold rounded-lg hover:bg-[#3b7de0] disabled:opacity-50">{sectionSaving === "summary" ? "Saving..." : "Save"}</button>
                  <button onClick={() => setEditingSummary(false)} className="px-3 py-1 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.55)] text-xs font-semibold rounded-lg hover:bg-surface-200">Cancel</button>
                </>
              ) : (
                <button onClick={() => { setEditingSummaryVal((ctx.summary as string) || ""); setEditingSummary(true); }} className="px-3 py-1 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.55)] text-xs font-semibold rounded-lg hover:bg-surface-200">Edit</button>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Personal Details */}
      {profile && (
        <section className="bg-[rgba(255,255,255,0.06)] rounded-xl border border-[rgba(255,255,255,0.1)] p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white">Personal Details</h2>
            <div className="flex gap-1.5">
              {editingPersonal ? (
                <>
                  <button onClick={handleSavePersonal} disabled={sectionSaving === "personal"} className="px-3 py-1 bg-[#4d8ef5] text-white text-xs font-semibold rounded-lg hover:bg-[#3b7de0] disabled:opacity-50">{sectionSaving === "personal" ? "Saving..." : "Save"}</button>
                  <button onClick={() => setEditingPersonal(false)} className="px-3 py-1 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.55)] text-xs font-semibold rounded-lg hover:bg-surface-200">Cancel</button>
                </>
              ) : (
                <button onClick={() => {
                  setPersonalDraft({
                    full_name: String(ctx.full_name || ""),
                    email: String(ctx.email || ""),
                    phone: String(ctx.phone || ""),
                    location: String(profile.location || ctx.location || ""),
                    nationality: String(ctx.nationality || ""),
                    linkedin_url: String(ctx.linkedin_url || ""),
                  });
                  setEditingPersonal(true);
                }} className="px-3 py-1 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.55)] text-xs font-semibold rounded-lg hover:bg-surface-200">Edit</button>
              )}
            </div>
          </div>
          {editingPersonal ? (
            <div className="grid grid-cols-2 gap-3">
              <EditField label="Name" value={personalDraft.full_name} onChange={(v) => setPersonalDraft({ ...personalDraft, full_name: v })} />
              <EditField label="Email" value={personalDraft.email} onChange={(v) => setPersonalDraft({ ...personalDraft, email: v })} />
              <EditField label="Phone" value={personalDraft.phone} onChange={(v) => setPersonalDraft({ ...personalDraft, phone: v })} />
              <EditField label="Location" value={personalDraft.location} onChange={(v) => setPersonalDraft({ ...personalDraft, location: v })} />
              <EditField label="Nationality" value={personalDraft.nationality} onChange={(v) => setPersonalDraft({ ...personalDraft, nationality: v })} />
              <EditField label="LinkedIn URL" value={personalDraft.linkedin_url} onChange={(v) => setPersonalDraft({ ...personalDraft, linkedin_url: v })} />
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              {Boolean(ctx.full_name) && <Fld label="Name" value={String(ctx.full_name)} />}
              {Boolean(ctx.email) && <Fld label="Email" value={String(ctx.email)} />}
              {Boolean(ctx.phone) && <Fld label="Phone" value={String(ctx.phone)} />}
              {Boolean(profile.location || ctx.location) && <Fld label="Location" value={String(profile.location || ctx.location)} />}
              {Boolean(ctx.nationality) && <Fld label="Nationality" value={String(ctx.nationality)} />}
              {Boolean(ctx.linkedin_url) && (<div><div className="text-[11px] font-medium text-[rgba(255,255,255,0.4)] uppercase mb-0.5">LinkedIn</div><a href={String(ctx.linkedin_url)} target="_blank" rel="noopener" className="text-sm text-[#4d8ef5] font-medium truncate block">{String(ctx.linkedin_url)}</a></div>)}
              {!ctx.full_name && !ctx.email && !ctx.phone && !profile.location && !ctx.location && !ctx.nationality && !ctx.linkedin_url && (
                <div className="col-span-2 text-sm text-ink-300 italic">No personal details yet. Click Edit to add.</div>
              )}
            </div>
          )}
        </section>
      )}

      {/* Skills */}
      {profile && (
        <section className="bg-[rgba(255,255,255,0.06)] rounded-xl border border-[rgba(255,255,255,0.1)] p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white">Skills</h2>
            <div className="flex gap-1.5">
              {editingSkills ? (
                <>
                  <button onClick={handleSaveSkills} disabled={sectionSaving === "skills"} className="px-3 py-1 bg-[#4d8ef5] text-white text-xs font-semibold rounded-lg hover:bg-[#3b7de0] disabled:opacity-50">{sectionSaving === "skills" ? "Saving..." : "Save"}</button>
                  <button onClick={() => setEditingSkills(false)} className="px-3 py-1 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.55)] text-xs font-semibold rounded-lg hover:bg-surface-200">Cancel</button>
                </>
              ) : (
                <button onClick={() => { setSkillsDraft([...skills]); setEditingSkills(true); }} className="px-3 py-1 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.55)] text-xs font-semibold rounded-lg hover:bg-surface-200">Edit</button>
              )}
            </div>
          </div>
          {editingSkills ? (
            <div>
              <div className="flex flex-wrap gap-1.5 mb-3">
                {skillsDraft.map((s, i) => (
                  <span key={i} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[rgba(77,142,245,0.08)] text-[#4d8ef5] text-sm font-medium border border-brand-200">
                    {s}
                    <button onClick={() => setSkillsDraft(skillsDraft.filter((_, j) => j !== i))} className="text-brand-400 hover:text-[#4d8ef5] ml-0.5">&times;</button>
                  </span>
                ))}
              </div>
              <div className="flex gap-2">
                <input value={newSkill} onChange={(e) => setNewSkill(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && newSkill.trim()) { e.preventDefault(); setSkillsDraft([...skillsDraft, newSkill.trim()]); setNewSkill(""); }}} placeholder="Type a skill + Enter" className="flex-1 px-3 py-2 rounded-lg border border-[rgba(255,255,255,0.1)] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20" />
                <button onClick={() => { if (newSkill.trim()) { setSkillsDraft([...skillsDraft, newSkill.trim()]); setNewSkill(""); }}} className="px-3 py-2 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.7)] text-sm rounded-lg hover:bg-surface-200">Add</button>
              </div>
            </div>
          ) : (
            skills.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">{skills.map((s) => <span key={s} className="px-2.5 py-1 rounded-lg bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.7)] text-sm font-medium border border-[rgba(255,255,255,0.1)]">{s}</span>)}</div>
            ) : (
              <div className="text-sm text-ink-300 italic">No skills added yet. Click Edit to add.</div>
            )
          )}
        </section>
      )}

      {/* Languages */}
      {profile && (
        <section className="bg-[rgba(255,255,255,0.06)] rounded-xl border border-[rgba(255,255,255,0.1)] p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white">Languages</h2>
            <div className="flex gap-1.5">
              {editingLanguages ? (
                <>
                  <button onClick={handleSaveLanguages} disabled={sectionSaving === "languages"} className="px-3 py-1 bg-[#4d8ef5] text-white text-xs font-semibold rounded-lg hover:bg-[#3b7de0] disabled:opacity-50">{sectionSaving === "languages" ? "Saving..." : "Save"}</button>
                  <button onClick={() => setEditingLanguages(false)} className="px-3 py-1 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.55)] text-xs font-semibold rounded-lg hover:bg-surface-200">Cancel</button>
                </>
              ) : (
                <button onClick={() => { setLanguagesDraft([...languages]); setEditingLanguages(true); }} className="px-3 py-1 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.55)] text-xs font-semibold rounded-lg hover:bg-surface-200">Edit</button>
              )}
            </div>
          </div>
          {editingLanguages ? (
            <div>
              <div className="flex flex-wrap gap-1.5 mb-3">
                {languagesDraft.map((l, i) => (
                  <span key={i} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[rgba(77,142,245,0.08)] text-[#4d8ef5] text-sm font-medium border border-brand-200">
                    {l}
                    <button onClick={() => setLanguagesDraft(languagesDraft.filter((_, j) => j !== i))} className="text-brand-400 hover:text-[#4d8ef5] ml-0.5">&times;</button>
                  </span>
                ))}
              </div>
              <div className="flex gap-2">
                <input value={newLanguage} onChange={(e) => setNewLanguage(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && newLanguage.trim()) { e.preventDefault(); setLanguagesDraft([...languagesDraft, newLanguage.trim()]); setNewLanguage(""); }}} placeholder="Type a language + Enter" className="flex-1 px-3 py-2 rounded-lg border border-[rgba(255,255,255,0.1)] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20" />
                <button onClick={() => { if (newLanguage.trim()) { setLanguagesDraft([...languagesDraft, newLanguage.trim()]); setNewLanguage(""); }}} className="px-3 py-2 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.7)] text-sm rounded-lg hover:bg-surface-200">Add</button>
              </div>
            </div>
          ) : (
            languages.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">{languages.map((l) => <span key={l} className="px-2.5 py-1 rounded-lg bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.7)] text-sm font-medium border border-[rgba(255,255,255,0.1)]">{l}</span>)}</div>
            ) : (
              <div className="text-sm text-ink-300 italic">No languages added yet. Click Edit to add, or re-import your CV to auto-extract.</div>
            )
          )}
        </section>
      )}

      {/* Education */}
      {profile && (
        <section className="bg-[rgba(255,255,255,0.06)] rounded-xl border border-[rgba(255,255,255,0.1)] p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white">Education</h2>
            <div className="flex gap-1.5">
              {editingEducation ? (
                <>
                  <button onClick={handleSaveEducation} disabled={sectionSaving === "education"} className="px-3 py-1 bg-[#4d8ef5] text-white text-xs font-semibold rounded-lg hover:bg-[#3b7de0] disabled:opacity-50">{sectionSaving === "education" ? "Saving..." : "Save"}</button>
                  <button onClick={() => setEditingEducation(false)} className="px-3 py-1 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.55)] text-xs font-semibold rounded-lg hover:bg-surface-200">Cancel</button>
                </>
              ) : (
                <button onClick={() => { setEducationDraft(education.map((e) => ({ ...e }))); setEditingEducation(true); }} className="px-3 py-1 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.55)] text-xs font-semibold rounded-lg hover:bg-surface-200">Edit</button>
              )}
            </div>
          </div>
          {editingEducation ? (
            <div className="space-y-3">
              <button onClick={() => setEducationDraft([{ institution: "", degree: "", field: "", start_date: "", end_date: "" }, ...educationDraft])} className="text-sm text-[#4d8ef5] font-semibold hover:text-[#4d8ef5]">+ Add Education</button>
              {educationDraft.map((edu, i) => (
                <div key={i} className="bg-[rgba(255,255,255,0.04)] rounded-lg px-4 py-3 space-y-2 border border-[rgba(255,255,255,0.1)]">
                  <div className="flex justify-between items-center">
                    <div className="text-xs font-medium text-[rgba(255,255,255,0.4)]">Entry {i + 1}</div>
                    <button onClick={() => setEducationDraft(educationDraft.filter((_, j) => j !== i))} className="text-xs text-red-500 hover:text-red-700 font-medium">Delete</button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <EditField label="Institution" value={edu.institution || ""} onChange={(v) => { const d = [...educationDraft]; d[i] = { ...d[i], institution: v }; setEducationDraft(d); }} />
                    <EditField label="Degree" value={edu.degree || ""} onChange={(v) => { const d = [...educationDraft]; d[i] = { ...d[i], degree: v }; setEducationDraft(d); }} />
                    <EditField label="Field of Study" value={edu.field || ""} onChange={(v) => { const d = [...educationDraft]; d[i] = { ...d[i], field: v }; setEducationDraft(d); }} />
                    <EditField label="Year" value={edu.end_date || edu.start_date || ""} onChange={(v) => { const d = [...educationDraft]; d[i] = { ...d[i], end_date: v }; setEducationDraft(d); }} />
                  </div>
                </div>
              ))}
              {educationDraft.length === 0 && <div className="text-sm text-ink-300 italic">No education entries. Click &quot;+ Add Education&quot; above.</div>}
            </div>
          ) : (
            education.length > 0 ? (
              <div className="space-y-2">{education.map((edu, i) => (
                <div key={i} className="bg-[rgba(255,255,255,0.04)] rounded-lg px-4 py-2.5">
                  <div className="text-sm font-medium text-white">{edu.degree}{edu.field ? ` in ${edu.field}` : ""}</div>
                  <div className="text-[11px] text-[rgba(255,255,255,0.4)]">{edu.institution}{edu.start_date || edu.end_date ? ` · ${edu.start_date || ""}–${edu.end_date || ""}` : ""}</div>
                </div>
              ))}</div>
            ) : (
              <div className="text-sm text-ink-300 italic">No education added yet. Click Edit to add, or re-import your CV to auto-extract.</div>
            )
          )}
        </section>
      )}

      {/* CVs */}
      {cvs.length > 0 && (
        <section className="bg-[rgba(255,255,255,0.06)] rounded-xl border border-[rgba(255,255,255,0.1)] p-5">
          <h2 className="text-sm font-semibold text-white mb-3">Uploaded CVs</h2>
          <div className="space-y-2">{cvs.map((cv) => (
            <div key={cv.id} className="flex items-center justify-between bg-[rgba(255,255,255,0.04)] rounded-lg px-4 py-2.5">
              <div className="flex items-center gap-3"><span className="text-lg">&#128196;</span><div><div className="text-sm font-medium text-white">{cv.original_filename}</div><div className="text-[11px] text-[rgba(255,255,255,0.4)]">{cv.status === "parsed" ? "Ready" : cv.status}</div></div></div>
              {cv.quality_score !== null && <span className={`text-sm font-bold px-2 py-0.5 rounded ${cv.quality_score >= 70 ? "text-green-700 bg-green-50" : cv.quality_score >= 40 ? "text-amber-700 bg-amber-50" : "text-red-700 bg-red-50"}`}>{cv.quality_score}%</span>}
            </div>
          ))}</div>
        </section>
      )}

      {/* Experiences - expandable + editable */}
      {profile && (
        <section className="bg-[rgba(255,255,255,0.06)] rounded-xl border border-[rgba(255,255,255,0.1)] p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white">Experience {profile.experiences?.length > 0 ? `(${completeCount}/${profile.experiences.length} complete)` : ""}</h2>
            {!addingExp && (
              <button onClick={() => { setNewExpDraft({ ...EMPTY_EXP }); setAddingExp(true); }} className="px-3 py-1 bg-[#4d8ef5] text-white text-xs font-semibold rounded-lg hover:bg-[#3b7de0]">+ Add Experience</button>
            )}
          </div>

          {/* Add new experience form */}
          {addingExp && (
            <div className="bg-[rgba(77,142,245,0.08)] rounded-lg border border-brand-200 p-4 mb-3 space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-white">New Experience</div>
                <div className="flex gap-1.5">
                  <button onClick={handleAddExperience} disabled={sectionSaving === "new-exp" || !newExpDraft.role_title.trim()} className="px-3 py-1 bg-[#4d8ef5] text-white text-xs font-semibold rounded-lg hover:bg-[#3b7de0] disabled:opacity-50">{sectionSaving === "new-exp" ? "Saving..." : "Save"}</button>
                  <button onClick={() => setAddingExp(false)} className="px-3 py-1 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.55)] text-xs font-semibold rounded-lg hover:bg-surface-200">Cancel</button>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <EditField label="Role Title *" value={newExpDraft.role_title} onChange={(v) => setNewExpDraft({ ...newExpDraft, role_title: v })} />
                <EditField label="Company Name" value={newExpDraft.company_name} onChange={(v) => setNewExpDraft({ ...newExpDraft, company_name: v })} />
                <EditField label="Start Date" value={newExpDraft.start_date} onChange={(v) => setNewExpDraft({ ...newExpDraft, start_date: v })} placeholder="e.g. 2020-01" />
                <EditField label="End Date" value={newExpDraft.end_date} onChange={(v) => setNewExpDraft({ ...newExpDraft, end_date: v })} placeholder="e.g. 2023-06 or blank for Present" />
                <EditField label="Location" value={newExpDraft.location} onChange={(v) => setNewExpDraft({ ...newExpDraft, location: v })} />
              </div>
              <EditTextarea label="Context & Situation" value={newExpDraft.context} onChange={(v) => setNewExpDraft({ ...newExpDraft, context: v })} />
              <EditTextarea label="Contribution" value={newExpDraft.contribution} onChange={(v) => setNewExpDraft({ ...newExpDraft, contribution: v })} />
              <EditTextarea label="Outcomes & Impact" value={newExpDraft.outcomes} onChange={(v) => setNewExpDraft({ ...newExpDraft, outcomes: v })} />
              <EditTextarea label="How They Did It" value={newExpDraft.methods} onChange={(v) => setNewExpDraft({ ...newExpDraft, methods: v })} />
            </div>
          )}

          {/* Existing experiences */}
          <div className="space-y-2">
            {profile.experiences?.length > 0 ? profile.experiences.map((exp) => {
              const isOpen = expandedExps.has(exp.id);
              const isEditing = editingExpId === exp.id;
              const dateStr = [exp.start_date, exp.end_date || "Present"].filter(Boolean).join(" – ");
              return (
                <div key={exp.id} className="bg-[rgba(255,255,255,0.04)] rounded-lg border border-[rgba(255,255,255,0.1)] overflow-hidden">
                  <button onClick={() => toggleExp(exp.id)} className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[rgba(255,255,255,0.06)] transition-colors">
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-white">{exp.role_title}</div>
                      <div className="text-[11px] text-[rgba(255,255,255,0.4)]">{exp.company_name}</div>
                      {(dateStr || exp.location) && <div className="text-[11px] text-[rgba(255,255,255,0.4)] mt-0.5">{dateStr}{exp.location ? ` · ${exp.location}` : ""}</div>}
                    </div>
                    <div className="flex items-center gap-2 shrink-0 ml-3">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${exp.is_complete ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"}`}>{exp.is_complete ? "Complete" : `${exp.fields_completed || 0}/6`}</span>
                      <span className="text-[rgba(255,255,255,0.4)] text-xs">{isOpen ? "▾" : "▸"}</span>
                    </div>
                  </button>
                  {isOpen && (
                    <div className="px-4 pb-3 border-t border-[rgba(255,255,255,0.1)] pt-2.5">
                      {isEditing ? (
                        <div className="space-y-3">
                          <div className="flex justify-end gap-1.5">
                            <button onClick={handleSaveExperience} disabled={sectionSaving === "exp-" + exp.id} className="px-3 py-1 bg-[#4d8ef5] text-white text-xs font-semibold rounded-lg hover:bg-[#3b7de0] disabled:opacity-50">{sectionSaving === "exp-" + exp.id ? "Saving..." : "Save"}</button>
                            <button onClick={() => setEditingExpId(null)} className="px-3 py-1 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.55)] text-xs font-semibold rounded-lg hover:bg-surface-200">Cancel</button>
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <EditField label="Role Title" value={expDraft.role_title} onChange={(v) => setExpDraft({ ...expDraft, role_title: v })} />
                            <EditField label="Company Name" value={expDraft.company_name} onChange={(v) => setExpDraft({ ...expDraft, company_name: v })} />
                            <EditField label="Start Date" value={expDraft.start_date} onChange={(v) => setExpDraft({ ...expDraft, start_date: v })} />
                            <EditField label="End Date" value={expDraft.end_date} onChange={(v) => setExpDraft({ ...expDraft, end_date: v })} placeholder="blank for Present" />
                            <EditField label="Location" value={expDraft.location} onChange={(v) => setExpDraft({ ...expDraft, location: v })} />
                          </div>
                          <EditTextarea label="Context & Situation" value={expDraft.context} onChange={(v) => setExpDraft({ ...expDraft, context: v })} />
                          <EditTextarea label="Contribution" value={expDraft.contribution} onChange={(v) => setExpDraft({ ...expDraft, contribution: v })} />
                          <EditTextarea label="Outcomes & Impact" value={expDraft.outcomes} onChange={(v) => setExpDraft({ ...expDraft, outcomes: v })} />
                          <EditTextarea label="How They Did It" value={expDraft.methods} onChange={(v) => setExpDraft({ ...expDraft, methods: v })} />
                        </div>
                      ) : (
                        <div className="space-y-2.5">
                          <div className="flex justify-end gap-1.5 mb-2">
                            <button onClick={(e) => { e.stopPropagation(); setExpDraft({ role_title: exp.role_title || "", company_name: exp.company_name || "", start_date: exp.start_date || "", end_date: exp.end_date || "", location: exp.location || "", context: exp.context || "", contribution: exp.contribution || "", outcomes: exp.outcomes || "", methods: exp.methods || "" }); setEditingExpId(exp.id); }} className="px-3 py-1 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.55)] text-xs font-semibold rounded-lg hover:bg-surface-200">Edit</button>
                            <button onClick={(e) => { e.stopPropagation(); handleDeleteExperience(exp.id); }} disabled={sectionSaving === "del-" + exp.id} className="px-3 py-1 bg-red-50 text-red-600 text-xs font-semibold rounded-lg hover:bg-red-100 disabled:opacity-50">{sectionSaving === "del-" + exp.id ? "Deleting..." : "Delete"}</button>
                          </div>
                          {exp.context && <DFld label="Context & Situation" value={exp.context} />}
                          {exp.contribution && <DFld label="Contribution" value={exp.contribution} />}
                          {exp.outcomes && <DFld label="Outcomes & Impact" value={exp.outcomes} />}
                          {exp.methods && <DFld label="How They Did It" value={exp.methods} />}
                          {!exp.context && !exp.contribution && !exp.outcomes && !exp.methods && <div className="text-[12px] text-[rgba(255,255,255,0.4)] italic">No details filled yet.</div>}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            }) : (
              !addingExp && <div className="text-sm text-ink-300 italic">No experiences yet. Click &quot;+ Add Experience&quot; to add one.</div>
            )}
          </div>
        </section>
      )}

      {/* Preferences */}
      {profile && (
        <section className="bg-[rgba(255,255,255,0.06)] rounded-xl border border-[rgba(255,255,255,0.1)] p-5 space-y-5">
          <h2 className="text-sm font-semibold text-white">Job Search Preferences</h2>
          <div>
            <label className="text-[12px] font-medium text-[rgba(255,255,255,0.45)] uppercase block mb-2">Target Regions</label>
            <div className="flex flex-wrap gap-2">{REGIONS.map((r) => <button key={r} onClick={() => toggleItem(selectedRegions, r, setSelectedRegions)} className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${selectedRegions.includes(r) ? "bg-[rgba(77,142,245,0.08)] text-[#4d8ef5] border-brand-200 font-medium" : "bg-[rgba(255,255,255,0.04)] text-[rgba(255,255,255,0.45)] border-[rgba(255,255,255,0.1)] hover:bg-[rgba(255,255,255,0.06)]"}`}>{r}</button>)}</div>
          </div>
          <div>
            <label className="text-[12px] font-medium text-[rgba(255,255,255,0.45)] uppercase block mb-2">Target Sectors</label>
            <div className="flex flex-wrap gap-2">{SECTORS.map((s) => <button key={s} onClick={() => toggleItem(selectedSectors, s, setSelectedSectors)} className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${selectedSectors.includes(s) ? "bg-[rgba(77,142,245,0.08)] text-[#4d8ef5] border-brand-200 font-medium" : "bg-[rgba(255,255,255,0.04)] text-[rgba(255,255,255,0.45)] border-[rgba(255,255,255,0.1)] hover:bg-[rgba(255,255,255,0.06)]"}`}>{s}</button>)}</div>
          </div>
          <div>
            <label className="text-[12px] font-medium text-[rgba(255,255,255,0.45)] uppercase block mb-2">Target Roles</label>
            {selectedRoles.length > 0 && <div className="flex flex-wrap gap-1.5 mb-2">{selectedRoles.map((r) => <span key={r} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[rgba(77,142,245,0.08)] text-[#4d8ef5] text-sm font-medium border border-brand-200">{r}<button onClick={() => setSelectedRoles(selectedRoles.filter((x) => x !== r))} className="text-brand-400 hover:text-[#4d8ef5] ml-0.5">&times;</button></span>)}</div>}
            <div className="flex flex-wrap gap-1.5 mb-2">{ROLE_SUGGESTIONS.filter((r) => !selectedRoles.includes(r)).slice(0, 12).map((r) => <button key={r} onClick={() => setSelectedRoles([...selectedRoles, r])} className="px-2.5 py-1 rounded-lg text-[12px] bg-[rgba(255,255,255,0.04)] text-[rgba(255,255,255,0.45)] border border-[rgba(255,255,255,0.1)] hover:bg-[rgba(77,142,245,0.08)] hover:text-[#4d8ef5] hover:border-brand-200 transition-colors">{r}</button>)}</div>
            <div className="flex gap-2">
              <input value={customRole} onChange={(e) => setCustomRole(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && customRole.trim()) { e.preventDefault(); if (!selectedRoles.includes(customRole.trim())) setSelectedRoles([...selectedRoles, customRole.trim()]); setCustomRole(""); }}} placeholder="Type a custom role + Enter" className="flex-1 px-3 py-2 rounded-lg border border-[rgba(255,255,255,0.1)] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20" />
              <button onClick={() => { if (customRole.trim() && !selectedRoles.includes(customRole.trim())) { setSelectedRoles([...selectedRoles, customRole.trim()]); setCustomRole(""); }}} className="px-3 py-2 bg-[rgba(255,255,255,0.06)] text-[rgba(255,255,255,0.7)] text-sm rounded-lg hover:bg-surface-200">Add</button>
            </div>
          </div>
          <div>
            <label className="text-[12px] font-medium text-[rgba(255,255,255,0.45)] uppercase block mb-2">Seniority Level</label>
            <select value={selectedSeniority} onChange={(e) => setSelectedSeniority(e.target.value)} className="w-full px-3 py-2.5 rounded-lg border border-[rgba(255,255,255,0.1)] text-sm bg-[rgba(255,255,255,0.06)] focus:outline-none focus:ring-2 focus:ring-brand-500/20"><option value="">Any</option>{SENIORITY.map((s) => <option key={s} value={s}>{s}</option>)}</select>
          </div>
          <div>
            <label className="text-[12px] font-medium text-[rgba(255,255,255,0.45)] uppercase block mb-2">Salary Range (USD/year)</label>
            {/* Selected range display */}
            <div className="text-base font-semibold text-white mb-3">
              USD ${(parseInt(salaryMin) || 80) >= 1000 ? Math.round((parseInt(salaryMin) || 80) / 1000) + "K" : (parseInt(salaryMin) || 80) + "K"}
              {" → "}
              ${(parseInt(salaryMax) || 500) >= 1000 ? Math.round((parseInt(salaryMax) || 500) / 1000) + "K" : (parseInt(salaryMax) || 500) + "K"}
              <span className="text-xs text-[rgba(255,255,255,0.35)] font-normal ml-2">per year</span>
            </div>
            {/* Dual range sliders */}
            <div className="relative h-12 mb-3">
              <div className="absolute top-[22px] left-0 right-0 h-1 rounded-full bg-[rgba(255,255,255,0.08)]" />
              <div
                className="absolute top-[22px] h-1 rounded-full"
                style={{
                  background: "linear-gradient(90deg, #4d8ef5, #a78bfa)",
                  left: `${Math.max(0, Math.min(100, ((parseInt(salaryMin) || 80) - 80) / (500 - 80) * 100))}%`,
                  right: `${100 - Math.max(0, Math.min(100, ((parseInt(salaryMax) || 500) - 80) / (500 - 80) * 100))}%`,
                }}
              />
              <input
                type="range"
                min={80}
                max={500}
                step={10}
                value={parseInt(salaryMin) || 80}
                onChange={(e) => {
                  const v = parseInt(e.target.value);
                  const max = parseInt(salaryMax) || 500;
                  setSalaryMin(String(Math.min(v, max - 10)));
                }}
                className="absolute top-0 left-0 w-full h-12 appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[#4d8ef5] [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:cursor-pointer"
              />
              <input
                type="range"
                min={80}
                max={500}
                step={10}
                value={parseInt(salaryMax) || 500}
                onChange={(e) => {
                  const v = parseInt(e.target.value);
                  const min = parseInt(salaryMin) || 80;
                  setSalaryMax(String(Math.max(v, min + 10)));
                }}
                className="absolute top-0 left-0 w-full h-12 appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[#a78bfa] [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:cursor-pointer"
              />
            </div>
            {/* Quick bracket chips */}
            <div className="flex flex-wrap gap-1.5">
              {[
                { l: "Under $100K", min: 80, max: 100 },
                { l: "$100–150K", min: 100, max: 150 },
                { l: "$150–200K", min: 150, max: 200 },
                { l: "$200–300K", min: 200, max: 300 },
                { l: "$300–400K", min: 300, max: 400 },
                { l: "$400K+", min: 400, max: 500 },
                { l: "$500K+", min: 500, max: 500 },
              ].map((b) => {
                const active = parseInt(salaryMin) === b.min && parseInt(salaryMax) === b.max;
                return (
                  <button
                    key={b.l}
                    type="button"
                    onClick={() => { setSalaryMin(String(b.min)); setSalaryMax(String(b.max)); }}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-medium border transition-colors ${
                      active
                        ? "bg-[rgba(77,142,245,0.15)] text-[#4d8ef5] border-brand-200"
                        : "bg-[rgba(255,255,255,0.04)] text-[rgba(255,255,255,0.45)] border-[rgba(255,255,255,0.1)] hover:bg-[rgba(255,255,255,0.08)]"
                    }`}
                  >
                    {b.l}
                  </button>
                );
              })}
            </div>
          </div>
          <button onClick={handleSavePreferences} disabled={saving} className="w-full py-2.5 bg-[#4d8ef5] text-white text-sm font-semibold rounded-lg hover:bg-[#3b7de0] disabled:opacity-50 transition-colors">
            {saving ? "Saving..." : "Save Preferences"}
          </button>
        </section>
      )}

      </>}
      {/* END PROFILE TAB */}

      <Modal open={showLinkedIn} onClose={() => setShowLinkedIn(false)} title="Import from LinkedIn">
        <div className="space-y-4">
          <p className="text-sm text-[rgba(255,255,255,0.45)]">Paste your LinkedIn profile URL.</p>
          <input type="url" value={linkedinUrl} onChange={(e) => setLinkedinUrl(e.target.value)} placeholder="https://www.linkedin.com/in/your-profile" className="w-full px-3 py-2.5 rounded-lg border border-[rgba(255,255,255,0.1)] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20" />
          <button onClick={handleLinkedInImport} disabled={linkedinLoading || !linkedinUrl.trim()} className="w-full py-2.5 bg-[#4d8ef5] text-white text-sm font-semibold rounded-lg hover:bg-[#3b7de0] disabled:opacity-50">{linkedinLoading ? "Importing..." : "Import Profile"}</button>
        </div>
      </Modal>
    </div>
  );
}

/* ── Helper components ── */

function Fld({ label, value }: { label: string; value: string }) {
  return <div><div className="text-[11px] font-medium text-[rgba(255,255,255,0.4)] uppercase mb-0.5">{label}</div><div className="text-sm font-medium text-white">{value}</div></div>;
}
function DFld({ label, value }: { label: string; value: string }) {
  return <div><div className="text-[11px] font-medium text-[rgba(255,255,255,0.4)] uppercase mb-0.5">{label}</div><div className="text-sm text-[rgba(255,255,255,0.7)] whitespace-pre-wrap">{value}</div></div>;
}

function EditField({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div>
      <div className="text-[11px] font-medium text-[rgba(255,255,255,0.4)] uppercase mb-0.5">{label}</div>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder || label} className="w-full px-3 py-1.5 rounded-lg border border-[rgba(255,255,255,0.12)] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20" />
    </div>
  );
}

function EditTextarea({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <div className="text-[11px] font-medium text-[rgba(255,255,255,0.4)] uppercase mb-0.5">{label}</div>
      <textarea value={value} onChange={(e) => onChange(e.target.value)} rows={3} placeholder={label} className="w-full px-3 py-2 rounded-lg border border-[rgba(255,255,255,0.12)] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 leading-relaxed" />
    </div>
  );
}
