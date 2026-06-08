"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { ArrowLeft, Brain, Upload } from "lucide-react";

const LEVELS = [
  { value: "internship", label: "Internship" },
  { value: "new_grad", label: "New Grad" },
  { value: "mid_level", label: "Mid Level" },
  { value: "senior", label: "Senior" },
] as const;

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [hasResume, setHasResume] = useState(false);
  const [company, setCompany] = useState("Google");
  const [role, setRole] = useState("Software Engineer");
  const [level, setLevel] = useState("internship");
  const [loading, setLoading] = useState(false);
  const [checkingProfile, setCheckingProfile] = useState(true);
  const [progressLabel, setProgressLabel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    api
      .getProfile()
      .then((profile) => {
        if (profile.resume_parsed) {
          setHasResume(true);
        }
      })
      .catch(() => {
        /* new user — no profile yet */
      })
      .finally(() => setCheckingProfile(false));
  }, [router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!resumeFile && !hasResume) {
      setError("Please upload your resume");
      return;
    }

    setLoading(true);
    setError(null);
    setProgressLabel("Uploading resume and starting analysis...");

    try {
      if (resumeFile) {
        await api.uploadResume(resumeFile);
        setHasResume(true);
      }
      setProgressLabel("Saving your career goal...");
      const goal = await api.createGoal({
        target_company: company,
        target_role: role,
        level,
        description: `I want a ${company} ${role} ${level}`,
      });
      const job = await api.runAnalysis(goal.id);
      setProgressLabel("Reviewing GitHub & detecting skill gaps...");

      const poll = async (attempt = 0) => {
        try {
          const status = await api.getAnalysisJob(job.id);
          if (status.result?.step_label) {
            setProgressLabel(status.result.step_label);
          }
          if (status.status === "completed") {
            localStorage.removeItem("pendingAnalysisJob");
            router.push("/dashboard");
          } else if (
            status.status === "running" &&
            (status.result?.phase === "gaps_ready" || status.result?.gap_analysis)
          ) {
            localStorage.setItem("pendingAnalysisJob", job.id);
            router.push("/dashboard");
          } else if (status.status === "failed") {
            setError(status.error || "Analysis failed");
            setLoading(false);
            setProgressLabel(null);
          } else {
            setTimeout(() => poll(0), 1500);
          }
        } catch (err) {
          const message = err instanceof Error ? err.message : "";
          if (message.includes("Job not found") && attempt < 5) {
            setTimeout(() => poll(attempt + 1), 500);
            return;
          }
          setError(message || "Analysis failed");
          setLoading(false);
          setProgressLabel(null);
        }
      };
      poll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setLoading(false);
      setProgressLabel(null);
    }
  }

  if (checkingProfile) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-2xl">
        <Link
          href="/dashboard"
          className="mb-6 inline-flex items-center gap-2 text-sm text-white/60 hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Dashboard
        </Link>

        <div className="mb-8 flex items-center gap-2">
          <Brain className="h-8 w-8 text-brand-500" />
          <h1 className="text-2xl font-bold">Set Up Your Career Goal</h1>
        </div>

        <div className="mb-8 flex gap-2">
          {[1, 2].map((s) => (
            <div
              key={s}
              className={`h-2 flex-1 rounded-full ${step >= s ? "bg-brand-500" : "bg-white/10"}`}
            />
          ))}
        </div>

        <form onSubmit={handleSubmit} className="card space-y-6">
          {step === 1 && (
            <>
              <h2 className="text-lg font-semibold">Upload Your Resume</h2>
              {hasResume && (
                <p className="text-sm text-green-400">
                  Resume already on file. Upload a new PDF to replace it, or continue to set your goal.
                </p>
              )}
              <label className="flex cursor-pointer flex-col items-center gap-4 rounded-lg border-2 border-dashed border-white/20 p-10 transition hover:border-brand-500">
                <Upload className="h-10 w-10 text-white/40" />
                <span className="text-white/60">
                  {resumeFile ? resumeFile.name : "Click to upload PDF resume"}
                </span>
                <input
                  type="file"
                  accept=".pdf"
                  className="hidden"
                  onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
                />
              </label>
              <button
                type="button"
                className="btn-primary w-full"
                disabled={!resumeFile && !hasResume}
                onClick={() => setStep(2)}
              >
                Continue
              </button>
            </>
          )}

          {step === 2 && (
            <>
              <h2 className="text-lg font-semibold">What&apos;s Your Goal?</h2>
              <div>
                <label className="mb-1 block text-sm text-white/60">Target Company</label>
                <input
                  className="input"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  placeholder="Google"
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-white/60">Target Role</label>
                <input
                  className="input"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  placeholder="Software Engineer"
                  required
                />
              </div>
              <div>
                <label className="mb-2 block text-sm text-white/60">Level</label>
                <div className="grid grid-cols-2 gap-3">
                  {LEVELS.map((item) => (
                    <button
                      key={item.value}
                      type="button"
                      onClick={() => setLevel(item.value)}
                      className={`rounded-lg border px-4 py-3 text-left text-sm font-medium transition ${
                        level === item.value
                          ? "border-brand-500 bg-brand-600/25 text-white shadow-[0_0_0_1px_rgba(99,102,241,0.4)]"
                          : "border-white/15 bg-white/5 text-white/70 hover:border-white/30 hover:bg-white/10"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
              {error && <p className="text-sm text-red-400">{error}</p>}
              {loading && progressLabel && (
                <p className="text-sm text-brand-300">{progressLabel}</p>
              )}
              <div className="flex gap-3">
                <button type="button" className="btn-secondary" onClick={() => setStep(1)}>
                  Back
                </button>
                <button type="submit" className="btn-primary flex-1" disabled={loading}>
                  {loading ? progressLabel || "Analyzing your profile..." : "Start Analysis"}
                </button>
              </div>
            </>
          )}
        </form>
      </div>
    </main>
  );
}
