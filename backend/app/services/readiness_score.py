"""Evidence-based readiness scoring — avoids LLM defaulting to ~6.5 for every profile."""

from __future__ import annotations

from typing import Any


def _target_difficulty_adjustment(target: str, level: str) -> float:
    """Top companies and competitive levels raise the bar (lowers score slightly)."""
    target_l = target.lower()
    level_l = level.lower()
    penalty = 0.0
    top_companies = ("google", "meta", "amazon", "apple", "microsoft", "netflix")
    if any(company in target_l for company in top_companies):
        penalty += 0.35
    if level_l in ("internship", "new_grad"):
        penalty += 0.15
    elif level_l == "senior":
        penalty += 0.25
    return penalty


def evidence_readiness_score(
    gaps: dict[str, Any],
    *,
    github_analysis: dict[str, Any] | None = None,
    resume_analysis: dict[str, Any] | None = None,
    target: str = "",
) -> float:
    strengths = gaps.get("strengths") or []
    critical = gaps.get("critical_gaps") or []
    nice = gaps.get("nice_to_have_gaps") or []

    score = 3.0
    score += min(len(strengths) * 0.55, 2.75)
    score -= min(len(critical) * 0.72, 3.6)
    score -= min(len(nice) * 0.22, 1.1)

    resume = resume_analysis or {}
    skills = resume.get("skills") or []
    exp_count = int(resume.get("experience_count") or 0)
    score += min(len(skills) * 0.07, 0.7)
    score += min(exp_count * 0.18, 0.9)

    github = github_analysis or {}
    if github.get("error"):
        score -= 0.6
    elif github:
        repos = int(github.get("public_repos") or 0)
        top_repos = github.get("top_repos") or []
        stars = sum(int(r.get("stars") or 0) for r in top_repos[:3])
        if repos == 0:
            score -= 0.55
        elif repos >= 20:
            score += 0.75
        elif repos >= 8:
            score += 0.5
        elif repos >= 3:
            score += 0.3
        elif repos >= 1:
            score += 0.15
        if stars >= 20:
            score += 0.45
        elif stars >= 5:
            score += 0.25
        elif stars >= 1:
            score += 0.1

    if target:
        level = ""
        if "(" in target and ")" in target:
            level = target[target.rindex("(") + 1 : target.rindex(")")].strip()
        score -= _target_difficulty_adjustment(target, level)

    return max(0.5, min(9.8, score))


def finalize_readiness_score(
    gaps: dict[str, Any],
    *,
    github_analysis: dict[str, Any] | None = None,
    resume_analysis: dict[str, Any] | None = None,
    target: str = "",
) -> float:
    """Blend LLM judgment with measurable signals so scores differ across profiles."""
    llm_raw = gaps.get("readiness_score")
    try:
        llm_score = float(llm_raw) if llm_raw is not None else None
    except (TypeError, ValueError):
        llm_score = None

    evidence = evidence_readiness_score(
        gaps,
        github_analysis=github_analysis,
        resume_analysis=resume_analysis,
        target=target,
    )

    if llm_score is None:
        return round(evidence, 1)

    # Weight evidence more when LLM clusters around the common default (~6-6.5)
    if 5.8 <= llm_score <= 6.8:
        final = 0.35 * llm_score + 0.65 * evidence
    else:
        final = 0.45 * llm_score + 0.55 * evidence

    return round(max(0.0, min(10.0, final)), 1)
