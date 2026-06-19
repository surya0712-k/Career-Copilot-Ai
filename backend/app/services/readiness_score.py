"""Role-aware readiness scoring — weights interview-critical gaps by severity and target."""

from __future__ import annotations

import re
from typing import Any

TOP_COMPANIES = ("google", "meta", "amazon", "apple", "microsoft", "netflix")

# (pattern, penalty, category) — one category counted once across all gaps
GAP_SEVERITY: list[tuple[str, float, str]] = [
    (
        r"data structure|algorithm|leetcode|competitive program|coding interview|"
        r"problem.?solv|interview prep",
        1.35,
        "dsa",
    ),
    (
        r"systems design|distributed|large.?scale|scalability|performance optim|"
        r"high availability|microservice",
        1.05,
        "systems",
    ),
    (
        r"fundamental|core cs|computer science|theory|operating system|networking",
        0.75,
        "fundamentals",
    ),
    (
        r"no (demonstrated |mention of )?experience|limited .*experience|"
        r"no internship|lack of professional|thin experience",
        0.55,
        "experience",
    ),
    (
        r"communication|behavioral|soft skill",
        0.4,
        "communication",
    ),
]

STRENGTH_RELEVANCE: list[tuple[str, float]] = [
    (r"data structure|algorithm|leetcode|competitive program|coding interview", 0.65),
    (r"systems design|distributed|large.?scale|scalab", 0.6),
    (r"internship|full.?time|worked at|professional experience|years of", 0.55),
    (r"deploy|production|ci/?cd|aws|docker|kubernetes|cloud", 0.4),
    (r"portfolio|project|open.?source|github|built .{0,20}(api|service|app)", 0.35),
    (r"learn|cutting.?edge|modern|framework", 0.2),
]

FAANG_CORE_MULTIPLIER = 1.25  # DSA/systems gaps hurt more at top companies


def _parse_target(target: str) -> tuple[str, str, str]:
    target_l = target.lower()
    level = ""
    if "(" in target and ")" in target:
        level = target[target.rindex("(") + 1 : target.rindex(")")].strip().lower()
    is_top = any(c in target_l for c in TOP_COMPANIES)
    is_swe = bool(re.search(r"software|swe|engineer|developer|backend|frontend|full.?stack", target_l))
    return target_l, level, "top_swe" if is_top and is_swe else "default"


def _gap_text(gap: str) -> str:
    return gap.lower().strip()


def _classify_gap(gap: str) -> tuple[float, str]:
    text = _gap_text(gap)
    best_penalty = 0.45
    best_cat = "generic"
    for pattern, penalty, category in GAP_SEVERITY:
        if re.search(pattern, text, re.I):
            if penalty > best_penalty:
                best_penalty = penalty
                best_cat = category
    return best_penalty, best_cat


def _gap_penalties(critical_gaps: list[str], target_l: str, is_top_swe: bool) -> float:
    seen: dict[str, float] = {}
    for gap in critical_gaps:
        penalty, category = _classify_gap(gap)
        if is_top_swe and category in ("dsa", "systems", "fundamentals"):
            penalty *= FAANG_CORE_MULTIPLIER
        seen[category] = max(seen.get(category, 0), penalty)

    return min(sum(seen.values()), 5.5)


def _strength_points(strengths: list[str], critical_gaps: list[str]) -> float:
    """Portfolio strengths count less when core interview gaps are present."""
    gap_blob = " ".join(_gap_text(g) for g in critical_gaps)
    has_core_gap = bool(
        re.search(r"data structure|algorithm|leetcode|systems|fundamental", gap_blob, re.I)
    )

    total = 0.0
    for strength in strengths:
        text = _gap_text(strength)
        best = 0.25
        for pattern, weight in STRENGTH_RELEVANCE:
            if re.search(pattern, text, re.I):
                best = max(best, weight)
        if has_core_gap and best <= 0.4:
            best *= 0.55  # deployment/portfolio can't fully offset missing DSA
        total += best

    return min(total, 2.0)


def _empty_profile_penalty(
    critical_gaps: list[str],
    github_analysis: dict[str, Any] | None,
    resume_analysis: dict[str, Any] | None,
) -> float:
    penalty = 0.0
    resume = resume_analysis or {}
    github = github_analysis or {}
    skills = resume.get("skills") or []
    repos = int(github.get("public_repos") or 0)

    if len(skills) < 3:
        penalty += 1.0
    if repos == 0:
        penalty += 0.85
    if len(critical_gaps) >= 4:
        penalty += 0.65
    return penalty


