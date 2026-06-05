"use client";

import Link from "next/link";
import { ArrowRight, Brain, GitBranch, MessageSquare, Target } from "lucide-react";
import { getGitHubAuthUrl } from "@/lib/api";

export default function HomePage() {
  return (
    <main className="min-h-screen">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2 text-xl font-bold">
          <Brain className="h-8 w-8 text-brand-500" />
          Career Copilot AI
        </div>
        <Link href="/login" className="btn-primary">
          Get Started
        </Link>
      </nav>

      <section className="mx-auto max-w-4xl px-6 py-20 text-center">
        <h1 className="mb-6 text-5xl font-bold leading-tight">
          Your Agentic Career Coach
          <span className="block text-brand-500">with Memory</span>
        </h1>
        <p className="mb-10 text-lg text-white/70">
          Tell it &quot;I want a Google internship&quot; — it analyzes your resume and GitHub,
          finds skill gaps, builds a roadmap, conducts mock interviews, and tracks your progress.
        </p>
        <a href={getGitHubAuthUrl()} className="btn-primary inline-flex items-center gap-2 text-lg">
          Sign in with GitHub <ArrowRight className="h-5 w-5" />
        </a>
      </section>

      <section className="mx-auto grid max-w-5xl gap-6 px-6 pb-20 md:grid-cols-3">
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
