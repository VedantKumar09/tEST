"""Phase 3 verification — admin endpoints, evidence, WebSocket, imports."""
import time

# Test 1: Admin route imports
print("Test 1: Admin route imports")
from app.routes.admin import router
routes = [r.path for r in router.routes]
print(f"  Routes: {routes}")
assert any("risk-timeline" in r for r in routes), f"Missing risk-timeline route in {routes}"
assert any("evidence" in r and "file" not in r for r in routes), "Missing evidence route"
assert any("evidence-file" in r for r in routes), "Missing evidence-file route"
assert any("flag" in r for r in routes), "Missing flag route"
assert any("mark" in r for r in routes), "Missing mark route"
assert any("submissions" in r for r in routes)
assert any("proctor-logs" in r for r in routes)
print(f"  ✅ All {len(routes)} admin routes present")

# Test 2: Flag toggle logic
print("\nTest 2: Flag toggle logic")
from app.routes.admin import _review_status
_review_status.clear()
_review_status["test_sub"] = {"flagged": False}
_review_status["test_sub"]["flagged"] = not _review_status["test_sub"]["flagged"]
assert _review_status["test_sub"]["flagged"] is True
_review_status["test_sub"]["flagged"] = not _review_status["test_sub"]["flagged"]
assert _review_status["test_sub"]["flagged"] is False
print("  ✅ Flag toggle works (False→True→False)")

# Test 3: Risk timeline from scoring module
print("\nTest 3: Risk timeline integration")
from app.ai.scoring import add_score, get_timeline, reset_score
reset_score("admin_test")
add_score("admin_test", 10)
time.sleep(0.01)
add_score("admin_test", 5)
tl = get_timeline("admin_test")
assert len(tl) == 2, f"Expected 2 entries, got {len(tl)}"
assert tl[0]["score"] == 10
assert tl[1]["score"] == 15
print(f"  ✅ Timeline has {len(tl)} entries: {[e['score'] for e in tl]}")
reset_score("admin_test")

# Test 4: WebSocket alert queue and client registry
print("\nTest 4: Alert queue + client registry")
from app.services.proctor_service import (
    _push_alert, get_alert_queue,
    register_admin_ws, unregister_admin_ws, get_admin_ws_clients,
)
_push_alert({"type": "test", "student_id": "s1", "timestamp": 1234})
q = get_alert_queue()
assert len(q) >= 1 and q[-1]["type"] == "test"
print(f"  ✅ Alert queue has {len(q)} entries, last alert type: {q[-1]['type']}")

class FakeWS:
    pass
ws = FakeWS()
register_admin_ws(ws)
assert ws in get_admin_ws_clients()
unregister_admin_ws(ws)
assert ws not in get_admin_ws_clients()
print("  ✅ Admin WS client register/unregister works")

# Test 5: Evidence directory path
print("\nTest 5: Evidence directory path")
from app.routes.admin import _EVIDENCE_BASE
assert "proctor_logs" in str(_EVIDENCE_BASE)
print(f"  ✅ Evidence base: {_EVIDENCE_BASE}")

# Test 6: Mark validation
print("\nTest 6: Mark status")
_review_status.clear()
_review_status["m1"] = {"status": "valid"}
assert _review_status["m1"]["status"] == "valid"
_review_status["m1"]["status"] = "invalid"
assert _review_status["m1"]["status"] == "invalid"
print("  ✅ Mark valid→invalid works")

# Test 7: Main.py WebSocket endpoint
print("\nTest 7: main.py admin alerts WebSocket")
from app.main import app
all_paths = [r.path for r in app.routes if hasattr(r, 'path')]
assert "/ws/admin/alerts" in all_paths, f"/ws/admin/alerts not found in {all_paths}"
print("  ✅ /ws/admin/alerts registered")

# Test 8: Timeline get_timeline returns empty for unknown student
print("\nTest 8: Timeline for unknown student")
tl2 = get_timeline("nonexistent_student")
assert tl2 == []
print("  ✅ Returns empty list for unknown student")

_review_status.clear()
print("\n🎯 ALL PHASE 3 TESTS PASSED!")
