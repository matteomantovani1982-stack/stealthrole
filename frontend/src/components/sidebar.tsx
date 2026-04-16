"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const NAV_ITEMS = [
  { href: "/", label: "Home", icon: HomeIcon },
  { href: "/scout", label: "Job Scout", icon: SearchIcon },
  { href: "/applications", label: "Applications", icon: KanbanIcon },
  { href: "/messages", label: "Messages", icon: MessageIcon },
  { href: "/profile", label: "Profile", icon: UserIcon },
  { href: "/billing", label: "Billing", icon: CreditIcon },
  { href: "/settings", label: "Settings", icon: GearIcon },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[180px] border-r border-white/[0.06] flex flex-col z-30" style={{ background: "rgba(11,15,42,0.85)", backdropFilter: "blur(12px)" }}>
      {/* Logo */}
      <div className="px-5 pt-6 pb-8 flex items-center gap-2">
        <Image src="/images/sr-logo.png" alt="" width={24} height={24} className="rounded-md" />
        <span className="text-base font-bold tracking-tight text-white/90">
          Stealth<span className="text-[#7F8CFF]">Role</span>
        </span>
      </div>

      {/* New Job CTA */}
      <div className="px-3 mb-4">
        <Link
          href="/new-job"
          className="flex items-center justify-center gap-2 w-full py-2.5 text-white text-[13px] font-semibold rounded-lg transition-colors"
          style={{ background: "linear-gradient(135deg, #5B6CFF 0%, #7F8CFF 100%)" }}
        >
          + New Job
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 flex flex-col gap-0.5 px-2">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`
                flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] transition-colors
                ${
                  active
                    ? "bg-[#7F8CFF]/10 text-[#7F8CFF] font-semibold"
                    : "text-[#6B7194] hover:bg-white/[0.04] hover:text-[#8B92B0]"
                }
              `}
            >
              <item.icon active={active} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* User — avatar/name navigates to /profile, small icon button signs out */}
      <div className="px-3 py-4 border-t border-white/[0.06]">
        <div className="flex items-center gap-1.5">
          <Link
            href="/profile"
            className="flex items-center gap-2.5 flex-1 min-w-0 px-2 py-2 rounded-lg hover:bg-white/[0.04] transition-colors"
          >
            <div className="w-8 h-8 rounded-full bg-[#7F8CFF]/15 text-[#7F8CFF] flex items-center justify-center text-xs font-semibold flex-shrink-0">
              {user?.full_name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || "?"}
            </div>
            <div className="text-left min-w-0">
              <div className="text-[12px] font-medium text-white/80 truncate">
                {user?.full_name || user?.email?.split("@")[0] || "User"}
              </div>
              <div className="text-[11px] text-[#555C7A] truncate">
                {user?.email || ""}
              </div>
            </div>
          </Link>
          <button
            onClick={logout}
            title="Sign out"
            aria-label="Sign out"
            className="flex-shrink-0 p-2 rounded-lg text-[#555C7A] hover:bg-white/[0.04] hover:text-white/80 transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path d="M6 2H3a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M10 11l3-3-3-3M13 8H6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
      </div>
    </aside>
  );
}

// ── Inline SVG icons (16x16) ────────────────────────────────────────────────

function HomeIcon({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={active ? "text-[#7F8CFF]" : "text-[#555C7A]"}>
      <path d="M2 8.5L8 3L14 8.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M3.5 7.5V13H6.5V10H9.5V13H12.5V7.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function SearchIcon({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={active ? "text-[#7F8CFF]" : "text-[#555C7A]"}>
      <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M10.5 10.5L14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}

function KanbanIcon({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={active ? "text-[#7F8CFF]" : "text-[#555C7A]"}>
      <rect x="2" y="2" width="3.5" height="12" rx="1" stroke="currentColor" strokeWidth="1.5"/>
      <rect x="6.25" y="2" width="3.5" height="8" rx="1" stroke="currentColor" strokeWidth="1.5"/>
      <rect x="10.5" y="2" width="3.5" height="10" rx="1" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  );
}

function UserIcon({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={active ? "text-[#7F8CFF]" : "text-[#555C7A]"}>
      <circle cx="8" cy="5.5" r="3" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M2.5 14C2.5 11.5 5 9.5 8 9.5C11 9.5 13.5 11.5 13.5 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}

function CreditIcon({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={active ? "text-[#7F8CFF]" : "text-[#555C7A]"}>
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M9.5 5.5C9.5 5.5 9 4.5 8 4.5C6.5 4.5 5.5 5.5 5.5 6.5C5.5 7.5 6.5 8 8 8C9.5 8 10.5 8.5 10.5 9.5C10.5 10.5 9.5 11.5 8 11.5C7 11.5 6.5 10.5 6.5 10.5M8 3.5V4.5M8 11.5V12.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}

function MessageIcon({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={active ? "text-[#7F8CFF]" : "text-[#555C7A]"}>
      <path d="M2 3.5C2 2.67 2.67 2 3.5 2H12.5C13.33 2 14 2.67 14 3.5V10.5C14 11.33 13.33 12 12.5 12H5L2 14.5V3.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M5 6H11M5 8.5H9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}

function GearIcon({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={active ? "text-[#7F8CFF]" : "text-[#555C7A]"}>
      <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M8 1.5V3M8 13V14.5M1.5 8H3M13 8H14.5M3.05 3.05L4.11 4.11M11.89 11.89L12.95 12.95M12.95 3.05L11.89 4.11M4.11 11.89L3.05 12.95" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}
