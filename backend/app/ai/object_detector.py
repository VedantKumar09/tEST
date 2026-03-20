"""
Object Detector v2.5 — Hybrid Real-World Phone Detection.

Model: YOLOv8s (Ultralytics) — Upgraded to "small" model for better accuracy.

Features:
  - Layer 1: YOLOv8s primary detection
  - Layer 2: Heuristic Fallback (contour detection + face proximity)
  - 960x720 resolution for small object clarity
  - Phone detection with dedicated flag & possible_phone_detected
  - Per-class confidence thresholds
  - Person counting for multi-person detection
  - Bounding boxes with confidence scores + labels
  - Debug logging (configurable)
  - Warm-up at load time for zero cold-start
"""
from __future__ import annotations

import base64
import logging
import os
import cv2
import numpy as np
import time

from .proctor_config import (
    PHONE_CONF_THRESHOLD,
    PERSON_CONF_THRESHOLD,
    BOOK_CONF_THRESHOLD,
    YOLO_CONFIDENCE_THRESHOLD,
    FRAME_RESOLUTION,
    DETECTION_DEBUG_LOGGING,
)

logger = logging.getLogger("proctor.yolo")

# ── Lazy-loaded model ─────────────────────────────────────────────────────────
_model = None

# Classes we care about (COCO names)
_SUSPICIOUS_CLASSES = {"cell phone", "book", "laptop", "remote"}
_PERSON_CLASS = "person"

# Per-class confidence thresholds (lower = more sensitive, more false positives)
_CLASS_CONF = {
    "cell phone": PHONE_CONF_THRESHOLD,    # 0.35 — phones are small/partly hidden
    "person":     PERSON_CONF_THRESHOLD,    # 0.40 — reasonably confident
    "book":       BOOK_CONF_THRESHOLD,      # 0.45
    "laptop":     YOLO_CONFIDENCE_THRESHOLD, # 0.40
    "remote":     YOLO_CONFIDENCE_THRESHOLD, # 0.40
}

# Alternative COCO labels that map to phone (YOLO sometimes uses these)
_PHONE_ALIASES = {"cell phone", "mobile phone", "phone"}


def _get_model():
    """Lazy-load YOLOv8s with warm-up."""
    global _model
    if _model is None:
        from ultralytics import YOLO

        # Use YOLOv8s for better real-world accuracy
        model_path = os.path.join(os.path.dirname(__file__), "yolov8s.pt")
        
        # Download if it doesn't exist
        if not os.path.exists(model_path):
            logger.info("Downloading YOLOv8s model...")
            _model = YOLO("yolov8s.pt")
            _model.save(model_path)
        else:
            _model = YOLO(model_path)
            
        # Warm-up on realistic-size frame (eliminates 3s cold start)
        dummy = np.zeros((960, 960, 3), dtype=np.uint8)
        _model.predict(dummy, conf=0.25, imgsz=960, verbose=False)
        logger.info("YOLOv8s model loaded successfully.")
    return _model


