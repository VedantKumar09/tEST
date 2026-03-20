"""Quick Phase 1 verification script."""
from app.services.code_executor import execute_code, run_test_cases, SUPPORTED_LANGUAGES

print(f"✅ Supported languages: {SUPPORTED_LANGUAGES}")

# Test 1: Python execution
r = execute_code("python", 'print(42 + 58)')
print(f"✅ Python exec: stdout={r.stdout.strip()!r}, exit={r.exit_code}, time={r.execution_time_ms}ms")
assert r.stdout.strip() == "100", f"Expected '100', got {r.stdout.strip()!r}"

# Test 2: Python with stdin
r = execute_code("python", "n = int(input())\nprint(n * 2)", "21")
print(f"✅ Python stdin: stdout={r.stdout.strip()!r}")
assert r.stdout.strip() == "42"

# Test 3: SQL execution
r = execute_code("sql", 'SELECT name, salary FROM employees WHERE department="Engineering" AND salary > 100000 ORDER BY salary DESC')
print(f"✅ SQL exec: stdout={r.stdout[:80]!r}")
assert "Charlie" in r.stdout

# Test 4: Test case runner
results = run_test_cases("python", "s = input()\nprint(s[::-1])", [
    {"input": "hello", "expected_output": "olleh"},
    {"input": "abc", "expected_output": "cba"},
])
print(f"✅ Test cases: {results['passed']}/{results['total']} passed, score={results['score']}%")
assert results["passed"] == 2

# Test 5: Unsupported language
r = execute_code("rust", "fn main() {}")
print(f"✅ Unsupported lang: error={r.error!r}")
assert r.error is not None

# Test 6: Timeout (infinite loop)
r = execute_code("python", "while True: pass")
print(f"✅ Timeout test: timed_out={r.timed_out}, exit={r.exit_code}, time={r.execution_time_ms}ms")
assert r.timed_out or r.exit_code != 0

# Test 7: Import router (without loading AI models)
from app.routes.code import router
print(f"✅ Code router imported: {len(router.routes)} routes registered")

# Test 8: Import exam router  
from app.routes.exam import router as exam_router, ALL_QUESTIONS
print(f"✅ Exam router imported: {len(ALL_QUESTIONS)} total questions (MCQ + coding)")

print("\n🎯 ALL PHASE 1 TESTS PASSED!")
