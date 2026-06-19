"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  api,
  Goal,
  Profile,
  ProgressData,
  Roadmap,
  User,
} from "@/lib/api";
import { AppNav } from "@/components/AppNav";
import { MobileBottomNav } from "@/components/MobileBottomNav";
import {
  AlertTriangle,
  Brain,
  CheckCircle,
  MessageSquare,
  Mic,
  Target,
  TrendingUp,
} from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [goal, setGoal] = useState<Goal | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [loading, setLoading] = useState(true);
  const [roadmapLoading, setRoadmapLoading] = useState(false);

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
        if (prog) setProgress(prog);
        if (g) {
          const rm = await api.getLatestRoadmap(g.id).catch(() => null);
          setRoadmap(rm);
          if (!rm && localStorage.getItem("pendingAnalysisJob")) {
            setRoadmapLoading(true);
          }
        }
      })
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  useEffect(() => {
    if (!goal || roadmap || !roadmapLoading) return;

    let cancelled = false;
    const pendingJobId = localStorage.getItem("pendingAnalysisJob");

    const poll = async () => {
      try {
        const rm = await api.getLatestRoadmap(goal.id).catch(() => null);
        if (cancelled) return;
        if (rm) {
          setRoadmap(rm);
          setRoadmapLoading(false);
          localStorage.removeItem("pendingAnalysisJob");
          return;
        }
        if (pendingJobId) {
          try {
            const job = await api.getAnalysisJob(pendingJobId);
            if (job.status === "completed" && job.result?.roadmap_id) {
              const rmById = await api.getRoadmap(job.result.roadmap_id);
              setRoadmap(rmById);
              setRoadmapLoading(false);
              localStorage.removeItem("pendingAnalysisJob");
              return;
            }
            if (job.status === "failed") {
              setRoadmapLoading(false);
              localStorage.removeItem("pendingAnalysisJob");
              return;
            }
          } catch (err) {
            const message = err instanceof Error ? err.message : "";
            if (message.includes("Job not found")) {
              localStorage.removeItem("pendingAnalysisJob");
            }
          }
        }
      } catch {
        /* keep polling */
      }
      if (!cancelled) setTimeout(poll, 1500);
    };

    poll();
    return () => {
      cancelled = true;
    };
  }, [goal, roadmap, roadmapLoading]);

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
    <main className="min-h-screen min-h-[100dvh]">
      <AppNav user={user} onLogout={logout} />

      <div className="page-container-nav max-w-7xl">
        <div className="xl:grid xl:grid-cols-[minmax(0,1fr)_260px] xl:items-start xl:gap-10">
        <div className="min-w-0 space-y-6 sm:space-y-8">
        {!goal && (
          <div className="card mb-8 text-center">
            <Target className="mx-auto mb-4 h-12 w-12 text-brand-500" />
            <h1 className="mb-2 text-2xl font-bold">Welcome to Career Copilot</h1>
            <p className="mb-6 text-white/60">
              Add a career goal to upload your resume, run gap analysis, and get a personalized
              roadmap with practice tasks and application projects.
            </p>
            <Link href="/onboarding" className="btn-primary inline-flex items-center gap-2">
              <Target className="h-5 w-5" />
              Add a Goal
            </Link>
          </div>
        )}

        {goal && (
          <div className="card mb-6 sm:mb-8">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-3">
              <div className="flex min-w-0 flex-1 items-start gap-3">
                <Target className="mt-0.5 h-6 w-6 shrink-0 text-brand-500" />
                <div className="min-w-0">
                  <h1 className="text-lg font-bold leading-snug sm:text-xl">
                    {goal.target_company} — {goal.target_role}
                  </h1>
                  <p className="text-sm text-white/60 capitalize">{goal.level.replace("_", " ")}</p>
                </div>
              </div>
              {gaps?.readiness_score !== undefined && (
                <div className="flex items-center justify-between gap-3 rounded-lg bg-brand-600/10 px-4 py-3 md:ml-auto md:block md:bg-transparent md:p-0 md:text-right">
                  <span className="text-sm text-white/50 md:hidden">Readiness</span>
                  <div>
                    <p className="text-2xl font-bold text-brand-500 md:text-3xl lg:text-4xl">
                      {gaps.readiness_score.toFixed(1)}
                    </p>
                    <p className="text-xs text-white/40">Readiness / 10</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="grid gap-6 md:grid-cols-2 lg:gap-8">
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

        {roadmapLoading && !roadmap && (
          <div className="card mb-8">
            <p className="text-sm text-brand-300">Building your personalized roadmap...</p>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
              <div className="h-full w-1/3 animate-pulse bg-brand-500" />
            </div>
          </div>
        )}

        {roadmap && (
          <div className="card mb-8">
            <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="font-semibold leading-snug">{roadmap.title}</h2>
              <Link
                href={`/roadmap/${roadmap.id}`}
                className="btn-secondary w-full text-center text-sm sm:w-auto"
              >
                View Full Roadmap
              </Link>
            </div>
            {roadmap.completion_pct !== undefined && (
              <div className="mb-4">
                <div className="mb-1 flex justify-between text-xs text-white/50">
                  <span>Completion</span>
                  <span>{roadmap.completion_pct}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full bg-brand-500"
                    style={{ width: `${roadmap.completion_pct}%` }}
                  />
                </div>
              </div>
            )}
            <div className="space-y-3">
              {roadmap.milestones?.slice(0, 3).map((m, i) => (
                <div key={i} className="rounded-lg bg-white/5 p-4">
                  <p className="font-medium">
                    Week {i + 1}: {m.title}
                  </p>
                  <p className="mt-1 text-sm text-white/50">{m.description}</p>
                </div>
              ))}
              {(roadmap.milestones?.length ?? 0) > 3 && (
                <Link
                  href={`/roadmap/${roadmap.id}`}
                  className="block text-center text-sm text-brand-400 hover:text-brand-300 hover:underline"
                >
                  ...more ({roadmap.milestones!.length - 3} more week
                  {roadmap.milestones!.length - 3 === 1 ? "" : "s"})
                </Link>
              )}
            </div>
          </div>
        )}

        {progress && (
          <div className="card mb-8">
            <h2 className="mb-4 flex items-center gap-2 font-semibold">
              <TrendingUp className="h-5 w-5 text-brand-500" />
              Progress Summary
            </h2>
            <p className="mb-4 text-sm text-white/70">{progress.summary}</p>
            <div className="grid gap-4 sm:grid-cols-3 text-sm">
              <div>
                <p className="text-white/40">Roadmap</p>
                <p className="text-lg font-semibold text-brand-400">{progress.completion_pct}%</p>
              </div>
              <div>
                <p className="text-white/40">Study hours</p>
                <p className="text-lg font-semibold">{progress.total_study_hours.toFixed(1)}h</p>
              </div>
              <div>
                <p className="text-white/40">Topics done</p>
                <p className="text-lg font-semibold">{progress.completed_topics.length}</p>
              </div>
            </div>
            {progress.weak_areas.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {progress.weak_areas.slice(0, 5).map((w) => (
                  <span
                    key={w.topic}
                    className="rounded-full bg-red-500/10 px-3 py-1 text-xs text-red-300"
                  >
                    {w.topic} ({w.count}x)
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="action-grid xl:hidden">
          <Link href="/coach" className="btn-primary">
            <Brain className="h-5 w-5" />
            Ask Coach
          </Link>
          <Link href="/interview/voice" className="btn-primary">
            <Mic className="h-5 w-5" />
            Voice Interview
          </Link>
          <Link href="/interview/new" className="btn-secondary">
            <MessageSquare className="h-5 w-5" />
            Text Interview
          </Link>
          {goal ? (
            <Link href="/onboarding" className="btn-secondary">
              Update Goal
            </Link>
          ) : (
            <Link href="/onboarding" className="btn-primary">
              <Target className="h-5 w-5" />
              Add a Goal
            </Link>
          )}
        </div>
        </div>

        <aside className="hidden xl:block">
          <div className="card sticky top-24 space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-white/40">Quick actions</p>
            <Link href="/coach" className="btn-primary w-full">
              <Brain className="h-5 w-5" />
              Ask Coach
            </Link>
            <Link href="/interview/voice" className="btn-primary w-full">
              <Mic className="h-5 w-5" />
              Voice Interview
            </Link>
            <Link href="/interview/new" className="btn-secondary w-full">
              <MessageSquare className="h-5 w-5" />
              Text Interview
            </Link>
            <Link href="/onboarding" className="btn-secondary w-full">
              <Target className="h-5 w-5" />
              {goal ? "Update Goal" : "Add a Goal"}
            </Link>
            {roadmap && (
              <Link href={`/roadmap/${roadmap.id}`} className="btn-secondary w-full text-center text-sm">
                View Roadmap
              </Link>
            )}
          </div>
        </aside>
        </div>
      </div>
      <MobileBottomNav />
    </main>
  );
}
