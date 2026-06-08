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
  practice_projects?: PracticeProject[];
}

export interface PracticeProject {
  name: string;
  description: string;
}

export type DsaLanguage = "python" | "java" | "cpp" | "javascript" | "go";

export interface Profile {
  id: string;
  resume_parsed?: Record<string, unknown>;
  github_data?: Record<string, unknown>;
  skills_extracted?: Record<string, unknown>;
  preferred_dsa_language?: DsaLanguage;
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
  version?: number;
  completion_pct?: number;
  created_at: string;
}

export interface Milestone {
  id?: string;
  title: string;
  description?: string;
  week_start?: number;
  week_end?: number;
  status?: string;
  tasks?: {
    title: string;
    description?: string;
    task_type?: "practice" | "project";
    resources?: string[];
    completed?: boolean;
    completed_at?: string | null;
  }[];
  success_criteria?: string;
}

export interface ProgressData {
  summary: string;
  interview_scores: { score: number; role_context: string; date: string }[];
  gap_improvements: string[];
  recent_memory: string[];
  completion_pct: number;
  total_study_hours: number;
  completed_topics: string[];
  weak_areas: { topic: string; count: number; source: string }[];
  current_week?: number | null;
  readiness_score?: number | null;
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
    step?: string;
    step_label?: string;
    phase?: string;
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

  let res!: Response;
  let lastError: unknown;
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      res = await fetch(`${API_URL}${path}`, { ...options, headers });
      lastError = null;
      break;
    } catch (err) {
      lastError = err;
      if (attempt === 0) {
        await new Promise((r) => setTimeout(r, 1500));
        continue;
      }
    }
  }
  if (lastError) {
    throw new Error(
      `Cannot reach the API at ${API_URL}. Wait for Docker to finish starting (backend healthcheck), then refresh.`
    );
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(", ")
          : "Request failed";
    throw new Error(message || "Request failed");
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

  getProgress: () => request<ProgressData>("/progress/me"),

  completeTask: (
    roadmapId: string,
    milestoneId: string,
    taskIndex: number,
    studyMinutes = 0,
    completed = true
  ) =>
    request<{ completion_pct: number }>(
      `/roadmaps/${roadmapId}/tasks/${milestoneId}/${taskIndex}`,
      {
        method: "PATCH",
        body: JSON.stringify({ study_minutes: studyMinutes, completed }),
      }
    ),

  updateProfilePreferences: (preferred_dsa_language: DsaLanguage) =>
    request<Profile>("/profiles/me/preferences", {
      method: "PATCH",
      body: JSON.stringify({ preferred_dsa_language }),
    }),

  getPracticeProjects: (goalId: string) =>
    request<PracticeProject[]>(`/goals/${goalId}/practice-projects`),

  updatePracticeProjects: (goalId: string, projects: PracticeProject[]) =>
    request<PracticeProject[]>(`/goals/${goalId}/practice-projects`, {
      method: "PUT",
      body: JSON.stringify({ projects }),
    }),

  recalculateRoadmap: (roadmapId: string) =>
    request<Roadmap>(`/roadmaps/${roadmapId}/recalculate`, { method: "POST" }),

  logStudySession: (data: { goal_id: string; topic: string; duration_minutes: number; notes?: string }) =>
    request<{ total_study_hours: number }>("/progress/study-session", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  askCoach: (question: string, goalId?: string) =>
    request<{
      answer: string;
      citations: { content: string; chunk_type: string; score: number }[];
      weak_area_stats: { topic: string; occurrence_count: number }[];
    }>("/memory/ask", {
      method: "POST",
      body: JSON.stringify({ question, goal_id: goalId ?? null }),
    }),

  saveVoiceSummary: (data: {
    goal_id?: string;
    summary: string;
    score?: number;
    improvements?: string[];
    strengths?: string[];
  }) =>
    request<{ session_id: string }>("/interviews/voice/summary", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getLiveKitToken: (params?: {
    goalId?: string;
    roadmapId?: string;
    milestoneId?: string;
  }) =>
    request<{
      token: string;
      url: string;
      room_name: string;
      identity: string;
      focus_label?: string | null;
    }>("/livekit/token", {
      method: "POST",
      body: JSON.stringify({
        goal_id: params?.goalId ?? null,
        roadmap_id: params?.roadmapId ?? null,
        milestone_id: params?.milestoneId ?? null,
      }),
    }),
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