def _signal_bonus(
    github_analysis: dict[str, Any] | None,
    resume_analysis: dict[str, Any] | None,
) -> float:
    bonus = 0.0
    resume = resume_analysis or {}
    skills = resume.get("skills") or []
    exp_count = int(resume.get("experience_count") or 0)
    bonus += min(len(skills) * 0.04, 0.35)
    bonus += min(exp_count * 0.12, 0.45)

    github = github_analysis or {}
    if github.get("error"):
        return bonus - 0.5
    if not github:
        return bonus

    repos = int(github.get("public_repos") or 0)
    stars = sum(int(r.get("stars") or 0) for r in (github.get("top_repos") or [])[:3])
    if repos >= 15:
        bonus += 0.35
    elif repos >= 5:
        bonus += 0.2
    elif repos >= 1:
        bonus += 0.1
    if stars >= 10:
        bonus += 0.2
    elif stars >= 1:
        bonus += 0.08
    return min(bonus, 0.85)


def _blocker_cap(
    critical_gaps: list[str],
    strengths: list[str],
    is_top_swe: bool,
) -> float | None:
    """Hard ceiling when interview blockers exist without matching strengths."""
    if not is_top_swe:
        return None

    gap_blob = " ".join(_gap_text(g) for g in critical_gaps)
    strength_blob = " ".join(_gap_text(s) for s in strengths)

    missing_dsa = bool(re.search(r"data structure|algorithm|leetcode|competitive|problem.?solv", gap_blob, re.I))
    has_dsa_proof = bool(re.search(r"data structure|algorithm|leetcode|competitive|problem.?solv", strength_blob, re.I))

    missing_systems = bool(re.search(r"systems|distributed|large.?scale", gap_blob, re.I))
    has_systems_proof = bool(re.search(r"systems|distributed|large.?scale|scalab", strength_blob, re.I))

    strength_points = _strength_points(strengths, critical_gaps)

    if missing_dsa and not has_dsa_proof:
        if strength_points < 0.8:
            return 3.2
        return 5.5
    if missing_dsa and missing_systems and not has_systems_proof:
        return min(4.5, 5.5 if strength_points >= 0.8 else 3.5)
    return None


def evidence_readiness_score(
    gaps: dict[str, Any],
    *,
    github_analysis: dict[str, Any] | None = None,
    resume_analysis: dict[str, Any] | None = None,
    target: str = "",
) -> float:
    critical = gaps.get("critical_gaps") or []
    nice = gaps.get("nice_to_have_gaps") or []
    strengths = gaps.get("strengths") or []

    _, level, target_kind = _parse_target(target)
    is_top_swe = target_kind == "top_swe"
    target_l = target.lower()

    # Start high and subtract for gaps (penalize missing interview skills heavily)
    score = 9.2
    score -= _gap_penalties(critical, target_l, is_top_swe)
    score -= _empty_profile_penalty(critical, github_analysis, resume_analysis)
    score -= min(len(nice) * 0.18, 0.9)
    score += _strength_points(strengths, critical)
    score += _signal_bonus(github_analysis, resume_analysis)

    if is_top_swe and level in ("internship", "new_grad"):
        score -= 0.35  # higher bar for new-grad loops at FAANG

    cap = _blocker_cap(critical, strengths, is_top_swe)
    if cap is not None:
        score = min(score, cap)

    return max(1.0, min(9.5, score))


def finalize_readiness_score(
    gaps: dict[str, Any],
    *,
    github_analysis: dict[str, Any] | None = None,
    resume_analysis: dict[str, Any] | None = None,
    target: str = "",
) -> float:
    """Compute readiness from evidence; LLM score is advisory only when far from computed."""
    computed = evidence_readiness_score(
        gaps,
        github_analysis=github_analysis,
        resume_analysis=resume_analysis,
        target=target,
    )

    llm_raw = gaps.get("readiness_score")
    try:
        llm_score = float(llm_raw) if llm_raw is not None else None
    except (TypeError, ValueError):
        llm_score = None

    if llm_score is None:
        return round(computed, 1)

    # Ignore LLM when it clusters on generic defaults; trust severity-weighted evidence
    if 5.5 <= llm_score <= 7.0:
        return round(computed, 1)

    # Only nudge slightly when LLM is confident and agrees on direction
    if abs(llm_score - computed) <= 1.5:
        final = 0.85 * computed + 0.15 * llm_score
    else:
        final = computed

    return round(max(0.0, min(10.0, final)), 1)
