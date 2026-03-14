"""
Admin Routes — View all student submissions
"""
from fastapi import APIRouter
from ..database import get_db
import time

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Fallback in-memory demo data when MongoDB is unavailable
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


@router.get("/submissions")
async def get_submissions():
    db = get_db()
    if db is None:
        return _demo_submissions
    docs = await db.submissions.find({}, {"_id": 0}).sort("submitted_at", -1).to_list(100)
    return docs if docs else _demo_submissions


@router.get("/submissions/{submission_id}")
async def get_submission(submission_id: str):
    db = get_db()
    if db is None:
        return _demo_submissions[0]
    doc = await db.submissions.find_one({"submission_id": submission_id}, {"_id": 0})
    return doc or _demo_submissions[0]
