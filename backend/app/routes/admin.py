"""
Admin Routes — View all student submissions and proctoring data
"""
from fastapi import APIRouter, Depends, HTTPException
from .auth import verify_token
from ..database import get_db
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/admin", tags=["admin"])

# In-memory fallback submissions (used when MongoDB is unavailable)
_MOCK_SUBMISSIONS = [
    {
        "submission_id": str(uuid.uuid4()),
        "student_email": "student@mindmesh.ai",
        "student_name": "Demo Student",
        "score": 73,
        "correct": 11,
        "questions_total": 15,
        "questions_answered": 14,
        "time_used": 342,
        "category_scores": {
            "CS Fundamentals": {"total": 5, "correct": 4},
            "AI & ML": {"total": 5, "correct": 3},
            "Networking": {"total": 5, "correct": 4},
        },
        "proctoring_summary": {
            "total_violations": 3,
            "violation_types": ["no_face", "object:cell phone"],
            "risk_level": "Medium",
            "snapshots_analyzed": 24,
        },
        "submitted_at": datetime(2026, 3, 14, 17, 30).isoformat(),
    },
]


def _require_admin(payload: dict = Depends(verify_token)):
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


@router.get("/submissions")
async def get_all_submissions(payload: dict = Depends(_require_admin)):
    """Return all student exam submissions."""
    db = get_db()
    if db is not None:
        cursor = db.submissions.find({}, {"_id": 0}).sort("submitted_at", -1).limit(100)
        results = await cursor.to_list(100)
        return results if results else _MOCK_SUBMISSIONS
    return _MOCK_SUBMISSIONS


@router.get("/submissions/{submission_id}")
async def get_submission(submission_id: str, payload: dict = Depends(_require_admin)):
    """Return a single submission's full proctoring detail."""
    db = get_db()
    if db is not None:
        doc = await db.submissions.find_one({"submission_id": submission_id}, {"_id": 0})
        if doc:
            return doc
    # Try mock
    for s in _MOCK_SUBMISSIONS:
        if s["submission_id"] == submission_id:
            return s
    raise HTTPException(status_code=404, detail="Submission not found")
