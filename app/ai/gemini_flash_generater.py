"""
gemini_flash_generator.py
Generates fast, lightweight nutrition/recovery tips using Gemini Flash.
"""

import os
import json
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

TIP_MODEL = os.getenv("GEMINI_TIP_MODEL", "gemini-2.5-flash")


def _fallback_nutrition() -> str:
    return "BREAKFAST: 3 eggs or 200 g Greek yogurt, 60 g oats, 1 banana, and 300 ml water.\nLUNCH: 150 g chicken, fish, tofu, or paneer; 150 g cooked rice; 1 cup dal; and 2 cups vegetables.\nDINNER: 150 g lean protein; 200 g potato or 2 whole-wheat rotis; 2 cups vegetables; and 300 ml water.\nSNACK: 1 fruit plus 20-25 g nuts or 200 ml milk. Adjust portions to your goal and medical guidance."


def generate_nutrition_tip_with_flash(goal: str) -> str:
    """
    Generate a concise, practical nutrition or recovery tip tailored to the
    user's selected fitness goal (e.g. "weight loss", "muscle gain").
    """
    if not GOOGLE_API_KEY:
        return _fallback_nutrition()

    prompt = (
        f"Give one clear, helpful nutrition or recovery tip for someone focused on "
        f"'{goal}'. The tip should be practical, friendly, and easy to understand. "
        f"Give exact breakfast, lunch, dinner, and snack food names with practical serving sizes in grams, cups, or pieces. Include approximate protein and calorie ranges, water target, and substitutions for vegetarian users. Keep the answer structured and practical."
    )

    try:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{TIP_MODEL}:generateContent?key={GOOGLE_API_KEY}"
        payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
        request = Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=20) as response:
            result = json.load(response)
        return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return _fallback_nutrition()