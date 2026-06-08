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
import {
  AlertTriangle,
  Brain,
  CheckCircle,
  LogOut,
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
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-semibold">{roadmap.title}</h2>
              <Link href={`/roadmap/${roadmap.id}`} className="text-sm text-brand-500 hover:underline">
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

        <div className="flex flex-wrap gap-4">
          <Link href="/coach" className="btn-primary inline-flex items-center gap-2">
            <Brain className="h-5 w-5" />
            Ask Coach
          </Link>
          <Link
            href="/interview/voice"
            className="btn-primary inline-flex items-center gap-2"
          >
            <Mic className="h-5 w-5" />
            Voice Interview (LiveKit)
          </Link>
          <Link
            href="/interview/new"
            className="btn-secondary inline-flex items-center gap-2"
          >
            <MessageSquare className="h-5 w-5" />
            Text Interview
          </Link>
          {goal ? (
            <Link href="/onboarding" className="btn-secondary">
              Update Goal
            </Link>
          ) : (
            <Link href="/onboarding" className="btn-primary inline-flex items-center gap-2">
              <Target className="h-5 w-5" />
              Add a Goal
            </Link>
          )}
        </div>
      </div>
    </main>
  );
}
