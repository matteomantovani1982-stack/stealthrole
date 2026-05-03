/**
 * Shared UI constants for the StealthRole frontend.
 *
 * Design tokens from the approved Claude Designer artboards.
 * Light theme for dashboard, dark theme for login only.
 */

/* ── Design tokens (mirrors sr-app-shell.jsx SR object) ── */

export const SR = {
  bg: "#f4f5fb",
  bgDark: "#03040f",
  panel: "#ffffff",
  panelSoft: "#fafbff",
  border: "rgba(15,18,40,0.08)",
  border2: "rgba(15,18,40,0.14)",
  divider: "rgba(15,18,40,0.06)",
  ink: "#0c1030",
  ink2: "rgba(12,16,48,0.82)",
  ink3: "rgba(12,16,48,0.62)",
  ink4: "rgba(12,16,48,0.45)",
  ink5: "rgba(12,16,48,0.30)",
  brand: "#5B6CFF",
  brand2: "#7F8CFF",
  brandDeep: "#4754E8",
  violet: "#9F7AEA",
  brandTint: "rgba(91,108,255,0.08)",
  brandTint2: "rgba(91,108,255,0.14)",
  green: "#22c55e",
  amber: "#fbbf24",
  red: "#ef4444",
} as const;

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
  rejected: "#ef4444",
};

export const STAGE_TINTS: Record<string, string> = {
  watching: "rgba(77,142,245,0.06)",
  applied: "rgba(167,139,250,0.06)",
  interview: "rgba(34,197,94,0.07)",
  offer: "rgba(251,191,36,0.08)",
  rejected: "rgba(239,68,68,0.04)",
};

export const TRIGGER_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  funding: { bg: "rgba(34,197,94,0.08)", text: "#16a34a", dot: "#22c55e" },
  leadership: { bg: "rgba(77,142,245,0.08)", text: "#2e6dd9", dot: "#4d8ef5" },
  expansion: { bg: "rgba(251,191,36,0.08)", text: "#ca8a04", dot: "#fbbf24" },
  hiring: { bg: "rgba(167,139,250,0.08)", text: "#7c3aed", dot: "#a78bfa" },
  product: { bg: "rgba(236,72,153,0.08)", text: "#db2777", dot: "#ec4899" },
  velocity: { bg: "rgba(251,146,60,0.08)", text: "#ea580c", dot: "#fb923c" },
  distress: { bg: "rgba(239,68,68,0.08)", text: "#dc2626", dot: "#ef4444" },
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
