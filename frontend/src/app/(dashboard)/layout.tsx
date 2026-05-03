"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/sidebar";
import ExtensionBanner from "@/components/extension-banner";
import { useAuth } from "@/lib/auth-context";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: "#f4f5fb" }}
      >
        <div className="w-6 h-6 border-2 border-[#5B6CFF] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div
      className="min-h-screen"
      style={{ background: "#f4f5fb", color: "#0c1030" }}
    >
      <Sidebar />
      <main className="ml-[200px]">{children}</main>
      <ExtensionBanner />
    </div>
  );
}
