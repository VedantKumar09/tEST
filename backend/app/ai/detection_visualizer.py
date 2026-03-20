"""
Detection Visualizer — Real-time debug overlay generator.
Draws bounding boxes, hand landmarks, face proximity zones,
and violation labels directly on frames for debugging and admin monitoring.
"""
from __future__ import annotations

import base64
import cv2
import numpy as np

from .hand_face_detector import HAND_CONNECTIONS
from .proctor_config import HAND_NEAR_FACE_FRAMES_THRESHOLD


def _decode_image(image_b64: str) -> np.ndarray | None:
    try:
        data = image_b64.split(",")[1] if "," in image_b64 else image_b64
        img_bytes = base64.b64decode(data)
        arr = np.frombuffer(img_bytes, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _encode_image(img: np.ndarray) -> str:
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode()


def draw_debug_overlay(
    image_b64: str,
    face_result: dict,
    yolo_result: dict,
    violations: list[str],
    hand_result: dict | None = None,
) -> str:
    """
    Draw detection debug info onto the frame.
    Returns the new base64 image string.
    """
    img = _decode_image(image_b64)
    if img is None:
        return image_b64

    # ── Draw YOLO Detections (bounding boxes) ────────────────────────────────
    for det in yolo_result.get("all_detections", []):
        bbox = det.get("bbox", {})
        x1, y1 = bbox.get("x1", 0), bbox.get("y1", 0)
        x2, y2 = bbox.get("x2", 0), bbox.get("y2", 0)
        label = det.get("label", "")

        is_suspicious = det.get("class", "") != "person"
        color = (0, 0, 255) if is_suspicious else (255, 100, 0)
        thickness = 2 if is_suspicious else 1

        cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
        (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(img, (x1, y1 - 20), (x1 + w, y1), color, -1)
        cv2.putText(img, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # ── Draw Face Bounding Box ───────────────────────────────────────────────
    face_bbox = face_result.get("face_bbox")
    if face_bbox and isinstance(face_bbox, dict):
        fx1 = face_bbox.get("x1", face_bbox.get("x", 0))
        fy1 = face_bbox.get("y1", face_bbox.get("y", 0))
        fx2 = face_bbox.get("x2", fx1 + face_bbox.get("width", 0))
        fy2 = face_bbox.get("y2", fy1 + face_bbox.get("height", 0))

        status = "OK"
        color = (0, 255, 0)

        if "looking_away" in violations:
            status = "LOOKING AWAY"
            color = (0, 165, 255)
        elif "gaze_offscreen" in violations:
            status = "GAZE OFF"
            color = (0, 165, 255)
        elif "phone_usage_suspected" in violations:
            status = "PHONE?"
            color = (0, 0, 255)

        cv2.rectangle(img, (fx1, fy1), (fx2, fy2), color, 2)
        cv2.putText(img, f"Face: {status}", (fx1, fy1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # ── Draw Hand Landmarks + Proximity ──────────────────────────────────────
    if hand_result and hand_result.get("hands_detected"):
        hand_near = hand_result.get("hand_near_face", False)
        frames_count = hand_result.get("hand_near_face_frames", 0)
        phone_suspected = hand_result.get("phone_usage_suspected", False)

        for hand_lms in hand_result.get("hand_landmarks_px", []):
            # Choose color: red if near face / green if normal
            if phone_suspected:
                lm_color = (0, 0, 255)      # Red — phone suspected
            elif hand_near:
                lm_color = (0, 165, 255)    # Orange — hand near face
            else:
                lm_color = (0, 255, 0)      # Green — normal

            # Draw landmark points
            for i, (px, py) in enumerate(hand_lms):
                pt = (int(px), int(py))
                cv2.circle(img, pt, 3, lm_color, -1)

            # Draw connections
            for start_idx, end_idx in HAND_CONNECTIONS:
                if start_idx < len(hand_lms) and end_idx < len(hand_lms):
                    pt1 = (int(hand_lms[start_idx][0]), int(hand_lms[start_idx][1]))
                    pt2 = (int(hand_lms[end_idx][0]), int(hand_lms[end_idx][1]))
                    cv2.line(img, pt1, pt2, lm_color, 1)

        # Draw proximity counter overlay
        if frames_count > 0:
            pct = min(100, int(frames_count / HAND_NEAR_FACE_FRAMES_THRESHOLD * 100))
            bar_color = (0, 0, 255) if phone_suspected else (0, 165, 255)
            label = f"Hand near face: {frames_count}/{HAND_NEAR_FACE_FRAMES_THRESHOLD} ({pct}%)"

            img_h, img_w = img.shape[:2]
            bar_y = img_h - 40
            bar_w = int((img_w - 20) * pct / 100)

            cv2.rectangle(img, (10, bar_y), (10 + bar_w, bar_y + 25), bar_color, -1)
            cv2.rectangle(img, (10, bar_y), (img_w - 10, bar_y + 25), (200, 200, 200), 1)
            cv2.putText(img, label, (15, bar_y + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # ── Draw Global Violation Overlay ────────────────────────────────────────
    if violations:
        y_offset = 30
        cv2.putText(img, "VIOLATIONS:", (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        for i, v in enumerate(violations):
            y_offset += 25
            cv2.putText(img, f"- {v}", (20, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    return _encode_image(img)
