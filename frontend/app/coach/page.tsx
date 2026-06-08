"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, Goal } from "@/lib/api";
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
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem("token")) {
      router.push("/login");
      return;
    }
    api.getActiveGoal().then(setGoal);
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

  return (
    <main className="min-h-screen px-6 py-8">
      <div className="mx-auto max-w-2xl">
        <Link href="/dashboard" className="mb-6 inline-flex items-center gap-2 text-sm text-white/60 hover:text-white">
          <ArrowLeft className="h-4 w-4" /> Dashboard
        </Link>

        <div className="mb-6 flex items-center gap-2">
          <Brain className="h-7 w-7 text-brand-500" />
          <h1 className="text-2xl font-bold">Career Coach</h1>
        </div>
        <p className="mb-6 text-sm text-white/60">
          Ask about your interview patterns, progress, and what to study next — powered by your Second Brain.
        </p>

        <div className="mb-4 flex flex-wrap gap-2">
          {PROMPTS.map((p) => (
            <button key={p} type="button" onClick={() => ask(p)} className="btn-secondary text-xs">
              {p}
            </button>
          ))}
        </div>

        <div className="card mb-4 min-h-[320px] space-y-4">
          {messages.length === 0 && (
            <p className="text-center text-sm text-white/40">Ask a question to get started.</p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`rounded-lg p-3 text-sm ${
                m.role === "user" ? "ml-8 bg-brand-600/20" : "mr-8 bg-white/5"
              }`}
            >
              {m.text}
            </div>
          ))}
          {loading && (
            <div className="mr-8 rounded-lg bg-white/5 p-3 text-sm text-white/40">Thinking...</div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            className="input flex-1"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask your career coach..."
            disabled={loading}
          />
          <button type="submit" className="btn-primary px-4" disabled={loading || !input.trim()}>
            <Send className="h-5 w-5" />
          </button>
        </form>
      </div>
    </main>
  );
}
