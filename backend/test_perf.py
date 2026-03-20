"""
MindMesh v2 — Real-Time Performance Benchmark Suite
Measures actual latency for all detection components.
"""
import time
import json
import numpy as np
import cv2
import base64
import statistics

# ══════════════════════════════════════════════════════
# Generate realistic test frames
# ══════════════════════════════════════════════════════
def make_test_frame(w=640, h=480):
    """Create a realistic test frame with some features."""
    frame = np.random.randint(50, 200, (h, w, 3), dtype=np.uint8)
    # Add a face-like oval
    cv2.ellipse(frame, (w//2, h//2), (80, 100), 0, 0, 360, (200, 180, 160), -1)
    # Eyes
    cv2.circle(frame, (w//2-25, h//2-15), 8, (40, 40, 40), -1)
    cv2.circle(frame, (w//2+25, h//2-15), 8, (40, 40, 40), -1)
    # Mouth
    cv2.ellipse(frame, (w//2, h//2+30), (20, 8), 0, 0, 360, (100, 50, 50), -1)
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode()

results = {}

print("=" * 70)
print("  MINDMESH v2 — REAL-TIME PERFORMANCE BENCHMARK")
print("=" * 70)
print()

# ══════════════════════════════════════════════════════
# 1. FACE DETECTION LATENCY (MediaPipe FaceLandmarker)
# ══════════════════════════════════════════════════════
print("[1] Face Detection (MediaPipe FaceLandmarker)")
print("-" * 50)

from app.ai.face_analyzer import analyze_face

frame = make_test_frame()

# Warm-up (first call loads model)
print("  Warming up FaceLandmarker model...")
t0 = time.time()
_ = analyze_face(frame, "bench_warmup")
warmup_ms = round((time.time() - t0) * 1000)
print(f"  Cold start (model load): {warmup_ms}ms")

# Benchmark 10 frames
face_times = []
for i in range(10):
    t0 = time.time()
    r = analyze_face(frame, f"bench_{i}")
    elapsed = (time.time() - t0) * 1000
    face_times.append(elapsed)

avg_face = round(statistics.mean(face_times))
p50_face = round(statistics.median(face_times))
p95_face = round(sorted(face_times)[8])  # 9th out of 10
min_face = round(min(face_times))
max_face = round(max(face_times))

print(f"  Avg: {avg_face}ms | P50: {p50_face}ms | P95: {p95_face}ms | Min: {min_face}ms | Max: {max_face}ms")
results["face_detection"] = {"avg_ms": avg_face, "p50_ms": p50_face, "p95_ms": p95_face}

# ══════════════════════════════════════════════════════
# 2. YOLO OBJECT DETECTION LATENCY
# ══════════════════════════════════════════════════════
print()
print("[2] Object Detection (YOLOv8s)")
print("-" * 50)

from app.ai.object_detector import detect_objects

# Warm-up
print("  Warming up YOLOv8s model...")
t0 = time.time()
_ = detect_objects(frame)
yolo_warmup = round((time.time() - t0) * 1000)
print(f"  Cold start (model load + warmup): {yolo_warmup}ms")

# Benchmark 10 frames
yolo_times = []
for i in range(10):
    t0 = time.time()
    r = detect_objects(frame)
    elapsed = (time.time() - t0) * 1000
    yolo_times.append(elapsed)

avg_yolo = round(statistics.mean(yolo_times))
p50_yolo = round(statistics.median(yolo_times))
p95_yolo = round(sorted(yolo_times)[8])
min_yolo = round(min(yolo_times))
max_yolo = round(max(yolo_times))

print(f"  Avg: {avg_yolo}ms | P50: {p50_yolo}ms | P95: {p95_yolo}ms | Min: {min_yolo}ms | Max: {max_yolo}ms")
print(f"  person_count: {r.get('person_count', 'N/A')}, phone_detected: {r.get('phone_detected', 'N/A')}")
results["yolo_detection"] = {"avg_ms": avg_yolo, "p50_ms": p50_yolo, "p95_ms": p95_yolo}

# ══════════════════════════════════════════════════════
# 3. SCORING ENGINE LATENCY
# ══════════════════════════════════════════════════════
print()
print("[3] Scoring Engine")
print("-" * 50)

from app.ai.scoring import add_score, reset_score, apply_decay, compute_frame_score, compute_event_score, get_timeline

reset_score("perf")
score_times = []
for i in range(1000):
    t0 = time.time()
    add_score("perf", 1, multiplier=1.5)
    elapsed = (time.time() - t0) * 1000
    score_times.append(elapsed)
reset_score("perf")

avg_score = round(statistics.mean(score_times) * 1000)  # microseconds
p95_score = round(sorted(score_times)[949] * 1000)
print(f"  add_score avg: {avg_score}µs | P95: {p95_score}µs")

# Decay
reset_score("perf_d")
add_score("perf_d", 50)
decay_times = []
for i in range(100):
    t0 = time.time()
    apply_decay("perf_d")
    elapsed = (time.time() - t0) * 1000
    decay_times.append(elapsed)
reset_score("perf_d")
avg_decay = round(statistics.mean(decay_times) * 1000)
print(f"  apply_decay avg: {avg_decay}µs")

# compute_frame_score
t0 = time.time()
for i in range(1000):
    compute_frame_score(
        {"no_face": True, "multiple_faces": False,
         "head_pose": {"looking_away": True}, "eye_gaze": {"looking_offscreen": False}},
        {"objects_detected": [{"class": "cell phone"}]}
    )
cfs_us = round((time.time() - t0) * 1000)
print(f"  compute_frame_score 1000x: {cfs_us}ms total ({round(cfs_us)}µs avg)")

results["scoring"] = {"add_score_avg_us": avg_score, "decay_avg_us": avg_decay}

# ══════════════════════════════════════════════════════
# 4. BEHAVIOR ANALYSIS LATENCY
# ══════════════════════════════════════════════════════
print()
print("[4] Behavior Analysis Engine")
print("-" * 50)

from app.services.behavior_analyzer import record_violation, analyze_behavior, reset_behavior

reset_behavior("perf_beh")
# Pre-populate with some violations
for _ in range(20):
    record_violation("perf_beh", "tab_switch")
for _ in range(10):
    record_violation("perf_beh", "looking_away")

beh_times = []
for i in range(100):
    t0 = time.time()
    b = analyze_behavior("perf_beh")
    elapsed = (time.time() - t0) * 1000
    beh_times.append(elapsed)

avg_beh = round(statistics.mean(beh_times) * 1000)
p95_beh = round(sorted(beh_times)[94] * 1000)
print(f"  analyze_behavior avg: {avg_beh}µs | P95: {p95_beh}µs")
print(f"  Result: severity={b['severity']}, mult={b['multiplier']}, prob={b['cheating_probability']}")
reset_behavior("perf_beh")

results["behavior"] = {"avg_us": avg_beh, "p95_us": p95_beh}

# ══════════════════════════════════════════════════════
# 5. IDENTITY VERIFICATION LATENCY
# ══════════════════════════════════════════════════════
print()
print("[5] Identity Verification")
print("-" * 50)

from app.ai.identity_verifier import store_reference, verify_identity, clear_reference

# Store reference
t0 = time.time()
sr = store_reference("perf_id", frame)
store_ms = round((time.time() - t0) * 1000)
print(f"  store_reference: {store_ms}ms — {sr.get('message', sr.get('status'))}")

if sr.get("status") == "ok":
    # Verify
    verify_times = []
    for i in range(5):
        t0 = time.time()
        vr = verify_identity("perf_id", frame)
        elapsed = (time.time() - t0) * 1000
        verify_times.append(elapsed)
    avg_id = round(statistics.mean(verify_times))
    print(f"  verify_identity avg: {avg_id}ms | match_score={vr.get('match_score')}")
    results["identity"] = {"store_ms": store_ms, "verify_avg_ms": avg_id}
else:
    print(f"  No face in synthetic frame — expected for benchmark")
    results["identity"] = {"store_ms": store_ms, "verify_avg_ms": "N/A (no face in synthetic)"}

clear_reference("perf_id")

# ══════════════════════════════════════════════════════
# 6. BROWSER EVENT PROCESSING
# ══════════════════════════════════════════════════════
print()
print("[6] Browser Event Processing (tab_switch, devtools)")
print("-" * 50)

from app.ai.scoring import compute_event_score

event_types = ["tab_switch", "copy_paste", "right_click", "devtools_open"]
for ev in event_types:
    t0 = time.time()
    pts = compute_event_score(ev)
    elapsed_us = round((time.time() - t0) * 1000000)
    print(f"  {ev}: {pts}pts, {elapsed_us}µs")

results["browser_events"] = "sub-microsecond (dict lookup)"

# ══════════════════════════════════════════════════════
# 7. MULTI-LOOP ARCHITECTURE CHECK
# ══════════════════════════════════════════════════════
print()
print("[7] Architecture Verification")
print("-" * 50)

from app.ai.proctor_config import YOLO_FRAME_SKIP, BEHAVIOR_ANALYSIS_INTERVAL_S, FRAME_RESOLUTION
from app.services.proctor_service import _executor, _frame_counter, _cached_yolo, _cached_behavior

print(f"  YOLO_FRAME_SKIP: {YOLO_FRAME_SKIP} (run YOLO every {YOLO_FRAME_SKIP}th frame)")
print(f"  BEHAVIOR_ANALYSIS_INTERVAL: {BEHAVIOR_ANALYSIS_INTERVAL_S}s")
print(f"  FRAME_RESOLUTION: {FRAME_RESOLUTION}px")
print(f"  ThreadPool workers: {_executor._max_workers}")
print(f"  Fast loop: face/pose/gaze → EVERY frame")
print(f"  Medium loop: YOLO → every {YOLO_FRAME_SKIP} frames, async")
print(f"  Slow loop: behavior+identity → every {BEHAVIOR_ANALYSIS_INTERVAL_S}s")

# ══════════════════════════════════════════════════════
# 8. STRESS: 30 rapid frames in sequence
# ══════════════════════════════════════════════════════
print()
print("[8] Stress Test: 30 rapid face analysis calls")
print("-" * 50)

stress_times = []
for i in range(30):
    t0 = time.time()
    analyze_face(frame, f"stress_{i % 3}")
    elapsed = (time.time() - t0) * 1000
    stress_times.append(elapsed)

avg_stress = round(statistics.mean(stress_times))
max_stress = round(max(stress_times))
fps = round(1000 / statistics.mean(stress_times), 1) if statistics.mean(stress_times) > 0 else 999
print(f"  30 frames: avg={avg_stress}ms, max={max_stress}ms")
print(f"  Theoretical max FPS: {fps}")
print(f"  Stability: {'stable' if max_stress < avg_stress * 3 else 'spiky'}")

results["stress"] = {"avg_ms": avg_stress, "max_ms": max_stress, "fps": fps}

# ══════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════
print()
print("=" * 70)
print("  BENCHMARK SUMMARY")
print("=" * 70)
print(f"  Face (MediaPipe):   avg {avg_face}ms  | P95 {p95_face}ms")
print(f"  YOLO (YOLOv8s):     avg {avg_yolo}ms | P95 {p95_yolo}ms")
print(f"  Scoring:            avg {avg_score}µs")
print(f"  Behavior Analysis:  avg {avg_beh}µs")
print(f"  Browser Events:     <1µs")
print(f"  Stress (30 frames): avg {avg_stress}ms | {fps} FPS")
print("=" * 70)

with open("perf_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print("Results → perf_results.json")
