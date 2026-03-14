"""
Server-Side Face Analyzer using OpenCV
Detects faces and multiple people in a frame snapshot.
Falls back gracefully if OpenCV is unavailable.
"""
import base64
import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# Load Haar cascade for face detection (bundled with OpenCV)
_face_cascade = None

def _get_cascade():
    global _face_cascade
    if _face_cascade is None and CV2_AVAILABLE:
        _face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
    return _face_cascade


def decode_base64_image(b64_string: str) -> "np.ndarray | None":
    """Decode a base64 data URI or raw base64 string to a numpy BGR image."""
    try:
        if "," in b64_string:
            b64_string = b64_string.split(",", 1)[1]
        img_bytes = base64.b64decode(b64_string)
        arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def analyze_face(b64_image: str) -> dict:
    """
    Analyze a frame for face presence.
    Returns:
        face_detected (bool)
        face_count (int)
        multiple_faces (bool)
        no_face (bool)
    """
    if not CV2_AVAILABLE:
        return {"face_detected": True, "face_count": 1, "multiple_faces": False, "no_face": False, "error": "opencv_unavailable"}

    img = decode_base64_image(b64_image)
    if img is None:
        return {"face_detected": False, "face_count": 0, "multiple_faces": False, "no_face": True, "error": "decode_failed"}

    cascade = _get_cascade()
    if cascade is None:
        return {"face_detected": True, "face_count": 1, "multiple_faces": False, "no_face": False, "error": "cascade_unavailable"}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))

    face_count = len(faces)
    return {
        "face_detected": face_count >= 1,
        "face_count": face_count,
        "multiple_faces": face_count > 1,
        "no_face": face_count == 0,
        "error": None,
    }
