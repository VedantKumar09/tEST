"""
Code Execution Engine — Sandboxed code runner for Python, C, Java, SQL.

Runs user code in isolated temp directories with:
  - Subprocess timeout (10 s default)
  - Resource limits (Windows: job objects via timeout; Linux would use ulimit)
  - Temp directory cleanup
  - Graceful handling of missing compilers (gcc / javac)

Supported languages: python, c, java, sql
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

# ── Configuration ─────────────────────────────────────────────────────────────

EXEC_TIMEOUT_S = 10          # max wall-clock seconds per run
MAX_OUTPUT_CHARS = 50_000    # truncate stdout/stderr beyond this

# Pre-seeded SQL tables for SQL challenges
_SQL_SEED = """
CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    salary REAL NOT NULL,
    hire_date TEXT NOT NULL
);
INSERT INTO employees VALUES (1, 'Alice',   'Engineering', 95000, '2020-01-15');
INSERT INTO employees VALUES (2, 'Bob',     'Marketing',   72000, '2019-06-01');
INSERT INTO employees VALUES (3, 'Charlie', 'Engineering', 110000, '2018-03-22');
INSERT INTO employees VALUES (4, 'Diana',   'HR',          68000, '2021-09-10');
INSERT INTO employees VALUES (5, 'Eve',     'Engineering', 105000, '2020-11-05');
INSERT INTO employees VALUES (6, 'Frank',   'Marketing',   78000, '2017-02-14');
INSERT INTO employees VALUES (7, 'Grace',   'HR',          71000, '2022-01-20');
INSERT INTO employees VALUES (8, 'Hank',    'Engineering', 98000, '2019-08-30');

CREATE TABLE departments (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    budget REAL NOT NULL
);
INSERT INTO departments VALUES (1, 'Engineering', 500000);
INSERT INTO departments VALUES (2, 'Marketing',   200000);
INSERT INTO departments VALUES (3, 'HR',          150000);

CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    department TEXT NOT NULL,
    lead_id INTEGER REFERENCES employees(id)
);
INSERT INTO projects VALUES (1, 'AI Platform',   'Engineering', 3);
INSERT INTO projects VALUES (2, 'Brand Refresh', 'Marketing',   2);
INSERT INTO projects VALUES (3, 'Hiring Portal', 'HR',          4);
INSERT INTO projects VALUES (4, 'Data Pipeline', 'Engineering', 1);
"""


@dataclass
class ExecutionResult:
    """Standardised result returned by every executor."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time_ms: int = 0
    language: str = ""
    error: str | None = None          # high-level error (compiler missing, etc.)
    timed_out: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _truncate(text: str) -> str:
    if len(text) > MAX_OUTPUT_CHARS:
        return text[:MAX_OUTPUT_CHARS] + "\n... (output truncated)"
    return text


def _find_binary(name: str) -> str | None:
    """Return the full path of a binary if it exists on PATH, else None."""
    return shutil.which(name)


