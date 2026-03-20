"""
Exam Routes — Questions and submission (MCQ + Coding)
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import time
from ..database import get_db

router = APIRouter(prefix="/api/exam", tags=["exam"])

# ── MCQ Questions ─────────────────────────────────────────────────────────────

MCQ_QUESTIONS = [
    {"id": 1, "type": "mcq", "category": "CS Fundamentals", "text": "Which data structure uses LIFO ordering?",
     "options": ["Queue", "Stack", "Linked List", "Tree"], "correct": 1},
    {"id": 2, "type": "mcq", "category": "CS Fundamentals", "text": "Time complexity of binary search?",
     "options": ["O(n)", "O(n²)", "O(log n)", "O(n log n)"], "correct": 2},
    {"id": 3, "type": "mcq", "category": "CS Fundamentals", "text": "Which protocol is used for secure communication?",
     "options": ["HTTP", "FTP", "HTTPS", "SMTP"], "correct": 2},
    {"id": 4, "type": "mcq", "category": "CS Fundamentals", "text": "What does DDL stand for in SQL?",
     "options": ["Data Definition Language", "Data Display Logic", "Dynamic Data Layer", "Database Design Language"], "correct": 0},
    {"id": 5, "type": "mcq", "category": "CS Fundamentals", "text": "Which sorting algorithm has best average-case complexity?",
     "options": ["Bubble Sort", "Selection Sort", "Merge Sort", "Insertion Sort"], "correct": 2},
    {"id": 6, "type": "mcq", "category": "AI & ML", "text": "Which technique classifies spam emails?",
     "options": ["Linear Regression", "K-Means", "Naive Bayes", "PCA"], "correct": 2},
    {"id": 7, "type": "mcq", "category": "AI & ML", "text": "Activation function outputting values 0–1?",
     "options": ["ReLU", "Sigmoid", "Tanh", "Leaky ReLU"], "correct": 1},
    {"id": 8, "type": "mcq", "category": "AI & ML", "text": "Technique to prevent overfitting in neural networks?",
     "options": ["Dropout", "Batch Norm", "Gradient Descent", "Backpropagation"], "correct": 0},
    {"id": 9, "type": "mcq", "category": "AI & ML", "text": "CNN stands for?",
     "options": ["Computer Neural Nets", "Convolutional Neural Network", "Central Neuron Node", "Connected Network"], "correct": 1},
    {"id": 10, "type": "mcq", "category": "AI & ML", "text": "Algorithm used for recommendation systems?",
     "options": ["Decision Trees", "Collaborative Filtering", "KNN", "SVM"], "correct": 1},
    {"id": 11, "type": "mcq", "category": "Networking", "text": "TCP stands for?",
     "options": ["Transfer Control Protocol", "Transmission Control Protocol", "Traffic Control Protocol", "Transfer Call Protocol"], "correct": 1},
    {"id": 12, "type": "mcq", "category": "Networking", "text": "OSI layer handling routing between networks?",
     "options": ["Transport", "Data Link", "Network", "Application"], "correct": 2},
    {"id": 13, "type": "mcq", "category": "Networking", "text": "Encryption using public/private key pair?",
     "options": ["Symmetric", "Asymmetric", "Hashing", "Caesar Cipher"], "correct": 1},
    {"id": 14, "type": "mcq", "category": "Networking", "text": "Attack that floods a server?",
     "options": ["Phishing", "SQL Injection", "DDoS", "Man-in-the-Middle"], "correct": 2},
    {"id": 15, "type": "mcq", "category": "Networking", "text": "Default HTTPS port?",
     "options": ["80", "21", "443", "8080"], "correct": 2},
]

# ── Coding Questions (references — full definitions live in routes/code.py) ──

CODING_QUESTION_REFS = [
    {"id": 101, "type": "coding", "category": "Coding — Python", "title": "Two Sum",
     "language": "python", "difficulty": "Easy"},
    {"id": 102, "type": "coding", "category": "Coding — Python", "title": "Reverse String",
     "language": "python", "difficulty": "Easy"},
    {"id": 103, "type": "coding", "category": "Coding — C", "title": "FizzBuzz",
     "language": "c", "difficulty": "Easy"},
    {"id": 104, "type": "coding", "category": "Coding — Java", "title": "Hello Java",
     "language": "java", "difficulty": "Easy"},
    {"id": 105, "type": "coding", "category": "Coding — SQL", "title": "Employee Query",
     "language": "sql", "difficulty": "Easy"},
]

# Combined list for the exam
ALL_QUESTIONS = MCQ_QUESTIONS + CODING_QUESTION_REFS


class SubmitRequest(BaseModel):
    answers: list[int]                          # MCQ answers (-1 = unanswered)
    coding_scores: Optional[dict] = None        # {question_id: score_pct} from frontend
    time_used: int
    proctoring_data: Optional[dict] = None


@router.get("/questions")
async def get_questions():
    """Return all questions (MCQ + coding refs) without answers."""
    result = []
    for q in MCQ_QUESTIONS:
        result.append({
            "id": q["id"],
            "type": "mcq",
            "category": q["category"],
            "text": q["text"],
            "options": q["options"],
        })
    for q in CODING_QUESTION_REFS:
        result.append({
            "id": q["id"],
            "type": "coding",
            "category": q["category"],
            "title": q["title"],
            "language": q["language"],
            "difficulty": q["difficulty"],
        })
    return result


@router.post("/submit")
async def submit_exam(body: SubmitRequest):
    # ── Score MCQs ──
    mcq_correct = sum(
        1 for i, ans in enumerate(body.answers)
        if i < len(MCQ_QUESTIONS) and ans == MCQ_QUESTIONS[i]["correct"]
    )
    mcq_total = len(MCQ_QUESTIONS)

    # ── Score Coding (from frontend-submitted scores) ──
    coding_scores = body.coding_scores or {}
    coding_total = len(CODING_QUESTION_REFS)
    coding_avg = 0
    if coding_scores:
        coding_avg = round(sum(coding_scores.values()) / len(coding_scores))

    # ── Combined score: weighted average (MCQ 60% + Coding 40%) ──
    mcq_pct = round((mcq_correct / mcq_total) * 100) if mcq_total else 0
    if coding_total > 0 and coding_scores:
        combined_score = round(mcq_pct * 0.6 + coding_avg * 0.4)
    else:
        combined_score = mcq_pct

    result = {
        "score": combined_score,
        "mcq_score": mcq_pct,
        "mcq_correct": mcq_correct,
        "mcq_total": mcq_total,
        "coding_score": coding_avg,
        "coding_total": coding_total,
        "coding_details": coding_scores,
        "questions_total": mcq_total + coding_total,
        "questions_answered": sum(1 for a in body.answers if a != -1) + len(coding_scores),
        "time_used": body.time_used,
        "category_scores": _category_scores(body.answers),
        "proctoring_summary": body.proctoring_data,
    }

    db = get_db()
    if db is not None:
        await db.submissions.insert_one({
            **result,
            "student_name": "Demo Student",
            "submitted_at": int(time.time() * 1000),
        })

    return result


def _category_scores(answers: list[int]) -> dict:
    cats: dict[str, dict] = {}
    for i, q in enumerate(MCQ_QUESTIONS):
        c = q["category"]
        if c not in cats:
            cats[c] = {"correct": 0, "total": 0}
        cats[c]["total"] += 1
        if i < len(answers) and answers[i] == q["correct"]:
            cats[c]["correct"] += 1
    return {c: round((v["correct"] / v["total"]) * 100) for c, v in cats.items()}
