"""
Proctoring Routes — AI frame analysis + secondary camera frame store
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
_second_cam_frames: dict[str, dict] = {}


class AnalyzeRequest(BaseModel):
    image: str       # base64 JPEG
    student_id: str


class SecondFrameRequest(BaseModel):
    image: str       # base64 frame from phone
    student_id: str


@router.post("/analyze")
async def analyze_snapshot(body: AnalyzeRequest):
    if not body.image:
        raise HTTPException(status_code=400, detail="No image provided")

    face_result = analyze_face(body.image)
    object_result = detect_objects(body.image)

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
    _second_cam_frames[body.student_id] = {
        "image": body.image,
        "timestamp": int(time.time() * 1000),
    }
    return {"status": "ok"}


@router.get("/second-cam/{student_id}")
async def get_second_cam_frame(student_id: str):
    frame = _second_cam_frames.get(student_id)
    if not frame:
        return {"image": None, "connected": False}
    age_ms = int(time.time() * 1000) - frame["timestamp"]
    connected = age_ms < 5000
    return {"image": frame["image"] if connected else None, "connected": connected}
