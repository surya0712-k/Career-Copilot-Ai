"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, DsaLanguage, Goal, Milestone, PracticeProject, Roadmap } from "@/lib/api";
import { AppNav } from "@/components/AppNav";
import { MobileBottomNav } from "@/components/MobileBottomNav";
import { PageHeader } from "@/components/PageHeader";
import { displayProjectTitle, isMockInterviewTask, partitionTasks } from "@/lib/roadmapTasks";
import { CheckCircle2, Circle, Mic, Plus, RefreshCw, Trash2 } from "lucide-react";

const DSA_LANGUAGES: { value: DsaLanguage; label: string }[] = [
  { value: "python", label: "Python" },
  { value: "java", label: "Java" },
  { value: "cpp", label: "C++" },
  { value: "javascript", label: "JavaScript" },
  { value: "go", label: "Go" },
];

function renderTaskRow(
  t: NonNullable<Milestone["tasks"]>[number],
  j: number,
  m: Milestone,
  toggleTask: (milestoneId: string, taskIndex: number, completed: boolean) => void,
  startVoiceInterview: (milestoneId?: string) => void,
) {
  return (
    <li key={j} className="flex items-start gap-2 text-sm">
      <button
        type="button"
        onClick={() => m.id && toggleTask(m.id, j, !!t.completed)}
        className="mt-0.5 shrink-0"
        disabled={!m.id}
        aria-label={t.completed ? "Mark incomplete" : "Mark complete"}
      >
        {t.completed ? (
          <CheckCircle2 className="h-5 w-5 text-green-400 hover:text-green-300" />
        ) : (
          <Circle className="h-5 w-5 text-white/30 hover:text-brand-400" />
        )}
      </button>
      <div className={`flex-1 ${t.completed ? "text-white/40 line-through" : ""}`}>
        <p className="font-medium">{t.title}</p>
        {t.description && <p className="text-white/50">{t.description}</p>}
        {isMockInterviewTask(t.title) && m.id && (
          <button
            type="button"
            onClick={() => startVoiceInterview(m.id)}
            className="mt-1 inline-flex items-center gap-1 text-xs text-brand-400 hover:underline"
          >
            <Mic className="h-3 w-3" />
            Start voice mock interview
          </button>
        )}
      </div>
    </li>
  );
}

