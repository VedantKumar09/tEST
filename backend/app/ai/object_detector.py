"""
Object Detector — YOLOv8n (Ultralytics)
Lazy-loads the nano model on first call for minimal memory footprint.
Filters COCO detections to suspicious exam items only.
"""
from __future__ import annotations

import base64
import cv2
import numpy as np

# Lazy-loaded model reference
_model = None

# COCO class names we consider suspicious during an exam
_SUSPICIOUS_CLASSES = {"cell phone", "book", "laptop", "remote"}


def _get_model():
    """Lazy-load YOLOv8n. Downloads weights (~6 MB) on first run."""
    global _model
    if _model is None:
        from ultralytics import YOLO
        _model = YOLO("yolov8n.pt")
        # Warm-up with a tiny dummy image so first real call is fast
        _model.predict(np.zeros((64, 64, 3), dtype=np.uint8), verbose=False)
    return _model


def _decode_image(image_b64: str) -> np.ndarray | None:
    try:
        data = image_b64.split(",")[1] if "," in image_b64 else image_b64
        img_bytes = base64.b64decode(data)
        arr = np.frombuffer(img_bytes, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None


def detect_objects(image_b64: str) -> dict:
    """
    Run YOLOv8n on a base64 JPEG frame.
    Returns only suspicious exam-related objects with class, confidence, bbox.
    """
    img = _decode_image(image_b64)
    if img is None:
        return {"objects_detected": [], "suspicious_found": False}

    try:
        model = _get_model()
        # Resize frame for faster inference — 480p is sufficient for object detection
        h, w = img.shape[:2]
        if max(h, w) > 480:
            scale = 480 / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
        results = model.predict(img, conf=0.40, imgsz=480, verbose=False)
        detections = []

        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                cls_name = model.names[cls_id]
                if cls_name in _SUSPICIOUS_CLASSES:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    detections.append({
                        "class": cls_name,
                        "confidence": round(float(box.conf[0]), 2),
                        "bbox": {
                            "x1": int(x1), "y1": int(y1),
                            "x2": int(x2), "y2": int(y2),
                        },
                    })

        return {
            "objects_detected": detections,
            "suspicious_found": len(detections) > 0,
        }
    except Exception:
        return {"objects_detected": [], "suspicious_found": False}
