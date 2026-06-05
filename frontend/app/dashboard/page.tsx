"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  api,
  Goal,
  Profile,
  Roadmap,
  User,
} from "@/lib/api";
import {
  AlertTriangle,
  Brain,
  CheckCircle,
  LogOut,
  MessageSquare,
  Target,
  TrendingUp,
} from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [goal, setGoal] = useState<Goal | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [progress, setProgress] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    Promise.all([
      api.getMe(),
      api.getActiveGoal(),
      api.getAnalysis(),
      api.getProgress().catch(() => null),
    ])
      .then(async ([u, g, p, prog]) => {
        setUser(u);
        setGoal(g);
        setProfile(p);
        if (prog) setProgress(prog.summary);
        if (g) {
          const rm = await api.getLatestRoadmap(g.id).catch(() => null);
          setRoadmap(rm);
        }
      })
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  function logout() {
    localStorage.removeItem("token");
    router.push("/");
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      </main>
    );
  }

  const gaps = profile?.gap_analysis;

  return (
    <main className="min-h-screen">
      <nav className="border-b border-white/10 px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div className="flex items-center gap-2 font-bold">
            <Brain className="h-6 w-6 text-brand-500" />
            Career Copilot
          </div>
          <div className="flex items-center gap-4">
            {user?.avatar_url && (
              <img src={user.avatar_url} alt="" className="h-8 w-8 rounded-full" />
            )}
            <span className="text-sm text-white/60">@{user?.github_username}</span>
            <button onClick={logout} className="text-white/40 hover:text-white">
              <LogOut className="h-5 w-5" />
            </button>
          </div>
        </div>
      </nav>

      <div className="mx-auto max-w-6xl px-6 py-8">
        {goal && (
          <div className="card mb-8">
            <div className="flex items-center gap-3">
              <Target className="h-6 w-6 text-brand-500" />
              <div>
                <h1 className="text-xl font-bold">
                  {goal.target_company} — {goal.target_role}
                </h1>
                <p className="text-white/60 capitalize">{goal.level.replace("_", " ")}</p>
              </div>
              {gaps?.readiness_score !== undefined && (
                <div className="ml-auto text-right">
                  <p className="text-3xl font-bold text-brand-500">
                    {gaps.readiness_score.toFixed(1)}
                  </p>
                  <p className="text-xs text-white/40">Readiness / 10</p>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="mb-8 grid gap-6 md:grid-cols-2">
          <div className="card">
            <h2 className="mb-4 flex items-center gap-2 font-semibold">
              <AlertTriangle className="h-5 w-5 text-yellow-400" />
              Critical Gaps
            </h2>
            <ul className="space-y-2">
              {gaps?.critical_gaps?.length ? (
                gaps.critical_gaps.map((g, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-white/70">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-yellow-400" />
                    {g}
                  </li>
                ))
              ) : (
                <li className="text-sm text-white/40">Run analysis to see gaps</li>
              )}
            </ul>
          </div>

          <div className="card">
            <h2 className="mb-4 flex items-center gap-2 font-semibold">
              <CheckCircle className="h-5 w-5 text-green-400" />
              Strengths
            </h2>
            <ul className="space-y-2">
              {gaps?.strengths?.length ? (
                gaps.strengths.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-white/70">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-green-400" />
                    {s}
                  </li>
                ))
              ) : (
                <li className="text-sm text-white/40">Run analysis to see strengths</li>
              )}
            </ul>
          </div>
        </div>

        {roadmap && (
          <div className="card mb-8">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-semibold">{roadmap.title}</h2>
              <Link href={`/roadmap/${roadmap.id}`} className="text-sm text-brand-500 hover:underline">
                View Full Roadmap
              </Link>
            </div>
            <div className="space-y-3">
              {roadmap.milestones?.slice(0, 3).map((m, i) => (
                <div key={i} className="rounded-lg bg-white/5 p-4">
                  <p className="font-medium">
                    Week {m.week_start}-{m.week_end}: {m.title}
                  </p>
                  <p className="mt-1 text-sm text-white/50">{m.description}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {progress && (
          <div className="card mb-8">
            <h2 className="mb-2 flex items-center gap-2 font-semibold">
              <TrendingUp className="h-5 w-5 text-brand-500" />
              Progress Summary
            </h2>
            <p className="text-sm text-white/70">{progress}</p>
          </div>
        )}

        <div className="flex gap-4">
          <Link
            href="/interview/new"
            className="btn-primary inline-flex items-center gap-2"
          >
            <MessageSquare className="h-5 w-5" />
            Start Mock Interview
          </Link>
          <Link href="/onboarding" className="btn-secondary">
            Update Goal
          </Link>
        </div>
      </div>
    </main>
  );
}
