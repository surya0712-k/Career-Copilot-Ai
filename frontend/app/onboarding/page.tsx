"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Brain, Upload } from "lucide-react";

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
  const [company, setCompany] = useState("Google");
  const [role, setRole] = useState("Software Engineer");
  const [level, setLevel] = useState("internship");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!resumeFile) {
      setError("Please upload your resume");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await api.uploadResume(resumeFile);
      const goal = await api.createGoal({
        target_company: company,
        target_role: role,
        level,
        description: `I want a ${company} ${role} ${level}`,
      });
      const job = await api.runAnalysis(goal.id);

      const poll = async () => {
        const status = await api.getAnalysisJob(job.id);
        if (status.status === "completed") {
          router.push("/dashboard");
        } else if (status.status === "failed") {
          setError(status.error || "Analysis failed");
          setLoading(false);
        } else {
          setTimeout(poll, 3000);
        }
      };
      poll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 flex items-center gap-2">
          <Brain className="h-8 w-8 text-brand-500" />
          <h1 className="text-2xl font-bold">Set Up Your Career Copilot</h1>
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
                disabled={!resumeFile}
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
              <div className="flex gap-3">
                <button type="button" className="btn-secondary" onClick={() => setStep(1)}>
                  Back
                </button>
                <button type="submit" className="btn-primary flex-1" disabled={loading}>
                  {loading ? "Analyzing your profile..." : "Start Analysis"}
                </button>
              </div>
            </>
          )}
        </form>
      </div>
    </main>
  );
}
