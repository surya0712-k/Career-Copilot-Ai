"""Token analysis for detect_gaps and generate_roadmap prompts (standalone, no app imports)."""
import json

import tiktoken
from pydantic import BaseModel, Field

enc = tiktoken.get_encoding("cl100k_base")

GAP_ANALYSIS_PROMPT = """You are a career gap analyst. Compare the candidate's profile against the target role requirements.
Identify:
- Critical skill gaps (must fix before applying)
- Nice-to-have gaps
- Strengths to highlight
- Specific recommendations
Use the role research data to ground your analysis."""

ROADMAP_PROMPT = """You are a career roadmap planner for tech internships and jobs.
Create a structured learning roadmap based on the gap analysis.
Constraints:
- Maximum 4 milestones (weeks)
- Maximum 3 tasks per milestone
- Keep descriptions concise (1-2 sentences each)
Each milestone needs: title, description, week_start, week_end, tasks (title + brief description), success_criteria."""


class GapAnalysisOutput(BaseModel):
    critical_gaps: list[str] = Field(default_factory=list)
    nice_to_have_gaps: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    readiness_score: float = Field(default=0.0, ge=0, le=10)


class MilestoneTask(BaseModel):
    title: str
    description: str = ""
    resources: list[str] = Field(default_factory=list)


class MilestoneOutput(BaseModel):
    title: str
    description: str = ""
    week_start: int = 1
    week_end: int = 2
    tasks: list[MilestoneTask] = Field(default_factory=list)
    success_criteria: str = ""


class RoadmapOutput(BaseModel):
    title: str
    milestones: list[MilestoneOutput] = Field(default_factory=list)


def tok(s) -> int:
    if not isinstance(s, str):
        s = json.dumps(s)
    return len(enc.encode(s))


lines = [
    f"Bullet {i}: Developed Python/FastAPI microservices; optimized PostgreSQL queries; led code reviews."
    for i in range(120)
]
resume_text = "\n".join(lines)[:6000]
summary = resume_text[:2000]

resume_analysis = {
    "summary": summary,
    "skills": ["Python", "Java", "TypeScript", "React", "SQL", "Docker", "AWS", "Git", "REST", "Algorithms"] * 2,
    "experience_count": 3,
    "raw_text_length": len(resume_text),
}

top_repos = [
    {
        "name": f"backend-project-{i}",
        "description": "A scalable REST API with authentication, caching, and observability built for production workloads.",
        "language": ["Python", "TypeScript", "Go"][i % 3],
        "stars": max(0, 15 - i * 2),
        "url": f"https://github.com/candidate/backend-project-{i}",
        "updated_at": "2025-03-15T10:00:00Z",
    }
    for i in range(10)
]

github_analysis = {
    "username": "candidate",
    "name": "Alex Candidate",
    "bio": "CS @ University | backend + systems | open source",
    "public_repos": 32,
    "followers": 18,
    "languages": {"Python": 14, "TypeScript": 9, "Go": 5, "Java": 4, "Rust": 2},
    "total_stars": 47,
    "repos_with_description": 24,
    "top_repos": top_repos,
}

role_research_fast = {
    "company": "Google",
    "role": "Software Engineer",
    "level": "internship",
    "requirements_summary": "Software Engineer at Google (internship) — standard technical interview expectations.",
    "search_results": [],
}

role_research_full = {
    "company": "Google",
    "role": "Software Engineer",
    "level": "internship",
    "requirements_summary": " ".join(
        ["Google SWE intern interviews emphasize algorithms, system design basics, and coding fluency."] * 4
    ),
    "search_results": [
        {
            "title": f"Google SWE intern guide part {i}",
            "url": f"https://leetcode.com/discuss/{i}",
            "snippet": "Focus on medium LC problems and Googleyness.",
        }
        for i in range(5)
    ],
}

gap_response = {
    "critical_gaps": [
        "System design at scale — lacks experience designing distributed services",
        "Advanced algorithms — needs more graph and DP practice for Google bar",
        "Production operations — limited exposure to monitoring and incident response",
        "Concurrency — weak on threading/async patterns in large codebases",
    ],
    "nice_to_have_gaps": ["Kubernetes/GKE", "Go language depth", "Formal verification"],
    "strengths": [
        "Strong Python backend portfolio with real API projects",
        "Solid SQL and data modeling from internship",
        "Active GitHub with multiple starred repositories",
        "Clear communication in resume project descriptions",
    ],
    "recommendations": [
        "Complete 40 medium LeetCode problems focusing on graphs and DP",
        "Build one distributed system project (queue + workers + idempotency)",
        "Read Designing Data-Intensive Applications chapters 1-5",
        "Practice 5 mock behavioral interviews using STAR format",
        "Contribute one meaningful PR to an open-source Python project",
    ],
    "readiness_score": 5.8,
}

