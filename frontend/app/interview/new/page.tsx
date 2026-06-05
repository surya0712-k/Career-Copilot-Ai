"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  api,
  Goal,
  InterviewSession,
  submitInterviewAnswer,
} from "@/lib/api";
import { ArrowLeft, Send } from "lucide-react";

interface ChatMessage {
  role: "interviewer" | "user" | "feedback" | "system";
  content: string;
  score?: number;
}

export default function NewInterviewPage() {
  const router = useRouter();
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(true);
  const [completed, setCompleted] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    api
      .getActiveGoal()
      .then((goal: Goal | null) => api.startInterview(goal?.id))
      .then((s) => {
        setSession(s);
        const firstTurn = s.turns?.[0];
        if (firstTurn) {
          setMessages([
            {
              role: "interviewer",
              content: firstTurn.question,
            },
          ]);
        }
      })
      .catch(() => router.push("/dashboard"))
      .finally(() => setStarting(false));
  }, [router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!session || !answer.trim() || loading) return;

    const userAnswer = answer.trim();
    setAnswer("");
    setMessages((prev) => [...prev, { role: "user", content: userAnswer }]);
    setLoading(true);

    try {
      await submitInterviewAnswer(session.id, userAnswer, (event, data) => {
        if (event === "feedback") {
          const fb = data as { score?: number; feedback?: string };
          setMessages((prev) => [
            ...prev,
            {
              role: "feedback",
              content: fb.feedback || "Feedback received",
              score: fb.score,
            },
          ]);
        }
        if (event === "question") {
          const q = data as { question: string };
          setMessages((prev) => [
            ...prev,
            { role: "interviewer", content: q.question },
          ]);
        }
        if (event === "summary") {
          const summary = data as { overall_score?: number; readiness?: string };
          setMessages((prev) => [
            ...prev,
            {
              role: "system",
              content: `Interview complete! Score: ${summary.overall_score}/10. ${summary.readiness || ""}`,
              score: summary.overall_score,
            },
          ]);
          setCompleted(true);
        }
      });
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "system", content: "Error submitting answer. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  if (starting) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
          <p className="mt-4 text-white/60">Preparing your mock interview...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen flex-col">
      <header className="border-b border-white/10 px-6 py-4">
        <div className="mx-auto flex max-w-3xl items-center gap-4">
          <Link href="/dashboard" className="text-white/60 hover:text-white">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="font-semibold">Mock Interview</h1>
            <p className="text-sm text-white/50">{session?.role_context}</p>
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-6 py-6">
        <div className="flex-1 space-y-4 overflow-y-auto pb-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-xl px-4 py-3 text-sm ${
                  msg.role === "user"
                    ? "bg-brand-600 text-white"
                    : msg.role === "feedback"
                    ? "border border-yellow-500/30 bg-yellow-500/10 text-yellow-100"
                    : msg.role === "system"
                    ? "border border-green-500/30 bg-green-500/10 text-green-100"
                    : "bg-white/10 text-white/90"
                }`}
              >
                {msg.role === "interviewer" && (
                  <p className="mb-1 text-xs font-medium text-brand-400">Interviewer</p>
                )}
                {msg.role === "feedback" && msg.score !== undefined && (
                  <p className="mb-1 text-xs font-medium text-yellow-400">
                    Score: {msg.score}/10
                  </p>
                )}
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {!completed ? (
          <form onSubmit={handleSubmit} className="flex gap-3 border-t border-white/10 pt-4">
            <textarea
              className="input flex-1 resize-none"
              rows={2}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Type your answer..."
              disabled={loading}
            />
            <button
              type="submit"
              className="btn-primary self-end"
              disabled={loading || !answer.trim()}
            >
              {loading ? (
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : (
                <Send className="h-5 w-5" />
              )}
            </button>
          </form>
        ) : (
          <div className="border-t border-white/10 pt-4 text-center">
            <Link href="/dashboard" className="btn-primary inline-block">
              Back to Dashboard
            </Link>
          </div>
        )}
      </div>
    </main>
  );
}
