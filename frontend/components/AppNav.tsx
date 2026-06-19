"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain, Home, LogOut, MessageSquare, Mic, Target } from "lucide-react";
import { User } from "@/lib/api";

const DESKTOP_LINKS = [
  { href: "/dashboard", label: "Dashboard", icon: Home },
  { href: "/coach", label: "Coach", icon: Brain },
  { href: "/interview/voice", label: "Voice", icon: Mic },
  { href: "/interview/new", label: "Text", icon: MessageSquare },
  { href: "/onboarding", label: "Goal", icon: Target },
] as const;

interface AppNavProps {
  user?: User | null;
  onLogout?: () => void;
}

export function AppNav({ user, onLogout }: AppNavProps) {
  const pathname = usePathname();

  function isActive(href: string) {
    if (href === "/dashboard") return pathname === "/dashboard" || pathname === "/";
    if (href === "/onboarding") return pathname.startsWith("/onboarding");
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-[#0f172a]/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:py-3.5">
        <Link href="/dashboard" className="flex shrink-0 items-center gap-2 font-bold">
          <Brain className="h-6 w-6 text-brand-500 lg:h-7 lg:w-7" />
          <span className="text-sm sm:text-base">Career Copilot</span>
        </Link>

        <nav
          className="hidden flex-1 items-center justify-center gap-1 lg:flex xl:gap-2"
          aria-label="Main"
        >
          {DESKTOP_LINKS.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition xl:px-4 ${
                isActive(href)
                  ? "bg-brand-600/25 text-brand-300"
                  : "text-white/60 hover:bg-white/5 hover:text-white"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          ))}
        </nav>

        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          {user?.avatar_url && (
            <img
              src={user.avatar_url}
              alt=""
              className="h-8 w-8 rounded-full ring-2 ring-white/10 lg:h-9 lg:w-9"
            />
          )}
          <span className="hidden text-sm text-white/60 md:inline lg:max-w-[140px] lg:truncate xl:max-w-none">
            @{user?.github_username}
          </span>
          {onLogout && (
            <button
              onClick={onLogout}
              className="touch-target rounded-lg p-2 text-white/40 hover:bg-white/5 hover:text-white"
              aria-label="Sign out"
            >
              <LogOut className="h-5 w-5" />
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
