"""
Admin Routes — Submissions, risk timeline, evidence, flagging, review status.

Phase 3 enhancements:
  - GET  /risk-timeline/{student_id}  — risk score timeline for charting
  - GET  /evidence/{student_id}       — evidence screenshots listing
  - POST /flag/{submission_id}        — flag a candidate
  - POST /mark/{submission_id}        — mark as valid / invalid
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import time
import os

from ..database import get_db
from ..ai.scoring import get_timeline

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Evidence base dir (relative to backend/)
_EVIDENCE_BASE = Path(__file__).resolve().parent.parent.parent / "proctor_logs"

# In-memory review status store (persists to DB when available)
_review_status: dict[str, dict] = {}


# ── Fallback demo data ────────────────────────────────────────────────────────

_demo_submissions = [
    {
        "submission_id": "demo_001",
        "student_name": "Demo Student",
        "student_email": "student@mindmesh.ai",
        "score": 7,
        "correct": 1,
        "questions_total": 15,
        "questions_answered": 15,
        "time_used": 245,
        "category_scores": {"CS Fundamentals": 20, "AI & ML": 0, "Networking": 0},
        "proctoring_summary": {
            "total_violations": 4,
            "violation_types": ["tab_switch", "no_face"],
            "tab_switches": 2,
            "risk_level": "Medium",
        },
        "submitted_at": int(time.time() * 1000),
    }
]


# ── Request models ────────────────────────────────────────────────────────────

class MarkRequest(BaseModel):
    status: str       # "valid" | "invalid"


# ── Existing endpoints (preserved) ────────────────────────────────────────────

@router.get("/submissions")
async def get_submissions():
    db = get_db()
    if db is None:
        subs = _demo_submissions
    else:
        docs = await db.submissions.find({}, {"_id": 0}).sort("submitted_at", -1).to_list(100)
        subs = docs if docs else _demo_submissions

    # Attach review status to each submission
    enriched = []
    for s in subs:
        sid = s.get("submission_id", s.get("student_email", ""))
        review = _review_status.get(sid, {})
        enriched.append({**s, "review_status": review.get("status"), "flagged": review.get("flagged", False)})
    return enriched


@router.get("/submissions/{submission_id}")
async def get_submission(submission_id: str):
    db = get_db()
    if db is None:
        doc = _demo_submissions[0]
    else:
        doc = await db.submissions.find_one({"submission_id": submission_id}, {"_id": 0})
        doc = doc or _demo_submissions[0]
    review = _review_status.get(submission_id, {})
    return {**doc, "review_status": review.get("status"), "flagged": review.get("flagged", False)}


@router.get("/proctor-logs")
async def get_all_proctor_logs():
    """Return aggregated proctoring violation events across all students."""
    db = get_db()
    if db is None:
        return []
    docs = await db.violation_events.find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).to_list(500)
    return docs


# ── Phase 3: Risk Timeline ───────────────────────────────────────────────────

@router.get("/risk-timeline/{student_id}")
async def get_risk_timeline(student_id: str):
    """
    Return the risk score timeline for a student.
    Data is sourced from the in-memory scoring module (Phase 2).
    Also checks DB for historical violation events as fallback.
    """
    # Try in-memory timeline first (current session)
    timeline = get_timeline(student_id)

    # If empty, try to reconstruct from DB violation events
    if not timeline:
        db = get_db()
        if db is not None:
            docs = await db.violation_events.find(
                {"student_id": student_id},
                {"_id": 0, "timestamp": 1, "cumulative_score": 1}
            ).sort("timestamp", 1).to_list(500)
            timeline = [
                {"timestamp": d["timestamp"], "score": d.get("cumulative_score", 0)}
                for d in docs
            ]

    return {"student_id": student_id, "timeline": timeline}


# ── Phase 3: Evidence Viewer ──────────────────────────────────────────────────

@router.get("/evidence/{student_id}")
async def get_evidence(student_id: str):
    """
    Return a list of evidence screenshots for a student.
    Scans the proctor_logs/{student_id}/ directory.
    """
    safe_id = "".join(c if c.isalnum() or c in ("_", "-", ".") else "_" for c in student_id)
    student_dir = _EVIDENCE_BASE / safe_id

    evidence = []
    if student_dir.exists() and student_dir.is_dir():
        for f in sorted(student_dir.iterdir()):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                # Parse filename:  {event_type}_{timestamp_ms}.jpg
                name = f.stem
                parts = name.rsplit("_", 1)
                event_type = parts[0] if len(parts) > 1 else "unknown"
                try:
                    ts = int(parts[-1]) if len(parts) > 1 else 0
                except ValueError:
                    ts = 0

                evidence.append({
                    "filename": f.name,
                    "type": event_type,
                    "timestamp": ts,
                    "url": f"/api/admin/evidence-file/{safe_id}/{f.name}",
                    "size_bytes": f.stat().st_size,
                })

    return {"student_id": student_id, "evidence": evidence, "total": len(evidence)}


@router.get("/evidence-file/{student_id}/{filename}")
async def serve_evidence_file(student_id: str, filename: str):
    """Serve a single evidence screenshot image file."""
    safe_id = "".join(c if c.isalnum() or c in ("_", "-", ".") else "_" for c in student_id)
    safe_file = "".join(c if c.isalnum() or c in ("_", "-", ".") else "_" for c in filename)
    filepath = _EVIDENCE_BASE / safe_id / safe_file

    if not filepath.exists() or not filepath.is_file():
        return {"error": "File not found"}

    return FileResponse(str(filepath), media_type="image/jpeg")


# ── Phase 3: Flag / Mark ─────────────────────────────────────────────────────

@router.post("/flag/{submission_id}")
async def flag_submission(submission_id: str):
    """Toggle the flagged status for a submission."""
    if submission_id not in _review_status:
        _review_status[submission_id] = {}

    current = _review_status[submission_id].get("flagged", False)
    _review_status[submission_id]["flagged"] = not current
    _review_status[submission_id]["flagged_at"] = int(time.time() * 1000) if not current else None

    # Persist to DB if available
    db = get_db()
    if db is not None:
        try:
            await db.submissions.update_one(
                {"submission_id": submission_id},
                {"$set": {"flagged": _review_status[submission_id]["flagged"]}},
            )
        except Exception:
            pass

    return {
        "submission_id": submission_id,
        "flagged": _review_status[submission_id]["flagged"],
        "message": "Flagged" if _review_status[submission_id]["flagged"] else "Unflagged",
    }


@router.post("/mark/{submission_id}")
async def mark_submission(submission_id: str, body: MarkRequest):
    """Mark a submission as 'valid' or 'invalid'."""
    if body.status not in ("valid", "invalid"):
        return {"error": "Status must be 'valid' or 'invalid'"}

    if submission_id not in _review_status:
        _review_status[submission_id] = {}

    _review_status[submission_id]["status"] = body.status
    _review_status[submission_id]["reviewed_at"] = int(time.time() * 1000)

    # Persist to DB if available
    db = get_db()
    if db is not None:
        try:
            await db.submissions.update_one(
                {"submission_id": submission_id},
                {"$set": {"review_status": body.status}},
            )
        except Exception:
            pass

    return {
        "submission_id": submission_id,
        "status": body.status,
        "message": f"Marked as {body.status}",
    }
