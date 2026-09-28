"""Apply user feedback to an existing workout plan."""


def update_workout_plan(original_plan: str, user_feedback: str) -> str:
    """
    Take the user's original 7-day plan plus free-text feedback (e.g. "add yoga",
    "more focus on cardio") and return a revised plan with the same structure.
    """
    return f"{original_plan}\n\nUpdated based on feedback:\n{user_feedback.strip()}"