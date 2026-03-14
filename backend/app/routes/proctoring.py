"""
Proctoring Routes — Receives snapshots from frontend, runs AI analysis
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import base64
import time

from ..ai.face_analyzer import analyze_face
from ..ai.object_detector import detect_objects
from ..database import get_db

router = APIRouter(prefix="/api/proctor", tags=["proctoring"])

# In-memory store for latest secondary camera frame per session
# Key: student email or session token
_second_cam_frames: dict[str, dict] = {}


# ── Schemas ───────────────────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    image: str          # base64 encoded JPEG snapshot
    student_id: str     # student email


class SecondFrameRequest(BaseModel):
    image: str          # base64 frame from phone
    student_id: str     # student email (or anonymous session id)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_snapshot(body: AnalyzeRequest):
    """
    Receive a webcam snapshot from the student browser.
    Run face detection + object detection.
    Return violation flags.
    """
    if not body.image:
        raise HTTPException(status_code=400, detail="No image provided")

    face_result = analyze_face(body.image)
    object_result = detect_objects(body.image)

    # Determine violation type
    violations = []
    if face_result.get("no_face"):
        violations.append("no_face")
    if face_result.get("multiple_faces"):
        violations.append("multiple_faces")
    if object_result.get("suspicious_found"):
        for obj in object_result.get("objects_detected", []):
            violations.append(f"object:{obj['class']}")

    result = {
        "face_detected": face_result.get("face_detected", False),
        "face_count": face_result.get("face_count", 0),
        "multiple_faces": face_result.get("multiple_faces", False),
        "no_face": face_result.get("no_face", False),
        "objects_detected": object_result.get("objects_detected", []),
        "suspicious_found": object_result.get("suspicious_found", False),
        "violations": violations,
        "violation_detected": len(violations) > 0,
        "timestamp": int(time.time() * 1000),
    }

    # Optionally save violation event to MongoDB
    db = get_db()
    if db is not None and result["violation_detected"]:
        await db.violation_events.insert_one({
            "student_id": body.student_id,
            "violations": violations,
            "timestamp": result["timestamp"],
        })

    return result


@router.post("/second-frame")
async def receive_second_frame(body: SecondFrameRequest):
    """
    Receive a frame from the student's phone (secondary camera).
    Store it in memory so the exam page can poll it.
    """
    _second_cam_frames[body.student_id] = {
        "image": body.image,
        "timestamp": int(time.time() * 1000),
    }
    return {"status": "ok"}


@router.get("/second-cam/{student_id}")
async def get_second_cam_frame(student_id: str):
    """
    Return the latest secondary camera frame for a given student.
    The exam page polls this endpoint every second.
    """
    frame = _second_cam_frames.get(student_id)
    if not frame:
        return {"image": None, "connected": False}
    
    # Consider connected if frame received in last 5 seconds
    age_ms = int(time.time() * 1000) - frame["timestamp"]
    connected = age_ms < 5000
    return {"image": frame["image"] if connected else None, "connected": connected}