tasks = [
    {
        "title": f"Task {j + 1}",
        "description": "Complete targeted study and a hands-on exercise demonstrating the skill.",
        "resources": ["https://leetcode.com/problemset/", "https://ddia.book"],
    }
    for j in range(3)
]
milestones = [
    {
        "title": f"Week {w}: {['Algorithms', 'System Design', 'Behavioral', 'Portfolio'][w - 1]}",
        "description": "Weekly focus with measurable deliverables aligned to critical gaps.",
        "week_start": w,
        "week_end": w,
        "tasks": tasks,
        "success_criteria": "Can explain concepts and complete a representative exercise without hints.",
    }
    for w in range(1, 5)
]
roadmap_response = {"title": "Google SWE Intern — 4-Week Prep Roadmap", "milestones": milestones}

gap_schema = GapAnalysisOutput.model_json_schema()
roadmap_schema = RoadmapOutput.model_json_schema()


def openai_tool_wrapper(schema: dict, name: str) -> dict:
    return {
        "type": "function",
        "function": {"name": name, "description": f"Extract {name}", "parameters": schema},
    }


gap_tool = openai_tool_wrapper(gap_schema, "GapAnalysisOutput")
roadmap_tool = openai_tool_wrapper(roadmap_schema, "RoadmapOutput")


def gap_context(research: str = "fast") -> dict:
    return {
        "resume_analysis": resume_analysis,
        "resume_excerpt": resume_text,
        "github_analysis": github_analysis,
        "role_research": role_research_fast if research == "fast" else role_research_full,
        "target": "Google Software Engineer (internship)",
    }


def roadmap_context(gap: dict, research: str = "fast", memory_chunks: int = 0) -> dict:
    memory = (
        "No prior context available."
        if memory_chunks == 0
        else "\n".join(
            [
                f"[{i + 1}] (resume_insight) Resume analysis chunk about Python backend APIs and internship impact."
                for i in range(memory_chunks)
            ]
        )
    )
    return {
        "gap_analysis": gap,
        "role_research": role_research_fast if research == "fast" else role_research_full,
        "memory": memory,
        "target": "Google Software Engineer (internship)",
    }


def section_breakdown(ctx: dict, extras: list[tuple[str, int]]) -> list[tuple[str, int, int]]:
    sections = [(k, tok(json.dumps({k: ctx[k]}, indent=2)), len(json.dumps({k: ctx[k]}, indent=2))) for k in ctx]
    sections.extend((name, t, 0) for name, t in extras)
    sections.sort(key=lambda x: -x[1])
    return sections


gap_h = json.dumps(gap_context(), indent=2)[:8000]
road_h = json.dumps(roadmap_context(gap_response), indent=2)[:8000]

r1 = {
    "system": tok(GAP_ANALYSIS_PROMPT),
    "human": tok(gap_h),
    "human_chars": len(gap_h),
    "schema": tok(json.dumps(gap_schema)),
    "schema_chars": len(json.dumps(gap_schema)),
    "tool": tok(json.dumps(gap_tool)),
    "response": tok(json.dumps(gap_response)),
}
r2 = {
    "system": tok(ROADMAP_PROMPT),
    "human": tok(road_h),
    "human_chars": len(road_h),
    "schema": tok(json.dumps(roadmap_schema)),
    "schema_chars": len(json.dumps(roadmap_schema)),
    "tool": tok(json.dumps(roadmap_tool)),
    "response": tok(json.dumps(roadmap_response)),
}

gap_secs = section_breakdown(
    gap_context(),
    [("system_prompt", r1["system"]), ("json_schema", r1["schema"]), ("openai_tool_wrapper", r1["tool"])],
)
road_secs = section_breakdown(
    roadmap_context(gap_response, memory_chunks=5),
    [("system_prompt", r2["system"]), ("json_schema", r2["schema"]), ("openai_tool_wrapper", r2["tool"])],
)

print("TOKEN ANALYSIS — cl100k_base (GPT-4 / Grok compatible)")
print("=" * 70)
for label, r in [("detect_gaps", r1), ("generate_roadmap", r2)]:
    inp_schema = r["system"] + r["human"] + r["schema"]
    inp_tool = r["system"] + r["human"] + r["tool"]
    print(f"\n{label.upper()}")
    print(f"  System prompt:          {r['system']:>5} tokens")
    print(f"  Human message:          {r['human']:>5} tokens  ({r['human_chars']} chars, cap=8000)")
    print(f"  JSON schema (Pydantic): {r['schema']:>5} tokens  ({r['schema_chars']} chars)")
    print(f"  OpenAI tool wrapper:    {r['tool']:>5} tokens  (LangChain structured-output overhead)")
    print("  ---")
    print(f"  Total INPUT (sys+human+schema): {inp_schema:>5} tokens")
    print(f"  Total INPUT (sys+human+tool):   {inp_tool:>5} tokens  [billing-relevant estimate]")
    print(f"  Response (typical):             {r['response']:>5} tokens")
    print(f"  Round-trip (tool in + response): {inp_tool + r['response']:>5} tokens")

