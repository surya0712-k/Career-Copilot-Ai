"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, Roadmap } from "@/lib/api";
import { ArrowLeft, CheckCircle2 } from "lucide-react";

export default function RoadmapPage() {
  const params = useParams();
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;

    api
      .getRoadmap(params.id as string)
      .then(setRoadmap)
      .finally(() => setLoading(false));
  }, [params.id]);

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

  return (
    <main className="min-h-screen px-6 py-8">
      <div className="mx-auto max-w-3xl">
        <Link href="/dashboard" className="mb-6 inline-flex items-center gap-2 text-sm text-white/60 hover:text-white">
          <ArrowLeft className="h-4 w-4" /> Back to Dashboard
        </Link>

        <h1 className="mb-2 text-3xl font-bold">{roadmap.title}</h1>
        <p className="mb-8 text-white/60 capitalize">Status: {roadmap.status}</p>

        <div className="space-y-6">
          {roadmap.milestones?.map((m, i) => (
            <div key={i} className="card">
              <div className="mb-3 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-600 text-sm font-bold">
                  {i + 1}
                </div>
                <div>
                  <h2 className="font-semibold">{m.title}</h2>
                  <p className="text-sm text-white/50">
                    Week {m.week_start} – {m.week_end}
                  </p>
                </div>
              </div>
              {m.description && (
                <p className="mb-4 text-sm text-white/70">{m.description}</p>
              )}
              {m.tasks && m.tasks.length > 0 && (
                <ul className="space-y-2">
                  {m.tasks.map((t, j) => (
                    <li key={j} className="flex items-start gap-2 text-sm">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />
                      <div>
                        <p className="font-medium">{t.title}</p>
                        {t.description && (
                          <p className="text-white/50">{t.description}</p>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              {m.success_criteria && (
                <p className="mt-3 text-xs text-white/40">
                  Success: {m.success_criteria}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
