"""
routes.py
All routing logic for FitBuddy: the HTML page flow (form-based, used by a browser)
and a small JSON API surface (usable/testable at /docs).
"""

import os
import random
import time
from datetime import date, timedelta
from uuid import uuid4
from fastapi import APIRouter, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .schemas import UserInput, FeedbackRequest
from .gemini_generator import generate_workout_gemini
from .ai.gemini_flash_generater import generate_nutrition_tip_with_flash
from .updated_plan import update_workout_plan
from .database import (
    save_user,
    save_plan,
    update_plan,
    get_original_plan,
    get_user,
    get_user_by_contact,
    delete_user,
    get_latest_plan,
    get_all_users_with_plans,
    save_daily_log,
    get_daily_logs,
    get_progress,
    get_rank,
    get_calendar_activity,
    get_profile_summary,
)

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)
PENDING_OTPS: dict[str, tuple[str, float]] = {}
SHOW_DEV_OTP = os.getenv("SHOW_DEV_OTP", "true").lower() == "true"
MOTIVATIONAL_QUOTES = [
    "The shadow becomes strong one rep at a time.",
    "Discipline is your hidden class. Equip it daily.",
    "You do not need a perfect day. You need your next action.",
    "Run toward the version of you that refuses to quit.",
    "Small progress still adds power to the final boss fight.",
]


def page_context(request: Request, **values: object) -> dict[str, object]:
    contact = active_contact(request)
    user = get_user_by_contact(contact) if contact else None
    context: dict[str, object] = {"request": request, "quote": random.choice(MOTIVATIONAL_QUOTES)}
    if user:
        context.update({"user": user, "rank": get_rank(contact), "profile": get_profile_summary(contact)})
    context.update(values)
    return context


def active_contact(request: Request, supplied: str = "") -> str:
    return supplied.strip() or request.cookies.get("fitbuddy_contact", "").strip()


def guest_contact(contact: str) -> bool:
    return contact.startswith("guest-")


def meal_cards(goal: str) -> list[dict[str, str]]:
    return [
        {"label": "BREAKFAST", "symbol": "EGG", "title": "Omelette + oats", "items": "Eggs + oats + fruit", "tone": "sunrise"},
        {"label": "LUNCH", "symbol": "BOWL", "title": "Protein bowl", "items": "Rice + protein + veg", "tone": "azure"},
        {"label": "DINNER", "symbol": "ROTI", "title": "Recovery plate", "items": "Lean protein + carbs + veg", "tone": "violet"},
        {"label": "SNACK", "symbol": "CUP", "title": "Fuel cup", "items": "Fruit + yogurt or nuts", "tone": "mint"},
    ]


def calorie_targets(weight: float, goal: str) -> tuple[int, int]:
    goal_name = (goal or "maintenance").lower()
    if "fat" in goal_name or "cut" in goal_name or "loss" in goal_name:
        kcal = int(weight * 24)
        protein = int(weight * 2.2)
    elif "muscle" in goal_name or "gain" in goal_name or "bulk" in goal_name:
        kcal = int(weight * 30)
        protein = int(weight * 2.4)
    else:
        kcal = int(weight * 26)
        protein = int(weight * 2.1)
    return kcal, protein


