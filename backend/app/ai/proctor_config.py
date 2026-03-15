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

# ── Scoring Weights ───────────────────────────────────────────────────────────
SCORE_NO_FACE = 2
SCORE_LOOKING_AWAY = 1
SCORE_GAZE_OFFSCREEN = 1
SCORE_MULTIPLE_FACES = 5
SCORE_OBJECT_DETECTED = 10
SCORE_TAB_SWITCH = 3
SCORE_FULLSCREEN_EXIT = 2
SCORE_COPY_PASTE = 3
SCORE_RIGHT_CLICK = 1
