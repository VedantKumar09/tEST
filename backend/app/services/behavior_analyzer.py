"""
Behavior Analyzer — Pattern-based intelligence layer for smart violation detection.

Instead of treating each violation independently, this module looks for
temporal patterns and combined violation clusters that indicate higher
suspicion of cheating.

Patterns detected:
  A) Frequent looking away:  3+ in 60s window  → Medium severity
  B) Rapid tab switching:    2+ in 30s window   → High severity
  C) Combined violations:    phone + looking_away within 10s → High severity
  D) Sustained no-face:      2+ no_face in 30s  → Medium severity
  E) Object + gaze off:      object + gaze offscreen within 10s → High severity

Output:
  {
    severity: "low" | "medium" | "high",
    multiplier: 1.0 | 1.5 | 2.0,
    patterns: ["rapid_tab_switch", ...],
    cheating_probability: 0.0 – 1.0,
  }

Thread-safe per-student sliding-window state.
"""
from __future__ import annotations

import threading
import time
from collections import deque


# ── Config ────────────────────────────────────────────────────────────────────

# Windows for pattern detection (seconds)
LOOKING_AWAY_WINDOW = 60.0
LOOKING_AWAY_THRESHOLD = 3
TAB_SWITCH_WINDOW = 30.0
TAB_SWITCH_THRESHOLD = 2
NO_FACE_WINDOW = 30.0
NO_FACE_THRESHOLD = 2
COMBINED_WINDOW = 10.0  # seconds for combined pattern checks

# Severity → multiplier mapping
MULTIPLIERS = {
    "low": 1.0,
    "medium": 1.5,
    "high": 2.0,
}

# ── Per-student state ─────────────────────────────────────────────────────────

_lock = threading.Lock()

# Recent violations per student: deque of (timestamp, violation_type)
_violation_history: dict[str, deque] = {}

# Cumulative pattern stats
_pattern_counts: dict[str, dict[str, int]] = {}

_MAX_HISTORY = 200


def _get_history(student_id: str) -> deque:
    """Get or create the violation history deque for a student."""
    if student_id not in _violation_history:
        _violation_history[student_id] = deque(maxlen=_MAX_HISTORY)
    return _violation_history[student_id]


def _get_stats(student_id: str) -> dict:
    """Get cumulative pattern stats for a student."""
    if student_id not in _pattern_counts:
        _pattern_counts[student_id] = {
            "total_violations": 0,
            "looking_away_count": 0,
            "tab_switch_count": 0,
            "no_face_count": 0,
            "object_count": 0,
            "identity_mismatch_count": 0,
        }
    return _pattern_counts[student_id]


# ── Core Analysis ─────────────────────────────────────────────────────────────

def record_violation(student_id: str, violation_type: str) -> None:
    """Record a violation for pattern analysis. Call on every confirmed violation."""
    now = time.time()
    with _lock:
        history = _get_history(student_id)
        history.append((now, violation_type))

        stats = _get_stats(student_id)
        stats["total_violations"] += 1

        if violation_type == "looking_away":
            stats["looking_away_count"] += 1
        elif violation_type == "tab_switch":
            stats["tab_switch_count"] += 1
        elif violation_type == "no_face":
            stats["no_face_count"] += 1
        elif violation_type.startswith("object:"):
            stats["object_count"] += 1
        elif violation_type == "identity_mismatch":
            stats["identity_mismatch_count"] += 1


