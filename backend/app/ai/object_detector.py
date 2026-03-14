"""
Server-Side Object Detector using OpenCV DNN (MobileNet SSD)
Detects phones, books, and other suspicious objects.
Falls back gracefully if model files are unavailable.
"""
import base64
import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# Suspicious object class IDs in COCO (MobileNet SSD trained on COCO)
# 67=cell phone, 73=book, 84=notebook/laptop
SUSPICIOUS_CLASSES = {
    67: "cell phone",
    73: "book",
    76: "scissors",
    84: "laptop",
}

_net = None
_net_loaded = False
_CLASSES = None


def _load_model():
    """Try to load MobileNet SSD model. Returns None if not available."""
    global _net, _net_loaded, _CLASSES
    if _net_loaded:
        return _net
    _net_loaded = True
    if not CV2_AVAILABLE:
        return None
    try:
        # Use OpenCV's built-in DNN with a pre-compiled COCO model
        # We use Caffe MobileNet-SSD proto which ships with some OpenCV builds
        # If the files are not present, we fall back gracefully
        import os
        prototxt = os.path.join(os.path.dirname(__file__), "MobileNetSSD_deploy.prototxt")
        caffemodel = os.path.join(os.path.dirname(__file__), "MobileNetSSD_deploy.caffemodel")
        if os.path.exists(prototxt) and os.path.exists(caffemodel):
            _net = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
    except Exception:
        _net = None
    return _net


def detect_objects(b64_image: str) -> dict:
    """
    Detect objects in frame using OpenCV DNN.
    If model is not available, returns a safe default (no objects detected).
    """
    if not CV2_AVAILABLE:
        return {"objects_detected": [], "suspicious_found": False, "error": "opencv_unavailable"}

    net = _load_model()
    if net is None:
        # Model not downloaded yet — return safe default to avoid blocking exam
        return {"objects_detected": [], "suspicious_found": False, "error": "model_not_loaded"}

    try:
        if "," in b64_image:
            b64_image = b64_image.split(",", 1)[1]
        img_bytes = base64.b64decode(b64_image)
        arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return {"objects_detected": [], "suspicious_found": False, "error": "decode_failed"}

        (h, w) = img.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 0.007843, (300, 300), 127.5)
        net.setInput(blob)
        detections = net.forward()

        detected = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            class_id = int(detections[0, 0, i, 1])
            if confidence > 0.5 and class_id in SUSPICIOUS_CLASSES:
                detected.append({
                    "class": SUSPICIOUS_CLASSES[class_id],
                    "confidence": round(float(confidence), 2),
                })

        return {
            "objects_detected": detected,
            "suspicious_found": len(detected) > 0,
            "error": None,
        }
    except Exception as e:
        return {"objects_detected": [], "suspicious_found": False, "error": str(e)}
