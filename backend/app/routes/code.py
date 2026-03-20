"""
Code Execution Routes — Run and submit code for coding challenges.
Endpoints:
  POST /api/code/execute  — run code with optional stdin
  POST /api/code/submit   — run code against hidden test cases and grade
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

from ..services.code_executor import execute_code, run_test_cases, SUPPORTED_LANGUAGES

router = APIRouter(prefix="/api/code", tags=["code"])

_executor = ThreadPoolExecutor(max_workers=3)


# ── Request / Response Models ─────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    language: str                     # python | c | java | sql
    code: str
    stdin: str = ""                   # optional stdin input

class SubmitRequest(BaseModel):
    language: str
    code: str
    question_id: int                  # links to a coding question
    stdin: str = ""                   # ignored when test_cases are present

class TestCase(BaseModel):
    input: str = ""
    expected_output: str = ""


# ── Coding Questions Bank ─────────────────────────────────────────────────────
# Each question has hidden test cases used for grading.

CODING_QUESTIONS = {
    101: {
        "id": 101,
        "title": "Two Sum",
        "category": "Coding — Python",
        "language": "python",
        "difficulty": "Easy",
        "description": (
            "Given a list of integers and a target sum, return the indices of the "
            "two numbers that add up to the target.\n\n"
            "**Input format:** First line is the target. Second line is space-separated integers.\n"
            "**Output format:** Two space-separated indices (0-based).\n\n"
            "**Example:**\n"
            "Input:\n9\n2 7 11 15\n"
            "Output:\n0 1"
        ),
        "starter_code": (
            "# Read target and numbers from stdin\n"
            "target = int(input())\n"
            "nums = list(map(int, input().split()))\n\n"
            "# Your solution here\n"
        ),
        "test_cases": [
            {"input": "9\n2 7 11 15", "expected_output": "0 1"},
            {"input": "6\n3 2 4", "expected_output": "1 2"},
            {"input": "6\n3 3", "expected_output": "0 1"},
        ],
    },
    102: {
        "id": 102,
        "title": "Reverse String",
        "category": "Coding — Python",
        "language": "python",
        "difficulty": "Easy",
        "description": (
            "Read a string from stdin and print it reversed.\n\n"
            "**Example:**\n"
            "Input:\nhello\n"
            "Output:\nolleh"
        ),
        "starter_code": "s = input()\n# Print the reversed string\n",
        "test_cases": [
            {"input": "hello", "expected_output": "olleh"},
            {"input": "MindMesh", "expected_output": "hseMdniM"},
            {"input": "a", "expected_output": "a"},
            {"input": "racecar", "expected_output": "racecar"},
        ],
    },
    103: {
        "id": 103,
        "title": "FizzBuzz",
        "category": "Coding — C",
        "language": "c",
        "difficulty": "Easy",
        "description": (
            "Read an integer N from stdin. For each number from 1 to N:\n"
            "- Print 'FizzBuzz' if divisible by both 3 and 5\n"
            "- Print 'Fizz' if divisible by 3\n"
            "- Print 'Buzz' if divisible by 5\n"
            "- Otherwise print the number\n\n"
            "Each on a new line.\n\n"
            "**Example:**\nInput:\n5\nOutput:\n1\n2\nFizz\n4\nBuzz"
        ),
        "starter_code": (
            '#include <stdio.h>\n\n'
            'int main() {\n'
            '    int n;\n'
            '    scanf("%d", &n);\n'
            '    // Your solution here\n'
            '    return 0;\n'
            '}\n'
        ),
        "test_cases": [
            {"input": "5", "expected_output": "1\n2\nFizz\n4\nBuzz"},
            {"input": "15", "expected_output": "1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz"},
        ],
    },
    104: {
        "id": 104,
        "title": "Hello Java",
        "category": "Coding — Java",
        "language": "java",
        "difficulty": "Easy",
        "description": (
            "Read a name from stdin and print 'Hello, <name>!' to stdout.\n\n"
            "**Example:**\nInput:\nWorld\nOutput:\nHello, World!"
        ),
        "starter_code": (
            'import java.util.Scanner;\n\n'
            'public class Solution {\n'
            '    public static void main(String[] args) {\n'
            '        Scanner sc = new Scanner(System.in);\n'
            '        String name = sc.nextLine();\n'
            '        // Your solution here\n'
            '    }\n'
            '}\n'
        ),
        "test_cases": [
            {"input": "World", "expected_output": "Hello, World!"},
            {"input": "MindMesh", "expected_output": "Hello, MindMesh!"},
        ],
    },
    105: {
        "id": 105,
        "title": "Employee Query",
        "category": "Coding — SQL",
        "language": "sql",
        "difficulty": "Easy",
        "description": (
            "Write a SQL query to find all employees in the Engineering department "
            "with a salary greater than 100000.\n\n"
            "Return columns: name, salary\n"
            "Order by salary descending.\n\n"
            "**Available tables:** employees (id, name, department, salary, hire_date), "
            "departments (id, name, budget), projects (id, title, department, lead_id)"
        ),
        "starter_code": "SELECT name, salary\nFROM employees\nWHERE -- your conditions here\n",
        "test_cases": [
            {
                "input": "",
                "expected_output": "name | salary\n--------------\nCharlie | 110000.0\nEve | 105000.0",
            },
        ],
    },
}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/languages")
async def get_supported_languages():
    """Return list of supported languages."""
    return {"languages": SUPPORTED_LANGUAGES}


@router.get("/questions")
async def get_coding_questions():
    """Return all coding questions (without hidden test cases)."""
    questions = []
    for q in CODING_QUESTIONS.values():
        questions.append({
            "id": q["id"],
            "title": q["title"],
            "category": q["category"],
            "language": q["language"],
            "difficulty": q["difficulty"],
            "description": q["description"],
            "starter_code": q["starter_code"],
        })
    return questions


@router.get("/questions/{question_id}")
async def get_coding_question(question_id: int):
    """Return a single coding question (without hidden test cases)."""
    q = CODING_QUESTIONS.get(question_id)
    if not q:
        return {"error": f"Question {question_id} not found"}
    return {
        "id": q["id"],
        "title": q["title"],
        "category": q["category"],
        "language": q["language"],
        "difficulty": q["difficulty"],
        "description": q["description"],
        "starter_code": q["starter_code"],
    }


@router.post("/execute")
async def execute_user_code(body: ExecuteRequest):
    """
    Execute code in the given language with optional stdin.
    Does NOT grade — just runs and returns output.
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor,
        execute_code,
        body.language,
        body.code,
        body.stdin,
    )
    return result.to_dict()


@router.post("/submit")
async def submit_code(body: SubmitRequest):
    """
    Submit code for grading against hidden test cases.
    Returns pass/fail per test case + overall score.
    """
    question = CODING_QUESTIONS.get(body.question_id)
    if not question:
        return {"error": f"Question {body.question_id} not found", "score": 0}

    test_cases = question["test_cases"]

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor,
        run_test_cases,
        body.language,
        body.code,
        test_cases,
    )
    return result
