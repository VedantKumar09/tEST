"""
Proctoring Routes — AI frame analysis + browser event logging + score queries
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import time

from ..database import get_db
from ..services.proctor_service import analyze_frame, record_browser_event
from ..ai.scoring import get_score

router = APIRouter(prefix="/api/proctor", tags=["proctoring"])

# In-memory store for latest secondary camera frame per session
_second_cam_frames: dict[str, dict] = {}


class AnalyzeRequest(BaseModel):
    image: str       # base64 JPEG
    student_id: str


class SecondFrameRequest(BaseModel):
    image: str       # base64 frame from phone
    student_id: str


class BrowserEventRequest(BaseModel):
    student_id: str
    event_type: str  # tab_switch | fullscreen_exit | copy_paste | right_click


# ── Frame analysis (face + objects + scoring + screenshot) ─────────────────────

@router.post("/analyze")
async def analyze_snapshot(body: AnalyzeRequest):
    if not body.image:
        raise HTTPException(status_code=400, detail="No image provided")

    db = get_db()
    result = await analyze_frame(body.image, body.student_id, db)
    return result


# ── Browser monitoring events ─────────────────────────────────────────────────

@router.post("/browser-event")
async def browser_event(body: BrowserEventRequest):
    """Record a browser-side suspicious event (tab switch, copy/paste, etc.)."""
    db = get_db()
    score_result = await record_browser_event(body.student_id, body.event_type, db)
    return {"status": "ok", "score": score_result}


# ── Score query ───────────────────────────────────────────────────────────────

@router.get("/score/{student_id}")
async def get_student_score(student_id: str):
    return get_score(student_id)


# ── Violation log query ───────────────────────────────────────────────────────

@router.get("/logs/{student_id}")
async def get_student_logs(student_id: str):
    db = get_db()
    if db is None:
        return []
    docs = await db.violation_events.find(
        {"student_id": student_id}, {"_id": 0}
    ).sort("timestamp", -1).to_list(200)
    return docs


# ── Secondary camera frame relay (HTTP fallback) ──────────────────────────────

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