print("\n" + "=" * 70)
print("SCHEMA DETAIL")
print(f"  GapAnalysisOutput:  {r1['schema']} tokens / {r1['schema_chars']} chars")
print(f"  RoadmapOutput:      {r2['schema']} tokens / {r2['schema_chars']} chars")
print("  Nested: milestones[] -> MilestoneOutput -> tasks[] -> MilestoneTask(title, description, resources[])")

print("\n" + "=" * 70)
print("TOP 10 LARGEST PROMPT SECTIONS (both calls)")
combined = [(f"detect_gaps:{n}", t) for n, t, _ in gap_secs[:8]] + [
    (f"generate_roadmap:{n}", t) for n, t, _ in road_secs[:8]
]
combined.sort(key=lambda x: -x[1])
for name, t in combined[:10]:
    print(f"  {t:>5}  {name}")

print("\n" + "=" * 70)
print("P95 SCENARIOS")
gap_h_p95 = json.dumps(gap_context(research="full"), indent=2)[:8000]
road_h_p95 = json.dumps(roadmap_context(gap_response, research="full", memory_chunks=5), indent=2)[:8000]
print(f"  detect_gaps human (full research): {tok(gap_h_p95)} tokens")
print(f"  generate_roadmap human (full research + 5 RAG): {tok(road_h_p95)} tokens")

print("\n" + "=" * 70)
print("REDUNDANCY")
excerpt_t = tok(json.dumps({"resume_excerpt": resume_text}, indent=2))
analysis_t = tok(json.dumps({"resume_analysis": resume_analysis}, indent=2))
overlap = tok(resume_text[:2000])
rr = tok(json.dumps({"role_research": role_research_fast}, indent=2))
print(f"  resume_excerpt alone:      {excerpt_t} tokens")
print(f"  resume_analysis alone:     {analysis_t} tokens")
print(f"  overlapping content:       ~{overlap} tokens")
print(f"  role_research x2 calls:    {rr * 2} tokens")

slim_github = {
    "username": github_analysis["username"],
    "languages": github_analysis["languages"],
    "top_repos": [{"name": r["name"], "lang": r["language"], "stars": r["stars"]} for r in top_repos[:3]],
}
slim_gap_ctx = {
    "target": "Google Software Engineer (internship)",
    "skills": resume_analysis["skills"][:15],
    "resume_summary": summary[:800],
    "github": slim_github,
    "role": role_research_fast["requirements_summary"],
}
slim_gap_h = json.dumps(slim_gap_ctx, separators=(",", ":"))
slim_road_ctx = {
    "target": "Google Software Engineer (internship)",
    "critical_gaps": gap_response["critical_gaps"],
    "recommendations": gap_response["recommendations"][:3],
    "readiness": gap_response["readiness_score"],
}
slim_road_h = json.dumps(slim_road_ctx, separators=(",", ":"))

GAP_SYSTEM_SLIM = "Compare candidate vs target role. Output critical/nice gaps, strengths, recommendations, readiness 0-10."
ROADMAP_SYSTEM_SLIM = "4-week roadmap from gaps. Max 4 milestones, 3 tasks each. Concise titles/descriptions."

opt_gap_in = tok(GAP_SYSTEM_SLIM) + tok(slim_gap_h) + int(r1["schema"] * 0.85)
opt_road_in = tok(ROADMAP_SYSTEM_SLIM) + tok(slim_road_h) + int(r2["schema"] * 0.55)
opt_road_out = 350

orig_total = (r1["system"] + r1["human"] + r1["tool"] + r1["response"]) + (
    r2["system"] + r2["human"] + r2["tool"] + r2["response"]
)
opt_total = opt_gap_in + int(r1["response"] * 0.85) + opt_road_in + opt_road_out

print("\n" + "=" * 70)
print("OPTIMIZED ESTIMATE (proposed cuts)")
print(f"  Original round-trip both calls: {orig_total} tokens")
print(f"  Optimized round-trip estimate:  {opt_total} tokens ({100 * (1 - opt_total / orig_total):.0f}% reduction)")
print(f"  detect_gaps input:    {opt_gap_in} (was {r1['system'] + r1['human'] + r1['tool']})")
print(f"  generate_roadmap input: {opt_road_in} (was {r2['system'] + r2['human'] + r2['tool']})")
