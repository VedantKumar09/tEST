"""
Admin Routes — View all student submissions
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ..database import get_db
from ..config import settings
import time
import json
import requests
import random

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


class GenerateQuestionsRequest(BaseModel):
    topic: str = "Computer Science Fundamentals"
    total_questions: int = Field(default=15, ge=5, le=30)


LOCAL_QUESTION_BANK = [
    {"category": "CS Fundamentals", "text": "Which data structure follows LIFO order?", "options": ["Queue", "Stack", "Heap", "Graph"], "correct": 1},
    {"category": "CS Fundamentals", "text": "What is the average time complexity of binary search?", "options": ["O(n)", "O(log n)", "O(n log n)", "O(1)"], "correct": 1},
    {"category": "CS Fundamentals", "text": "Which SQL clause is used to filter rows?", "options": ["ORDER BY", "GROUP BY", "WHERE", "HAVING"], "correct": 2},
    {"category": "CS Fundamentals", "text": "Which normal form removes transitive dependencies?", "options": ["1NF", "2NF", "3NF", "BCNF"], "correct": 2},
    {"category": "CS Fundamentals", "text": "Which operation removes the top element from a stack?", "options": ["push", "insert", "pop", "peek"], "correct": 2},
    {"category": "AI & ML", "text": "Which algorithm is commonly used for binary classification?", "options": ["Linear Regression", "Logistic Regression", "PCA", "K-Means"], "correct": 1},
    {"category": "AI & ML", "text": "What does overfitting mean in ML?", "options": ["Model performs poorly on training data", "Model memorizes training data and generalizes poorly", "Model has too few parameters", "Model cannot converge"], "correct": 1},
    {"category": "AI & ML", "text": "Which metric is suitable for imbalanced classification?", "options": ["Accuracy", "MAE", "F1-score", "MSE"], "correct": 2},
    {"category": "AI & ML", "text": "What is the purpose of a validation set?", "options": ["Train model weights", "Tune hyperparameters", "Deploy model", "Store raw data"], "correct": 1},
    {"category": "AI & ML", "text": "Which activation function outputs values between 0 and 1?", "options": ["ReLU", "Sigmoid", "Tanh", "Softplus"], "correct": 1},
    {"category": "Networking", "text": "Which protocol is used to securely browse websites?", "options": ["HTTP", "FTP", "HTTPS", "SMTP"], "correct": 2},
    {"category": "Networking", "text": "Which OSI layer handles routing?", "options": ["Data Link", "Network", "Transport", "Session"], "correct": 1},
    {"category": "Networking", "text": "What does DNS primarily do?", "options": ["Encrypt traffic", "Translate domain names to IP addresses", "Compress data", "Route packets"], "correct": 1},
    {"category": "Networking", "text": "Which command checks path to a destination host?", "options": ["ping", "traceroute", "netstat", "arp"], "correct": 1},
    {"category": "Networking", "text": "Which port is commonly used for HTTPS?", "options": ["21", "53", "80", "443"], "correct": 3},
]

LOCAL_CODING_TEMPLATE_BANK = [
    {
        "title": "Array Left Rotation",
        "category": "Coding — Python",
        "language": "python",
        "difficulty": "Medium",
        "tags": ["array", "rotation", "data structure", "algorithm"],
        "description": (
            "Problem Statement\n"
            "You are given an array of integers and an integer d. Rotate the array to the left by d positions and print the rotated array.\n\n"
            "Input Format\n"
            "- First line: two integers n and d\n"
            "- Second line: n space-separated integers\n\n"
            "Constraints\n"
            "- 1 <= n <= 10^5\n"
            "- 0 <= d <= 10^5\n"
            "- Each value fits in 32-bit signed integer\n\n"
            "Output Format\n"
            "Print the rotated array as space-separated integers in one line.\n\n"
            "Sample Input\n"
            "5 2\n"
            "1 2 3 4 5\n\n"
            "Sample Output\n"
            "3 4 5 1 2"
        ),
        "starter_code": (
            "n, d = map(int, input().split())\n"
            "arr = list(map(int, input().split()))\n"
            "# Write your solution below\n"
        ),
        "test_cases": [
            {"input": "5 2\n1 2 3 4 5", "expected_output": "3 4 5 1 2"},
            {"input": "4 1\n10 20 30 40", "expected_output": "20 30 40 10"},
        ],
    },
    {
        "title": "Balanced Brackets",
        "category": "Coding — Python",
        "language": "python",
        "difficulty": "Medium",
        "tags": ["stack", "string", "brackets", "data structure"],
        "description": (
            "Problem Statement\n"
            "Given a string containing only brackets (), {}, and [], determine whether it is balanced.\n\n"
            "Input Format\n"
            "- A single line containing the bracket string s\n\n"
            "Constraints\n"
            "- 1 <= len(s) <= 10^5\n\n"
            "Output Format\n"
            "Print YES if the string is balanced, otherwise print NO.\n\n"
            "Sample Input\n"
            "{[()]}\n\n"
            "Sample Output\n"
            "YES"
        ),
        "starter_code": "s = input().strip()\n# Write your solution below\n",
        "test_cases": [
            {"input": "{[()]}", "expected_output": "YES"},
            {"input": "{[(])}", "expected_output": "NO"},
            {"input": "()[]{}", "expected_output": "YES"},
        ],
    },
    {
        "title": "FizzBuzz Sequence",
        "category": "Coding — C",
        "language": "c",
        "difficulty": "Easy",
        "tags": ["loops", "conditionals", "algorithm", "math"],
        "description": (
            "Problem Statement\n"
            "Given an integer N, print values from 1 to N using these rules:\n"
            "- Print FizzBuzz if divisible by both 3 and 5\n"
            "- Print Fizz if divisible by 3\n"
            "- Print Buzz if divisible by 5\n"
            "- Otherwise print the number\n\n"
            "Input Format\n"
            "- A single integer N\n\n"
            "Constraints\n"
            "- 1 <= N <= 10^5\n\n"
            "Output Format\n"
            "Print one output per line.\n\n"
            "Sample Input\n"
            "5\n\n"
            "Sample Output\n"
            "1\n"
            "2\n"
            "Fizz\n"
            "4\n"
            "Buzz"
        ),
        "starter_code": (
            "#include <stdio.h>\n\n"
            "int main() {\n"
            "    int n;\n"
            "    scanf(\"%d\", &n);\n"
            "    // Write your solution below\n"
            "    return 0;\n"
            "}\n"
        ),
        "test_cases": [
            {"input": "5", "expected_output": "1\n2\nFizz\n4\nBuzz"},
            {"input": "3", "expected_output": "1\n2\nFizz"},
            {"input": "15", "expected_output": "1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz"},
        ],
    },
    {
        "title": "Run-Length Encoding",
        "category": "Coding — Java",
        "language": "java",
        "difficulty": "Medium",
        "tags": ["string", "compression", "implementation", "java"],
        "description": (
            "Problem Statement\n"
            "Given a lowercase string, compress it using run-length encoding by replacing consecutive repeated characters with char + count.\n\n"
            "Input Format\n"
            "- A single lowercase string s\n\n"
            "Constraints\n"
            "- 1 <= len(s) <= 10^5\n\n"
            "Output Format\n"
            "Print the compressed string.\n\n"
            "Sample Input\n"
            "aaabbc\n\n"
            "Sample Output\n"
            "a3b2c1"
        ),
        "starter_code": (
            "import java.util.Scanner;\n\n"
            "public class Solution {\n"
            "    public static void main(String[] args) {\n"
            "        Scanner sc = new Scanner(System.in);\n"
            "        String s = sc.nextLine();\n"
            "        // Write your solution below\n"
            "    }\n"
            "}\n"
        ),
        "test_cases": [
            {"input": "aaabbc", "expected_output": "a3b2c1"},
            {"input": "abcd", "expected_output": "a1b1c1d1"},
        ],
    },
    {
        "title": "Employee Query",
        "category": "Coding — SQL",
        "language": "sql",
        "difficulty": "Easy",
        "tags": ["sql", "database", "query", "filtering"],
        "description": (
            "Problem Statement\n"
            "Write a SQL query to return all employees from the Engineering department with salary greater than 100000.\n\n"
            "Schema\n"
            "employees(id, name, department, salary, hire_date)\n\n"
            "Output Format\n"
            "Return columns: name, salary\n"
            "Sort by salary in descending order.\n\n"
            "Sample Output\n"
            "name | salary\n"
            "--------------\n"
            "Charlie | 110000.0\n"
            "Eve | 105000.0"
        ),
        "starter_code": "SELECT name, salary\nFROM employees\nWHERE -- add conditions\nORDER BY -- complete here\n",
        "test_cases": [
            {
                "input": "",
                "expected_output": "name | salary\n--------------\nCharlie | 110000.0\nEve | 105000.0",
            }
        ],
    },
]


def _safe_parse_json(text: str) -> dict:
    cleaned = (text or "").strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


def _normalize_generated_questions(raw_questions: list, total: int) -> list[dict]:
    if not isinstance(raw_questions, list):
        raise ValueError("Model output missing 'mcq_questions' list")

    normalized = []
    for index, item in enumerate(raw_questions[:total], start=1):
        if not isinstance(item, dict):
            continue

        options = item.get("options", [])
        if not isinstance(options, list) or len(options) != 4:
            continue

        correct = item.get("correct")
        if isinstance(correct, str) and correct.isdigit():
            correct = int(correct)
        if not isinstance(correct, int) or correct < 0 or correct > 3:
            continue

        category = str(item.get("category", "General")).strip() or "General"
        text = str(item.get("text", "")).strip()
        if not text:
            continue

        normalized.append({
            "id": index,
            "type": "mcq",
            "category": category,
            "text": text,
            "options": [str(opt) for opt in options],
            "correct": correct,
        })

    if len(normalized) < total:
        raise ValueError(f"Model returned only {len(normalized)} valid questions, expected {total}")

    return normalized


def _generate_questions_openai(topic: str, total_questions: int) -> list[dict]:
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY is not configured")

    model = settings.OPENAI_MODEL or "gpt-4o-mini"
    prompt = f"""
