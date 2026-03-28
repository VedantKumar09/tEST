"""
Scoring Engine — Suspicious activity risk scorer
Uses weights from proctor_config.py.
Maintains per-student cumulative scores in memory.
"""
from __future__ import annotations

import threading
from .proctor_config import (
    SCORE_NO_FACE,
    SCORE_LOOKING_AWAY,
    SCORE_GAZE_OFFSCREEN,
    SCORE_MULTIPLE_FACES,
    SCORE_OBJECT_DETECTED,
    SCORE_TAB_SWITCH,
    SCORE_FULLSCREEN_EXIT,
    SCORE_COPY_PASTE,
    SCORE_RIGHT_CLICK,
)

# ── Score weights (from config) ───────────────────────────────────────────────
WEIGHTS = {
    "no_face":         SCORE_NO_FACE,
    "looking_away":    SCORE_LOOKING_AWAY,
    "gaze_offscreen":  SCORE_GAZE_OFFSCREEN,
    "multiple_faces":  SCORE_MULTIPLE_FACES,
    "object":          SCORE_OBJECT_DETECTED,
    "tab_switch":      SCORE_TAB_SWITCH,
    "fullscreen_exit": SCORE_FULLSCREEN_EXIT,
    "copy_paste":      SCORE_COPY_PASTE,
    "right_click":     SCORE_RIGHT_CLICK,
}


def _risk_level(score: int) -> str:
    """Risk levels aligned with industry standards (HackerRank/CodeSignal).
    Minor events alone should never escalate beyond 'Safe'.
    Only sustained patterns of major violations should reach 'Cheating'."""
    if score <= 10:
        return "Safe"
    elif score <= 20:
        return "Suspicious"
    elif score <= 35:
        return "High Risk"
    else:
        return "Cheating"


# ── In-memory cumulative scores (thread-safe) ────────────────────────────────
_lock = threading.Lock()
_scores: dict[str, int] = {}


def compute_frame_score(face_result: dict, object_result: dict) -> int:
    score = 0
    if face_result.get("no_face"):
        score += WEIGHTS["no_face"]
    if face_result.get("multiple_faces"):
        score += WEIGHTS["multiple_faces"]
    if face_result.get("head_pose", {}).get("looking_away"):
        score += WEIGHTS["looking_away"]
    if face_result.get("eye_gaze", {}).get("looking_offscreen"):
        score += WEIGHTS["gaze_offscreen"]
    for _ in object_result.get("objects_detected", []):
        score += WEIGHTS["object"]
    return score


def compute_event_score(event_type: str) -> int:
    return WEIGHTS.get(event_type, 0)


def add_score(student_id: str, points: int) -> dict:
    with _lock:
        _scores[student_id] = _scores.get(student_id, 0) + points
        cumulative = _scores[student_id]
    return {
        "frame_score": points,
        "cumulative_score": cumulative,
        "risk_level": _risk_level(cumulative),
    }


def get_score(student_id: str) -> dict:
    with _lock:
        cumulative = _scores.get(student_id, 0)
    return {
        "cumulative_score": cumulative,
        "risk_level": _risk_level(cumulative),
    }


def reset_score(student_id: str) -> None:
    with _lock:
        _scores.pop(student_id, None)
