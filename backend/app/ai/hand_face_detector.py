"""
Hand-Face Proximity Detector — Behavior-Based Phone Usage Detection

Instead of detecting the phone *object* (unreliable with YOLO),
this module detects the **behavior of holding something to the face**.

Approach:
  1. MediaPipe HandLandmarker (Tasks API) detects hand landmarks (21 per hand)
  2. Calculate distance between hand center and face bounding box
  3. If hand stays near face for >N consecutive frames → trigger violation

Why this works:
  - Phone detection via YOLO fails on tilted/hidden/angled phones
  - The behavior of "holding phone to ear/face" is consistent regardless
    of what the phone looks like
  - MediaPipe HandLandmarker runs at <10ms on CPU

Thread-safe, per-student state tracking with temporal smoothing.
"""
from __future__ import annotations

import base64
import logging
import math
import os
import threading
import time

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from .proctor_config import (
    HAND_FACE_DISTANCE_THRESHOLD,
    HAND_NEAR_FACE_FRAMES_THRESHOLD,
    DETECTION_DEBUG_LOGGING,
)

logger = logging.getLogger("proctor.hand_face")

# ── HandLandmarker singleton (Tasks API) ─────────────────────────────────────
_hand_landmarker: vision.HandLandmarker | None = None
_hand_lock = threading.Lock()
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")

# ── Per-student temporal state ───────────────────────────────────────────────
_state_lock = threading.Lock()
_student_state: dict[str, dict] = {}

# MediaPipe hand landmark connections for visualization
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),       # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),       # Index
    (0, 9), (9, 10), (10, 11), (11, 12),   # Middle
    (0, 13), (13, 14), (14, 15), (15, 16), # Ring
    (0, 17), (17, 18), (18, 19), (19, 20), # Pinky
    (5, 9), (9, 13), (13, 17),             # Palm
]


def _get_hand_landmarker() -> vision.HandLandmarker:
    """Lazy-load MediaPipe HandLandmarker (Tasks API) with singleton pattern."""
    global _hand_landmarker
    if _hand_landmarker is None:
        with _hand_lock:
            if _hand_landmarker is None:
                base_options = mp_python.BaseOptions(
                    model_asset_path=_MODEL_PATH
                )
                options = vision.HandLandmarkerOptions(
                    base_options=base_options,
                    running_mode=vision.RunningMode.IMAGE,
                    num_hands=2,
                    min_hand_detection_confidence=0.5,
                    min_hand_presence_confidence=0.5,
                    min_tracking_confidence=0.4,
                )
                _hand_landmarker = vision.HandLandmarker.create_from_options(options)
                logger.info("MediaPipe HandLandmarker loaded (Tasks API, max 2 hands)")
    return _hand_landmarker


def warm_up():
    """Pre-load the hands model during server startup."""
    landmarker = _get_hand_landmarker()
    dummy = np.zeros((240, 320, 3), dtype=np.uint8)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=dummy)
    landmarker.detect(mp_image)
    logger.info("MediaPipe HandLandmarker warmed up")


def _get_student_state(student_id: str) -> dict:
    """Get or create per-student temporal tracking state."""
    with _state_lock:
        if student_id not in _student_state:
            _student_state[student_id] = {
                "hand_near_face_count": 0,
                "phone_behavior_triggered": False,
                "last_hand_positions": [],
                "last_detection_time": 0,
            }
        return _student_state[student_id]


def reset_state(student_id: str):
    """Clear tracking state for a student (on session reset)."""
    with _state_lock:
        _student_state.pop(student_id, None)


