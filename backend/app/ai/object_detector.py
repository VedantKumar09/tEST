"""
Object Detector — Stub detector (flags phones/books as suspicious)
Replace with a real model if needed.
"""


def detect_objects(image_b64: str) -> dict:
    """
    Placeholder object detection. In production replace with
    a real MobileNet SSD or YOLO model.
    Returns no suspicious objects for now.
    """
    return {
        "objects_detected": [],
        "suspicious_found": False,
    }
