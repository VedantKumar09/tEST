import os
import json
import time
import requests
from ..config import settings
# =========================
# CONFIG
# =========================
COOLDOWN_SECONDS = 20   # minimum gap between API calls
LAST_CALL_TIME = 0

PROVIDER = (settings.AI_PROVIDER or "gemini").strip().lower()

# =========================
# PROMPT BUILDER (OPTIMIZED)
# =========================
def _build_supervisor_prompt(events, violations, coding_scores, exam_duration):

    # compress logs instead of full timeline
    event_counts = {}
    for e in events:
        t = e.get("type", "unknown")
        event_counts[t] = event_counts.get(t, 0) + 1

    log_summary = ", ".join([f"{k}: {v}" for k, v in event_counts.items()])
    coding_summary = ", ".join([f"Q{k}: {v}%" for k, v in coding_scores.items()]) if coding_scores else "None"

    return f"""
You are an AI Exam Supervisor.

Summary:
Duration: {exam_duration}s
Violations: {violations}
Events: {log_summary}
Coding: {coding_summary}

Decide cheating probability and action.

Return ONLY JSON:
{{
"probability_cheating": "High" | "Medium" | "Low" | "None",
"reasoning": "short reasoning",
"recommended_action": "Pass" | "Review Timeline" | "Invalidate Exam"
}}
"""


# =========================
# SAFE JSON PARSER
# =========================
def _parse_json_text(text):
    try:
        return json.loads(text.strip())
    except:
        return {
            "probability_cheating": "Error",
            "reasoning": "Invalid JSON from model",
            "recommended_action": "Manual Review Required"
        }


# =========================
# GEMINI (BEST FREE OPTION)
# =========================
def _run_gemini(prompt):
    api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    for attempt in range(3):
        response = requests.post(url, json=payload, timeout=15)

        if response.status_code == 429:
            time.sleep(10 * (attempt + 1))  # slower retry
            continue

        response.raise_for_status()

        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]

        return _parse_json_text(text)

    raise RuntimeError("Gemini rate limit exceeded")


# =========================
# MAIN FUNCTION (SAFE)
# =========================
def generate_supervisor_report(events, violations, coding_scores, exam_duration, exam_finished=False):
    global LAST_CALL_TIME

    # 🚨 1. Skip if not important
    if not exam_finished and violations < 3:
        return {
            "probability_cheating": "Low",
            "reasoning": "Insufficient suspicious activity for AI review.",
            "recommended_action": "Continue Monitoring"
        }

    # 🚨 2. Cooldown protection
    if time.time() - LAST_CALL_TIME < COOLDOWN_SECONDS:
        return {
            "probability_cheating": "Skipped",
            "reasoning": "Skipped to prevent API rate limit.",
            "recommended_action": "Continue Monitoring"
        }

    LAST_CALL_TIME = time.time()

    prompt = _build_supervisor_prompt(events, violations, coding_scores, exam_duration)

    # 🚨 3. Only ONE provider (no spam)
    try:
        if PROVIDER == "gemini":
            result = _run_gemini(prompt)
        else:
            raise RuntimeError("Only Gemini enabled in free-tier mode")

        return {
            "probability_cheating": result.get("probability_cheating", "Unknown"),
            "reasoning": result.get("reasoning", "No reasoning"),
            "recommended_action": result.get("recommended_action", "Manual Review Required"),
        }

    except Exception as e:
        return {
            "probability_cheating": "Error",
            "reasoning": f"API failed: {str(e)}",
            "recommended_action": "Manual Review Required"
        }
