/**
 * API client for StealthRole backend.
 *
 * All requests go through Next.js rewrite → localhost:8000.
 * Auth token stored in localStorage.
 */

const API_BASE = "/api/v1";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("sr_token");
}

export function setToken(token: string) {
  localStorage.setItem("sr_token", token);
}

export function clearToken() {
  localStorage.removeItem("sr_token");
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearToken();
    // Don't redirect if this is a login/register attempt — let the form show the error
    const isAuthAttempt =
      path.includes("/auth/login") || path.includes("/auth/register");
    if (!isAuthAttempt && typeof window !== "undefined") {
      window.location.href = "/login";
    }
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Invalid email or password");
  }

  if (res.status === 204) return undefined as T;

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error ${res.status}`);
  }

  return res.json();
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_verified: boolean;
}

export async function login(email: string, password: string) {
  const data = await request<{ access_token: string }>(
    "/auth/login",
    {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }
  );
  setToken(data.access_token);
  // Login response doesn't include user — fetch it separately
  const user = await getMe();
  return { ...data, user };
}

export async function register(
  email: string,
  password: string,
  full_name?: string
) {
  const data = await request<{ access_token: string; user: User }>(
    "/auth/register",
    {
      method: "POST",
      body: JSON.stringify({ email, password, full_name }),
    }
  );
  setToken(data.access_token);
  return data;
}

export async function getMe(): Promise<User> {
  return request<User>("/auth/me");
}

// ── Dashboard ────────────────────────────────────────────────────────────────

export interface DashboardSummary {
  profile_strength: {
    score: number;
    max: number;
    breakdown: Record<string, unknown>;
    next_action: string;
  };
  top_opportunities: unknown[];
  radar_opportunities: unknown[];
  recent_applications: unknown[];
  recent_shadow_applications: unknown[];
  total_applications: number;
  total_shadow_applications: number;
  profile_completeness: number;
  sources_active: number;
}

export async function getDashboard(): Promise<DashboardSummary> {
  return request("/dashboard/summary");
}

// ── Applications ─────────────────────────────────────────────────────────────

export interface ApplicationAnalytics {
  total_applications: number;
  by_stage: { stage: string; count: number; rate: number }[];
  avg_days_to_interview: number | null;
  best_source_channel: string | null;
  source_performance: unknown[];
}

export async function getApplicationAnalytics(): Promise<ApplicationAnalytics> {
  return request("/applications/analytics");
}

export interface ApplicationItem {
  id: string;
  company: string;
  role: string;
  date_applied: string;
  source_channel: string;
  stage: string;
  notes: string | null;
  url: string | null;
  salary: string | null;
  contact_name: string | null;
  contact_email: string | null;
  interview_at: string | null;
  offer_at: string | null;
  rejected_at: string | null;
  job_run_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface BoardColumn {
  stage: string;
  count: number;
  applications: ApplicationItem[];
}

export interface BoardResponse {
  columns: BoardColumn[];
  total: number;
}

export async function getBoard(): Promise<BoardResponse> {
  return request("/applications/board");
}

export async function createApplication(data: {
  company: string;
  role: string;
  date_applied: string;
  source_channel: string;
  stage?: string;
  notes?: string;
  url?: string;
  salary?: string;
  contact_name?: string;
  contact_email?: string;
}): Promise<ApplicationItem> {
  return request("/applications", { method: "POST", body: JSON.stringify(data) });
}

export async function updateApplication(
  id: string,
  data: Partial<ApplicationItem>
): Promise<ApplicationItem> {
  return request(`/applications/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function updateApplicationStage(
  id: string,
  stage: string
): Promise<ApplicationItem> {
  return request(`/applications/${id}/stage`, {
    method: "PATCH",
    body: JSON.stringify({ stage }),
  });
}

export async function deleteApplication(id: string): Promise<void> {
  return request(`/applications/${id}`, { method: "DELETE" });
}

// ── Scout / Signals ──────────────────────────────────────────────────────────

