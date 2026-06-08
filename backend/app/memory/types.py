"""Chunk type constants for the Second Brain memory layer."""

RESUME_INSIGHT = "resume_insight"
GITHUB_INSIGHT = "github_insight"
GAP_FINDING = "gap_finding"
GOAL_INTENT = "goal_intent"
ROADMAP_UPDATE = "roadmap_update"
INTERVIEW_FEEDBACK = "interview_feedback"
INTERVIEW_WEAKNESS = "interview_weakness"
INTERVIEW_STRENGTH = "interview_strength"
USER_NOTE = "user_note"
STUDY_LOG = "study_log"
DSA_PREFERENCE = "dsa_preference"

ALL_CHUNK_TYPES = [
    RESUME_INSIGHT,
    GITHUB_INSIGHT,
    GAP_FINDING,
    GOAL_INTENT,
    ROADMAP_UPDATE,
    INTERVIEW_FEEDBACK,
    INTERVIEW_WEAKNESS,
    INTERVIEW_STRENGTH,
    USER_NOTE,
    STUDY_LOG,
    DSA_PREFERENCE,
]

INTERVIEW_CHUNK_TYPES = [INTERVIEW_FEEDBACK, INTERVIEW_WEAKNESS, INTERVIEW_STRENGTH]
