"use client";

import { ReactNode } from "react";
import { AppNav } from "@/components/AppNav";
import { MobileBottomNav } from "@/components/MobileBottomNav";
import { User } from "@/lib/api";

interface AppShellProps {
  children: ReactNode;
  user?: User | null;
  onLogout?: () => void;
  /** narrow = coach/roadmap; default = dashboard width; wide = interview */
  width?: "narrow" | "default" | "wide";
  withNav?: boolean;
}

const WIDTH_CLASS = {
  narrow: "max-w-3xl",
  default: "max-w-6xl",
  wide: "max-w-4xl",
} as const;

export function AppShell({
  children,
  user,
  onLogout,
  width = "default",
  withNav = true,
}: AppShellProps) {
  return (
    <main className="min-h-screen min-h-[100dvh]">
      {withNav && <AppNav user={user} onLogout={onLogout} />}
      <div className={`page-container-nav mx-auto w-full ${WIDTH_CLASS[width]}`}>{children}</div>
      {withNav && <MobileBottomNav />}
    </main>
  );
}
