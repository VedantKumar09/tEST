"""
Proctor Configuration — Centralised thresholds for all detection modules.
Adjust these values to tune sensitivity vs. false-positive rate.
"""

# ── Head Pose Thresholds ──────────────────────────────────────────────────────
HEAD_POSE_YAW_THRESHOLD = 35       # degrees — flag if |yaw| exceeds this
HEAD_POSE_PITCH_UP_THRESHOLD = 30  # degrees — flag if pitch > this
HEAD_POSE_PITCH_DOWN_THRESHOLD = 25  # degrees — flag if pitch < -this

# ── Eye Gaze Thresholds ───────────────────────────────────────────────────────
GAZE_LEFT_THRESHOLD = 0.30
GAZE_RIGHT_THRESHOLD = 0.70
GAZE_SMOOTHING_WINDOW = 10        # frames for moving-average

# ── Temporal Buffers (seconds) ────────────────────────────────────────────────
NO_FACE_TIMEOUT_S = 3.0
LOOKING_AWAY_TIMEOUT_S = 2.0
GAZE_OFFSCREEN_TIMEOUT_S = 2.0

# ── Bounding Box Smoothing ────────────────────────────────────────────────────
BBOX_SMOOTH_FACTOR = 0.7

# ── YOLO ──────────────────────────────────────────────────────────────────────
YOLO_INTERVAL_S = 2.0
YOLO_CONFIDENCE_THRESHOLD = 0.40

# ── Multi-Loop Detection Architecture ────────────────────────────────────────
# Fast loop:  runs every frame (face, head pose, gaze)
# Medium loop: runs every YOLO_FRAME_SKIP frames (object detection)
# Slow loop:  runs every BEHAVIOR_ANALYSIS_INTERVAL_S (behavior, identity)
YOLO_FRAME_SKIP = 3                   # run YOLO every N frames (lower = faster detection)
PHONE_CONF_THRESHOLD = 0.25           # phone is small — extremely sensitive to catch reliably
PERSON_CONF_THRESHOLD = 0.40          # person detection confidence
BOOK_CONF_THRESHOLD = 0.45            # book detection confidence
FRAME_RESOLUTION = 800                # higher resolution catches small objects (phone)
BEHAVIOR_ANALYSIS_INTERVAL_S = 2.0    # slow loop interval

# ── Debug / Visualization ────────────────────────────────────────────────────
DETECTION_DEBUG_LOGGING = True         # log detected objects + confidence to console
DETECTION_BBOX_IN_RESPONSE = True      # include bounding boxes in API response

# ── Hand-Face Proximity (Behavior-Based Phone Detection) ─────────────────────
HAND_FACE_DISTANCE_THRESHOLD = 0.6    # normalized distance (1.0 = one face-width)
HAND_NEAR_FACE_FRAMES_THRESHOLD = 30  # ~1 second at 30 FPS before triggering
SCORE_PHONE_BEHAVIOR = 25             # risk score for phone usage behavior

# ── Scoring Weights ───────────────────────────────────────────────────────────
# Updated for production-grade sensitivity (HackerRank/Mettl style)
SCORE_NO_FACE = 5           # face disappeared
SCORE_LOOKING_AWAY = 5      # looking away from screen
SCORE_GAZE_OFFSCREEN = 3    # gaze drifted offscreen
SCORE_MULTIPLE_FACES = 50   # another person visible
SCORE_OBJECT_DETECTED = 25  # phone / book / laptop detected
SCORE_TAB_SWITCH = 10       # switched tab/window
SCORE_FULLSCREEN_EXIT = 8   # exited fullscreen
SCORE_COPY_PASTE = 8        # copy/paste attempt
SCORE_RIGHT_CLICK = 3       # right-click (context menu)
SCORE_DEVTOOLS_OPEN = 15    # DevTools opened
SCORE_IDENTITY_MISMATCH = 40  # face doesn't match reference

# ── Score Decay ───────────────────────────────────────────────────────────────
# If the student behaves well (no violations), score decays over time.
SCORE_DECAY_RATE = 2              # points reduced per decay tick
SCORE_DECAY_INTERVAL_S = 30.0    # decay applied every 30 seconds of clean behavior
SCORE_DECAY_GRACE_PERIOD_S = 15.0  # no decay within 15 s of last violation

# ── Score Limits ──────────────────────────────────────────────────────────────
MAX_RISK_SCORE = 200        # cap — score never exceeds this
MIN_RISK_SCORE = 0          # floor — score never goes below this

# ── Risk Level Thresholds ─────────────────────────────────────────────────────
RISK_LEVEL_LOW = 20         # 0 – 20
RISK_LEVEL_MEDIUM = 50      # 21 – 50
RISK_LEVEL_HIGH = 80        # 51 – 80
                            # 81+  → CRITICAL
