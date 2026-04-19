/**
 * Shared utility functions for the StealthRole frontend.
 *
 * Consolidates helpers that were previously duplicated across
 * page components and feature modules.
 */

// ── Time formatting ─────────────────────────────────────────────────────────

export function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

export function freshnessTag(firstSeen: string | null): string {
  if (!firstSeen) return "New";
  const days = Math.floor(
    (Date.now() - new Date(firstSeen).getTime()) / 86_400_000
  );
  if (days < 1) return "New";
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

// ── Name / avatar helpers ───────────────────────────────────────────────────

export function initials(name: string): string {
  return name
    .split(/[\s&]+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() || "")
    .join("");
}

const AVATAR_COLORS = ["blue", "teal", "amber", "purple", "coral"] as const;
export type AvatarColor = (typeof AVATAR_COLORS)[number];

export function avatarColor(name: string): AvatarColor {
  return AVATAR_COLORS[(name.charCodeAt(0) || 0) % AVATAR_COLORS.length];
}

// ── Greeting ────────────────────────────────────────────────────────────────

export function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning,";
  if (h < 18) return "Good afternoon,";
  return "Good evening,";
}

// ── Auth headers helper ─────────────────────────────────────────────────────
// Eliminates the 37+ scattered localStorage.getItem("sr_token") calls.

export function getAuthHeaders(includeContentType = true): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("sr_token") : null;
  const headers: Record<string, string> = {};
  if (includeContentType) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}
