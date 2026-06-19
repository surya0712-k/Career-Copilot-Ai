"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, Goal } from "@/lib/api";
import { AppNav } from "@/components/AppNav";
import { MobileBottomNav } from "@/components/MobileBottomNav";
import { ArrowLeft, Brain, Send } from "lucide-react";

const PROMPTS = [
  "What weakness keeps appearing in my interviews?",
  "How has my readiness changed?",
  "What should I focus on this week?",
];

interface Message {
  role: "user" | "coach";
  text: string;
}

export default function CoachPage() {
  const router = useRouter();
  const [goal, setGoal] = useState<Goal | null>(null);
  const [user, setUser] = useState<Awaited<ReturnType<typeof api.getMe>> | null>(null);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem("token")) {
      router.push("/login");
      return;
    }
    Promise.all([api.getActiveGoal(), api.getMe()])
      .then(([g, u]) => {
        setGoal(g);
        setUser(u);
      })
      .catch(() => router.push("/login"));
  }, [router]);

  async function ask(question: string) {
    if (!question.trim() || loading) return;
    setMessages((m) => [...m, { role: "user", text: question }]);
    setInput("");
    setLoading(true);
    try {
      const res = await api.askCoach(question, goal?.id);
      setMessages((m) => [...m, { role: "coach", text: res.answer }]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "coach", text: e instanceof Error ? e.message : "Something went wrong" },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    ask(input);
  }

  function logout() {
    localStorage.removeItem("token");
    router.push("/");
  }

  return (
    <main className="flex min-h-screen min-h-[100dvh] flex-col">
      <AppNav user={user} onLogout={logout} />
      <div className="page-container-nav mx-auto flex w-full max-w-3xl flex-1 flex-col lg:max-w-4xl">
        <Link
          href="/dashboard"
          className="mb-4 inline-flex min-h-[44px] items-center gap-2 text-sm text-white/60 hover:text-white lg:hidden"
        >
          <ArrowLeft className="h-4 w-4" /> Dashboard
        </Link>

        <div className="mb-4 flex items-center gap-2">
          <Brain className="h-7 w-7 shrink-0 text-brand-500" />
          <h1 className="text-xl font-bold sm:text-2xl">Career Coach</h1>
        </div>
        <p className="mb-4 text-sm text-white/60">
          Ask about your interview patterns, progress, and what to study next.
        </p>

        <div className="mb-4 flex flex-col gap-2 md:flex-row md:flex-wrap lg:gap-3">
          {PROMPTS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => ask(p)}
              className="btn-secondary w-full text-left text-xs md:w-auto lg:text-sm"
            >
              {p}
            </button>
          ))}
        </div>

        <div className="card mb-4 min-h-[240px] flex-1 space-y-3 overflow-y-auto md:min-h-[360px] lg:min-h-[420px]">
          {messages.length === 0 && (
            <p className="text-center text-sm text-white/40">Ask a question to get started.</p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`rounded-lg p-3 text-sm leading-relaxed ${
                m.role === "user" ? "ml-2 bg-brand-600/20 sm:ml-8" : "mr-2 bg-white/5 sm:mr-8"
              }`}
            >
              {m.text}
            </div>
          ))}
          {loading && (
            <div className="mr-2 rounded-lg bg-white/5 p-3 text-sm text-white/40 sm:mr-8">Thinking...</div>
          )}
        </div>

        <form
          onSubmit={handleSubmit}
          className="sticky-composer flex gap-2 lg:gap-3"
          style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}
        >
          <input
            className="input min-h-[44px] flex-1"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask your career coach..."
            disabled={loading}
          />
          <button
            type="submit"
            className="btn-primary shrink-0 px-4"
            disabled={loading || !input.trim()}
            aria-label="Send"
          >
            <Send className="h-5 w-5" />
          </button>
        </form>
      </div>
      <MobileBottomNav />
    </main>
  );
}