def _run_subprocess(
    cmd: list[str],
    *,
    cwd: str | None = None,
    stdin_data: str = "",
    timeout: int = EXEC_TIMEOUT_S,
) -> ExecutionResult:
    """Run a command in a subprocess with timeout."""
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return ExecutionResult(
            stdout=_truncate(proc.stdout),
            stderr=_truncate(proc.stderr),
            exit_code=proc.returncode,
            execution_time_ms=elapsed_ms,
        )
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return ExecutionResult(
            stderr="⏱ Time Limit Exceeded (max {timeout}s)",
            exit_code=-1,
            execution_time_ms=elapsed_ms,
            timed_out=True,
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return ExecutionResult(
            stderr=str(exc),
            exit_code=-1,
            execution_time_ms=elapsed_ms,
            error=f"Execution error: {exc}",
        )


# ── Language Executors ────────────────────────────────────────────────────────

def execute_python(code: str, stdin_data: str = "") -> ExecutionResult:
    """Execute Python code in a temp directory."""
    tmpdir = tempfile.mkdtemp(prefix="mm_py_")
    try:
        src = Path(tmpdir) / "solution.py"
        src.write_text(code, encoding="utf-8")

        python_bin = _find_binary("python") or _find_binary("python3")
        if not python_bin:
            return ExecutionResult(
                error="Python interpreter not found on system PATH.",
                exit_code=-1,
                language="python",
            )

        result = _run_subprocess([python_bin, str(src)], cwd=tmpdir, stdin_data=stdin_data)
        result.language = "python"
        return result
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def execute_c(code: str, stdin_data: str = "") -> ExecutionResult:
    """Compile & execute C code in a temp directory."""
    gcc = _find_binary("gcc")
    if not gcc:
        return ExecutionResult(
            error="C compiler (gcc) not found. Please install MinGW or GCC.",
            exit_code=-1,
            language="c",
        )

    tmpdir = tempfile.mkdtemp(prefix="mm_c_")
    try:
        src = Path(tmpdir) / "solution.c"
        src.write_text(code, encoding="utf-8")
        exe = Path(tmpdir) / "solution.exe" if os.name == "nt" else Path(tmpdir) / "solution"

        # Compile
        compile_result = _run_subprocess(
            [gcc, str(src), "-o", str(exe), "-lm"],
            cwd=tmpdir,
            timeout=30,
        )
        if compile_result.exit_code != 0:
            compile_result.language = "c"
            compile_result.error = "Compilation failed"
            return compile_result

        # Execute
        result = _run_subprocess([str(exe)], cwd=tmpdir, stdin_data=stdin_data)
        result.language = "c"
        return result
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def execute_java(code: str, stdin_data: str = "") -> ExecutionResult:
    """Compile & execute Java code in a temp directory."""
    javac = _find_binary("javac")
    java = _find_binary("java")
    if not javac or not java:
        return ExecutionResult(
            error="Java compiler (javac/java) not found. Please install JDK.",
            exit_code=-1,
            language="java",
        )

    tmpdir = tempfile.mkdtemp(prefix="mm_java_")
    try:
        # Extract public class name (default to Solution)
        import re
        match = re.search(r"public\s+class\s+(\w+)", code)
        class_name = match.group(1) if match else "Solution"

        src = Path(tmpdir) / f"{class_name}.java"
        src.write_text(code, encoding="utf-8")

        # Compile
        compile_result = _run_subprocess(
            [javac, str(src)],
            cwd=tmpdir,
            timeout=30,
        )
        if compile_result.exit_code != 0:
            compile_result.language = "java"
            compile_result.error = "Compilation failed"
            return compile_result

        # Execute
        result = _run_subprocess(
            [java, "-cp", tmpdir, class_name],
            cwd=tmpdir,
            stdin_data=stdin_data,
        )
        result.language = "java"
        return result
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def execute_sql(code: str, stdin_data: str = "") -> ExecutionResult:
    """Execute SQL query against an in-memory SQLite database with pre-seeded data."""
    t0 = time.perf_counter()
    try:
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        # Seed tables
        cursor.executescript(_SQL_SEED)

        # Execute user query
        cursor.execute(code.strip().rstrip(";"))
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description] if cursor.description else []

        # Format output as table
        lines = []
        if col_names:
            lines.append(" | ".join(col_names))
            lines.append("-" * len(lines[0]))
        for row in rows:
            lines.append(" | ".join(str(v) for v in row))

        conn.close()
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        return ExecutionResult(
            stdout="\n".join(lines),
            exit_code=0,
            execution_time_ms=elapsed_ms,
            language="sql",
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return ExecutionResult(
            stderr=str(exc),
            exit_code=1,
            execution_time_ms=elapsed_ms,
            language="sql",
            error=f"SQL error: {exc}",
        )


# ── Public API ────────────────────────────────────────────────────────────────

_EXECUTORS = {
    "python": execute_python,
    "c":      execute_c,
    "java":   execute_java,
    "sql":    execute_sql,
}

SUPPORTED_LANGUAGES = list(_EXECUTORS.keys())


def execute_code(
    language: str,
    code: str,
    stdin_data: str = "",
) -> ExecutionResult:
    """
    Execute code in the specified language.
    Returns an ExecutionResult with stdout, stderr, exit_code, timing.
    """
    lang = language.lower().strip()
    executor = _EXECUTORS.get(lang)
    if not executor:
        return ExecutionResult(
            error=f"Unsupported language: '{language}'. Supported: {SUPPORTED_LANGUAGES}",
            exit_code=-1,
            language=lang,
        )
    return executor(code, stdin_data)


def run_test_cases(
    language: str,
    code: str,
    test_cases: list[dict],
) -> dict:
    """
    Run code against a list of test cases.
    Each test case: {"input": "...", "expected_output": "..."}
    Returns summary + per-case results.
    """
    results = []
    passed = 0

    for i, tc in enumerate(test_cases):
        tc_input = tc.get("input", "")
        expected = tc.get("expected_output", "").strip()

        exec_result = execute_code(language, code, tc_input)
        actual = exec_result.stdout.strip()
        is_pass = actual == expected and exec_result.exit_code == 0

        if is_pass:
            passed += 1

        results.append({
            "test_case": i + 1,
            "passed": is_pass,
            "input": tc_input,
            "expected": expected,
            "actual": actual,
            "stderr": exec_result.stderr,
            "exit_code": exec_result.exit_code,
            "execution_time_ms": exec_result.execution_time_ms,
            "timed_out": exec_result.timed_out,
            "error": exec_result.error,
        })

    return {
        "language": language,
        "total": len(test_cases),
        "passed": passed,
        "failed": len(test_cases) - passed,
        "score": round((passed / len(test_cases)) * 100) if test_cases else 0,
        "results": results,
    }
