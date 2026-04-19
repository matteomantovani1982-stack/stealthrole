/**
 * Shared UI constants for the StealthRole frontend.
 *
 * Centralizes color maps, stage configs, and other constants
 * that were previously scattered across page components.
 */

export const TIER_COLORS: Record<string, string> = {
  high: "#4d8ef5",
  medium: "#a78bfa",
  low: "#22c55e",
};

export const STAGE_COLORS: Record<string, string> = {
  watching: "#4d8ef5",
  applied: "#a78bfa",
  interview: "#22c55e",
  offer: "#fbbf24",
  closed: "rgba(255,255,255,0.3)",
};

export const TRIGGER_COLORS: Record<string, string> = {
  funding: "bg-green-50 text-green-700",
  regulatory: "bg-red-50 text-red-700",
  expansion: "bg-blue-50 text-blue-700",
  competitive: "bg-amber-50 text-amber-700",
  lifecycle: "bg-purple-50 text-purple-700",
  industry_shift: "bg-cyan-50 text-cyan-700",
  ma_activity: "bg-orange-50 text-orange-700",
};

export const SOURCE_LABELS: Record<string, string> = {
  job_board: "Job Board",
  referral: "Referral",
  cold_outreach: "Cold Outreach",
  recruiter: "Recruiter",
  company_site: "Company Site",
  linkedin: "LinkedIn",
  other: "Other",
};
