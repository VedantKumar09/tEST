"""
Exam Routes — Questions and submission
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import time
from ..database import get_db

router = APIRouter(prefix="/api/exam", tags=["exam"])

QUESTIONS = [
    {"id": 1, "category": "CS Fundamentals", "text": "Which data structure uses LIFO ordering?",
     "options": ["Queue", "Stack", "Linked List", "Tree"], "correct": 1},
    {"id": 2, "category": "CS Fundamentals", "text": "Time complexity of binary search?",
     "options": ["O(n)", "O(n²)", "O(log n)", "O(n log n)"], "correct": 2},
    {"id": 3, "category": "CS Fundamentals", "text": "Which protocol is used for secure communication?",
     "options": ["HTTP", "FTP", "HTTPS", "SMTP"], "correct": 2},
    {"id": 4, "category": "CS Fundamentals", "text": "What does DDL stand for in SQL?",
     "options": ["Data Definition Language", "Data Display Logic", "Dynamic Data Layer", "Database Design Language"], "correct": 0},
    {"id": 5, "category": "CS Fundamentals", "text": "Which sorting algorithm has best average-case complexity?",
     "options": ["Bubble Sort", "Selection Sort", "Merge Sort", "Insertion Sort"], "correct": 2},
    {"id": 6, "category": "AI & ML", "text": "Which technique classifies spam emails?",
     "options": ["Linear Regression", "K-Means", "Naive Bayes", "PCA"], "correct": 2},
    {"id": 7, "category": "AI & ML", "text": "Activation function outputting values 0–1?",
     "options": ["ReLU", "Sigmoid", "Tanh", "Leaky ReLU"], "correct": 1},
    {"id": 8, "category": "AI & ML", "text": "Technique to prevent overfitting in neural networks?",
     "options": ["Dropout", "Batch Norm", "Gradient Descent", "Backpropagation"], "correct": 0},
    {"id": 9, "category": "AI & ML", "text": "CNN stands for?",
     "options": ["Computer Neural Nets", "Convolutional Neural Network", "Central Neuron Node", "Connected Network"], "correct": 1},
    {"id": 10, "category": "AI & ML", "text": "Algorithm used for recommendation systems?",
     "options": ["Decision Trees", "Collaborative Filtering", "KNN", "SVM"], "correct": 1},
    {"id": 11, "category": "Networking", "text": "TCP stands for?",
     "options": ["Transfer Control Protocol", "Transmission Control Protocol", "Traffic Control Protocol", "Transfer Call Protocol"], "correct": 1},
    {"id": 12, "category": "Networking", "text": "OSI layer handling routing between networks?",
     "options": ["Transport", "Data Link", "Network", "Application"], "correct": 2},
    {"id": 13, "category": "Networking", "text": "Encryption using public/private key pair?",
     "options": ["Symmetric", "Asymmetric", "Hashing", "Caesar Cipher"], "correct": 1},
    {"id": 14, "category": "Networking", "text": "Attack that floods a server?",
     "options": ["Phishing", "SQL Injection", "DDoS", "Man-in-the-Middle"], "correct": 2},
    {"id": 15, "category": "Networking", "text": "Default HTTPS port?",
     "options": ["80", "21", "443", "8080"], "correct": 2},
]


class SubmitRequest(BaseModel):
    answers: list[int]
    time_used: int
    proctoring_data: Optional[dict] = None


@router.get("/questions")
async def get_questions():
    return [{"id": q["id"], "category": q["category"], "text": q["text"], "options": q["options"]} for q in QUESTIONS]


@router.post("/submit")
async def submit_exam(body: SubmitRequest):
    correct = sum(
        1 for i, ans in enumerate(body.answers)
        if i < len(QUESTIONS) and ans == QUESTIONS[i]["correct"]
    )
    score = round((correct / len(QUESTIONS)) * 100)

    result = {
        "score": score,
        "correct": correct,
        "questions_total": len(QUESTIONS),
        "questions_answered": sum(1 for a in body.answers if a != -1),
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
    for i, q in enumerate(QUESTIONS):
        c = q["category"]
        if c not in cats:
            cats[c] = {"correct": 0, "total": 0}
        cats[c]["total"] += 1
        if i < len(answers) and answers[i] == q["correct"]:
            cats[c]["correct"] += 1
    return {c: round((v["correct"] / v["total"]) * 100) for c, v in cats.items()}
