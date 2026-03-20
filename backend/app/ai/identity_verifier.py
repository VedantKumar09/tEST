"""
Identity Verifier — Lightweight face matching using MediaPipe FaceLandmarker (tasks API).

Uses the same FaceLandmarker model as face_analyzer.py to extract normalized
inter-landmark distance vectors (68-dim) and compare with cosine similarity.

API:
  store_reference(student_id, image_b64)  → dict
  verify_identity(student_id, image_b64)  → dict
  clear_reference(student_id)             → None

Thread-safe; state is per-student in-memory.
"""
from __future__ import annotations

import base64
import threading
import math
import os
import numpy as np
import cv2

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# ── Lazy FaceLandmarker (shared model with face_analyzer) ─────────────────────
_landmarker: vision.FaceLandmarker | None = None
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "face_landmarker.task")


def _get_landmarker() -> vision.FaceLandmarker:
    global _landmarker
    if _landmarker is None:
        base_options = mp_python.BaseOptions(model_asset_path=_MODEL_PATH)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        _landmarker = vision.FaceLandmarker.create_from_options(options)
    return _landmarker


# ── Key landmark pairs for distance-based embedding ───────────────────────────
# 68 carefully chosen pair indices covering jawline, eyes, nose, mouth, brow
_LANDMARK_PAIRS = [
    (10, 152),   # forehead to chin (face height)
    (234, 454),  # left cheek to right cheek (face width)
    (33, 263),   # left eye outer to right eye outer
    (133, 362),  # left eye inner to right eye inner
    (46, 276),   # left eye top to right eye top
    (70, 300),   # left eyebrow outer to right eyebrow outer
    (63, 293),   # left eyebrow inner to right eyebrow inner
    (1, 4),      # nose bridge to nose tip
    (5, 4),      # nose ridge to tip
    (61, 291),   # mouth left to right
    (0, 17),     # upper lip to lower lip center
    (13, 14),    # lip inner top to inner bottom
    (78, 308),   # mouth inner left to right
    (10, 1),     # forehead to nose bridge
    (152, 4),    # chin to nose tip
    (234, 33),   # left cheek to left eye outer
    (454, 263),  # right cheek to right eye outer
    (93, 323),   # left jaw to right jaw
    (127, 356),  # left jaw mid to right jaw mid
    (162, 389),  # left jaw lower to right jaw lower
    (172, 397),  # near chin left to near chin right
    (10, 234),   # forehead to left cheek
    (10, 454),   # forehead to right cheek
    (152, 234),  # chin to left cheek
    (152, 454),  # chin to right cheek
    (33, 133),   # left eye outer to inner
    (263, 362),  # right eye outer to inner
    (33, 4),     # left eye to nose tip
    (263, 4),    # right eye to nose tip
    (33, 61),    # left eye to mouth left
    (263, 291),  # right eye to mouth right
    (70, 33),    # left eyebrow to left eye
    (300, 263),  # right eyebrow to right eye
    (4, 61),     # nose tip to mouth left
    (4, 291),    # nose tip to mouth right
    (1, 33),     # nose bridge to left eye
    (1, 263),    # nose bridge to right eye
    (93, 152),   # left jaw to chin
    (323, 152),  # right jaw to chin
    (33, 152),   # left eye to chin
    (263, 152),  # right eye to chin
    (70, 10),    # left eyebrow to forehead
    (300, 10),   # right eyebrow to forehead
    (4, 152),    # nose tip to chin
    (61, 152),   # mouth left to chin
    (291, 152),  # mouth right to chin
    (33, 0),     # left eye to upper lip
    (263, 0),    # right eye to upper lip
    (10, 0),     # forehead to upper lip
    (93, 33),    # left jaw to left eye
    (323, 263),  # right jaw to right eye
    (234, 1),    # left cheek to nose bridge
    (454, 1),    # right cheek to nose bridge
    (133, 61),   # left eye inner to mouth left
    (362, 291),  # right eye inner to mouth right
    (46, 4),     # left eye top to nose tip
    (276, 4),    # right eye top to nose tip
    (93, 61),    # left jaw to mouth left
    (323, 291),  # right jaw to mouth right
    (127, 61),   # jaw mid left to mouth left
    (356, 291),  # jaw mid right to mouth right
    (162, 0),    # jaw lower left to upper lip
    (389, 0),    # jaw lower right to upper lip
    (172, 152),  # near chin left to chin
    (397, 152),  # near chin right to chin
    (162, 172),  # jaw lower left to near chin left
    (389, 397),  # jaw lower right to near chin right
    (10, 61),    # forehead to mouth left
    (10, 291),   # forehead to mouth right
]

