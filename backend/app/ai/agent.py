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

PROVIDER = (settings.AI_PROVIDER or "groq").strip().lower()

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
# GROQ
# =========================
def _run_groq(prompt):
    api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You are an AI Exam Supervisor. Return ONLY valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    for attempt in range(3):
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        if response.status_code in (401, 403):
            raise RuntimeError("Groq key invalid or unauthorized")
        response.raise_for_status()

        data = response.json()
        text = data["choices"][0]["message"]["content"]
        return _parse_json_text(text)

    raise RuntimeError("Groq rate limit exceeded")


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

    # 🚨 3. Groq primary with Gemini fallback
    try:
        if PROVIDER == "groq":
            try:
                result = _run_groq(prompt)
            except Exception as groq_error:
                result = _run_gemini(prompt)
        elif PROVIDER == "gemini":
            result = _run_gemini(prompt)
        else:
            raise RuntimeError("Unsupported provider configured")

        return {
            "probability_cheating": result.get("probability_cheating", "Unknown"),
            "reasoning": result.get("reasoning", "No reasoning"),
            "recommended_action": result.get("recommended_action", "Manual Review Required"),
        }

    except Exception as e:
        return {
            "probability_cheating": "Error",
            "reasoning": f"{PROVIDER.upper()} API failed and fallback did not succeed: {str(e)}",
            "recommended_action": "Manual Review Required"
        }