Generate exactly {total_questions} multiple-choice exam questions for topic: {topic}.

Requirements:
- Return ONLY valid JSON.
- JSON shape:
{{
  "mcq_questions": [
    {{
      "category": "string",
      "text": "string",
      "options": ["A", "B", "C", "D"],
      "correct": 0
    }}
  ]
}}
- Each question must have exactly 4 options.
- "correct" must be an integer in range 0..3.
- No explanations, no markdown, no extra keys.
"""

    response = None
    for attempt in range(3):
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a strict JSON generator for exam MCQs."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.4,
                    "response_format": {"type": "json_object"},
                },
                timeout=45,
            )
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"OpenAI request failed: {exc}")

        if response.status_code == 429:
            error_code = "rate_limit_exceeded"
            error_message = "OpenAI rate limit exceeded"
            try:
                error_payload = response.json().get("error", {})
                error_code = str(error_payload.get("code") or error_payload.get("type") or error_code)
                error_message = str(error_payload.get("message") or error_message)
            except Exception:
                pass

            if error_code == "insufficient_quota":
                raise HTTPException(
                    status_code=429,
                    detail="OpenAI insufficient_quota: this API key has no available credits. Add billing/credits or replace OPENAI_API_KEY.",
                )

            if attempt < 2:
                retry_after = response.headers.get("Retry-After", "")
                wait_s = int(retry_after) if retry_after.isdigit() else (8 * (attempt + 1))
                time.sleep(wait_s)
                continue

            raise HTTPException(
                status_code=429,
                detail=f"OpenAI rate limit exceeded: {error_message} (OpenAI-only mode; no fallback used)",
            )

        if response.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="OpenAI key invalid or unauthorized")

        response.raise_for_status()
        break

    if response is None:
        raise HTTPException(status_code=500, detail="OpenAI request did not return a response")

    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    payload = _safe_parse_json(content)
    questions = _normalize_generated_questions(payload.get("mcq_questions", []), total_questions)
    return questions


def _generate_questions_local(topic: str, total_questions: int) -> list[dict]:
    topic_l = (topic or "").lower()
    prioritized = [
        q for q in LOCAL_QUESTION_BANK
        if topic_l and (topic_l in q["text"].lower() or topic_l in q["category"].lower())
    ]
    base_pool = prioritized + [q for q in LOCAL_QUESTION_BANK if q not in prioritized]
    if not base_pool:
        raise HTTPException(status_code=500, detail="Local question bank is empty")

    random.shuffle(base_pool)
    generated = []
    for i in range(total_questions):
        source = base_pool[i % len(base_pool)]
        text = source["text"]
        if i >= len(base_pool):
            text = f"{text} ({topic})"
        generated.append({
            "id": i + 1,
            "type": "mcq",
            "category": source["category"],
            "text": text,
            "options": list(source["options"]),
            "correct": int(source["correct"]),
        })
    return generated


def _generate_coding_questions_local(topic: str, total_questions: int = 5) -> list[dict]:
    topic_l = (topic or "").lower().strip()

    scored_pool: list[tuple[int, float, dict]] = []
    for template in LOCAL_CODING_TEMPLATE_BANK:
        tags = [str(tag).lower() for tag in template.get("tags", [])]
        score = sum(2 for tag in tags if tag and tag in topic_l)
        score += sum(1 for token in topic_l.split() if token in tags)
        scored_pool.append((score, random.random(), template))

    scored_pool.sort(key=lambda x: (-x[0], x[1]))
    base_pool = [item[2] for item in scored_pool]

    generated = []
    for i in range(total_questions):
        source = base_pool[i % len(base_pool)]
        description = source["description"]
        if topic_l:
            description = f"{description}\n\nTopic Focus: {topic}"

        generated.append({
            "id": 1001 + i,
            "type": "coding",
            "title": source["title"],
            "category": source["category"],
            "language": source["language"],
            "difficulty": source["difficulty"],
            "description": description,
            "starter_code": source["starter_code"],
            "test_cases": list(source["test_cases"]),
        })
    return generated


@router.post("/questions/generate")
async def generate_questions(body: GenerateQuestionsRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable. Cannot store generated questions.")

    provider = "openai"
    model = settings.OPENAI_MODEL
    notice = None
    try:
        questions = _generate_questions_openai(body.topic, body.total_questions)
    except HTTPException as exc:
        if exc.status_code == 429 and "insufficient_quota" in str(exc.detail):
            questions = _generate_questions_local(body.topic, body.total_questions)
            provider = "local"
            model = "rule-based-fallback"
            notice = "OpenAI key has insufficient quota; generated from local fallback bank."
        else:
            raise

    coding_questions = _generate_coding_questions_local(body.topic, total_questions=5)

    now_ms = int(time.time() * 1000)

    try:
        await db.exam_question_sets.update_many({"active": True}, {"$set": {"active": False}})
        await db.exam_question_sets.insert_one({
            "active": True,
            "provider": provider,
            "model": model,
            "topic": body.topic,
            "created_at": now_ms,
            "mcq_questions": questions,
            "coding_questions": coding_questions,
        })
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist generated questions: {exc}")

    return {
        "status": "ok",
        "provider": provider,
        "model": model,
        "topic": body.topic,
        "mcq_count": len(questions),
        "coding_count": len(coding_questions),
        "count": len(questions) + len(coding_questions),
        "created_at": now_ms,
        "notice": notice,
    }


@router.get("/questions/active")
async def get_active_questions_meta():
    db = get_db()
    if db is None:
        return {"active": False, "count": 0}

    doc = await db.exam_question_sets.find_one(
        {"active": True},
        {"_id": 0, "provider": 1, "model": 1, "topic": 1, "created_at": 1, "mcq_questions": 1, "coding_questions": 1},
        sort=[("created_at", -1)],
    )
    if not doc:
        return {"active": False, "count": 0}

    return {
        "active": True,
        "provider": doc.get("provider", "unknown"),
        "model": doc.get("model", "unknown"),
        "topic": doc.get("topic", "General"),
        "created_at": doc.get("created_at"),
        "mcq_count": len(doc.get("mcq_questions", [])),
        "coding_count": len(doc.get("coding_questions", [])),
        "count": len(doc.get("mcq_questions", [])) + len(doc.get("coding_questions", [])),
    }


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
