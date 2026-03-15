"""
Face Analyzer — MediaPipe FaceLandmarker (tasks API)
Provides: face detection, head pose estimation (solvePnP), eye gaze tracking.

Stabilisation features:
  - Per-student yaw/pitch moving-average over GAZE_SMOOTHING_WINDOW frames
  - Per-student gaze moving-average over GAZE_SMOOTHING_WINDOW frames
  - Bounding box exponential smoothing (BBOX_SMOOTH_FACTOR)
  - Thresholds read from proctor_config.py

Bug fixes (v3):
  - Chin landmark corrected: 199 (upper lip) → 152 (actual chin)
  - Added yaw/pitch moving-average smoothing (was missing)
  - Gaze gracefully falls back if iris landmarks unavailable

The temporal violation logic (must persist 2–3s) lives in proctor_service.py.
"""
import cv2
import numpy as np
import base64
import os
import collections
import threading

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from .proctor_config import (
    HEAD_POSE_YAW_THRESHOLD,
    HEAD_POSE_PITCH_UP_THRESHOLD,
    HEAD_POSE_PITCH_DOWN_THRESHOLD,
    GAZE_LEFT_THRESHOLD,
    GAZE_RIGHT_THRESHOLD,
    GAZE_SMOOTHING_WINDOW,
    BBOX_SMOOTH_FACTOR,
)

# ── Lazy-loaded FaceLandmarker singleton ───────────────────────────────────────
_landmarker: vision.FaceLandmarker | None = None
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "face_landmarker.task")


def _get_landmarker() -> vision.FaceLandmarker:
    global _landmarker
    if _landmarker is None:
        base_options = mp_python.BaseOptions(model_asset_path=_MODEL_PATH)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_faces=2,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        _landmarker = vision.FaceLandmarker.create_from_options(options)
    return _landmarker


# ── 3-D reference model for solvePnP ─────────────────────────────────────────
# The 3D points MUST match the order of _POSE_LANDMARK_IDS below.
#
#   Index 1   = Nose tip
#   Index 152 = Chin  (NOT 199 — that's the upper lip!)
#   Index 33  = Left eye outer corner
#   Index 263 = Right eye outer corner
#   Index 61  = Left mouth corner
#   Index 291 = Right mouth corner
#
_FACE_3D_MODEL = np.array([
    [0.0,      0.0,     0.0],     # Nose tip
    [0.0,   -330.0,   -65.0],     # Chin
    [-225.0,  170.0,  -135.0],    # Left eye outer corner
    [225.0,   170.0,  -135.0],    # Right eye outer corner
    [-150.0, -150.0,  -125.0],    # Left mouth corner
    [150.0,  -150.0,  -125.0],    # Right mouth corner
], dtype=np.float64)

_POSE_LANDMARK_IDS = [1, 152, 33, 263, 61, 291]
#                        ^^^
#                   FIXED: was 199 (upper lip → garbage solvePnP)


# ── Per-student smoothing state (thread-safe) ─────────────────────────────────
_lock = threading.Lock()
_yaw_history: dict[str, collections.deque] = {}
_pitch_history: dict[str, collections.deque] = {}
_gaze_history: dict[str, collections.deque] = {}
_prev_bbox: dict[str, dict] = {}


