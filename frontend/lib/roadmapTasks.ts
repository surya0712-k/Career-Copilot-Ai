import { Milestone } from "./api";

export function isMockInterviewTask(title: string) {
  return /mock interview/i.test(title);
}

export type RoadmapTask = NonNullable<Milestone["tasks"]>[number] & {
  task_type?: "practice" | "project";
};

export function isPracticeOrDrillTask(t: { title: string; description?: string; task_type?: string }) {
  if (t.task_type === "practice") return true;
  if (t.task_type === "project") return false;
  const text = `${t.title} ${t.description ?? ""}`.toLowerCase();
  return /leetcode|solve \d+|timed practice|practice session|\bmediums?\b|mock interview|study |read |chapters?/.test(
    text,
  );
}

export function isApplicationProjectTask(t: {
  title: string;
  description?: string;
  task_type?: string;
}) {
  if (t.task_type === "project") return true;
  if (t.task_type === "practice") return false;
  if (isPracticeOrDrillTask(t)) return false;
  const title = t.title.toLowerCase();
  const text = `${t.title} ${t.description ?? ""}`.toLowerCase();
  if (/^project\s*\d+\s*:/i.test(t.title)) return true;
  if (/^(build|create|develop|deploy|add)\s/.test(title)) {
    if (/load test|metrics|monitoring|url shortener|backend|service|api/.test(text)) return true;
    if (/^(build|create|develop|deploy)\s/.test(title)) return true;
  }
  if (
    /load test|load testing|url shortener|backend service|scalable|microservice|rest api|fastapi service/.test(
      text,
    )
  ) {
    return !/implement solutions|leetcode|solve \d+/.test(text);
  }
  return false;
}

export function getApplicationProjectTasks(m: Milestone) {
  return (m.tasks ?? []).filter(isApplicationProjectTask);
}

export function partitionTasks(tasks: NonNullable<Milestone["tasks"]>) {
  const practice: { task: (typeof tasks)[number]; index: number }[] = [];
  const projects: { task: (typeof tasks)[number]; index: number }[] = [];
  tasks.forEach((task, index) => {
    if (isApplicationProjectTask(task)) projects.push({ task, index });
    else practice.push({ task, index });
  });
  return { practice, projects };
}

export function findPrimaryProjectMilestoneIndex(milestones: Milestone[] | undefined) {
  if (!milestones?.length) return -1;
  let bestIdx = -1;
  let bestCount = 0;
  milestones.forEach((m, i) => {
    const count = getApplicationProjectTasks(m).length;
    if (count > bestCount) {
      bestCount = count;
      bestIdx = i;
    }
  });
  return bestIdx;
}

export function displayProjectTitle(title: string) {
  return title.replace(/^project\s*\d+\s*:\s*/i, "").trim() || title;
}
