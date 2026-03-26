"""
Exam Routes — Questions and submission
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import time
from ..database import get_db
from ..ai.agent import generate_supervisor_report

router = APIRouter(prefix="/api/exam", tags=["exam"])

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

CODING_QUESTION_REFS = [
    {"id": 101, "type": "coding", "category": "Coding — Python", "title": "Two Sum", "language": "python", "difficulty": "Easy"},
    {"id": 102, "type": "coding", "category": "Coding — Python", "title": "Reverse String", "language": "python", "difficulty": "Easy"},
    {"id": 103, "type": "coding", "category": "Coding — C", "title": "FizzBuzz", "language": "c", "difficulty": "Easy"},
    {"id": 104, "type": "coding", "category": "Coding — Java", "title": "Hello Java", "language": "java", "difficulty": "Easy"},
    {"id": 105, "type": "coding", "category": "Coding — SQL", "title": "Employee Query", "language": "sql", "difficulty": "Easy"},
]

ALL_QUESTIONS = MCQ_QUESTIONS + CODING_QUESTION_REFS

class SubmitRequest(BaseModel):
    answers: list[int]
    coding_scores: Optional[dict] = None
    time_used: int
    proctoring_data: Optional[dict] = None


async def _load_mcq_questions() -> list[dict]:
    db = get_db()
    if db is None:
        return MCQ_QUESTIONS

    try:
        doc = await db.exam_question_sets.find_one(
            {"active": True},
            {"_id": 0, "mcq_questions": 1},
            sort=[("created_at", -1)],
        )
        if doc and isinstance(doc.get("mcq_questions"), list) and len(doc["mcq_questions"]) > 0:
            return doc["mcq_questions"]
    except Exception as e:
        print(f"Failed to load active generated questions: {e}")

    return MCQ_QUESTIONS


async def _load_coding_questions() -> list[dict]:
    db = get_db()
    if db is None:
        return CODING_QUESTION_REFS

    try:
        doc = await db.exam_question_sets.find_one(
            {"active": True},
            {"_id": 0, "coding_questions": 1},
            sort=[("created_at", -1)],
        )
        if doc and isinstance(doc.get("coding_questions"), list) and len(doc["coding_questions"]) > 0:
            return doc["coding_questions"]
    except Exception as e:
        print(f"Failed to load active generated coding questions: {e}")

    return CODING_QUESTION_REFS

@router.get("/questions")
async def get_questions():
    mcq_questions = await _load_mcq_questions()
    coding_questions = await _load_coding_questions()
    result = []
    for q in mcq_questions:
        result.append({
            "id": q["id"],
            "type": "mcq",
            "category": q["category"],
            "text": q["text"],
            "options": q["options"],
        })
    for q in coding_questions:
        result.append({
            "id": q["id"],
            "type": "coding",
            "category": q["category"],
            "title": q["title"],
            "language": q["language"],
            "difficulty": q["difficulty"],
            "description": q.get("description"),
            "starter_code": q.get("starter_code"),
        })
    return result

@router.post("/submit")
async def submit_exam(body: SubmitRequest):
    mcq_questions = await _load_mcq_questions()
    coding_questions = await _load_coding_questions()

    # MCQ Score
    correct = sum(
        1 for i, ans in enumerate(body.answers)
        if i < len(mcq_questions) and ans == mcq_questions[i]["correct"]
    )
    mcq_total = len(mcq_questions)
    mcq_score = round((correct / mcq_total) * 100) if mcq_total > 0 else 0

    # Coding Score
    coding_scores = body.coding_scores or {}
    coding_total_questions = len(coding_questions)
    coding_score = 0
    if coding_scores:
        coding_score = round(sum(coding_scores.values()) / coding_total_questions)

    # Weighted Scoring: 50/50
    if coding_total_questions > 0 and coding_scores:
        final_score = round((mcq_score * 0.5) + (coding_score * 0.5))
    else:
        final_score = mcq_score

    # Run Agentic Supervisor Action
    if isinstance(body.proctoring_data, dict):
        events = body.proctoring_data.get("events", [])
        violations = body.proctoring_data.get("violations", body.proctoring_data.get("total_violations", 0))
    else:
        events = []
        violations = 0

    agent_report = generate_supervisor_report(events, violations, body.coding_scores, body.time_used, exam_finished=True)

    result = {
        "score": final_score,
        "mcq_score": mcq_score,
        "coding_score": coding_score,
        "correct": correct,
        "questions_total": mcq_total + coding_total_questions,
        "questions_answered": sum(1 for a in body.answers if a != -1) + len(coding_scores),
        "time_used": body.time_used,
        "category_scores": _category_scores(body.answers, mcq_questions),
        "proctoring_summary": body.proctoring_data,
        "ai_supervisor": agent_report,
    }

    db = get_db()
    if db is not None:
        try:
            await db.submissions.insert_one({
                **result,
                "student_name": "Demo Student",
                "submitted_at": int(time.time() * 1000),
            })
        except Exception as e:
            print(f"Failed to insert submission into MongoDB: {e}")

    return result

def _category_scores(answers: list[int], mcq_questions: list[dict]) -> dict:
    cats: dict[str, dict] = {}
    for i, q in enumerate(mcq_questions):
        c = q["category"]
        if c not in cats:
            cats[c] = {"correct": 0, "total": 0}
        cats[c]["total"] += 1
        if i < len(answers) and answers[i] == q["correct"]:
            cats[c]["correct"] += 1
    return {c: round((v["correct"] / v["total"]) * 100) for c, v in cats.items()}

