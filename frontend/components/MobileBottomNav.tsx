"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain, Home, Mic, Target } from "lucide-react";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Home", icon: Home },
  { href: "/coach", label: "Coach", icon: Brain },
  { href: "/interview/voice", label: "Voice", icon: Mic },
  { href: "/onboarding", label: "Goal", icon: Target },
] as const;

export function MobileBottomNav() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-white/10 bg-[#0f172a]/95 backdrop-blur-lg md:max-w-none lg:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
      aria-label="Main navigation"
    >
      <div className="mx-auto flex max-w-lg items-stretch justify-around px-2 py-2">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active =
            pathname === href ||
            (href === "/dashboard" && pathname === "/") ||
            (href === "/onboarding" && pathname.startsWith("/onboarding"));
          return (
            <Link
              key={href}
              href={href}
              className={`flex min-h-[48px] min-w-[64px] flex-1 flex-col items-center justify-center gap-0.5 rounded-lg px-2 py-1 text-xs transition ${
                active ? "text-brand-400" : "text-white/50 hover:text-white/80"
              }`}
            >
              <Icon className={`h-5 w-5 ${active ? "text-brand-500" : ""}`} />
              <span className="font-medium">{label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
