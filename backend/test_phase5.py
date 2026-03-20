"""Phase 5 verification — identity verifier, behavior analyzer, scoring multiplier, integration."""
import time
import sys

# ── Test 1: Identity verifier imports & embedding extraction ──
print("Test 1: Identity verifier module")
from app.ai.identity_verifier import store_reference, verify_identity, clear_reference
print("  ✅ identity_verifier imports OK")

# ── Test 2: Behavior analyzer imports & pattern detection ──
print("\nTest 2: Behavior analyzer")
from app.services.behavior_analyzer import record_violation, analyze_behavior, reset_behavior, get_behavior_summary

reset_behavior("test_student")

# Simulate rapid tab switching (2 in 30s)
record_violation("test_student", "tab_switch")
record_violation("test_student", "tab_switch")
result = analyze_behavior("test_student")
assert "rapid_tab_switch" in result["patterns"], f"Expected rapid_tab_switch, got {result['patterns']}"
assert result["severity"] == "high", f"Expected high severity, got {result['severity']}"
assert result["multiplier"] == 2.0, f"Expected 2.0 multiplier, got {result['multiplier']}"
print(f"  ✅ Rapid tab switch: severity={result['severity']}, mult={result['multiplier']}")

# Reset and test frequent looking away
reset_behavior("test_student")
for _ in range(4):
    record_violation("test_student", "looking_away")
result = analyze_behavior("test_student")
assert "frequent_looking_away" in result["patterns"]
assert result["severity"] in ("medium", "high")
print(f"  ✅ Frequent looking away: severity={result['severity']}, patterns={result['patterns']}")

# Reset and test combined phone + looking_away
reset_behavior("test_student")
record_violation("test_student", "object:phone")
record_violation("test_student", "looking_away")
result = analyze_behavior("test_student")
assert "phone_plus_looking_away" in result["patterns"]
assert result["severity"] == "high"
print(f"  ✅ Combined phone+looking_away: severity={result['severity']}")

# Test cheating probability
assert 0 <= result["cheating_probability"] <= 1.0
print(f"  ✅ Cheating probability: {result['cheating_probability']}")

reset_behavior("test_student")

# ── Test 3: Scoring multiplier system ──
print("\nTest 3: Scoring multiplier")
from app.ai.scoring import add_score, reset_score, get_score

reset_score("mult_test")
# Without multiplier (default 1.0)
r1 = add_score("mult_test", 10)
assert r1["frame_score"] == 10
assert r1["multiplier"] == 1.0
assert r1["cumulative_score"] == 10
print(f"  ✅ Default multiplier: score={r1['cumulative_score']}")

# With 2x multiplier
r2 = add_score("mult_test", 10, multiplier=2.0)
assert r2["frame_score"] == 20  # 10 * 2.0
assert r2["base_score"] == 10
assert r2["multiplier"] == 2.0
assert r2["cumulative_score"] == 30  # 10 + 20
print(f"  ✅ 2x multiplier: base=10, adjusted=20, total={r2['cumulative_score']}")

# With 1.5x multiplier
r3 = add_score("mult_test", 10, multiplier=1.5)
assert r3["frame_score"] == 15  # 10 * 1.5
assert r3["cumulative_score"] == 45  # 30 + 15
print(f"  ✅ 1.5x multiplier: base=10, adjusted=15, total={r3['cumulative_score']}")

reset_score("mult_test")

# ── Test 4: devtools_open and identity_mismatch in WEIGHTS ──
print("\nTest 4: New weight entries")
from app.ai.scoring import WEIGHTS
assert "devtools_open" in WEIGHTS, "Missing devtools_open weight"
assert WEIGHTS["devtools_open"] == 15
assert "identity_mismatch" in WEIGHTS, "Missing identity_mismatch weight"
assert WEIGHTS["identity_mismatch"] == 40
print(f"  ✅ devtools_open={WEIGHTS['devtools_open']}, identity_mismatch={WEIGHTS['identity_mismatch']}")

# ── Test 5: Session reset clears behavior + identity ──
print("\nTest 5: Session reset integration")
from app.services.proctor_service import reset_session
record_violation("session_test", "tab_switch")
record_violation("session_test", "tab_switch")
b1 = analyze_behavior("session_test")
assert len(b1["patterns"]) > 0

reset_session("session_test")
b2 = analyze_behavior("session_test")
assert len(b2["patterns"]) == 0
print("  ✅ reset_session clears behavior state")

# ── Test 6: Behavior summary ──
print("\nTest 6: Behavior summary")
reset_behavior("sum_test")
record_violation("sum_test", "tab_switch")
record_violation("sum_test", "tab_switch")
record_violation("sum_test", "looking_away")
summary = get_behavior_summary("sum_test")
assert summary["total_violations"] == 3
assert summary["tab_switch_count"] == 2
assert summary["looking_away_count"] == 1
assert "severity" in summary
assert "cheating_probability" in summary
print(f"  ✅ Summary: total={summary['total_violations']}, tab_switch={summary['tab_switch_count']}, severity={summary['severity']}")
reset_behavior("sum_test")

# ── Test 7: ProctorService has store_identity_reference ──
print("\nTest 7: ProctorService identity function")
from app.services.proctor_service import store_identity_reference
# Can't test actual face without a real image, but function should exist
assert callable(store_identity_reference)
print("  ✅ store_identity_reference callable")

# ── Test 8: Low severity returns 1.0 multiplier ──
print("\nTest 8: Low severity = 1.0x")
reset_behavior("low_test")
record_violation("low_test", "right_click")
b = analyze_behavior("low_test")
assert b["severity"] == "low"
assert b["multiplier"] == 1.0
print(f"  ✅ Low severity: mult={b['multiplier']}")
reset_behavior("low_test")

# ── Test 9: Identity mismatch pattern always high ──
print("\nTest 9: Identity mismatch always high")
reset_behavior("id_test")
record_violation("id_test", "identity_mismatch")
b = analyze_behavior("id_test")
assert "identity_mismatch" in b["patterns"]
assert b["severity"] == "high"
assert b["multiplier"] == 2.0
print(f"  ✅ Identity mismatch: severity=high, prob={b['cheating_probability']}")
reset_behavior("id_test")

print("\n🎯 ALL PHASE 5 TESTS PASSED! (9/9)")
