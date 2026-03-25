"""
Screenshot Manager — Save evidence images to disk
Stores frames under  proctor_logs/{student_id}/{event}_{timestamp}.jpg
"""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path

# Base directory for evidence screenshots (relative to backend/)
_BASE_DIR = Path(__file__).resolve().parent.parent.parent / "proctor_logs"


def save_screenshot(image_b64: str, student_id: str, event_type: str) -> str | None:
    """
    Save a base64-encoded JPEG to disk.
    Returns the relative path on success, None on failure.
    """
    try:
        data = image_b64.split(",")[1] if "," in image_b64 else image_b64
        img_bytes = base64.b64decode(data)

        # Sanitise student_id for filesystem
        safe_id = "".join(c if c.isalnum() or c in ("_", "-", ".") else "_" for c in student_id)

        student_dir = _BASE_DIR / safe_id
        student_dir.mkdir(parents=True, exist_ok=True)

        ts = int(time.time() * 1000)
        filename = f"{event_type}_{ts}.jpg"
        filepath = student_dir / filename

        with open(filepath, "wb") as f:
            f.write(img_bytes)

        # Return path relative to project root
        return f"proctor_logs/{safe_id}/{filename}"
    except Exception:
        return None
