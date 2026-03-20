"""
Proctor Service — Multi-Loop Orchestration Layer

Architecture (3-tier):
  FAST LOOP  (every frame):  Face detection, head pose, gaze → instant violations
  MEDIUM LOOP (every N frames): YOLO object detection (async, non-blocking)
  SLOW LOOP  (every 2s):     Behavior analysis, identity re-check, scoring decay

Preserves all existing APIs and integrates with Phase 2-5 systems:
  - Score decay + risk timeline (Phase 2)
  - Admin WebSocket alert broadcasting (Phase 3)
  - Identity re-verification (Phase 5)
  - Behavior analysis multiplier (Phase 5)
"""
from __future__ import annotations

import asyncio
import time
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from ..ai.face_analyzer import analyze_face
from ..ai.object_detector import detect_objects
from ..ai.hand_face_detector import analyze_hands, reset_state as reset_hand_state
from ..ai.scoring import (
    compute_frame_score,
    compute_event_score,
    add_score,
    get_score,
    apply_decay,
    get_timeline,
    reset_score,
)
from ..ai.screenshot_manager import save_screenshot
from ..ai.detection_visualizer import draw_debug_overlay
from ..ai.proctor_config import (
    YOLO_FRAME_SKIP,
    NO_FACE_TIMEOUT_S,
    LOOKING_AWAY_TIMEOUT_S,
    GAZE_OFFSCREEN_TIMEOUT_S,
    SCORE_IDENTITY_MISMATCH,
    BEHAVIOR_ANALYSIS_INTERVAL_S,
    DETECTION_BBOX_IN_RESPONSE,
)
from ..ai.identity_verifier import (
    store_reference,
    verify_identity as _verify_identity,
    clear_reference,
)
from ..services.behavior_analyzer import (
    record_violation,
    analyze_behavior,
    reset_behavior,
)

# ── Thread Pool ──────────────────────────────────────────────────────────────
# 3 workers: 1 for face (fast), 1 for YOLO (medium), 1 for identity (slow)
_executor = ThreadPoolExecutor(max_workers=3)

# ── Per-student state ────────────────────────────────────────────────────────
_temporal: dict[str, dict] = {}
_frame_counter: dict[str, int] = {}              # medium-loop frame skip
_cached_yolo: dict[str, dict] = {}               # latest YOLO result
_yolo_running: dict[str, bool] = {}              # prevent concurrent YOLO runs
_last_behavior_time: dict[str, float] = {}       # slow-loop timer
_cached_behavior: dict[str, dict] = {}           # cached behavior result
_IDENTITY_CHECK_INTERVAL_S = 30.0
_last_identity_check: dict[str, float] = {}

# ── Admin alert queue (Phase 3) ──────────────────────────────────────────────
_alert_lock = threading.Lock()
_alert_queue: deque[dict] = deque(maxlen=200)
_admin_ws_clients: list = []


def get_alert_queue() -> deque:
    return _alert_queue

def register_admin_ws(ws) -> None:
    if ws not in _admin_ws_clients:
        _admin_ws_clients.append(ws)

def unregister_admin_ws(ws) -> None:
    if ws in _admin_ws_clients:
        _admin_ws_clients.remove(ws)

def get_admin_ws_clients() -> list:
    return list(_admin_ws_clients)

def _push_alert(alert: dict) -> None:
    with _alert_lock:
        _alert_queue.append(alert)


# ── Session management ───────────────────────────────────────────────────────

def reset_session(student_id: str) -> None:
    """Clear ALL per-student state for a fresh exam session."""
    reset_score(student_id)
    reset_behavior(student_id)
    clear_reference(student_id)
    _temporal.pop(student_id, None)
    _frame_counter.pop(student_id, None)
    _cached_yolo.pop(student_id, None)
    _yolo_running.pop(student_id, None)
    _last_behavior_time.pop(student_id, None)
    _cached_behavior.pop(student_id, None)
    _last_identity_check.pop(student_id, None)
    reset_hand_state(student_id)