# ── Per-Student State ─────────────────────────────────────────────────────────
_lock = threading.Lock()
_reference_embeddings: dict[str, np.ndarray] = {}

# Match threshold: similarity below this → identity mismatch
MATCH_THRESHOLD = 0.82  # cosine similarity (0-1, higher = more similar)


def _decode_image(image_b64: str) -> np.ndarray | None:
    """Decode base64 JPEG to BGR numpy array."""
    try:
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        img_bytes = base64.b64decode(image_b64)
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _extract_embedding(image: np.ndarray) -> np.ndarray | None:
    """
    Extract a 68-dimensional face embedding from FaceLandmarker.
    The embedding is a normalized vector of inter-landmark distances,
    making it scale/translation invariant.
    """
    try:
        landmarker = _get_landmarker()
    except Exception:
        return None

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    result = landmarker.detect(mp_image)
    if not result.face_landmarks or len(result.face_landmarks) == 0:
        return None

    landmarks = result.face_landmarks[0]
    h, w = image.shape[:2]

    # Convert to pixel coordinates
    pts = np.array([[lm.x * w, lm.y * h] for lm in landmarks])

    # Compute distances for all landmark pairs
    distances = []
    for i, j in _LANDMARK_PAIRS:
        if i < len(pts) and j < len(pts):
            d = math.sqrt((pts[i][0] - pts[j][0])**2 + (pts[i][1] - pts[j][1])**2)
            distances.append(d)
        else:
            distances.append(0.0)

    vec = np.array(distances, dtype=np.float64)

    # Normalize by face diagonal (scale invariant)
    if vec.max() > 0:
        vec = vec / vec.max()

    # L2 normalize for cosine similarity
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm

    return vec


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    return float(np.dot(a, b))


# ── Public API ────────────────────────────────────────────────────────────────

def store_reference(student_id: str, image_b64: str) -> dict:
    """
    Capture and store the reference face embedding for a student.
    Called at exam start after identity photo capture.
    """
    image = _decode_image(image_b64)
    if image is None:
        return {"status": "error", "message": "Failed to decode image"}

    embedding = _extract_embedding(image)
    if embedding is None:
        return {"status": "error", "message": "No face detected in reference image"}

    with _lock:
        _reference_embeddings[student_id] = embedding

    return {
        "status": "ok",
        "message": "Reference face stored",
        "embedding_dim": len(embedding),
    }


def verify_identity(student_id: str, image_b64: str) -> dict:
    """
    Compare current frame against stored reference.
    Returns match score and whether the person is the same.
    """
    with _lock:
        ref = _reference_embeddings.get(student_id)

    if ref is None:
        return {
            "match_score": 0.0,
            "is_same_person": True,  # no reference = can't flag
            "message": "No reference stored — skipping verification",
        }

    image = _decode_image(image_b64)
    if image is None:
        return {
            "match_score": 0.0,
            "is_same_person": True,  # decode failure = skip
            "message": "Failed to decode frame",
        }

    embedding = _extract_embedding(image)
    if embedding is None:
        return {
            "match_score": 0.0,
            "is_same_person": True,  # no face this frame = don't flag mismatch
            "message": "No face in current frame — skipping check",
        }

    score = _cosine_similarity(ref, embedding)
    is_same = score >= MATCH_THRESHOLD

    return {
        "match_score": round(float(score), 4),
        "is_same_person": is_same,
        "threshold": MATCH_THRESHOLD,
        "message": "Match" if is_same else "Identity mismatch detected",
    }


def clear_reference(student_id: str) -> None:
    """Remove stored reference for a student (session cleanup)."""
    with _lock:
        _reference_embeddings.pop(student_id, None)
