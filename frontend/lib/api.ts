const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";

export interface User {
  id: string;
  github_id: string;
  github_username: string;
  email?: string;
  avatar_url?: string;
}

export interface Goal {
  id: string;
  target_company: string;
  target_role: string;
  level: string;
  description?: string;
  is_active: boolean;
}

export interface Profile {
  id: string;
  resume_parsed?: Record<string, unknown>;
  github_data?: Record<string, unknown>;
  skills_extracted?: Record<string, unknown>;
  gap_analysis?: {
    critical_gaps?: string[];
    nice_to_have_gaps?: string[];
    strengths?: string[];
    recommendations?: string[];
    readiness_score?: number;
  };
}

export interface Roadmap {
  id: string;
  title: string;
  status: string;
  milestones?: Milestone[];
  goal_id: string;
  created_at: string;
}

export interface Milestone {
  title: string;
  description?: string;
  week_start?: number;
  week_end?: number;
  tasks?: { title: string; description?: string; resources?: string[] }[];
  success_criteria?: string;
}

export interface InterviewSession {
  id: string;
  role_context: string;
  status: string;
  feedback_summary?: Record<string, unknown>;
  score?: number;
  turns?: InterviewTurn[];
}

export interface InterviewTurn {
  id: string;
  turn_number: number;
  question: string;
  answer?: string;
  feedback?: {
    score?: number;
    feedback?: string;
    strengths?: string[];
    improvements?: string[];
  };
  score?: number;
}

export interface AnalysisJob {
  id: string;
  status: string;
  result?: {
    gap_analysis?: Profile["gap_analysis"];
    roadmap_id?: string;
    readiness_score?: number;
  };
  error?: string;
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  githubAuth: (code: string) =>
    request<{ access_token: string; user: User }>("/auth/github", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),

  getMe: () => request<User>("/auth/me"),

  uploadResume: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Profile>("/profiles/resume", { method: "POST", body: form });
  },

  getProfile: () => request<Profile>("/profiles/me"),

  createGoal: (data: {
    target_company: string;
    target_role: string;
    level?: string;
    description?: string;
  }) =>
    request<Goal>("/goals", { method: "POST", body: JSON.stringify(data) }),

  getActiveGoal: () => request<Goal | null>("/goals/active"),

  runAnalysis: (goalId: string) =>
    request<AnalysisJob>("/analysis/run", {
      method: "POST",
      body: JSON.stringify({ goal_id: goalId }),
    }),

  getAnalysisJob: (jobId: string) =>
    request<AnalysisJob>(`/analysis/jobs/${jobId}`),

  getAnalysis: () => request<Profile | null>("/analysis/me"),

  getRoadmap: (id: string) => request<Roadmap>(`/roadmaps/${id}`),

  getLatestRoadmap: (goalId: string) =>
    request<Roadmap | null>(`/roadmaps/goal/${goalId}/latest`),

  startInterview: (goalId?: string) =>
    request<InterviewSession>("/interviews", {
      method: "POST",
      body: JSON.stringify({ goal_id: goalId }),
    }),

  getInterview: (id: string) => request<InterviewSession>(`/interviews/${id}`),

  getProgress: () =>
    request<{
      summary: string;
      interview_scores: { score: number; role_context: string; date: string }[];
      gap_improvements: string[];
      recent_memory: string[];
    }>("/progress/me"),
};

export function isGitHubAuthConfigured(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_GITHUB_CLIENT_ID?.trim());
}

export function getGitHubAuthUrl(): string {
  const clientId = process.env.NEXT_PUBLIC_GITHUB_CLIENT_ID?.trim() || "";
  const redirectUri =
    process.env.NEXT_PUBLIC_GITHUB_REDIRECT_URI?.trim() ||
    "http://localhost:3001/auth/callback";
  return `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&scope=read:user user:email repo`;
}

export async function submitInterviewAnswer(
  sessionId: string,
  answer: string,
  onEvent: (event: string, data: unknown) => void
): Promise<void> {
  const token = getToken();
  const res = await fetch(`${API_URL}/interviews/${sessionId}/turn`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ answer }),
  });

  if (!res.ok) throw new Error("Failed to submit answer");

  const reader = res.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      const lines = part.split("\n");
      let event = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data = line.slice(5).trim();
      }
      if (data) {
        try {
          onEvent(event, JSON.parse(data));
        } catch {
          onEvent(event, data);
        }
      }
    }
  }
}
