"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const NAV_ITEMS = [
  { href: "/", label: "Home", icon: HomeIcon },
  { href: "/scout", label: "Job Scout", icon: SearchIcon },
  { href: "/applications", label: "Applications", icon: KanbanIcon },
  { href: "/profile", label: "Profile", icon: UserIcon },
  { href: "/billing", label: "Billing", icon: CreditIcon },
  { href: "/settings", label: "Settings", icon: GearIcon },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  const initials =
    user?.full_name?.[0]?.toUpperCase() ||
    user?.email?.[0]?.toUpperCase() ||
    "?";

  return (
    <aside
      className="fixed left-0 top-0 bottom-0 w-[200px] flex flex-col z-30"
      style={{
        background: "rgba(255,255,255,0.96)",
        backdropFilter: "blur(12px)",
        borderRight: "1px solid rgba(15,18,40,0.08)",
        fontFamily: "Inter, system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5" style={{ padding: "22px 20px 28px" }}>
        <SRMark size={26} />
        <span
          className="text-[15px] font-bold"
          style={{ letterSpacing: -0.3, color: "#0c1030" }}
        >
          Stealth<span style={{ color: "#7F8CFF" }}>Role</span>
        </span>
      </div>

      {/* New Job CTA */}
      <div style={{ padding: "0 12px 18px" }}>
        <Link
          href="/new-job"
          className="flex items-center justify-center gap-1.5 w-full text-white text-[13px] font-semibold rounded-[10px] cursor-pointer"
          style={{
            padding: "10px 12px",
            background: "linear-gradient(135deg, #5B6CFF 0%, #7F8CFF 100%)",
            boxShadow: "0 6px 18px rgba(91,108,255,0.32)",
          }}
        >
          + New Job
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 flex flex-col gap-0.5" style={{ padding: "0 8px" }}>
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-[11px] rounded-[9px] text-[13px] no-underline"
              style={{
                padding: "9px 11px",
                fontWeight: active ? 600 : 500,
                color: active ? "#7F8CFF" : "rgba(12,16,48,0.55)",
                background: active ? "rgba(127,140,255,0.10)" : "transparent",
              }}
            >
              <item.icon active={active} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* User footer */}
      <div
        className="flex items-center gap-2.5"
        style={{
          padding: "14px 12px",
          borderTop: "1px solid rgba(15,18,40,0.08)",
        }}
      >
        <Link
          href="/profile"
          className="flex items-center gap-2.5 flex-1 min-w-0 no-underline"
        >
          <div
            className="w-[30px] h-[30px] rounded-full flex items-center justify-center text-[11px] font-bold flex-shrink-0"
            style={{
              background: "rgba(127,140,255,0.18)",
              color: "#7F8CFF",
            }}
          >
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <div
              className="text-[12px] font-medium truncate"
              style={{ color: "rgba(12,16,48,0.82)" }}
            >
              {user?.full_name || user?.email?.split("@")[0] || "User"}
            </div>
            <div
              className="text-[10px] truncate"
              style={{ color: "rgba(12,16,48,0.45)" }}
            >
              {user?.email || ""}
            </div>
          </div>
        </Link>
        <button
          onClick={logout}
          title="Sign out"
          aria-label="Sign out"
          className="flex-shrink-0 p-1 rounded-lg cursor-pointer border-0 bg-transparent"
          style={{ color: "rgba(12,16,48,0.45)" }}
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path
              d="M6 2H3a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M10 11l3-3-3-3M13 8H6"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </div>
    </aside>
  );
}

/* ── Brand mark ── */
function SRMark({ size = 24 }: { size?: number }) {
  return (
    <div
      className="rounded-md flex items-center justify-center flex-shrink-0 overflow-hidden"
      style={{
        width: size,
        height: size,
        background: "linear-gradient(135deg, #5B6CFF 0%, #9F7AEA 100%)",
        fontSize: size * 0.45,
        fontWeight: 800,
        color: "#fff",
        fontFamily: "'JetBrains Mono', ui-monospace, monospace",
        letterSpacing: 1,
      }}
    >
      SR
    </div>
  );
}

/* ── Inline SVG icons (16x16) ── */

function HomeIcon({ active }: { active: boolean }) {
  const c = active ? "#7F8CFF" : "rgba(12,16,48,0.45)";
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M2 8.5L8 3L14 8.5" stroke={c} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M3.5 7.5V13H6.5V10H9.5V13H12.5V7.5" stroke={c} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SearchIcon({ active }: { active: boolean }) {
  const c = active ? "#7F8CFF" : "rgba(12,16,48,0.45)";
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="7" cy="7" r="4.5" stroke={c} strokeWidth="1.5" />
      <path d="M10.5 10.5L14 14" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function KanbanIcon({ active }: { active: boolean }) {
  const c = active ? "#7F8CFF" : "rgba(12,16,48,0.45)";
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="2" y="2" width="3.5" height="12" rx="1" stroke={c} strokeWidth="1.5" />
      <rect x="6.25" y="2" width="3.5" height="8" rx="1" stroke={c} strokeWidth="1.5" />
      <rect x="10.5" y="2" width="3.5" height="10" rx="1" stroke={c} strokeWidth="1.5" />
    </svg>
  );
}

function UserIcon({ active }: { active: boolean }) {
  const c = active ? "#7F8CFF" : "rgba(12,16,48,0.45)";
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="5.5" r="3" stroke={c} strokeWidth="1.5" />
      <path d="M2.5 14C2.5 11.5 5 9.5 8 9.5C11 9.5 13.5 11.5 13.5 14" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function CreditIcon({ active }: { active: boolean }) {
  const c = active ? "#7F8CFF" : "rgba(12,16,48,0.45)";
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="2" y="4" width="12" height="9" rx="1.5" stroke={c} strokeWidth="1.5" />
      <path d="M2 7.5H14" stroke={c} strokeWidth="1.5" />
    </svg>
  );
}

function GearIcon({ active }: { active: boolean }) {
  const c = active ? "#7F8CFF" : "rgba(12,16,48,0.45)";
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="2" stroke={c} strokeWidth="1.5" />
      <path d="M8 1.5V3M8 13V14.5M1.5 8H3M13 8H14.5M3.05 3.05L4.11 4.11M11.89 11.89L12.95 12.95M12.95 3.05L11.89 4.11M4.11 11.89L3.05 12.95" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