export interface Opportunity {
  id: string;
  company: string;
  role: string | null;
  location: string | null;
  sector: string | null;
  radar_score: number;
  urgency: string;
  evidence_tier: string;
  reasoning: string;
  suggested_action: string;
  outreach_hook: string;
  sources: { type: string; signal_type: string; headline: string }[];
  source_tags: string[];
  timeline: string;
  fit_reasons: string[];
  red_flags: string[];
  first_seen_at: string | null;
}

export interface RadarResult {
  opportunities: Opportunity[];
  total: number;
  scoring: Record<string, unknown>;
}

export async function getRadar(limit = 20): Promise<RadarResult> {
  return request(`/opportunities/radar?limit=${limit}`);
}

export interface ScoutSignals {
  opportunities: unknown[];
  live_openings: unknown[];
  signals_detected: number;
  sources_searched: number;
  is_demo: boolean;
  scored_by: string;
}

export async function getScoutSignals(): Promise<ScoutSignals> {
  return request("/scout/signals");
}

export interface HiddenSignal {
  id: string;
  company_name: string;
  signal_type: string;
  confidence: number;
  likely_roles: string[];
  reasoning: string;
  source_url: string;
  source_name: string;
  evidence_tier?: string;
  signal_data?: Record<string, unknown>;
  created_at: string;
}

export async function getHiddenMarket(): Promise<{
  signals: HiddenSignal[];
  total: number;
}> {
  return request("/scout/hidden-market");
}

// ── CV Upload ────────────────────────────────────────────────────────────────

export async function uploadCV(file: File): Promise<{ id: string; status: string }> {
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/cvs`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Upload failed: ${res.status}`);
  }
  return res.json();
}

export async function listCVs(): Promise<{ id: string; original_filename: string; status: string; quality_score: number | null }[]> {
  return request("/cvs") || [];
}

// ── Job Runs (Intelligence Pack) ─────────────────────────────────────────────

export interface JobRunCreate {
  cv_id: string;
  jd_text?: string;
  jd_url?: string;
  preferences?: {
    tone?: string;
    region?: string;
    page_limit?: number;
  };
}

export interface JobRun {
  id: string;
  status: string;
  cv_id: string;
  created_at: string;
  updated_at: string;
  role_title?: string;
  company_name?: string;
  keyword_match_score?: number;
  pipeline_stage?: string;
  reports?: Record<string, unknown>;
  positioning?: Record<string, unknown>;
  download_url?: string;
  failed_step?: string;
  error_message?: string;
}

export async function createJobRun(data: JobRunCreate): Promise<JobRun> {
  return request("/jobs", { method: "POST", body: JSON.stringify(data) });
}

export async function getJobRun(id: string): Promise<JobRun> {
  return request(`/jobs/${id}`);
}

export async function listJobRuns(): Promise<JobRun[]> {
  return request("/jobs");
}

export async function getDownloadUrl(id: string): Promise<{ download_url: string }> {
  return request(`/jobs/${id}/download`);
}

// ── Profiles ─────────────────────────────────────────────────────────────────

export interface ExperienceEntry {
  id: string;
  company_name: string;
  role_title: string;
  start_date: string | null;
  end_date: string | null;
  location: string | null;
  context: string | null;
  contribution: string | null;
  outcomes: string | null;
  methods: string | null;
  is_complete: boolean;
  fields_completed: number;
}

export interface CandidateProfile {
  id: string;
  headline: string | null;
  location: string | null;
  status: string;
  global_context: string | null;
  preferences: Record<string, unknown> | null;
  experiences: ExperienceEntry[];
  cv_id: string | null;
  created_at: string;
  updated_at: string;
}

