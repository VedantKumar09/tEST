"""
Exam Routes — Questions + Submit
"""
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Any
import uuid

from ..database import get_db
from .auth import verify_token

router = APIRouter(prefix="/api/exam", tags=["exam"])

# ── Static question bank ──────────────────────────────────────────────────────
QUESTIONS = [
    {"id": 1, "category": "CS Fundamentals", "text": "Which data structure uses LIFO ordering?", "options": ["Queue", "Stack", "Linked List", "Tree"], "correct": 1},
    {"id": 2, "category": "CS Fundamentals", "text": "Time complexity of binary search on a sorted array?", "options": ["O(n)", "O(n²)", "O(log n)", "O(n log n)"], "correct": 2},
    {"id": 3, "category": "CS Fundamentals", "text": "Which protocol is used for secure communication?", "options": ["HTTP", "FTP", "HTTPS", "SMTP"], "correct": 2},
    {"id": 4, "category": "CS Fundamentals", "text": "In SQL, what does DDL stand for?", "options": ["Data Definition Language", "Data Display Logic", "Dynamic Data Layer", "Database Design Language"], "correct": 0},
    {"id": 5, "category": "CS Fundamentals", "text": "Which sorting algorithm has best average-case complexity?", "options": ["Bubble Sort", "Selection Sort", "Merge Sort", "Insertion Sort"], "correct": 2},
    {"id": 6, "category": "AI & ML", "text": "Which technique is used for classifying spam emails?", "options": ["Linear Regression", "K-Means", "Naive Bayes", "PCA"], "correct": 2},
    {"id": 7, "category": "AI & ML", "text": "Which activation function outputs values between 0 and 1?", "options": ["ReLU", "Sigmoid", "Tanh", "Leaky ReLU"], "correct": 1},
    {"id": 8, "category": "AI & ML", "text": "Which technique prevents overfitting in neural networks?", "options": ["Dropout", "Batch Norm", "Gradient Descent", "Backpropagation"], "correct": 0},
    {"id": 9, "category": "AI & ML", "text": "CNN stands for?", "options": ["Computer Neural Network", "Convolutional Neural Network", "Central Neuron Node", "Connected Network"], "correct": 1},
    {"id": 10, "category": "AI & ML", "text": "Algorithm used for recommendation systems?", "options": ["Decision Trees", "Collaborative Filtering", "KNN", "SVM"], "correct": 1},
    {"id": 11, "category": "Networking", "text": "What does TCP stand for?", "options": ["Transfer Control Protocol", "Transmission Control Protocol", "Traffic Control Protocol", "Transfer Call Protocol"], "correct": 1},
    {"id": 12, "category": "Networking", "text": "OSI layer that handles routing between networks?", "options": ["Transport", "Data Link", "Network", "Application"], "correct": 2},
    {"id": 13, "category": "Networking", "text": "Encryption using public/private key pair?", "options": ["Symmetric", "Asymmetric", "Hashing", "Caesar Cipher"], "correct": 1},
    {"id": 14, "category": "Networking", "text": "Attack that floods a server to make it unavailable?", "options": ["Phishing", "SQL Injection", "DDoS", "Man-in-the-Middle"], "correct": 2},
    {"id": 15, "category": "Networking", "text": "Which port does HTTPS use by default?", "options": ["80", "21", "443", "8080"], "correct": 2},
]


# ── Schemas ───────────────────────────────────────────────────────────────────
class SubmitRequest(BaseModel):
    answers: list[int]
    time_used: int
    proctoring_data: dict[str, Any] = {}


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.get("/questions")
async def get_questions():
    return [{"id": q["id"], "category": q["category"], "text": q["text"], "options": q["options"]} for q in QUESTIONS]


@router.post("/submit")
async def submit_exam(body: SubmitRequest, payload: dict = Depends(verify_token)):
    # Score calculation
    correct = 0
    category_scores: dict[str, dict] = {}
    for i, q in enumerate(QUESTIONS):
        cat = q["category"]
        if cat not in category_scores:
            category_scores[cat] = {"total": 0, "correct": 0}
        category_scores[cat]["total"] += 1
        if i < len(body.answers) and body.answers[i] == q["correct"]:
            correct += 1
            category_scores[cat]["correct"] += 1

    score = round((correct / len(QUESTIONS)) * 100)
    answered = sum(1 for a in body.answers if a != -1)

    result = {
        "submission_id": str(uuid.uuid4()),
        "student_email": payload["sub"],
        "student_name": payload["name"],
        "score": score,
        "correct": correct,
        "questions_total": len(QUESTIONS),
        "questions_answered": answered,
        "time_used": body.time_used,
        "category_scores": category_scores,
        "proctoring_summary": body.proctoring_data,
        "submitted_at": datetime.utcnow().isoformat(),
    }

    # Persist to MongoDB if available
    db = get_db()
    if db is not None:
        await db.submissions.insert_one({**result})

    return result
