"""
Proctor Service — Orchestration layer with temporal violation buffers.
Routes call this; it coordinates face_analyzer, object_detector, scoring,
and screenshot_manager, keeping routes lightweight.

Key stabilisation:  Violations (no_face, looking_away, gaze_offscreen) are
only emitted when the condition persists continuously for a configurable
number of seconds.  This eliminates transient single-frame false positives.
"""
from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from ..ai.face_analyzer import analyze_face
from ..ai.object_detector import detect_objects
from ..ai.scoring import compute_frame_score, compute_event_score, add_score, get_score
from ..ai.screenshot_manager import save_screenshot
from ..ai.proctor_config import (
    YOLO_INTERVAL_S,
    NO_FACE_TIMEOUT_S,
    LOOKING_AWAY_TIMEOUT_S,
    GAZE_OFFSCREEN_TIMEOUT_S,
)

# Thread pool for CPU-bound AI work
_executor = ThreadPoolExecutor(max_workers=2)

# ── Per-student temporal state ────────────────────────────────────────────────
_temporal: dict[str, dict[str, Optional[float]]] = {}
_last_yolo_run: dict[str, float] = {}
_cached_yolo: dict[str, dict] = {}       # cached YOLO results per student
_yolo_running: dict[str, bool] = {}      # prevent duplicate YOLO runs


def _get_temporal(student_id: str) -> dict:
    if student_id not in _temporal:
        _temporal[student_id] = {
            "no_face_since": None,
            "looking_away_since": None,
            "gaze_offscreen_since": None,
        }
    return _temporal[student_id]


def _check_temporal(state: dict, key: str, is_active: bool, timeout: float, now: float) -> bool:
    since_key = f"{key}_since"
    if is_active:
        if state[since_key] is None:
            state[since_key] = now
        elapsed = now - state[since_key]
        return elapsed >= timeout
    else:
        state[since_key] = None
        return False


def _run_yolo_background(image_b64: str, student_id: str):
    """Run YOLO in background thread and cache the result."""
    try:
        result = detect_objects(image_b64)
        _cached_yolo[student_id] = result
    except Exception:
        pass
    finally:
        _yolo_running[student_id] = False


async def analyze_frame(image_b64: str, student_id: str, db=None) -> dict:
    """
    Low-latency analysis pipeline:
    1. Face analysis (MediaPipe) — runs every frame, returns immediately
    2. YOLO object detection — runs in background every 2s, uses cached results
    3. Temporal violation checks
    4. Scoring (only on confirmed violations)
    5. Screenshot + DB log on confirmed violations
    """
    loop = asyncio.get_event_loop()
    now = time.time()

    # 1. Face analysis — always runs, returns quickly (~30-50ms)
    face_result = await loop.run_in_executor(
        _executor, analyze_face, image_b64, student_id
    )

    # 2. YOLO — fire-and-forget background, use cached results for response
    last_yolo = _last_yolo_run.get(student_id, 0)
    if now - last_yolo >= YOLO_INTERVAL_S and not _yolo_running.get(student_id, False):
        _yolo_running[student_id] = True
        _last_yolo_run[student_id] = now
        # Fire-and-forget: don't await, don't block the response
        _executor.submit(_run_yolo_background, image_b64, student_id)

    # Use cached YOLO result (from previous background run)
    object_result = _cached_yolo.get(student_id, {"objects_detected": [], "suspicious_found": False})

    # 3. Temporal violation checks
    state = _get_temporal(student_id)

    raw_no_face = face_result.get("no_face", False)
    raw_looking_away = face_result.get("head_pose", {}).get("looking_away", False)
    raw_gaze_off = face_result.get("eye_gaze", {}).get("looking_offscreen", False)

    confirmed_no_face = _check_temporal(state, "no_face", raw_no_face, NO_FACE_TIMEOUT_S, now)
    confirmed_looking_away = _check_temporal(state, "looking_away", raw_looking_away, LOOKING_AWAY_TIMEOUT_S, now)
    confirmed_gaze_off = _check_temporal(state, "gaze_offscreen", raw_gaze_off, GAZE_OFFSCREEN_TIMEOUT_S, now)

    # Build confirmed violation list
    violations = _build_confirmed_violations(
        confirmed_no_face, confirmed_looking_away, confirmed_gaze_off,
        face_result, object_result,
    )

    # 4. Scoring — only on confirmed violations
    frame_score = compute_frame_score(
        {**face_result,
         "no_face": confirmed_no_face,
         "head_pose": {**face_result.get("head_pose", {}), "looking_away": confirmed_looking_away},
         "eye_gaze": {**face_result.get("eye_gaze", {}), "looking_offscreen": confirmed_gaze_off}},
        object_result,
    )
    score_result = add_score(student_id, frame_score) if frame_score > 0 else get_score(student_id)
    score_result["frame_score"] = frame_score

    # 5. Screenshot + DB log
    screenshot_path: Optional[str] = None
    if violations:
        primary_event = violations[0]
        screenshot_path = save_screenshot(image_b64, student_id, primary_event)

    if db is not None and violations:
        try:
            await db.violation_events.insert_one({
                "student_id": student_id,
                "violations": violations,
                "frame_score": frame_score,
                "cumulative_score": score_result.get("cumulative_score", 0),
                "risk_level": score_result.get("risk_level", "Safe"),
                "screenshot_path": screenshot_path,
                "timestamp": int(now * 1000),
            })
        except Exception:
            pass

    return {
        # Face — raw values for UI display
        "face_detected": face_result.get("face_detected", False),
        "face_count": face_result.get("face_count", 0),
        "multiple_faces": face_result.get("multiple_faces", False),
        "no_face": confirmed_no_face,           # temporal-filtered
        "head_pose": face_result.get("head_pose", {}),
        "eye_gaze": face_result.get("eye_gaze", {}),
        "face_bbox": face_result.get("face_bbox"),
        # Objects
        "objects_detected": object_result.get("objects_detected", []),
        "suspicious_found": object_result.get("suspicious_found", False),
        # Scoring
        "score": score_result,
        # Violations — only confirmed ones
        "violations": violations,
        "violation_detected": len(violations) > 0,
        "screenshot_path": screenshot_path,
        "timestamp": int(now * 1000),
    }


async def record_browser_event(student_id: str, event_type: str, db=None) -> dict:
    """Record a browser-side event (tab switch, fullscreen exit, etc.)."""
    pts = compute_event_score(event_type)
    score_result = add_score(student_id, pts) if pts > 0 else get_score(student_id)
    score_result["frame_score"] = pts

    if db is not None and pts > 0:
        try:
            await db.violation_events.insert_one({
                "student_id": student_id,
                "violations": [event_type],
                "frame_score": pts,
                "cumulative_score": score_result.get("cumulative_score", 0),
                "risk_level": score_result.get("risk_level", "Safe"),
                "screenshot_path": None,
                "timestamp": int(time.time() * 1000),
            })
        except Exception:
            pass

    return score_result


def _build_confirmed_violations(
    no_face: bool,
    looking_away: bool,
    gaze_off: bool,
    face_result: dict,
    object_result: dict,
) -> list[str]:
    """Only include violations that passed temporal thresholds."""
    violations = []
    if no_face:
        violations.append("no_face")
    if face_result.get("multiple_faces"):
        violations.append("multiple_faces")       # instant — no buffer needed
    if looking_away:
        violations.append("looking_away")
    if gaze_off:
        violations.append("gaze_offscreen")
    if object_result.get("suspicious_found"):
        for obj in object_result.get("objects_detected", []):
            violations.append(f"object:{obj['class']}")
    return violations