def daily_meal_plan(goal: str, weight: float = 70.0) -> list[dict[str, object]]:
    target_kcal, target_protein = calorie_targets(weight, goal)
    daily_plan = [
        {"day": "Day 1", "focus": "Power push", "meals": [
            {"label": "Breakfast", "symbol": "EGG", "title": "Egg + oat stack", "items": "3 eggs • oats • banana", "calories": int(target_kcal * 0.24), "protein": int(target_protein * 0.22), "tone": "sunrise"},
            {"label": "Lunch", "symbol": "BOWL", "title": "Chicken rice bowl", "items": "Chicken • rice • dal • veg", "calories": int(target_kcal * 0.29), "protein": int(target_protein * 0.31), "tone": "azure"},
            {"label": "Dinner", "symbol": "ROTI", "title": "Recovery plate", "items": "Fish or tofu • roti • salad", "calories": int(target_kcal * 0.27), "protein": int(target_protein * 0.25), "tone": "violet"},
            {"label": "Snack", "symbol": "CUP", "title": "Yogurt fuel", "items": "Yogurt • fruit • nuts", "calories": int(target_kcal * 0.12), "protein": int(target_protein * 0.14), "tone": "mint"},
        ]},
        {"day": "Day 2", "focus": "Pull engine", "meals": [
            {"label": "Breakfast", "symbol": "PAN", "title": "Protein oats", "items": "Oats • milk • berries", "calories": int(target_kcal * 0.23), "protein": int(target_protein * 0.21), "tone": "sunrise"},
            {"label": "Lunch", "symbol": "BOWL", "title": "Quinoa lift", "items": "Tuna • quinoa • greens", "calories": int(target_kcal * 0.28), "protein": int(target_protein * 0.3), "tone": "azure"},
            {"label": "Dinner", "symbol": "SPOON", "title": "Lean curry", "items": "Chicken • veggies • rice", "calories": int(target_kcal * 0.26), "protein": int(target_protein * 0.24), "tone": "violet"},
            {"label": "Snack", "symbol": "CUP", "title": "Shake pack", "items": "Banana • milk • peanut butter", "calories": int(target_kcal * 0.13), "protein": int(target_protein * 0.15), "tone": "mint"},
        ]},
        {"day": "Day 3", "focus": "Leg drive", "meals": [
            {"label": "Breakfast", "symbol": "EGG", "title": "Wrap + eggs", "items": "Eggs • wrap • fruit", "calories": int(target_kcal * 0.22), "protein": int(target_protein * 0.2), "tone": "sunrise"},
            {"label": "Lunch", "symbol": "BOWL", "title": "Turkey bowl", "items": "Turkey • rice • veg", "calories": int(target_kcal * 0.29), "protein": int(target_protein * 0.32), "tone": "azure"},
            {"label": "Dinner", "symbol": "ROTI", "title": "Lentil plate", "items": "Lentils • roti • salad", "calories": int(target_kcal * 0.25), "protein": int(target_protein * 0.25), "tone": "violet"},
            {"label": "Snack", "symbol": "CUP", "title": "Trail mix", "items": "Nuts • yogurt • fruit", "calories": int(target_kcal * 0.11), "protein": int(target_protein * 0.12), "tone": "mint"},
        ]},
    ]
    return daily_plan


def workout_cards(plan: str) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    mission_symbols = ["PUSH", "PULL", "LEGS", "RUN", "UPPER", "LOWER", "REST"]
    for raw_line in plan.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("phase ") or lower.startswith("day "):
            if current:
                cards.append(current)
            title, _, detail = line.partition(":")
            symbol = mission_symbols[len(cards)] if len(cards) < len(mission_symbols) else str(len(cards) + 1).zfill(2)
            current = {"title": title, "detail": detail.strip() or "Mission briefing", "symbol": symbol}
        elif current:
            current["detail"] += " " + line
    if current:
        cards.append(current)
    return cards or [{"title": "Lifetime protocol", "detail": plan, "symbol": "01"}]


# ---------------------------------------------------------------------------
# 1. Home route — displays the input form
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    contact = active_contact(request)
    if not contact or not get_user_by_contact(contact):
        return templates.TemplateResponse(request=request, name="welcome.html", context=page_context(request))
    user = get_user_by_contact(contact)
    return templates.TemplateResponse(request=request, name="index.html", context=page_context(request, user=user, rank=get_rank(contact), profile=get_profile_summary(contact)))


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return RedirectResponse(url="/", status_code=303)


