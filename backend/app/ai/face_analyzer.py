"""
Face Analyzer — OpenCV Haar Cascade face detection
"""
import cv2
import numpy as np
import base64
import os

# Load Haar cascade for face detection
_cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
_face_cascade = cv2.CascadeClassifier(_cascade_path)


def analyze_face(image_b64: str) -> dict:
    """Receive base64 JPEG, return face detection results."""
    try:
        data = image_b64.split(",")[1] if "," in image_b64 else image_b64
        img_bytes = base64.b64decode(data)
        arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return {"face_detected": False, "face_count": 0, "no_face": True, "multiple_faces": False}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = _face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        count = len(faces)
        return {
            "face_detected": count > 0,
            "face_count": count,
            "no_face": count == 0,
            "multiple_faces": count > 1,
        }
    except Exception:
        return {"face_detected": True, "face_count": 1, "no_face": False, "multiple_faces": False}
