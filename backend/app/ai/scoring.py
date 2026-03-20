"""
Scoring Engine — Adaptive risk scorer with time-based decay.

Features:
  - Per-student cumulative score with weighted violations
  - Time-based decay: score reduces when no violations occur
  - Risk score timeline: list of (timestamp_ms, score) for graphing
  - 4-tier risk levels: Low / Medium / High / Critical
  - Thread-safe in-memory state
  - Configurable via proctor_config.py
"""
from __future__ import annotations

import threading
import time
from typing import Optional

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
    SCORE_DEVTOOLS_OPEN,
    SCORE_IDENTITY_MISMATCH,
    SCORE_DECAY_RATE,
    SCORE_DECAY_INTERVAL_S,
    SCORE_DECAY_GRACE_PERIOD_S,
    MAX_RISK_SCORE,
    MIN_RISK_SCORE,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MEDIUM,
    RISK_LEVEL_HIGH,
)

# ── Score Weights (from config) ───────────────────────────────────────────────

WEIGHTS = {
    "no_face":            SCORE_NO_FACE,
    "looking_away":       SCORE_LOOKING_AWAY,
    "gaze_offscreen":     SCORE_GAZE_OFFSCREEN,
    "multiple_faces":     SCORE_MULTIPLE_FACES,
    "object":             SCORE_OBJECT_DETECTED,
    "tab_switch":         SCORE_TAB_SWITCH,
    "fullscreen_exit":    SCORE_FULLSCREEN_EXIT,
    "copy_paste":         SCORE_COPY_PASTE,
    "right_click":        SCORE_RIGHT_CLICK,
    "devtools_open":      SCORE_DEVTOOLS_OPEN,
    "identity_mismatch":  SCORE_IDENTITY_MISMATCH,
}


# ── Risk Level Classification ─────────────────────────────────────────────────

def _risk_level(score: int) -> str:
    """
    4-tier classification:
      0 – 20   → Low
      21 – 50  → Medium
      51 – 80  → High
      81+      → Critical
    """
    if score <= RISK_LEVEL_LOW:
        return "Low"
    elif score <= RISK_LEVEL_MEDIUM:
        return "Medium"
    elif score <= RISK_LEVEL_HIGH:
        return "High"
    else:
        return "Critical"


# ── Per-Student State (thread-safe) ───────────────────────────────────────────

_lock = threading.Lock()

# Cumulative score per student
_scores: dict[str, int] = {}

# Timestamps for decay logic
_last_violation_time: dict[str, float] = {}
_last_decay_time: dict[str, float] = {}

# Risk score timeline: student_id → [(timestamp_ms, score)]
_timelines: dict[str, list[tuple[int, int]]] = {}

# Maximum timeline length (cap to prevent unbounded memory growth)
_MAX_TIMELINE_LEN = 500


# ── Core Scoring Functions ────────────────────────────────────────────────────

def compute_frame_score(face_result: dict, object_result: dict) -> int:
    """Compute the points earned from a single frame's violations."""
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
    """Compute points for a browser-side event."""
    return WEIGHTS.get(event_type, 0)


def add_score(student_id: str, points: int, multiplier: float = 1.0) -> dict:
    """
    Add violation points to a student's cumulative score.
    Points are multiplied by the behavior-analysis multiplier.
    Updates timeline and records violation timestamp.
    """
    adjusted = int(round(points * multiplier))
    now = time.time()
    now_ms = int(now * 1000)

    with _lock:
        current = _scores.get(student_id, 0)
        new_score = min(current + adjusted, MAX_RISK_SCORE)
        _scores[student_id] = new_score

        # Record violation time (resets decay grace period)
        _last_violation_time[student_id] = now

        # Append to timeline (avoid duplicate timestamps)
        _append_timeline(student_id, now_ms, new_score)

    return {
        "frame_score": adjusted,
        "base_score": points,
        "multiplier": multiplier,
        "cumulative_score": new_score,
        "risk_level": _risk_level(new_score),
    }


def apply_decay(student_id: str) -> dict:
    """
    Apply time-based score decay if no violations recently.

    Rules:
      1. Only decay if SCORE_DECAY_GRACE_PERIOD_S has elapsed since last violation
      2. Only decay if SCORE_DECAY_INTERVAL_S has elapsed since last decay tick
      3. Reduce score by SCORE_DECAY_RATE, never below MIN_RISK_SCORE
      4. Record decay event in timeline

    Returns current score state (same shape as get_score).
    """
    now = time.time()
    now_ms = int(now * 1000)

    with _lock:
        current = _scores.get(student_id, 0)

        # Nothing to decay
        if current <= MIN_RISK_SCORE:
            return _make_result(student_id, current)

        # Check grace period: no decay within N seconds of last violation
        last_viol = _last_violation_time.get(student_id, 0)
        if now - last_viol < SCORE_DECAY_GRACE_PERIOD_S:
            return _make_result(student_id, current)

        # Check interval: only decay every N seconds
        last_decay = _last_decay_time.get(student_id, 0)
        if now - last_decay < SCORE_DECAY_INTERVAL_S:
            return _make_result(student_id, current)

        # Apply decay
        new_score = max(current - SCORE_DECAY_RATE, MIN_RISK_SCORE)
        _scores[student_id] = new_score
        _last_decay_time[student_id] = now

        # Record decay in timeline
        _append_timeline(student_id, now_ms, new_score)

    return {
        "cumulative_score": new_score,
        "risk_level": _risk_level(new_score),
        "decayed": True,
        "decay_amount": current - new_score,
    }


def get_score(student_id: str) -> dict:
    """Get current score state for a student."""
    with _lock:
        current = _scores.get(student_id, 0)
    return _make_result(student_id, current)


def get_timeline(student_id: str) -> list[dict]:
    """
    Get the full risk score timeline for a student.
    Returns list of {timestamp, score} dicts for charting.
    """
    with _lock:
        entries = _timelines.get(student_id, [])
        return [{"timestamp": ts, "score": sc} for ts, sc in entries]


def reset_score(student_id: str) -> None:
    """Clear all scoring state for a student (called on session start/end)."""
    with _lock:
        _scores.pop(student_id, None)
        _last_violation_time.pop(student_id, None)
        _last_decay_time.pop(student_id, None)
        _timelines.pop(student_id, None)


# ── Internal Helpers ──────────────────────────────────────────────────────────

def _make_result(student_id: str, score: int) -> dict:
    """Build a standard score response dict."""
    return {
        "cumulative_score": score,
        "risk_level": _risk_level(score),
    }


def _append_timeline(student_id: str, ts_ms: int, score: int) -> None:
    """
    Append a (timestamp_ms, score) to the timeline.
    Avoids duplicate timestamps. Caps at _MAX_TIMELINE_LEN.
    Must be called under _lock.
    """
    if student_id not in _timelines:
        _timelines[student_id] = []

    timeline = _timelines[student_id]

    # Avoid duplicate timestamp entries
    if timeline and timeline[-1][0] == ts_ms:
        # Update score at existing timestamp instead of duplicating
        timeline[-1] = (ts_ms, score)
    else:
        timeline.append((ts_ms, score))

    # Cap length (FIFO eviction of oldest entries)
    if len(timeline) > _MAX_TIMELINE_LEN:
        _timelines[student_id] = timeline[-_MAX_TIMELINE_LEN:]