def store_identity_reference(student_id: str, image_b64: str) -> dict:
    """Store the reference face for identity verification."""
    return store_reference(student_id, image_b64)


# ── Temporal helpers ─────────────────────────────────────────────────────────

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
        return (now - state[since_key]) >= timeout
    else:
        state[since_key] = None
        return False


def _run_yolo_sync(image_b64: str, student_id: str):
    """Run YOLO in background thread → cache result."""
    try:
        result = detect_objects(image_b64)
        _cached_yolo[student_id] = result
    except Exception:
        pass
    finally:
        _yolo_running[student_id] = False


async def _broadcast_admin_alert(alert: dict) -> None:
    dead = []
    for ws in _admin_ws_clients:
        try:
            await ws.send_json(alert)
        except Exception:
            dead.append(ws)
    for ws in dead:
        unregister_admin_ws(ws)


# ═══════════════════════════════════════════════════════════════════════
# MAIN FRAME ANALYSIS — 3-LOOP ARCHITECTURE
# ═══════════════════════════════════════════════════════════════════════

async def analyze_frame(image_b64: str, student_id: str, db=None) -> dict:
    """
    Multi-loop proctoring pipeline:

    ┌─────────────────────────────────────────────────┐
    │ FAST LOOP (every frame)                         │
    │   MediaPipe face → head pose + gaze + count     │
    │   → Instant violations: no_face, multiple_faces,│
    │     looking_away, gaze_offscreen                │
    ├─────────────────────────────────────────────────┤
    │ MEDIUM LOOP (every N frames, async)             │
    │   YOLO object detection → phone, book, laptop   │
    │   → Uses cached result until next YOLO run      │
    ├─────────────────────────────────────────────────┤
    │ SLOW LOOP (every 2s)                            │
    │   Behavior analysis + identity re-check         │
    │   → Score multiplier, cheating probability      │
    └─────────────────────────────────────────────────┘
    """
    loop = asyncio.get_event_loop()
    now = time.time()

    # ── FAST LOOP: Face analysis (runs every frame) ──────────────────
    face_result = await loop.run_in_executor(
        _executor, analyze_face, image_b64, student_id
    )

    # Fast-loop temporal violation checks
    state = _get_temporal(student_id)
    raw_no_face = face_result.get("no_face", False)
    raw_looking_away = face_result.get("head_pose", {}).get("looking_away", False)
    raw_gaze_off = face_result.get("eye_gaze", {}).get("looking_offscreen", False)

    confirmed_no_face = _check_temporal(state, "no_face", raw_no_face, NO_FACE_TIMEOUT_S, now)
    confirmed_looking_away = _check_temporal(state, "looking_away", raw_looking_away, LOOKING_AWAY_TIMEOUT_S, now)
    confirmed_gaze_off = _check_temporal(state, "gaze_offscreen", raw_gaze_off, GAZE_OFFSCREEN_TIMEOUT_S, now)

    # ── FAST LOOP Part 2: Hand-Face Proximity (behavior-based phone detection) ──
    face_bbox = face_result.get("face_bbox")
    hand_result = await loop.run_in_executor(
        _executor, analyze_hands, image_b64, student_id, face_bbox
    )

    # ── MEDIUM LOOP: YOLO (every YOLO_FRAME_SKIP frames, async) ─────
    # NOTE: YOLO is now used ONLY for multi-person detection, NOT phone detection
    frame_num = _frame_counter.get(student_id, 0) + 1
    _frame_counter[student_id] = frame_num

    if frame_num % YOLO_FRAME_SKIP == 0 and not _yolo_running.get(student_id, False):
        _yolo_running[student_id] = True
        _executor.submit(_run_yolo_sync, image_b64, student_id)

    object_result = _cached_yolo.get(student_id, _empty_yolo())

    # ── Build instant violations (fast + medium + hand combined) ─────
    violations = _build_instant_violations(
        confirmed_no_face, confirmed_looking_away, confirmed_gaze_off,
        face_result, object_result, hand_result,
    )

    # ── SLOW LOOP: Behavior + Identity (every 2s) ───────────────────
    last_beh_time = _last_behavior_time.get(student_id, 0)
    run_slow_loop = (now - last_beh_time) >= BEHAVIOR_ANALYSIS_INTERVAL_S

    identity_result = None
    if run_slow_loop:
        _last_behavior_time[student_id] = now

        # Record violations for behavior analysis
        for v in violations:
            record_violation(student_id, v)

        # Identity re-check (every 30s)
        last_id_check = _last_identity_check.get(student_id, 0)
        if face_result.get("face_detected") and now - last_id_check >= _IDENTITY_CHECK_INTERVAL_S:
            _last_identity_check[student_id] = now
            try:
                identity_result = await loop.run_in_executor(
                    _executor, _verify_identity, student_id, image_b64
                )
                if identity_result and not identity_result.get("is_same_person", True):
                    violations.append("identity_mismatch")
                    record_violation(student_id, "identity_mismatch")
            except Exception:
                pass

        # Behavior analysis → multiplier
        behavior = analyze_behavior(student_id)
        _cached_behavior[student_id] = behavior
    else:
        # Between slow-loop ticks: still record violations, use cached behavior
        for v in violations:
            record_violation(student_id, v)
        behavior = _cached_behavior.get(student_id, _default_behavior())

    multiplier = behavior.get("multiplier", 1.0)

    # ── Scoring (every frame if violations, otherwise decay) ─────────
    frame_score = compute_frame_score(
        {**face_result,
         "no_face": confirmed_no_face,
         "head_pose": {**face_result.get("head_pose", {}), "looking_away": confirmed_looking_away},
         "eye_gaze": {**face_result.get("eye_gaze", {}), "looking_offscreen": confirmed_gaze_off}},
        object_result,
    )

    if "identity_mismatch" in violations:
        frame_score += SCORE_IDENTITY_MISMATCH

    if frame_score > 0:
        score_result = add_score(student_id, frame_score, multiplier)
    else:
        score_result = apply_decay(student_id)

    score_result["frame_score"] = score_result.get("frame_score", frame_score)
    score_result["behavior"] = behavior

    # ── Debug Visualization Overlay ──────────────────────────────────
    debug_image_b64 = image_b64
    if DETECTION_BBOX_IN_RESPONSE:
        try:
            debug_image_b64 = draw_debug_overlay(image_b64, face_result, object_result, violations, hand_result)
        except Exception as e:
            pass

    # ── Screenshot + DB log + admin alert (only on violations) ───────
    screenshot_path: Optional[str] = None
    if violations:
        primary = violations[0]
        # Save the frame WITH BOUNDING BOXES as evidence
        screenshot_path = save_screenshot(debug_image_b64, student_id, primary)

    if db is not None and violations:
        try:
            await db.violation_events.insert_one({
                "student_id": student_id,
                "violations": violations,
                "frame_score": score_result.get("frame_score", 0),
                "cumulative_score": score_result.get("cumulative_score", 0),
                "risk_level": score_result.get("risk_level", "Low"),
                "behavior_severity": behavior.get("severity", "low"),
                "cheating_probability": behavior.get("cheating_probability", 0),
                "screenshot_path": screenshot_path,
                "timestamp": int(now * 1000),
            })
        except Exception:
            pass

    if violations:
        alert = {
            "type": "violation",
            "student_id": student_id,
            "violations": violations,
            "risk_score": score_result.get("cumulative_score", 0),
            "risk_level": score_result.get("risk_level", "Low"),
            "behavior_severity": behavior.get("severity", "low"),
            "cheating_probability": behavior.get("cheating_probability", 0),
            "timestamp": int(now * 1000),
        }
        _push_alert(alert)
        try:
            await _broadcast_admin_alert(alert)
        except Exception:
            pass

    return {
        "face_detected": face_result.get("face_detected", False),
        "face_count": face_result.get("face_count", 0),
        "multiple_faces": face_result.get("multiple_faces", False),
        "no_face": confirmed_no_face,
        "head_pose": face_result.get("head_pose", {}),
        "eye_gaze": face_result.get("eye_gaze", {}),
        "face_bbox": face_result.get("face_bbox"),
        "objects_detected": object_result.get("objects_detected", []),
        "suspicious_found": object_result.get("suspicious_found", False),
        "person_count": object_result.get("person_count", 0),
        "hand_near_face": hand_result.get("hand_near_face", False),
        "phone_usage_suspected": hand_result.get("phone_usage_suspected", False),
        "hand_near_face_frames": hand_result.get("hand_near_face_frames", 0),
        "hands_detected": hand_result.get("hands_detected", False),
        "score": score_result,
        "behavior": behavior,
        "identity": identity_result,
        "violations": violations,
        "violation_detected": len(violations) > 0,
        "screenshot_path": screenshot_path,
        "timestamp": int(now * 1000),
    }


