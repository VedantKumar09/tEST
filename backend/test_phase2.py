"""Phase 2 verification — scoring decay, timeline, risk levels."""
import time

from app.ai.scoring import (
    add_score, get_score, apply_decay, get_timeline, reset_score,
    compute_frame_score, compute_event_score, WEIGHTS,
)
from app.ai.proctor_config import (
    SCORE_TAB_SWITCH, SCORE_LOOKING_AWAY, SCORE_OBJECT_DETECTED,
    SCORE_MULTIPLE_FACES, SCORE_DECAY_RATE, SCORE_DECAY_INTERVAL_S,
    SCORE_DECAY_GRACE_PERIOD_S, MAX_RISK_SCORE, MIN_RISK_SCORE,
)

SID = "test_student_phase2"

# ── Test 1: Scoring weights match config ──
print("Test 1: Scoring weights")
assert WEIGHTS["tab_switch"] == SCORE_TAB_SWITCH == 10, f"tab_switch should be 10, got {WEIGHTS['tab_switch']}"
assert WEIGHTS["looking_away"] == SCORE_LOOKING_AWAY == 5, f"looking_away should be 5"
assert WEIGHTS["object"] == SCORE_OBJECT_DETECTED == 25, f"object should be 25"
assert WEIGHTS["multiple_faces"] == SCORE_MULTIPLE_FACES == 50, f"multiple_faces should be 50"
print(f"  ✅ tab_switch={WEIGHTS['tab_switch']}, looking_away={WEIGHTS['looking_away']}, "
      f"object={WEIGHTS['object']}, multiple_faces={WEIGHTS['multiple_faces']}")

# ── Test 2: Add score + risk levels ──
print("\nTest 2: Score addition + risk levels")
reset_score(SID)
r = add_score(SID, 10)
assert r["cumulative_score"] == 10
assert r["risk_level"] == "Low", f"10 should be Low, got {r['risk_level']}"
print(f"  ✅ score=10 → {r['risk_level']}")

r = add_score(SID, 15)
assert r["cumulative_score"] == 25
assert r["risk_level"] == "Medium", f"25 should be Medium, got {r['risk_level']}"
print(f"  ✅ score=25 → {r['risk_level']}")

r = add_score(SID, 30)
assert r["cumulative_score"] == 55
assert r["risk_level"] == "High", f"55 should be High, got {r['risk_level']}"
print(f"  ✅ score=55 → {r['risk_level']}")

r = add_score(SID, 30)
assert r["cumulative_score"] == 85
assert r["risk_level"] == "Critical", f"85 should be Critical, got {r['risk_level']}"
print(f"  ✅ score=85 → {r['risk_level']}")

# ── Test 3: MAX_RISK_SCORE cap ──
print("\nTest 3: Score cap")
reset_score(SID)
r = add_score(SID, 999)
assert r["cumulative_score"] == MAX_RISK_SCORE, f"Should cap at {MAX_RISK_SCORE}"
print(f"  ✅ Adding 999 → capped at {r['cumulative_score']}")

# ── Test 4: Timeline tracking ──
print("\nTest 4: Timeline tracking")
reset_score(SID)
add_score(SID, 10)
time.sleep(0.01)
add_score(SID, 5)
tl = get_timeline(SID)
assert len(tl) == 2, f"Expected 2 timeline entries, got {len(tl)}"
assert tl[0]["score"] == 10
assert tl[1]["score"] == 15
print(f"  ✅ Timeline has {len(tl)} entries: scores={[e['score'] for e in tl]}")

# ── Test 5: Decay — no decay within grace period ──
print("\nTest 5: Decay grace period")
reset_score(SID)
add_score(SID, 20)
r = apply_decay(SID)
assert r["cumulative_score"] == 20, "Should NOT decay during grace period"
print(f"  ✅ No decay during grace period (score stays {r['cumulative_score']})")

# ── Test 6: Decay — simulate time passing ──
print("\nTest 6: Decay after time passes")
reset_score(SID)

# Manually set up state to simulate old violation + old decay
from app.ai import scoring
with scoring._lock:
    scoring._scores[SID] = 30
    scoring._last_violation_time[SID] = time.time() - SCORE_DECAY_GRACE_PERIOD_S - 1  # grace expired
    scoring._last_decay_time[SID] = time.time() - SCORE_DECAY_INTERVAL_S - 1  # interval expired
    scoring._timelines[SID] = [(int(time.time() * 1000), 30)]

r = apply_decay(SID)
expected = 30 - SCORE_DECAY_RATE
assert r["cumulative_score"] == expected, f"Expected {expected} after decay, got {r['cumulative_score']}"
assert r.get("decayed") is True
print(f"  ✅ Decayed from 30 → {r['cumulative_score']} (rate={SCORE_DECAY_RATE})")

# ── Test 7: Score never goes below MIN ──
print("\nTest 7: Floor at MIN_RISK_SCORE")
with scoring._lock:
    scoring._scores[SID] = 1
    scoring._last_violation_time[SID] = time.time() - 999
    scoring._last_decay_time[SID] = time.time() - 999

r = apply_decay(SID)
assert r["cumulative_score"] == MIN_RISK_SCORE, f"Should floor at {MIN_RISK_SCORE}, got {r['cumulative_score']}"
print(f"  ✅ Decayed from 1 → floored at {r['cumulative_score']}")

# ── Test 8: Reset clears everything ──
print("\nTest 8: Session reset")
reset_score(SID)
assert get_score(SID)["cumulative_score"] == 0
assert get_timeline(SID) == []
print("  ✅ Score, timeline, decay state all cleared")

# ── Test 9: compute_frame_score ──
print("\nTest 9: compute_frame_score")
face = {"no_face": True, "multiple_faces": False, "head_pose": {"looking_away": True}, "eye_gaze": {"looking_offscreen": False}}
obj = {"objects_detected": [{"class": "cell phone", "confidence": 0.9}]}
fs = compute_frame_score(face, obj)
expected_fs = WEIGHTS["no_face"] + WEIGHTS["looking_away"] + WEIGHTS["object"]
assert fs == expected_fs, f"Expected {expected_fs}, got {fs}"
print(f"  ✅ no_face + looking_away + object = {fs} points")

# ── Test 10: compute_event_score ──
print("\nTest 10: compute_event_score")
assert compute_event_score("tab_switch") == 10
assert compute_event_score("unknown_event") == 0
print(f"  ✅ tab_switch={compute_event_score('tab_switch')}, unknown=0")

# ── Test 11: Imports in proctor_service ──
print("\nTest 11: proctor_service imports")
from app.services.proctor_service import reset_session, analyze_frame, record_browser_event
print("  ✅ proctor_service imported successfully (reset_session, analyze_frame, record_browser_event)")

# Clean up
reset_score(SID)

print("\n🎯 ALL PHASE 2 TESTS PASSED!")