export async function updateProfilePreferences(
  profileId: string,
  preferences: {
    regions?: string[];
    roles?: string[];
    sectors?: string[];
    seniority?: string[];
    salaryMin?: string;
  },
): Promise<CandidateProfile> {
  // This endpoint has /api/v1 baked in
  const token = getToken();
  const res = await fetch(`/api/v1/profiles/${profileId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ preferences }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Save failed");
  }
  return res.json();
}

export interface ExtractJDResponse {
  url: string;
  jd_text: string;
  char_count: number;
}

export async function extractJD(url: string): Promise<ExtractJDResponse> {
  return request("/jobs/extract-jd", { method: "POST", body: JSON.stringify({ url }) });
}



export async function getActiveProfile(): Promise<CandidateProfile | null> {
  try {
    return await request("/profiles/active");
  } catch {
    return null;
  }
}

export async function createProfile(data: { headline?: string }): Promise<CandidateProfile> {
  return request("/profiles", { method: "POST", body: JSON.stringify(data) });
}

export async function updateProfile(profileId: string, data: Record<string, unknown>): Promise<CandidateProfile> {
  return request(`/profiles/${profileId}`, { method: "PATCH", body: JSON.stringify(data) });
}

export async function addExperience(profileId: string, data: Record<string, string>): Promise<ExperienceEntry> {
  return request(`/profiles/${profileId}/experiences`, { method: "POST", body: JSON.stringify(data) });
}

export async function updateExperience(profileId: string, expId: string, data: Record<string, string>): Promise<ExperienceEntry> {
  return request(`/profiles/${profileId}/experiences/${expId}`, { method: "PATCH", body: JSON.stringify(data) });
}

export async function deleteExperience(profileId: string, expId: string): Promise<void> {
  return request(`/profiles/${profileId}/experiences/${expId}`, { method: "DELETE" });
}

export async function importLinkedIn(profileId: string, linkedinUrl: string): Promise<Record<string, unknown>> {
  const token = getToken();
  const res = await fetch(`/api/v1/profiles/${profileId}/import-linkedin`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ linkedin_url: linkedinUrl }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Import failed: ${res.status}`);
  }
  return res.json();
}

export async function importCVToProfile(profileId: string, cvId: string): Promise<Record<string, unknown>> {
  // This endpoint has /api/v1 baked into the route — use raw fetch
  const token = getToken();
  const res = await fetch(`/api/v1/profiles/${profileId}/import-cv`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ cv_id: cvId }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Import failed: ${res.status}`);
  }
  return res.json();
}

export async function applyImportToProfile(
  profileId: string,
  importedData: Record<string, unknown>,
  overwrite: boolean = true,
): Promise<unknown> {
  // This endpoint has /api/v1 baked into the route — use raw fetch
  const token = getToken();
  const res = await fetch(`/api/v1/profiles/${profileId}/apply-import`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ imported: importedData, overwrite_existing: overwrite }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Apply failed: ${res.status}`);
  }
  return res.json();
}

/** Full chain: upload CV → parse → extract → populate profile. One call to backend. */
export async function uploadAndPopulateProfile(
  file: File,
): Promise<{ cvId: string; profileId: string; extracted: Record<string, unknown> }> {
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/quickstart/upload-and-populate`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Upload failed: ${res.status}`);
  }

  const data = await res.json();
  return {
    cvId: data.cv_id,
    profileId: data.profile_id,
    extracted: data.extracted || {},
  };
}

// ── Email Integration ────────────────────────────────────────────────────────

export async function connectEmail(provider: "gmail" | "outlook"): Promise<{ auth_url: string }> {
  return request("/email-integration/connect", {
    method: "POST",
    body: JSON.stringify({ provider }),
  });
}

export async function listEmailAccounts(): Promise<{ accounts: unknown[]; total: number }> {
  return request("/email-integration/accounts");
}

// ── Credits ──────────────────────────────────────────────────────────────────

export async function getCreditBalance(): Promise<{ balance: number; lifetime_purchased: number; lifetime_spent: number }> {
  return request("/credits/balance");
}

export async function getCreditPricing(): Promise<{ action: string; credits: number; display: string }[]> {
  return request("/credits/pricing");
}

// ── Outreach ─────────────────────────────────────────────────────────────────

export async function generateOutreach(data: {
  company: string;
  role: string;
  jd_text?: string;
  jd_url?: string;
  tone?: string;
}): Promise<{ linkedin_note: string; cold_email: string; follow_up: string }> {
  return request("/outreach/generate", { method: "POST", body: JSON.stringify(data) });
}
