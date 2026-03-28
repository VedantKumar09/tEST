"""
Proctor Configuration — Centralised thresholds for all detection modules.
Adjust these values to tune sensitivity vs. false-positive rate.

Industry Reference (HackerRank, CodeSignal, Google):
- Minor flags (no_face, looking_away, right_click) = informational, not cheating
- Major flags (multiple_faces, phone/object detected) = suspicious, needs review
- No platform auto-invalidates; all flags go to human review
- Pattern matters more than individual events
"""

# ── Head Pose Thresholds ──────────────────────────────────────────────────────
HEAD_POSE_YAW_THRESHOLD = 40       # degrees — flag if |yaw| exceeds this (relaxed)
HEAD_POSE_PITCH_UP_THRESHOLD = 35  # degrees — flag if pitch > this (relaxed)
HEAD_POSE_PITCH_DOWN_THRESHOLD = 30  # degrees — flag if pitch < -this (relaxed)

# ── Eye Gaze Thresholds ───────────────────────────────────────────────────────
GAZE_LEFT_THRESHOLD = 0.25         # more lenient (was 0.30)
GAZE_RIGHT_THRESHOLD = 0.75       # more lenient (was 0.70)
GAZE_SMOOTHING_WINDOW = 15        # frames for moving-average (was 10)

# ── Temporal Buffers (seconds) ────────────────────────────────────────────────
# Increased buffers = fewer false positives from brief glitches
NO_FACE_TIMEOUT_S = 5.0           # was 3.0 — brief camera issues are common
LOOKING_AWAY_TIMEOUT_S = 4.0      # was 2.0 — people naturally glance away
GAZE_OFFSCREEN_TIMEOUT_S = 4.0    # was 2.0 — brief eye movement is normal

# ── Bounding Box Smoothing ────────────────────────────────────────────────────
BBOX_SMOOTH_FACTOR = 0.7

# ── YOLO ──────────────────────────────────────────────────────────────────────
YOLO_INTERVAL_S = 3.0             # was 2.0 — less frequent scanning
YOLO_CONFIDENCE_THRESHOLD = 0.50  # was 0.40 — higher confidence required

# ── Scoring Weights ───────────────────────────────────────────────────────────
# Industry approach: minor events have near-zero weight, only clear
# cheating indicators carry significant weight.
#
# Minor (informational — common false positives):
SCORE_NO_FACE = 1                 # was 2 — camera glitches are common
SCORE_LOOKING_AWAY = 1            # was 1 — people naturally look away
SCORE_GAZE_OFFSCREEN = 1          # was 1 — eye tracking has noise
SCORE_RIGHT_CLICK = 0             # was 1 — accidental, not cheating
SCORE_FULLSCREEN_EXIT = 1         # was 2 — can be accidental
SCORE_COPY_PASTE = 1              # was 3 — could be within-editor paste
#
# Major (suspicious — needs review):
SCORE_TAB_SWITCH = 2              # was 3 — suspicious but could be accidental
SCORE_MULTIPLE_FACES = 3          # was 5 — strong signal but needs context
SCORE_OBJECT_DETECTED = 5         # was 10 — phone/book is a real concern