@router.post("/login")
def login(request: Request, contact: str = Form(...)):
    contact = contact.strip()
    if len(contact) < 5:
        return templates.TemplateResponse(request=request, name="welcome.html", context=page_context(request, error="Enter a valid email address or mobile number."), status_code=400)
    response = RedirectResponse(url="/" if get_user_by_contact(contact) else f"/profile-setup?contact={contact}", status_code=303)
    response.set_cookie("fitbuddy_contact", contact, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
    return response


@router.post("/request-otp", response_class=HTMLResponse)
def request_otp(request: Request, contact: str = Form(...)):
    contact = contact.strip()
    if len(contact) < 5:
        return templates.TemplateResponse(request=request, name="welcome.html", context=page_context(request, error="Enter a valid email address or mobile number."), status_code=400)
    code = f"{random.randint(0, 999999):06d}"
    PENDING_OTPS[contact] = (code, time.time() + 300)
    print(f"FitBuddy OTP for {contact}: {code}")
    return templates.TemplateResponse(request=request, name="otp.html", context=page_context(request, contact=contact, dev_otp=code if SHOW_DEV_OTP else None))


@router.post("/verify-otp")
def verify_otp(request: Request, contact: str = Form(...), otp: str = Form(...)):
    pending = PENDING_OTPS.get(contact.strip())
    if not pending or pending[1] < time.time() or otp.strip() != pending[0]:
        return templates.TemplateResponse(request=request, name="otp.html", context=page_context(request, contact=contact, error="That code is invalid or expired. Request a new one."), status_code=400)
    PENDING_OTPS.pop(contact.strip(), None)
    response = RedirectResponse(url="/" if get_user_by_contact(contact) else f"/profile-setup?contact={contact.strip()}", status_code=303)
    response.set_cookie("fitbuddy_contact", contact.strip(), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
    return response


@router.post("/guest-login")
def guest_login():
    contact = f"guest-{uuid4().hex[:12]}"
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("fitbuddy_contact", contact, httponly=True, samesite="lax", max_age=60 * 60 * 24)
    response.headers["Location"] = f"/profile-setup?contact={contact}"
    return response


@router.post("/delete-account")
def delete_account(request: Request):
    contact = active_contact(request)
    delete_user(contact)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("fitbuddy_contact")
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("fitbuddy_contact")
    return response


@router.get("/profile-setup", response_class=HTMLResponse)
def profile_setup_page(request: Request, contact: str = Query(default="")):
    contact = active_contact(request, contact)
    return templates.TemplateResponse(request=request, name="profile_setup.html", context=page_context(request, contact=contact, guest=guest_contact(contact)))


@router.post("/profile-setup", response_class=HTMLResponse)
def complete_profile(
    request: Request,
    contact: str = Form(...),
    username: str = Form(...),
    age: int = Form(...),
    weight: float = Form(...),
    goal: str = Form(...),
    intensity: str = Form(...),
):
    plan = generate_workout_gemini({"goal": goal, "intensity": intensity})
    nutrition_tip = generate_nutrition_tip_with_flash(goal)
    user_id = save_user(contact, username, age, weight, goal, intensity)
    save_plan(user_id, plan, nutrition_tip)
    response = templates.TemplateResponse(request=request, name="result.html", context=page_context(request, username=username, contact=contact, user_id=user_id, age=age, weight=weight, goal=goal, intensity=intensity, workout_plan=plan, workout_cards=workout_cards(plan), meal_cards=meal_cards(goal), daily_meals=daily_meal_plan(goal), nutrition_tip=nutrition_tip, feedback_message=None, show_navigation=True))
    response.set_cookie("fitbuddy_contact", contact.strip(), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
    return response


@router.get("/workout-plan", response_class=HTMLResponse)
def workout_plan_page(request: Request):
    contact = active_contact(request)
    return templates.TemplateResponse(request=request, name="workout_plan.html", context=page_context(request, contact=contact, guest=guest_contact(contact)))


@router.get("/nutrition-tips", response_class=HTMLResponse)
def nutrition_tips_page(request: Request, goal: str = Query(default="everyday energy")):
    tip = generate_nutrition_tip_with_flash(goal)
    current_contact = active_contact(request)
    current_user = get_user_by_contact(current_contact)
    weight = float(current_user.weight) if current_user else 70.0
    return templates.TemplateResponse(
        request=request,
        name="nutrition_tips.html",
        context=page_context(request, goal=goal, nutrition_tip=tip, meal_cards=meal_cards(goal), daily_meals=daily_meal_plan(goal, weight), contact=current_contact, user=current_user),
    )


@router.post("/generate-nutrition-tip", response_class=HTMLResponse)
def generate_nutrition_tip(request: Request, goal: str = Form(...)):
    tip = generate_nutrition_tip_with_flash(goal)
    current_contact = active_contact(request)
    current_user = get_user_by_contact(current_contact)
    weight = float(current_user.weight) if current_user else 70.0
    return templates.TemplateResponse(
        request=request,
        name="nutrition_tips.html",
        context=page_context(request, goal=goal, nutrition_tip=tip, meal_cards=meal_cards(goal), daily_meals=daily_meal_plan(goal, weight), contact=current_contact, user=current_user),
    )


# ---------------------------------------------------------------------------
# 2. Generate workout — processes the form, calls Gemini, saves + renders result
# ---------------------------------------------------------------------------

@router.post("/generate-workout", response_class=HTMLResponse)
def generate_workout(
    request: Request,
    username: str = Form(...),
    contact: str = Form(...),
    age: int = Form(...),
    weight: float = Form(...),
    goal: str = Form(...),
    intensity: str = Form(...),
):
    plan = generate_workout_gemini({"goal": goal, "intensity": intensity})
    nutrition_tip = generate_nutrition_tip_with_flash(goal)

    user_id = save_user(contact, username, age, weight, goal, intensity)
    save_plan(user_id, plan, nutrition_tip)

    response = templates.TemplateResponse(
        request=request,
        name="result.html",
        context={
            "request": request,
            "username": username,
            "contact": contact,
            "user_id": user_id,
            "age": age,
            "weight": weight,
            "goal": goal,
            "intensity": intensity,
            "workout_plan": plan,
            "workout_cards": workout_cards(plan),
            "meal_cards": meal_cards(goal),
            "daily_meals": daily_meal_plan(goal),
            "nutrition_tip": nutrition_tip,
            "feedback_message": None,
            "show_navigation": True,
            "quote": random.choice(MOTIVATIONAL_QUOTES),
            "user": get_user_by_contact(contact),
            "rank": get_rank(contact),
            "profile": get_profile_summary(contact),
        },
    )
    response.set_cookie("fitbuddy_contact", contact.strip(), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
    return response


# ---------------------------------------------------------------------------
# 3. Submit feedback — revises the plan and re-renders result.html
# ---------------------------------------------------------------------------

@router.post("/submit-feedback", response_class=HTMLResponse)
def submit_feedback(
    request: Request,
    contact: str = Form(...),
    feedback: str = Form(...),
):
    user = get_user_by_contact(contact)
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Generate a plan first.")

    original = get_original_plan(user.id)
    if not original:
        raise HTTPException(status_code=404, detail="Original plan not found for this user.")

    updated = update_workout_plan(original, feedback)
    update_plan(user.id, updated)

    latest = get_latest_plan(user.id)
    nutrition_tip = latest.nutrition_tip if latest and latest.nutrition_tip else generate_nutrition_tip_with_flash(user.goal)

    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={
            "request": request,
            "username": user.name,
            "contact": user.contact,
            "user_id": user.id,
            "age": user.age,
            "weight": user.weight,
            "goal": user.goal,
            "intensity": user.intensity,
            "workout_plan": updated,
            "workout_cards": workout_cards(updated),
            "meal_cards": meal_cards(user.goal),
            "daily_meals": daily_meal_plan(user.goal),
            "nutrition_tip": nutrition_tip,
            "feedback_message": "Your plan has been updated based on your feedback!",
            "show_navigation": True,
            "quote": random.choice(MOTIVATIONAL_QUOTES),
            "user": user,
            "rank": get_rank(user.contact),
            "profile": get_profile_summary(user.contact),
        },
    )


@router.get("/daily-log", response_class=HTMLResponse)
def daily_log_page(request: Request, contact: str = Query(default="")):
    contact = active_contact(request, contact)
    return templates.TemplateResponse(
        request=request,
        name="daily_log.html",
        context=page_context(request, contact=contact, guest=guest_contact(contact), logs=get_daily_logs(contact), today=date.today().isoformat()),
    )


@router.post("/daily-log", response_class=HTMLResponse)
def save_log(
    request: Request,
    contact: str = Form(...),
    log_date: str = Form(...),
    run_km: float = Form(0),
    workout_name: str = Form(...),
    completed: bool = Form(False),
    nutrition_done: bool = Form(False),
    notes: str = Form(""),
):
    try:
        save_daily_log(contact, log_date, run_km, workout_name, completed, nutrition_done, notes)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return templates.TemplateResponse(
        request=request,
        name="daily_log.html",
        context=page_context(request, contact=contact, guest=guest_contact(contact), logs=get_daily_logs(contact), today=date.today().isoformat(), saved=True),
    )


@router.get("/progress", response_class=HTMLResponse)
def progress_page(request: Request, contact: str = Query(default="")):
    contact = active_contact(request, contact)
    progress = get_progress(contact)
    today = date.today()
    start = today - timedelta(days=29)
    activity = get_calendar_activity(contact, start.isoformat(), today.isoformat())
    calendar_days = [{"date": (start + timedelta(days=index)).isoformat(), "active": activity.get((start + timedelta(days=index)).isoformat(), False)} for index in range(30)]
    return templates.TemplateResponse(
        request=request,
        name="progress.html",
        context=page_context(request, contact=contact, guest=guest_contact(contact), progress=progress, rank=get_rank(contact), calendar_days=calendar_days),
    )


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, contact: str = Query(default="")):
    contact = active_contact(request, contact)
    user = get_user_by_contact(contact)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="profile.html", context=page_context(request, user=user, rank=get_rank(contact), progress=get_progress(contact), profile=get_profile_summary(contact)))


# ---------------------------------------------------------------------------
# 4. Admin view — lists all users and their plans
# ---------------------------------------------------------------------------

@router.get("/view-all-users", response_class=HTMLResponse)
@router.get("/admin/users", response_class=HTMLResponse)
def view_all_users(request: Request):
    users = get_all_users_with_plans()
    return templates.TemplateResponse(
        request=request,
        name="all_users.html",
        context=page_context(request, users=users),
    )


# ---------------------------------------------------------------------------
# JSON API — mirrors the same functionality for programmatic / /docs testing
# ---------------------------------------------------------------------------

@router.post("/api/generate-plan")
def api_generate_plan(user_data: UserInput):
    try:
        user_id = save_user(
            user_data.contact,
            user_data.username,
            user_data.age,
            user_data.weight,
            user_data.goal,
            user_data.intensity,
        )
        plan = generate_workout_gemini({"goal": user_data.goal, "intensity": user_data.intensity})
        tip = generate_nutrition_tip_with_flash(user_data.goal)
        save_plan(user_id, plan, tip)
        return {
            "message": "Workout plan generated and saved successfully!",
            "workout_plan": plan,
            "nutrition_tip": tip,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Something went wrong: {e}")


@router.post("/api/update-plan/{user_id}")
def api_update_plan(user_id: int, data: FeedbackRequest):
    original = get_original_plan(user_id)
    if not original:
        return {"error": "Original plan not found for this user."}
    updated = update_workout_plan(original, data.feedback)
    update_plan(user_id, updated)
    return {"updated_plan": updated}


@router.get("/api/nutrition-tip")
def api_nutrition_tip(goal: str):
    tip = generate_nutrition_tip_with_flash(goal)
    return {"goal": goal, "nutrition_tip": tip}


@router.get("/api/users")
def api_all_users():
    return get_all_users_with_plans()
