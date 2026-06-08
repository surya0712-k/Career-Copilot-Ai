"""Compact LLM payloads for onboarding — minimizes tokens without losing signal."""
import json
from typing import Any


def slim_github(github: dict[str, Any] | None) -> dict[str, Any]:
    if not github:
        return {}
    if github.get("error"):
        return {"error": github["error"]}
    top = github.get("top_repos") or []
    return {
        "username": github.get("username"),
        "languages": github.get("languages", {}),
        "public_repos": github.get("public_repos", 0),
        "top_repos": [
            {"name": r.get("name"), "lang": r.get("language"), "stars": r.get("stars", 0)}
            for r in top[:3]
        ],
    }


def build_gap_llm_payload(
    *,
    resume_analysis: dict[str, Any],
    resume_text: str,
    github_analysis: dict[str, Any],
    role_research: dict[str, Any],
    target: str,
) -> str:
    skills = resume_analysis.get("skills") or []
    summary = (resume_analysis.get("summary") or "")[:800]
    role_summary = (role_research.get("requirements_summary") or "")[:300]

    ctx: dict[str, Any] = {
        "target": target,
        "skills": skills[:15],
        "summary": summary,
        "github": slim_github(github_analysis),
        "role": role_summary,
    }
    if not summary and resume_text:
        ctx["resume"] = resume_text[:1500]
    return json.dumps(ctx, separators=(",", ":"))


DSA_LANGUAGE_LABELS = {
    "python": "Python",
    "java": "Java",
    "cpp": "C++",
    "javascript": "JavaScript",
    "go": "Go",
}


def build_roadmap_llm_payload(
    *,
    gap_analysis: dict[str, Any],
    target: str,
    memory: str | None = None,
    dsa_language: str = "python",
) -> str:
    ctx: dict[str, Any] = {
        "target": target,
        "gaps": (gap_analysis.get("critical_gaps") or [])[:5],
        "recs": (gap_analysis.get("recommendations") or [])[:3],
        "readiness": gap_analysis.get("readiness_score", 0),
        "dsa_language": DSA_LANGUAGE_LABELS.get(dsa_language, dsa_language),
    }
    if memory and memory != "No prior context available.":
        ctx["memory"] = memory[:500]
    return json.dumps(ctx, separators=(",", ":"))