export default function RoadmapPage() {
  const params = useParams();
  const router = useRouter();
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [goal, setGoal] = useState<Goal | null>(null);
  const [loading, setLoading] = useState(true);
  const [recalculating, setRecalculating] = useState(false);
  const [dsaLanguage, setDsaLanguage] = useState<DsaLanguage>("python");
  const [savingLang, setSavingLang] = useState(false);
  const [customProjects, setCustomProjects] = useState<PracticeProject[]>([]);
  const [savingProjects, setSavingProjects] = useState(false);
  const [projectsSaved, setProjectsSaved] = useState(false);
  const [user, setUser] = useState<Awaited<ReturnType<typeof api.getMe>> | null>(null);

  const load = useCallback(async () => {
    const rm = await api.getRoadmap(params.id as string);
    setRoadmap(rm);
    const [g, u] = await Promise.all([api.getActiveGoal(), api.getMe().catch(() => null)]);
    setGoal(g);
    setUser(u);
    if (g?.id === rm.goal_id) {
      const saved = await api.getPracticeProjects(g.id).catch(() => []);
      setCustomProjects(saved);
    }
    const profile = await api.getProfile().catch(() => null);
    if (profile?.preferred_dsa_language) {
      setDsaLanguage(profile.preferred_dsa_language as DsaLanguage);
    }
  }, [params.id]);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      setLoading(false);
      return;
    }
    load().finally(() => setLoading(false));
  }, [load, router]);

  async function toggleTask(milestoneId: string, taskIndex: number, completed: boolean) {
    if (!roadmap || !milestoneId) return;
    await api.completeTask(roadmap.id, milestoneId, taskIndex, 0, !completed);
    await load();
  }

  async function recalculate() {
    if (!roadmap) return;
    setRecalculating(true);
    try {
      const updated = await api.recalculateRoadmap(roadmap.id);
      window.location.href = `/roadmap/${updated.id}`;
    } finally {
      setRecalculating(false);
    }
  }

  async function saveLanguage(lang: DsaLanguage) {
    setDsaLanguage(lang);
    setSavingLang(true);
    try {
      await api.updateProfilePreferences(lang);
    } finally {
      setSavingLang(false);
    }
  }

  async function saveProjects() {
    if (!goal) return;
    const filtered = customProjects.filter((p) => p.name.trim());
    setSavingProjects(true);
    setProjectsSaved(false);
    try {
      await api.updatePracticeProjects(goal.id, filtered);
      setCustomProjects(filtered);
      setProjectsSaved(true);
    } finally {
      setSavingProjects(false);
    }
  }

  function addCustomProjectSlot() {
    if (customProjects.length >= 2) return;
    setCustomProjects((prev) => [...prev, { name: "", description: "" }]);
    setProjectsSaved(false);
  }

  function removeCustomProject(index: number) {
    setCustomProjects((prev) => prev.filter((_, i) => i !== index));
    setProjectsSaved(false);
  }

  function startVoiceInterview(milestoneId?: string) {
    if (!roadmap) return;
    const qs = new URLSearchParams({ roadmapId: roadmap.id });
    if (milestoneId) qs.set("milestoneId", milestoneId);
    if (goal?.id) qs.set("goalId", goal.id);
    router.push(`/interview/voice?${qs.toString()}`);
  }

  function logout() {
    localStorage.removeItem("token");
    router.push("/");
  }

  function updateProject(index: number, field: keyof PracticeProject, value: string) {
    setCustomProjects((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
    setProjectsSaved(false);
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      </main>
    );
  }

  if (!roadmap) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-white/60">Roadmap not found</p>
      </main>
    );
  }

  const pct = roadmap.completion_pct ?? 0;

  return (
    <main className="min-h-screen min-h-[100dvh]">
      <AppNav user={user} onLogout={logout} />
      <div className="page-container-nav mx-auto w-full max-w-3xl lg:max-w-4xl xl:max-w-5xl">
        <PageHeader
          backHref="/dashboard"
          backLabel="Back to Dashboard"
          title={roadmap.title}
          subtitle={`Status: ${roadmap.status} · v${roadmap.version ?? 1}`}
        />

        <div className="card mb-6">
          <div className="flex flex-col gap-4 md:flex-row md:flex-wrap md:items-end lg:justify-between">
            <div className="w-full flex-1 md:min-w-[200px] lg:max-w-sm">
              <label className="mb-2 block text-sm font-medium">DSA coding language</label>
              <select
                className="select input w-full sm:max-w-xs"
                value={dsaLanguage}
                onChange={(e) => saveLanguage(e.target.value as DsaLanguage)}
                disabled={savingLang}
              >
                {DSA_LANGUAGES.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </select>
              <p className="mt-2 text-xs text-white/50">
                Saved to your profile and memory for mock interviews. Click Recalculate to update task language.
              </p>
            </div>
            <button
              onClick={recalculate}
              disabled={recalculating}
              className="btn-primary w-full gap-2 text-sm md:w-auto"
            >
              <RefreshCw className={`h-4 w-4 ${recalculating ? "animate-spin" : ""}`} />
              Recalculate roadmap
            </button>
          </div>
        </div>

        <div className="card mb-8">
          <div className="mb-2 flex justify-between text-sm">
            <span className="text-white/60">Progress</span>
            <span className="font-medium text-brand-400">{pct}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/10">
            <div className="h-full bg-brand-500 transition-all" style={{ width: `${pct}%` }} />
          </div>
        </div>

        <div className="space-y-6">
          {roadmap.milestones?.map((m, i) => {
            const { practice, projects } = partitionTasks(m.tasks ?? []);

            return (
              <div key={m.id ?? i} className="card">
                <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex min-w-0 items-start gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-600 text-sm font-bold">
                      {i + 1}
                    </div>
                    <div className="min-w-0">
                      <h2 className="font-semibold leading-snug">{m.title}</h2>
                      <p className="text-sm text-white/50">
                        Week {i + 1}
                        {m.status && m.status !== "pending" && (
                          <span className="ml-2 capitalize text-brand-400">· {m.status}</span>
                        )}
                      </p>
                    </div>
                  </div>
                  {m.id && (
                    <button
                      type="button"
                      onClick={() => startVoiceInterview(m.id)}
                      className="btn-primary w-full shrink-0 gap-2 text-xs sm:w-auto"
                    >
                      <Mic className="h-4 w-4" />
                      Voice mock
                    </button>
                  )}
                </div>
                {m.description && <p className="mb-4 text-sm text-white/70">{m.description}</p>}
                {practice.length > 0 && (
                  <ul className="space-y-2">
                    {practice.map(({ task, index }) =>
                      renderTaskRow(task, index, m, toggleTask, startVoiceInterview),
                    )}
                  </ul>
                )}

                {projects.length > 0 && (
                  <div className="mt-4 space-y-3">
                    <h3 className="text-sm font-semibold text-brand-300">Application projects</h3>
                    {projects.map(({ task, index }, projectIdx) => (
                      <div key={index} className="rounded-lg border border-brand-500/20 bg-brand-600/5 p-3">
                        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-brand-400">
                          Project {projectIdx + 1}
                        </p>
                        <ul className="space-y-0">
                          <li className="flex items-start gap-2 text-sm">
                            <button
                              type="button"
                              onClick={() => m.id && toggleTask(m.id, index, !!task.completed)}
                              className="mt-0.5 shrink-0"
                              disabled={!m.id}
                              aria-label={task.completed ? "Mark incomplete" : "Mark complete"}
                            >
                              {task.completed ? (
                                <CheckCircle2 className="h-5 w-5 text-green-400 hover:text-green-300" />
                              ) : (
                                <Circle className="h-5 w-5 text-white/30 hover:text-brand-400" />
                              )}
                            </button>
                            <div className={`flex-1 ${task.completed ? "text-white/40 line-through" : ""}`}>
                              <p className="font-medium">{displayProjectTitle(task.title)}</p>
                              {task.description && <p className="text-white/50">{task.description}</p>}
                            </div>
                          </li>
                        </ul>
                      </div>
                    ))}
                  </div>
                )}

                {m.success_criteria && (
                  <p className="mt-3 text-xs text-white/40">Success: {m.success_criteria}</p>
                )}
              </div>
            );
          })}
        </div>

        {goal && (
          <div className="card mt-6">
            <h3 className="mb-1 text-sm font-semibold">Custom projects for mock interviews</h3>
            <p className="mb-4 text-xs text-white/50">
              Roadmap application projects appear above as Project 1, Project 2, etc. Add up to 2 of your
              own here for voice mock interviews only — not added to your resume.
            </p>

            {customProjects.length > 0 && (
              <div className="mb-4 space-y-3">
                <p className="text-xs font-medium text-white/70">Your custom projects</p>
                {customProjects.map((p, idx) => (
                  <div key={idx} className="space-y-2 rounded-md bg-white/5 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs text-white/40">Custom project {idx + 1}</span>
                      <button
                        type="button"
                        onClick={() => removeCustomProject(idx)}
                        className="text-white/40 hover:text-red-400"
                        aria-label="Remove project"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                    <input
                      className="input w-full"
                      placeholder="Project name"
                      value={p.name}
                      onChange={(e) => updateProject(idx, "name", e.target.value)}
                    />
                    <textarea
                      className="input min-h-[72px] w-full resize-y"
                      placeholder="What you built, tech stack, challenges..."
                      value={p.description}
                      onChange={(e) => updateProject(idx, "description", e.target.value)}
                    />
                  </div>
                ))}
              </div>
            )}

            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
              {customProjects.length < 2 && (
                <button
                  type="button"
                  onClick={addCustomProjectSlot}
                  className="btn-secondary w-full gap-2 text-xs sm:w-auto"
                >
                  <Plus className="h-4 w-4" />
                  Add custom project
                </button>
              )}
              {(customProjects.length > 0 || projectsSaved) && (
                <button
                  type="button"
                  onClick={saveProjects}
                  disabled={savingProjects}
                  className="btn-secondary text-xs"
                >
                  {savingProjects ? "Saving..." : "Save custom projects"}
                </button>
              )}
            </div>
            {projectsSaved && <p className="mt-2 text-xs text-green-400">Custom projects saved.</p>}
          </div>
        )}
      </div>
      <MobileBottomNav />
    </main>
  );
}
