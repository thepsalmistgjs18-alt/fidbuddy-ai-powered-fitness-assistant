import os
import json
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
def _fallback_plan(goal: str, intensity: str) -> str:
    return (
        f"Goal: {goal}\nIntensity: {intensity}\n\n"
        "TODAY'S GYM MISSION\n"
        "Day 1 - Push strength: Warm-up 8 min; barbell bench press 4x8, incline dumbbell press 3x10, seated shoulder press 3x10, cable triceps pushdown 3x12; rest 90 sec; cooldown 5 min.\n"
        "Day 2 - Pull strength: Warm-up 8 min; lat pulldown 4x10, seated cable row 4x10, face pull 3x15, dumbbell curl 3x12; rest 90 sec; cooldown 5 min.\n"
        "Day 3 - Leg strength: Warm-up 10 min; back squat 4x8, Romanian deadlift 3x10, walking lunge 3x10 each leg, standing calf raise 3x15; rest 120 sec; cooldown 6 min.\n"
        "Day 4 - Cardio and core: 5 min warm-up; treadmill run 3 km, bicycle crunch 3x20, plank 3x45 sec, dead bug 3x12 each side; cooldown 8 min.\n"
        "Day 5 - Upper body volume: Warm-up 8 min; push-up 4x12, one-arm dumbbell row 4x10 each side, lateral raise 3x15, chest-supported fly 3x12; rest 75 sec; cooldown 5 min.\n"
        "Day 6 - Lower body volume: Warm-up 10 min; leg press 4x10, hip thrust 4x10, Bulgarian split squat 3x8 each leg, hamstring curl 3x12; rest 90 sec; cooldown 6 min.\n"
        "Day 7 - Recovery mission: Easy walk 2 km, mobility 20 min, breathing 5 min, and full hydration. Stop if you feel pain."
    )


def _generate_with_gemini(prompt: str) -> str:
    model = os.getenv("GEMINI_WORKOUT_MODEL", "gemini-2.5-pro")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
    payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    request = Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    return result["candidates"][0]["content"]["parts"][0]["text"].strip()


def generate_workout_gemini(user_data: dict[str, str]) -> str:
    goal = user_data["goal"]
    intensity = user_data["intensity"]
    if not API_KEY:
        return _fallback_plan(goal, intensity)

    prompt = (
        f"Create a safe, practical 7-day gym trainee workout plan for the goal '{goal}' at '{intensity}' intensity. "
        "Return exactly Day 1 through Day 7, with a DIFFERENT daily focus such as push, pull, legs, cardio/core, upper volume, lower volume, and recovery. For every day provide exact exercise names, sets x reps or timed duration, running kilometers where relevant, rest times, warm-up, and cooldown. Do not organize the answer into Phase 1 or lifetime phases. Do not use vague phrases such as 'work out' or 'eat healthy'. Mention that users should stop if they feel pain."
    )
    try:
        return _generate_with_gemini(prompt)
    except Exception:
        return _fallback_plan(goal, intensity)