def analyze_behavior(student_id: str) -> dict:
    """
    Analyze recent violation patterns and return severity assessment.

    Returns:
      severity: "low" | "medium" | "high"
      multiplier: 1.0, 1.5, or 2.0
      patterns: list of detected pattern names
      cheating_probability: 0.0 – 1.0
    """
    now = time.time()
    detected_patterns = []

    with _lock:
        history = _get_history(student_id)
        stats = _get_stats(student_id)

        # Build recent events by type within windows
        recent_looking_away = []
        recent_tab_switch = []
        recent_no_face = []
        recent_objects = []
        recent_gaze_off = []

        for ts, vtype in history:
            age = now - ts
            if vtype == "looking_away" and age <= LOOKING_AWAY_WINDOW:
                recent_looking_away.append(ts)
            if vtype == "tab_switch" and age <= TAB_SWITCH_WINDOW:
                recent_tab_switch.append(ts)
            if vtype == "no_face" and age <= NO_FACE_WINDOW:
                recent_no_face.append(ts)
            if vtype.startswith("object:") and age <= COMBINED_WINDOW:
                recent_objects.append(ts)
            if vtype == "gaze_offscreen" and age <= COMBINED_WINDOW:
                recent_gaze_off.append(ts)

        # Pattern A: Frequent looking away
        if len(recent_looking_away) >= LOOKING_AWAY_THRESHOLD:
            detected_patterns.append("frequent_looking_away")

        # Pattern B: Rapid tab switching
        if len(recent_tab_switch) >= TAB_SWITCH_THRESHOLD:
            detected_patterns.append("rapid_tab_switch")

        # Pattern C: Phone + looking away within 10s
        for obj_ts in recent_objects:
            for la_ts in recent_looking_away:
                if abs(obj_ts - la_ts) <= COMBINED_WINDOW:
                    if "phone_plus_looking_away" not in detected_patterns:
                        detected_patterns.append("phone_plus_looking_away")
                    break

        # Pattern D: Sustained no-face
        if len(recent_no_face) >= NO_FACE_THRESHOLD:
            detected_patterns.append("sustained_no_face")

        # Pattern E: Object + gaze offscreen within 10s
        for obj_ts in recent_objects:
            for gaze_ts in recent_gaze_off:
                if abs(obj_ts - gaze_ts) <= COMBINED_WINDOW:
                    if "object_plus_gaze_off" not in detected_patterns:
                        detected_patterns.append("object_plus_gaze_off")
                    break

        # Pattern F: Identity mismatch (always high)
        if stats.get("identity_mismatch_count", 0) > 0:
            detected_patterns.append("identity_mismatch")

    # ── Determine severity ──
    high_patterns = {
        "rapid_tab_switch", "phone_plus_looking_away",
        "object_plus_gaze_off", "identity_mismatch",
    }
    medium_patterns = {"frequent_looking_away", "sustained_no_face"}

    has_high = any(p in high_patterns for p in detected_patterns)
    has_medium = any(p in medium_patterns for p in detected_patterns)

    if has_high:
        severity = "high"
    elif has_medium:
        severity = "medium"
    else:
        severity = "low"

    multiplier = MULTIPLIERS[severity]

    # ── Cheating probability estimate ──
    # Simple heuristic: weighted feature combination
    prob = _estimate_cheating_probability(stats, detected_patterns)

    return {
        "severity": severity,
        "multiplier": multiplier,
        "patterns": detected_patterns,
        "cheating_probability": round(prob, 3),
    }


def _estimate_cheating_probability(stats: dict, patterns: list) -> float:
    """
    Lightweight cheating probability estimate from violation stats + patterns.
    No ML training needed — uses a calibrated weighted sum.
    """
    score = 0.0

    # Base violation frequency contribution
    total = stats.get("total_violations", 0)
    if total > 0:
        score += min(total * 0.02, 0.3)  # max 0.3 from raw count

    # Pattern-specific boosts
    pattern_weights = {
        "rapid_tab_switch": 0.20,
        "phone_plus_looking_away": 0.25,
        "object_plus_gaze_off": 0.20,
        "identity_mismatch": 0.35,
        "frequent_looking_away": 0.10,
        "sustained_no_face": 0.10,
    }
    for p in patterns:
        score += pattern_weights.get(p, 0.05)

    # Object detection is strong signal
    if stats.get("object_count", 0) > 0:
        score += 0.15

    # Identity mismatch is strongest signal
    if stats.get("identity_mismatch_count", 0) > 0:
        score += 0.20

    return min(score, 1.0)


# ── Session management ────────────────────────────────────────────────────────

def reset_behavior(student_id: str) -> None:
    """Clear all behavior state for a fresh session."""
    with _lock:
        _violation_history.pop(student_id, None)
        _pattern_counts.pop(student_id, None)


def get_behavior_summary(student_id: str) -> dict:
    """Get cumulative stats for admin review."""
    with _lock:
        stats = _get_stats(student_id).copy()
    analysis = analyze_behavior(student_id)
    return {**stats, **analysis}