# ═══════════════════════════════════════════════════════════════════════
# BROWSER EVENTS (unchanged API)
# ═══════════════════════════════════════════════════════════════════════

async def record_browser_event(student_id: str, event_type: str, db=None) -> dict:
    """Record a browser-side event — instant score + behavior update."""
    pts = compute_event_score(event_type)

    if pts > 0:
        record_violation(student_id, event_type)
    behavior = analyze_behavior(student_id)
    multiplier = behavior.get("multiplier", 1.0)

    score_result = add_score(student_id, pts, multiplier) if pts > 0 else get_score(student_id)
    score_result["frame_score"] = score_result.get("frame_score", pts)
    score_result["behavior"] = behavior

    if db is not None and pts > 0:
        try:
            await db.violation_events.insert_one({
                "student_id": student_id,
                "violations": [event_type],
                "frame_score": score_result.get("frame_score", 0),
                "cumulative_score": score_result.get("cumulative_score", 0),
                "risk_level": score_result.get("risk_level", "Low"),
                "behavior_severity": behavior.get("severity", "low"),
                "cheating_probability": behavior.get("cheating_probability", 0),
                "screenshot_path": None,
                "timestamp": int(time.time() * 1000),
            })
        except Exception:
            pass

    if pts > 0:
        alert = {
            "type": "browser_event",
            "student_id": student_id,
            "violations": [event_type],
            "risk_score": score_result.get("cumulative_score", 0),
            "risk_level": score_result.get("risk_level", "Low"),
            "behavior_severity": behavior.get("severity", "low"),
            "timestamp": int(time.time() * 1000),
        }
        _push_alert(alert)
        try:
            await _broadcast_admin_alert(alert)
        except Exception:
            pass

    return score_result


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _build_instant_violations(
    no_face: bool, looking_away: bool, gaze_off: bool,
    face_result: dict, object_result: dict, hand_result: dict,
) -> list[str]:
    """
    Build violations list from fast-loop + medium-loop + hand results.
    These trigger INSTANTLY — no waiting for behavior analysis.
    """
    violations = []

    # Fast-loop violations (face)
    if no_face:
        violations.append("no_face")
    if face_result.get("multiple_faces"):
        violations.append("multiple_faces")
    if looking_away:
        violations.append("looking_away")
    if gaze_off:
        violations.append("gaze_offscreen")

    # Medium-loop violations (YOLO — multi-person only)
    if object_result.get("person_count", 0) > 1:
        if "multiple_faces" not in violations:
            violations.append("multiple_faces")

    # Hand-Face Proximity: Behavior-based phone usage detection
    if hand_result.get("phone_usage_suspected", False):
        violations.append("phone_usage_suspected")

    return violations


def _empty_yolo() -> dict:
    return {"objects_detected": [], "suspicious_found": False,
            "person_count": 0, "phone_detected": False, "possible_phone_detected": False, "all_detections": []}


def _default_behavior() -> dict:
    return {"severity": "low", "multiplier": 1.0, "patterns": [],
            "cheating_probability": 0.0}