def warm_up():
    """Call during server startup to pre-load model."""
    _get_model()


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

    Returns: dict
      objects_detected: list of suspicious objects
      suspicious_found: bool
      person_count: int
      phone_detected: bool
      possible_phone_detected: bool
      all_detections: list — ALL COCO detections (for debug)
    """
    img = _decode_image(image_b64)
    if img is None:
        return _empty_result()

    try:
        model = _get_model()
        t0 = time.time()

        # Resize for inference — CRITICAL: 960x720 minimum
        h, w = img.shape[:2]
        res = 960
        scale_x, scale_y = 1.0, 1.0
        if max(h, w) > res:
            scale = res / max(h, w)
            new_w, new_h = int(w * scale), int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            scale_x = w / new_w
            scale_y = h / new_h

        # Use LOWEST threshold for broad detection, then filter per-class
        min_conf = min(_CLASS_CONF.values(), default=0.30)
        results = model.predict(img, conf=min_conf, imgsz=res, verbose=False)

        suspicious = []
        person_count = 0
        phone_detected = False
        possible_phone_detected = False
        all_detections = []
        person_boxes = []

        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                cls_name = model.names[cls_id]
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                # Scale bounding box back to original frame coordinates
                bbox = {
                    "x1": int(x1 * scale_x), "y1": int(y1 * scale_y),
                    "x2": int(x2 * scale_x), "y2": int(y2 * scale_y),
                }

                detection = {
                    "class": cls_name,
                    "confidence": round(conf, 3),
                    "bbox": bbox,
                    "label": f"{cls_name} {conf:.0%}",
                }

                # Count persons and save box for heuristic layer
                if cls_name == _PERSON_CLASS and conf >= PERSON_CONF_THRESHOLD:
                    person_count += 1
                    all_detections.append(detection)
                    person_boxes.append(bbox)

                # Check suspicious items with per-class threshold
                if cls_name in _SUSPICIOUS_CLASSES or cls_name.lower() in _PHONE_ALIASES:
                    required_conf = _CLASS_CONF.get(cls_name, YOLO_CONFIDENCE_THRESHOLD)

                    # For phone: also check aliases
                    if cls_name.lower() in _PHONE_ALIASES:
                        required_conf = PHONE_CONF_THRESHOLD

                    if conf >= required_conf:
                        suspicious.append(detection)
                        all_detections.append(detection)

                        if cls_name.lower() in _PHONE_ALIASES or cls_name == "cell phone":
                            phone_detected = True

        elapsed_ms = round((time.time() - t0) * 1000)

        if DETECTION_DEBUG_LOGGING and (suspicious or person_count > 1):
            for det in suspicious:
                logger.info(
                    f"[YOLO] {det['class']} conf={det['confidence']:.3f} "
                    f"bbox=({det['bbox']['x1']},{det['bbox']['y1']})-"
                    f"({det['bbox']['x2']},{det['bbox']['y2']}) "
                    f"{elapsed_ms}ms"
                )
            if person_count > 1:
                logger.info(f"[YOLO] Multiple persons: {person_count} detected {elapsed_ms}ms")

        # LAYER 2: HYBRID HEURISTIC FALLBACK
        # If YOLO didn't definitively catch a phone, look for phone-like objects near the person
        if not phone_detected and person_boxes:
            # 1. Convert to grayscale and blur
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # 2. Edge detection
            edges = cv2.Canny(blurred, 50, 150)
            
            # 3. Find contours
            contours, _ = cv2.findContours(edges.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for c in contours:
                # Filter by area (phones aren't too small or too big)
                area = cv2.contourArea(c)
                if 800 < area < 15000:
                    # Approximate contour to see if it's rectangular
                    peri = cv2.arcLength(c, True)
                    approx = cv2.approxPolyDP(c, 0.04 * peri, True)
                    
                    if len(approx) == 4:
                        # It's a rectangle. Setup geometric info
                        x, y, w_box, h_box = cv2.boundingRect(approx)
                        aspect_ratio = float(w_box)/h_box
                        
                        # Phones are typically rectangular (portrait or landscape 0.4 to 2.5 AR)
                        if 0.4 <= aspect_ratio <= 2.5:
                            # 4. Proximity Check: Is it near a person's hands/face (bottom half of person box)?
                            # In real world, phones are held near the chest/face
                            for p_box in person_boxes:
                                # Translate person box to resized img scale
                                px1, py1 = int(p_box["x1"] / scale_x), int(p_box["y1"] / scale_y)
                                px2, py2 = int(p_box["x2"] / scale_x), int(p_box["y2"] / scale_y)
                                
                                # Define "hand/chest zone" (lower 2/3rds of person box, expanded slightly outwards)
                                zone_x1 = max(0, px1 - 50)
                                zone_y1 = py1 + int((py2 - py1) * 0.3)
                                zone_x2 = px2 + 50
                                zone_y2 = py2 + 100
                                
                                # If the rectangle is inside the hand/chest zone, flag it
                                if zone_x1 < x < zone_x2 and zone_y1 < y < zone_y2:
                                    possible_phone_detected = True
                                    
                                    # Scale back to original
                                    orig_bbox = {
                                        "x1": int(x * scale_x), "y1": int(y * scale_y),
                                        "x2": int((x+w_box) * scale_x), "y2": int((y+h_box) * scale_y),
                                    }
                                    
                                    heuristic_det = {
                                        "class": "possible_phone",
                                        "confidence": 0.50, # Heuristic confidence
                                        "bbox": orig_bbox,
                                        "label": "Heuristic Phone",
                                    }
                                    suspicious.append(heuristic_det)
                                    all_detections.append(heuristic_det)
                                    
                                    if DETECTION_DEBUG_LOGGING:
                                        logger.warning(f"[ObjectDetector] LAYER 2: Possible phone detected by heuristic at {orig_bbox}")
                                    break # Found one near this person

        dt_ms = int((time.time() - t0) * 1000)
        
        return {
            "objects_detected": suspicious,
            "suspicious_found": len(suspicious) > 0,
            "person_count": person_count,
            "phone_detected": phone_detected,
            "possible_phone_detected": possible_phone_detected,
            "all_detections": all_detections,
            "execution_time_ms": dt_ms,
        }
    except Exception as e:
        logger.error(f"YOLO detection failed: {e}")
        return _empty_result()


def _empty_result() -> dict:
    return {
        "objects_detected": [],
        "suspicious_found": False,
        "person_count": 0,
        "phone_detected": False,
        "possible_phone_detected": False,
        "all_detections": [],
        "execution_time_ms": 0,
    }