def _decode_image(image_b64: str) -> np.ndarray | None:
    try:
        data = image_b64.split(",")[1] if "," in image_b64 else image_b64
        img_bytes = base64.b64decode(data)
        arr = np.frombuffer(img_bytes, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _hand_center_from_landmarks(landmarks, img_w: int, img_h: int) -> tuple[float, float]:
    """Calculate the center of the hand using palm landmarks (0, 5, 9, 13, 17)."""
    palm_ids = [0, 5, 9, 13, 17]
    xs = [landmarks[i].x * img_w for i in palm_ids]
    ys = [landmarks[i].y * img_h for i in palm_ids]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _wrist_position(landmarks, img_w: int, img_h: int) -> tuple[float, float]:
    """Get the wrist position (landmark 0)."""
    w = landmarks[0]
    return w.x * img_w, w.y * img_h


def _fingertip_positions(landmarks, img_w: int, img_h: int) -> list[tuple[float, float]]:
    """Get fingertip positions (landmarks 4, 8, 12, 16, 20)."""
    tips = [4, 8, 12, 16, 20]
    return [(landmarks[i].x * img_w, landmarks[i].y * img_h) for i in tips]


def _distance_to_face_bbox(point: tuple[float, float], face_bbox: dict) -> float:
    """
    Min distance from a point to a face bounding box.
    Returns 0 if point is inside the bbox.
    """
    px, py = point
    x1, y1 = face_bbox["x1"], face_bbox["y1"]
    x2, y2 = face_bbox["x2"], face_bbox["y2"]

    if x1 <= px <= x2 and y1 <= py <= y2:
        return 0.0

    closest_x = max(x1, min(px, x2))
    closest_y = max(y1, min(py, y2))
    return math.sqrt((px - closest_x) ** 2 + (py - closest_y) ** 2)


def _normalize_distance(distance: float, face_bbox: dict) -> float:
    """Normalize distance by face size. 1.0 = one face-width away."""
    face_w = face_bbox["x2"] - face_bbox["x1"]
    face_h = face_bbox["y2"] - face_bbox["y1"]
    face_size = max(face_w, face_h, 1)
    return distance / face_size


def analyze_hands(image_b64: str, student_id: str, face_bbox: dict | None = None) -> dict:
    """
    Detect hands and check proximity to face.

    Returns dict with:
      - hands_detected, hand_count
      - hand_near_face (any hand near face this frame)
      - phone_usage_suspected (sustained hand near face)
      - hand_near_face_frames (consecutive frame count)
      - hand_landmarks_px (for debug visualization)
      - proximity_details (per-hand distances)
    """
    img = _decode_image(image_b64)
    if img is None:
        return _empty_result()

    # Resize for fast processing (keep aspect ratio)
    img_h, img_w = img.shape[:2]
    max_dim = 480
    if max(img_h, img_w) > max_dim:
        scale = max_dim / max(img_h, img_w)
        proc_w, proc_h = int(img_w * scale), int(img_h * scale)
        img_resized = cv2.resize(img, (proc_w, proc_h))
    else:
        proc_w, proc_h = img_w, img_h
        img_resized = img
        scale = 1.0

    # Scale face bbox to processing resolution
    scaled_face_bbox = None
    if face_bbox:
        scale_x = proc_w / img_w
        scale_y = proc_h / img_h
        scaled_face_bbox = {
            "x1": int(face_bbox["x1"] * scale_x),
            "y1": int(face_bbox["y1"] * scale_y),
            "x2": int(face_bbox["x2"] * scale_x),
            "y2": int(face_bbox["y2"] * scale_y),
        }

    # Convert BGR → RGB for MediaPipe
    rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    t0 = time.time()
    landmarker = _get_hand_landmarker()
    results = landmarker.detect(mp_image)
    detection_ms = int((time.time() - t0) * 1000)

    state = _get_student_state(student_id)

    if not results.hand_landmarks:
        # No hands — gradual decay
        state["hand_near_face_count"] = max(0, state["hand_near_face_count"] - 2)
        state["phone_behavior_triggered"] = (
            state["hand_near_face_count"] >= HAND_NEAR_FACE_FRAMES_THRESHOLD
        )
        state["last_hand_positions"] = []
        return {
            "hands_detected": False,
            "hand_count": 0,
            "hand_near_face": False,
            "phone_usage_suspected": state["phone_behavior_triggered"],
            "hand_near_face_frames": state["hand_near_face_count"],
            "hand_landmarks_px": [],
            "proximity_details": [],
            "detection_ms": detection_ms,
        }

    hand_count = len(results.hand_landmarks)
    hand_near_face = False
    proximity_details = []
    all_hand_landmarks_px = []

    for hand_lms in results.hand_landmarks:
        center = _hand_center_from_landmarks(hand_lms, proc_w, proc_h)
        wrist = _wrist_position(hand_lms, proc_w, proc_h)
        fingertips = _fingertip_positions(hand_lms, proc_w, proc_h)

        # Collect all landmarks in pixel coords (for visualization)
        landmarks_px = [(lm.x * proc_w, lm.y * proc_h) for lm in hand_lms]
        # Scale back to original image coordinates
        if scale != 1.0:
            landmarks_px = [(x / scale, y / scale) for x, y in landmarks_px]
        all_hand_landmarks_px.append(landmarks_px)

        # Check proximity to face
        if scaled_face_bbox:
            dist_center = _distance_to_face_bbox(center, scaled_face_bbox)
            dist_wrist = _distance_to_face_bbox(wrist, scaled_face_bbox)
            dist_tips = [_distance_to_face_bbox(tip, scaled_face_bbox) for tip in fingertips]
            min_tip_dist = min(dist_tips) if dist_tips else 9999

            min_dist = min(dist_center, dist_wrist, min_tip_dist)
            norm_dist = _normalize_distance(min_dist, scaled_face_bbox)

            is_near = norm_dist < HAND_FACE_DISTANCE_THRESHOLD
            if is_near:
                hand_near_face = True

            proximity_details.append({
                "center_dist": round(float(norm_dist), 2),
                "raw_dist_px": round(float(min_dist), 1),
                "is_near_face": is_near,
            })

            if DETECTION_DEBUG_LOGGING and is_near:
                logger.info(
                    f"[HandFace] Hand near face: norm_dist={norm_dist:.2f} "
                    f"(threshold={HAND_FACE_DISTANCE_THRESHOLD}), "
                    f"frames={state['hand_near_face_count']}/{HAND_NEAR_FACE_FRAMES_THRESHOLD}"
                )
        else:
            proximity_details.append({
                "center_dist": -1,
                "raw_dist_px": -1,
                "is_near_face": False,
            })

    # ── TEMPORAL LOGIC ────────────────────────────────────────────────────────
    if hand_near_face:
        state["hand_near_face_count"] += 1
    else:
        state["hand_near_face_count"] = max(0, state["hand_near_face_count"] - 2)

    phone_suspected = state["hand_near_face_count"] >= HAND_NEAR_FACE_FRAMES_THRESHOLD
    state["phone_behavior_triggered"] = phone_suspected

    if phone_suspected and DETECTION_DEBUG_LOGGING:
        logger.warning(
            f"[HandFace] PHONE USAGE SUSPECTED for {student_id} — "
            f"hand near face for {state['hand_near_face_count']} frames"
        )

    state["last_hand_positions"] = all_hand_landmarks_px
    state["last_detection_time"] = time.time()

    return {
        "hands_detected": True,
        "hand_count": hand_count,
        "hand_near_face": hand_near_face,
        "phone_usage_suspected": phone_suspected,
        "hand_near_face_frames": state["hand_near_face_count"],
        "hand_landmarks_px": all_hand_landmarks_px,
        "proximity_details": proximity_details,
        "detection_ms": detection_ms,
    }


def _empty_result() -> dict:
    return {
        "hands_detected": False,
        "hand_count": 0,
        "hand_near_face": False,
        "phone_usage_suspected": False,
        "hand_near_face_frames": 0,
        "hand_landmarks_px": [],
        "proximity_details": [],
        "detection_ms": 0,
    }
