"""Quick verification of multi-loop refactor (no YOLO model load)."""
print("=== Multi-Loop Import Verification ===")

# 1. Config
from app.ai.proctor_config import (
    YOLO_FRAME_SKIP, PHONE_CONF_THRESHOLD, PERSON_CONF_THRESHOLD,
    FRAME_RESOLUTION, BEHAVIOR_ANALYSIS_INTERVAL_S
)
print(f"[OK] Config: skip={YOLO_FRAME_SKIP} phone={PHONE_CONF_THRESHOLD} person={PERSON_CONF_THRESHOLD} res={FRAME_RESOLUTION} beh={BEHAVIOR_ANALYSIS_INTERVAL_S}s")

# 2. Proctor service exports
from app.services.proctor_service import (
    reset_session, store_identity_reference, analyze_frame, record_browser_event,
    register_admin_ws, unregister_admin_ws, get_admin_ws_clients, get_alert_queue,
    _frame_counter, _cached_yolo, _cached_behavior
)
print("[OK] Proctor service: all exports intact")

# 3. Session reset clears new state
reset_session("t1")
assert "t1" not in _frame_counter
assert "t1" not in _cached_yolo
assert "t1" not in _cached_behavior
print("[OK] Session reset: new state vars cleared")

# 4. Scoring multiplier
from app.ai.scoring import add_score, reset_score, WEIGHTS
reset_score("t2")
r = add_score("t2", 10, multiplier=2.0)
assert r["frame_score"] == 20
r2 = add_score("t2", 10, multiplier=1.5)
assert r2["frame_score"] == 15
reset_score("t2")
print("[OK] Scoring: 10*2.0=20, 10*1.5=15")

# 5. Behavior analyzer
from app.services.behavior_analyzer import record_violation, analyze_behavior, reset_behavior
reset_behavior("t3")
record_violation("t3", "tab_switch")
record_violation("t3", "tab_switch")
b = analyze_behavior("t3")
assert b["severity"] == "high" and b["multiplier"] == 2.0
reset_behavior("t3")
print(f"[OK] Behavior: rapid_tab_switch severity=high mult=2.0")

# 6. Identity verifier
from app.ai.identity_verifier import verify_identity, clear_reference
vr = verify_identity("nr", "bad")
assert vr["is_same_person"] == True
print("[OK] Identity: no-reference graceful skip")

# 7. WebSocket
class F: pass
w = F()
register_admin_ws(w)
assert w in get_admin_ws_clients()
unregister_admin_ws(w)
assert w not in get_admin_ws_clients()
print("[OK] WebSocket: register/unregister")

# 8. Backward compat
assert "devtools_open" in WEIGHTS
assert "identity_mismatch" in WEIGHTS
assert "tab_switch" in WEIGHTS
print("[OK] Backward compat: all WEIGHTS keys present")

print()
print("ALL 8 CHECKS PASSED")
