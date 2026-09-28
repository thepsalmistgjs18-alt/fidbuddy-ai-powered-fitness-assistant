import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parent.parent / "fitbuddy.db"


@dataclass
class User:
    id: int
    name: str
    contact: str
    age: int
    weight: float
    goal: str
    intensity: str


@dataclass
class Plan:
    workout_plan: str
    nutrition_tip: str | None = None


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                contact TEXT,
                age INTEGER NOT NULL,
                weight REAL NOT NULL,
                goal TEXT NOT NULL,
                intensity TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                workout_plan TEXT NOT NULL,
                nutrition_tip TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS daily_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                log_date TEXT NOT NULL,
                run_km REAL NOT NULL DEFAULT 0,
                workout_name TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                nutrition_done INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        if "contact" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN contact TEXT")
        connection.execute("UPDATE users SET contact = 'legacy-' || id WHERE contact IS NULL")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_contact ON users(contact)")
        log_columns = {row[1] for row in connection.execute("PRAGMA table_info(daily_logs)")}
        if "nutrition_done" not in log_columns:
            connection.execute("ALTER TABLE daily_logs ADD COLUMN nutrition_done INTEGER NOT NULL DEFAULT 0")


def save_user(contact: str, username: str, age: int, weight: float, goal: str, intensity: str) -> int:
    with _connect() as connection:
        existing = connection.execute("SELECT id FROM users WHERE contact = ?", (contact.strip(),)).fetchone()
        if existing:
            user_id = existing["id"]
        else:
            user_id = None
        connection.execute(
            """INSERT INTO users (id, name, contact, age, weight, goal, intensity)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET name=excluded.name, contact=excluded.contact,
               age=excluded.age, weight=excluded.weight, goal=excluded.goal, intensity=excluded.intensity""",
            (user_id, username.strip(), contact.strip(), age, weight, goal.strip(), intensity.strip()),
        )
        return int(connection.execute("SELECT id FROM users WHERE contact = ?", (contact.strip(),)).fetchone()[0])


def save_plan(user_id: int, workout_plan: str, nutrition_tip: str) -> None:
    with _connect() as connection:
        connection.execute(
            "INSERT INTO plans (user_id, workout_plan, nutrition_tip) VALUES (?, ?, ?)",
            (user_id, workout_plan, nutrition_tip),
        )


def update_plan(user_id: int, workout_plan: str) -> None:
    with _connect() as connection:
        connection.execute(
            """UPDATE plans SET workout_plan = ? WHERE id =
               (SELECT id FROM plans WHERE user_id = ? ORDER BY id DESC LIMIT 1)""",
            (workout_plan, user_id),
        )


def get_user(user_id: int) -> User | None:
    with _connect() as connection:
        row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return User(**dict(row)) if row else None


def get_user_by_contact(contact: str) -> User | None:
    with _connect() as connection:
        row = connection.execute("SELECT * FROM users WHERE contact = ?", (contact.strip(),)).fetchone()
    return User(**dict(row)) if row else None


def delete_user(contact: str) -> bool:
    user = get_user_by_contact(contact)
    if not user:
        return False
    with _connect() as connection:
        connection.execute("DELETE FROM daily_logs WHERE user_id = ?", (user.id,))
        connection.execute("DELETE FROM plans WHERE user_id = ?", (user.id,))
        connection.execute("DELETE FROM users WHERE id = ?", (user.id,))
    return True


def _plan_from_row(row: sqlite3.Row | None) -> Plan | None:
    return Plan(workout_plan=row["workout_plan"], nutrition_tip=row["nutrition_tip"]) if row else None


def get_original_plan(user_id: int) -> str | None:
    with _connect() as connection:
        row = connection.execute("SELECT workout_plan FROM plans WHERE user_id = ? ORDER BY id LIMIT 1", (user_id,)).fetchone()
    return row["workout_plan"] if row else None


def get_latest_plan(user_id: int) -> Plan | None:
    with _connect() as connection:
        row = connection.execute("SELECT workout_plan, nutrition_tip FROM plans WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    return _plan_from_row(row)


def get_all_users_with_plans() -> list[dict[str, object]]:
    with _connect() as connection:
        rows = connection.execute(
            """SELECT users.*, plans.workout_plan, plans.nutrition_tip
               FROM users LEFT JOIN plans ON plans.id =
               (SELECT id FROM plans p WHERE p.user_id = users.id ORDER BY id DESC LIMIT 1)
               ORDER BY users.id"""
        ).fetchall()
    return [dict(row) for row in rows]


def save_daily_log(contact: str, log_date: str, run_km: float, workout_name: str, completed: bool, nutrition_done: bool, notes: str) -> None:
    user = get_user_by_contact(contact)
    if not user:
        raise ValueError("Create a workout profile before recording activity.")
    with _connect() as connection:
        connection.execute(
                """INSERT INTO daily_logs (user_id, log_date, run_km, workout_name, completed, nutrition_done, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user.id, log_date, run_km, workout_name.strip(), int(completed), int(nutrition_done), notes.strip()),
        )


def get_daily_logs(contact: str) -> list[dict[str, object]]:
    user = get_user_by_contact(contact)
    if not user:
        return []
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM daily_logs WHERE user_id = ? ORDER BY log_date DESC, id DESC",
            (user.id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_progress(contact: str) -> dict[str, object]:
    logs = get_daily_logs(contact)
    return {
        "total_km": round(sum(float(log["run_km"]) for log in logs), 1),
        "workouts": sum(1 for log in logs if log["completed"]),
        "nutrition_days": sum(1 for log in logs if log["nutrition_done"]),
        "days_logged": len(logs),
        "logs": logs[:7],
    }


def get_rank(contact: str) -> dict[str, object]:
    progress = get_progress(contact)
    score = int(progress["workouts"]) * 100 + int(float(progress["total_km"])) * 10 + int(progress["nutrition_days"]) * 25
    ranks = [(0, "E", "Awakened"), (250, "D", "Rookie Hunter"), (600, "C", "Dungeon Runner"), (1200, "B", "Elite Hunter"), (2200, "A", "Shadow Captain"), (4000, "S", "Monarch Class")]
    current = ranks[0]
    for threshold in ranks:
        if score >= threshold[0]:
            current = threshold
    return {"score": score, "letter": current[1], "title": current[2]}


def get_calendar_activity(contact: str, start_date: str, end_date: str) -> dict[str, bool]:
    user = get_user_by_contact(contact)
    if not user:
        return {}
    with _connect() as connection:
        rows = connection.execute(
            """SELECT log_date, completed, nutrition_done FROM daily_logs
               WHERE user_id = ? AND log_date BETWEEN ? AND ?""",
            (user.id, start_date, end_date),
        ).fetchall()
    return {row["log_date"]: bool(row["completed"] and row["nutrition_done"]) for row in rows}


def get_profile_summary(contact: str) -> dict[str, object]:
    progress = get_progress(contact)
    logs = get_daily_logs(contact)
    active_dates = {log["log_date"] for log in logs if log["completed"]}
    streak = 0
    cursor = date.today()
    while cursor.isoformat() in active_dates:
        streak += 1
        cursor -= timedelta(days=1)
    achievements = []
    if progress["workouts"] >= 1:
        achievements.append("First mission")
    if progress["workouts"] >= 7:
        achievements.append("Seven-day awakening")
    if progress["total_km"] >= 10:
        achievements.append("10K runner")
    if progress["nutrition_days"] >= 5:
        achievements.append("Fuel discipline")
    return {"streak": streak, "achievements": achievements}