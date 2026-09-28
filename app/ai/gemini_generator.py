"""
gemini_generator.py
Generates the structured 7-day workout plan using Gemini 1.5 Pro, and is also
reused by updated_plan.py to revise plans based on user feedback.
"""

import os
import json
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
WORKOUT_MODEL = os.getenv("GEMINI_WORKOUT_MODEL", "gemini-2.5-pro")


def _fallback_plan(goal: str, intensity: str) -> str:
    return (
        f"Goal: {goal}\nIntensity: {intensity}\n\n"
        "Day 1: Full-body strength - 3 rounds of squats, push-ups, rows, and planks.\n"
        "Day 2: Low-impact cardio for 25-35 minutes and mobility work.\n"
        "Day 3: Lower body - 3 sets of lunges, hip hinges, bridges, and calf raises.\n"
        "Day 4: Recovery walk and 10 minutes of stretching.\n"
        "Day 5: Upper body - 3 sets of presses, rows, shoulder raises, and dead bugs.\n"
        "Day 6: Full-body circuit at a comfortable pace for 20-30 minutes.\n"
        "Day 7: Rest, hydration, and gentle mobility."
    )


def _generate_with_gemini(prompt: str) -> str:
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{WORKOUT_MODEL}"
        f":generateContent?key={GOOGLE_API_KEY}"
    )
    payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    request = Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    return result["candidates"][0]["content"]["parts"][0]["text"].strip()


def generate_workout_gemini(user_input: dict) -> str:
    """
    Generate a personalized, structured 7-day workout plan.

    user_input: {"goal": str, "intensity": str}
    """
    goal = user_input.get("goal", "general fitness")
    intensity = user_input.get("intensity", "moderate")
    if not GOOGLE_API_KEY:
        return _fallback_plan(goal, intensity)

    prompt = f"""
You are a professional fitness trainer.

Create a personalized, structured 7-day workout plan for someone with the goal of
"{user_input['goal']}", and who prefers "{user_input['intensity']}" intensity workouts.

Each day must include:
- A warm-up (5-10 mins)
- Main workout (targeted exercises, sets & reps)
- Cooldown or recovery tip

Format strictly like this:
Day 1:
Warm-up: ...
Main Workout: ...
Cooldown: ...
(Repeat for Day 2-7)
"""
    try:
        return _generate_with_gemini(prompt)
    except Exception as e:
        return f"{_fallback_plan(goal, intensity)}\n\nGemini unavailable: {e}"