def _decode_image(image_b64: str) -> np.ndarray | None:
    try:
        data = image_b64.split(",")[1] if "," in image_b64 else image_b64
        img_bytes = base64.b64decode(data)
        arr = np.frombuffer(img_bytes, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _estimate_head_pose(landmarks, img_w: int, img_h: int, student_id: str = "") -> dict:
    """
    Estimate yaw & pitch from 2D landmark geometry (no solvePnP / Euler angles).

    Yaw:   horizontal displacement of nose tip from the midpoint of both eyes.
           Normalized by inter-eye distance → bounded to roughly ±45°.
    Pitch: vertical ratio — how far nose is between eye-midpoint and chin.
           A forward face has nose at ~35-40% of the way from eyes to chin.

    This sidesteps all solvePnP / rotation-matrix / Euler-decomposition bugs.
    """
    import math

    # Key landmarks (normalized 0–1 coords from MediaPipe)
    nose   = landmarks[1]      # Nose tip
    chin   = landmarks[152]    # Chin
    l_eye  = landmarks[33]     # Left eye outer corner
    r_eye  = landmarks[263]    # Right eye outer corner

    # Convert to pixel coords
    nose_x, nose_y = nose.x * img_w, nose.y * img_h
    chin_x, chin_y = chin.x * img_w, chin.y * img_h
    le_x, le_y = l_eye.x * img_w, l_eye.y * img_h
    re_x, re_y = r_eye.x * img_w, r_eye.y * img_h

    # Eye midpoint
    mid_x = (le_x + re_x) / 2
    mid_y = (le_y + re_y) / 2

    # Inter-eye distance (used as normalization reference)
    eye_dist = math.sqrt((re_x - le_x) ** 2 + (re_y - le_y) ** 2)
    if eye_dist < 1:
        return {"yaw": 0, "pitch": 0, "raw_yaw": 0, "raw_pitch": 0, "looking_away": False}

    # ── Yaw: horizontal nose offset from eye-midpoint ──
    # Positive = looking right, Negative = looking left
    dx = nose_x - mid_x
    raw_yaw = math.degrees(math.atan2(dx, eye_dist)) * 2  # scale for sensitivity

    # ── Pitch: vertical nose position relative to eyes-to-chin span ──
    # For a forward face, nose is at ~35% of the way from eyes to chin.
    face_height = chin_y - mid_y
    if face_height < 1:
        raw_pitch = 0.0
    else:
        nose_ratio = (nose_y - mid_y) / face_height  # ~0.35 for forward
        # Map: 0.35 → 0° pitch.  Lower ratio → looking up, higher → looking down
        raw_pitch = (nose_ratio - 0.35) * 100  # scale to degrees-like range

    # ── Moving-average smoothing ──
    with _lock:
        if student_id not in _yaw_history:
            _yaw_history[student_id] = collections.deque(maxlen=GAZE_SMOOTHING_WINDOW)
            _pitch_history[student_id] = collections.deque(maxlen=GAZE_SMOOTHING_WINDOW)
        _yaw_history[student_id].append(raw_yaw)
        _pitch_history[student_id].append(raw_pitch)
        yaw = float(np.mean(_yaw_history[student_id]))
        pitch = float(np.mean(_pitch_history[student_id]))

    looking_away = (
        abs(yaw) > HEAD_POSE_YAW_THRESHOLD
        or abs(pitch) > HEAD_POSE_PITCH_DOWN_THRESHOLD
    )

    return {
        "yaw": round(yaw, 1),
        "pitch": round(pitch, 1),
        "raw_yaw": round(raw_yaw, 1),
        "raw_pitch": round(raw_pitch, 1),
        "looking_away": looking_away,
    }


# ── Eye Gaze with iris ratio smoothing ────────────────────────────────────────

_LEFT_IRIS = [468, 469, 470, 471, 472]
_RIGHT_IRIS = [473, 474, 475, 476, 477]
_LEFT_EYE_INNER = 133
_LEFT_EYE_OUTER = 33
_RIGHT_EYE_INNER = 362
_RIGHT_EYE_OUTER = 263


def _estimate_eye_gaze(landmarks, img_w: int, img_h: int, student_id: str = "") -> dict:
    """Estimate gaze with moving-average smoothing.  Falls back to 'center' if no iris."""
    try:
        num_landmarks = len(landmarks)

        # If iris landmarks are not available, assume center
        if num_landmarks < 473:
            return {"direction": "center", "ratio": 0.5, "looking_offscreen": False}

        # Raw per-eye ratios
        l_iris_x = np.mean([landmarks[i].x for i in _LEFT_IRIS if i < num_landmarks]) * img_w
        l_inner_x = landmarks[_LEFT_EYE_INNER].x * img_w
        l_outer_x = landmarks[_LEFT_EYE_OUTER].x * img_w
        l_eye_width = abs(l_inner_x - l_outer_x)
        if l_eye_width < 1:
            return {"direction": "center", "ratio": 0.5, "looking_offscreen": False}
        l_ratio = (l_iris_x - l_outer_x) / (l_inner_x - l_outer_x + 1e-6)

        r_iris_x = np.mean([landmarks[i].x for i in _RIGHT_IRIS if i < num_landmarks]) * img_w
        r_inner_x = landmarks[_RIGHT_EYE_INNER].x * img_w
        r_outer_x = landmarks[_RIGHT_EYE_OUTER].x * img_w
        r_eye_width = abs(r_outer_x - r_inner_x)
        if r_eye_width < 1:
            return {"direction": "center", "ratio": 0.5, "looking_offscreen": False}
        r_ratio = (r_iris_x - r_inner_x) / (r_outer_x - r_inner_x + 1e-6)

        raw_ratio = (l_ratio + r_ratio) / 2

        # Clamp to reasonable range to reject noise
        raw_ratio = max(0.0, min(1.0, raw_ratio))

        # Moving-average smoothing
        with _lock:
            if student_id not in _gaze_history:
                _gaze_history[student_id] = collections.deque(maxlen=GAZE_SMOOTHING_WINDOW)
            _gaze_history[student_id].append(raw_ratio)
            avg_ratio = float(np.mean(_gaze_history[student_id]))

        if avg_ratio < GAZE_LEFT_THRESHOLD:
            direction = "left"
        elif avg_ratio > GAZE_RIGHT_THRESHOLD:
            direction = "right"
        else:
            direction = "center"

        looking_offscreen = direction != "center"

        return {
            "direction": direction,
            "ratio": round(avg_ratio, 3),
            "looking_offscreen": looking_offscreen,
        }
    except Exception:
        return {"direction": "unknown", "ratio": 0.5, "looking_offscreen": False}


# ── Bounding box with exponential smoothing ───────────────────────────────────

def _face_bbox(landmarks, img_w: int, img_h: int, student_id: str = "") -> dict:
    xs = [lm.x * img_w for lm in landmarks]
    ys = [lm.y * img_h for lm in landmarks]
    new_bbox = {
        "x1": int(min(xs)), "y1": int(min(ys)),
        "x2": int(max(xs)), "y2": int(max(ys)),
    }

    with _lock:
        prev = _prev_bbox.get(student_id)
        if prev is not None:
            a = BBOX_SMOOTH_FACTOR
            smoothed = {
                "x1": int(a * prev["x1"] + (1 - a) * new_bbox["x1"]),
                "y1": int(a * prev["y1"] + (1 - a) * new_bbox["y1"]),
                "x2": int(a * prev["x2"] + (1 - a) * new_bbox["x2"]),
                "y2": int(a * prev["y2"] + (1 - a) * new_bbox["y2"]),
            }
        else:
            smoothed = new_bbox
        _prev_bbox[student_id] = smoothed

    return smoothed


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_face(image_b64: str, student_id: str = "") -> dict:
    """
    Analyse a base64 JPEG frame.
    Returns smoothed face detection, head pose, eye gaze, and bounding box.
    """
    img = _decode_image(image_b64)
    if img is None:
        return _empty_result()

    # ── Resize to max 480p for faster processing ──
    img_h, img_w = img.shape[:2]
    max_dim = 480
    if max(img_h, img_w) > max_dim:
        scale = max_dim / max(img_h, img_w)
        img = cv2.resize(img, (int(img_w * scale), int(img_h * scale)))
        img_h, img_w = img.shape[:2]

    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    try:
        landmarker = _get_landmarker()
        results = landmarker.detect(mp_image)
    except Exception:
        return _empty_result()

    if not results.face_landmarks:
        return _empty_result()

    face_count = len(results.face_landmarks)
    primary = results.face_landmarks[0]

    head_pose = _estimate_head_pose(primary, img_w, img_h, student_id)
    eye_gaze = _estimate_eye_gaze(primary, img_w, img_h, student_id)
    bbox = _face_bbox(primary, img_w, img_h, student_id)

    return {
        "face_detected": True,
        "face_count": face_count,
        "no_face": False,
        "multiple_faces": face_count > 1,
        "head_pose": head_pose,
        "eye_gaze": eye_gaze,
        "face_bbox": bbox,
    }


def _empty_result() -> dict:
    return {
        "face_detected": False,
        "face_count": 0,
        "no_face": True,
        "multiple_faces": False,
        "head_pose": {"yaw": 0, "pitch": 0, "raw_yaw": 0, "raw_pitch": 0, "looking_away": False},
        "eye_gaze": {"direction": "unknown", "ratio": 0.5, "looking_offscreen": False},
        "face_bbox": None,
    }
