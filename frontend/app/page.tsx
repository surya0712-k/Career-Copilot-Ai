"use client";

import Link from "next/link";
import { ArrowRight, Brain, GitBranch, MessageSquare, Target } from "lucide-react";
import { getGitHubAuthUrl } from "@/lib/api";

export default function HomePage() {
  return (
    <main className="min-h-screen min-h-[100dvh]">
      <nav className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8 lg:py-6">
        <div className="flex min-w-0 items-center gap-2 text-base font-bold sm:text-xl">
          <Brain className="h-7 w-7 shrink-0 text-brand-500 sm:h-8 sm:w-8" />
          <span className="truncate">Career Copilot AI</span>
        </div>
        <Link href="/login" className="btn-primary shrink-0 text-sm sm:text-base">
          Get Started
        </Link>
      </nav>

      <section className="mx-auto max-w-4xl px-4 py-12 text-center sm:px-6 sm:py-16 md:py-20 lg:max-w-5xl lg:py-24">
        <h1 className="mb-4 text-3xl font-bold leading-tight sm:mb-6 sm:text-4xl md:text-5xl lg:text-6xl">
          Your Agentic Career Coach
          <span className="block text-brand-500">with Memory</span>
        </h1>
        <p className="mb-8 text-base text-white/70 sm:mb-10 sm:text-lg">
          Tell it &quot;I want a Google internship&quot; — it analyzes your resume and GitHub,
          finds skill gaps, builds a roadmap, conducts mock interviews, and tracks your progress.
        </p>
        <a href={getGitHubAuthUrl()} className="btn-primary inline-flex w-full max-w-sm items-center justify-center gap-2 sm:w-auto sm:text-lg">
          Sign in with GitHub <ArrowRight className="h-5 w-5" />
        </a>
      </section>

      <section className="mx-auto grid max-w-6xl gap-4 px-4 pb-16 sm:gap-6 sm:px-6 sm:pb-20 md:grid-cols-2 lg:grid-cols-3 lg:gap-8 lg:px-8 lg:pb-24">
        {[
          {
            icon: Target,
            title: "Gap Analysis",
            desc: "Compares your profile against target role requirements using MCP research.",
          },
          {
            icon: GitBranch,
            title: "Personalized Roadmap",
            desc: "Week-by-week learning plan based on your specific weaknesses.",
          },
          {
            icon: MessageSquare,
            title: "Mock Interviews",
            desc: "AI interviewer that adapts questions and tracks improvement over time.",
          },
        ].map(({ icon: Icon, title, desc }) => (
          <div key={title} className="card">
            <Icon className="mb-4 h-8 w-8 text-brand-500" />
            <h3 className="mb-2 text-lg font-semibold">{title}</h3>
            <p className="text-sm text-white/60">{desc}</p>
          </div>
        ))}
      </section>
    </main>
  );
}
