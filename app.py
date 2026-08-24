
import os
import html
import textwrap
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client, Client

BASE_DIR = Path(__file__).parent

st.set_page_config(
    page_title="Lock In 90",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

STYLE = BASE_DIR / "style.css"
if STYLE.exists():
    st.markdown(f"<style>{STYLE.read_text()}</style>", unsafe_allow_html=True)

# =========================================================
# Config / Supabase
# =========================================================

def secret(name: str, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return os.getenv(name, default)

@st.cache_resource
def get_supabase() -> Client:
    url = str(secret("SUPABASE_URL", "")).strip()
    key = str(secret("SUPABASE_KEY", "")).strip()

    if not url or not key:
        st.error("Missing SUPABASE_URL or SUPABASE_KEY in Streamlit Secrets.")
        st.stop()

    if not url.startswith(("https://", "http://")):
        st.error("SUPABASE_URL must start with https://")
        st.stop()

    return create_client(url, key)

supabase = get_supabase()
AUTH_REQUIRED = str(secret("AUTH_REQUIRED", "false")).lower() == "true"
PUBLIC_PROFILE_ID = str(secret("PUBLIC_PROFILE_ID", "")).strip()
APP_TIMEZONE = str(secret("APP_TIMEZONE", "Europe/London")).strip() or "Europe/London"

try:
    TZ = ZoneInfo(APP_TIMEZONE)
except Exception:
    TZ = ZoneInfo("Europe/London")

def now_local():
    return datetime.now(TZ)

# =========================================================
# State / auth
# =========================================================

def init_state():
    defaults = {
        "access_token": None,
        "refresh_token": None,
        "user_email": None,
        "page": "Today",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def save_session(result):
    if not getattr(result, "session", None) or not getattr(result, "user", None):
        return
    st.session_state.access_token = result.session.access_token
    st.session_state.refresh_token = result.session.refresh_token
    st.session_state.user_email = result.user.email
    supabase.postgrest.auth(result.session.access_token)

def clear_session():
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state.user_email = None
    try:
        supabase.postgrest.auth(None)
    except Exception:
        pass

def restore_session():
    if st.session_state.access_token:
        try:
            supabase.postgrest.auth(st.session_state.access_token)
        except Exception:
            clear_session()

def current_user_id():
    if not AUTH_REQUIRED:
        return PUBLIC_PROFILE_ID or None

    try:
        result = supabase.auth.get_user()
        if result and result.user:
            return str(result.user.id)
    except Exception:
        return None
    return None

def render_login():
    render_html(
        """
        <section class="login-hero">
          <div>
            <div class="kicker on-dark">YOUR PERSONAL OPERATING SYSTEM</div>
            <h1>LOCK IN<br><span>90</span></h1>
            <p>Train, focus, build, organise and review — from one calm interface.</p>
          </div>
          <div class="login-orb">90</div>
        </section>
        """
    )

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("### Log in")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Log in", type="primary", use_container_width=True):
            try:
                result = supabase.auth.sign_in_with_password(
                    {"email": email.strip(), "password": password}
                )
                save_session(result)
                st.rerun()
            except Exception as exc:
                st.error(f"Login failed: {exc}")

    with right:
        st.markdown("### Create account")
        email = st.text_input("Email ", key="signup_email")
        password = st.text_input("Password ", type="password", key="signup_password")
        if st.button("Create account", use_container_width=True):
            try:
                result = supabase.auth.sign_up(
                    {"email": email.strip(), "password": password}
                )
                if getattr(result, "session", None):
                    save_session(result)
                    st.rerun()
                else:
                    st.success("Account created. Check your email if confirmation is enabled.")
            except Exception as exc:
                st.error(f"Sign up failed: {exc}")

# =========================================================
# HTML helpers
# =========================================================

def render_html(markup: str):
    st.markdown(textwrap.dedent(markup).strip(), unsafe_allow_html=True)

def safe(value):
    return html.escape("" if value is None else str(value))

# =========================================================
# Database
# =========================================================

def first_row(table, filters):
    query = supabase.table(table).select("*")
    for key, value in filters.items():
        query = query.eq(key, value)
    response = query.limit(1).execute()
    return response.data[0] if response.data else None

def get_program(user_id):
    response = (
        supabase.table("lockin_programs")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "active")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None

def create_program(user_id, values):
    start = values["start_date"]
    payload = {
        "user_id": user_id,
        "start_date": str(start),
        "end_date": str(start + timedelta(days=89)),
        "goal": values["goal"].strip(),
        "status": "active",
        "calorie_target": int(values["calorie_target"]),
        "protein_target": int(values["protein_target"]),
        "study_target": int(values["study_target"]),
        "business_target": int(values["business_target"]),
        "art_target": int(values["art_target"]),
        "room_target": int(values["room_target"]),
        "wake_target": str(values["wake_target"]),
        "bed_target": str(values["bed_target"]),
    }
    supabase.table("lockin_programs").insert(payload).execute()

def update_program(user_id, program_id, values):
    payload = {
        "goal": values["goal"].strip(),
        "calorie_target": int(values["calorie_target"]),
        "protein_target": int(values["protein_target"]),
        "study_target": int(values["study_target"]),
        "business_target": int(values["business_target"]),
        "art_target": int(values["art_target"]),
        "room_target": int(values["room_target"]),
        "wake_target": str(values["wake_target"]),
        "bed_target": str(values["bed_target"]),
    }
    (
        supabase.table("lockin_programs")
        .update(payload)
        .eq("id", program_id)
        .eq("user_id", user_id)
        .execute()
    )

def get_daily_log(user_id, log_date):
    return first_row("daily_lockin", {"user_id": user_id, "log_date": str(log_date)})

def save_daily_log(user_id, log_date, values):
    existing = get_daily_log(user_id, log_date)
    payload = {
        "user_id": user_id,
        "log_date": str(log_date),
        **values,
        "updated_at": datetime.utcnow().isoformat(),
    }

    if existing:
        (
            supabase.table("daily_lockin")
            .update(payload)
            .eq("id", existing["id"])
            .eq("user_id", user_id)
            .execute()
        )
    else:
        supabase.table("daily_lockin").insert(payload).execute()

def get_logs(user_id):
    response = (
        supabase.table("daily_lockin")
        .select("*")
        .eq("user_id", user_id)
        .order("log_date", desc=False)
        .execute()
    )
    return response.data or []

def get_tasks(user_id):
    response = (
        supabase.table("lockin_tasks")
        .select("*")
        .eq("user_id", user_id)
        .order("completed", desc=False)
        .order("task_date", desc=False)
        .order("task_time", desc=False)
        .execute()
    )
    return response.data or []

def add_task(
    user_id,
    title,
    notes,
    priority,
    task_date,
    task_time,
    task_end_time,
    category,
):
    supabase.table("lockin_tasks").insert(
        {
            "user_id": user_id,
            "title": title.strip(),
            "notes": notes.strip(),
            "priority": priority,
            "task_date": str(task_date),
            "task_time": str(task_time) if task_time else None,
            "task_end_time": str(task_end_time) if task_end_time else None,
            "category": category,
            "completed": False,
        }
    ).execute()

def get_workouts(user_id):
    response = (
        supabase.table("workouts")
        .select("*")
        .eq("user_id", user_id)
        .order("workout_date", desc=True)
        .limit(100)
        .execute()
    )
    return response.data or []

def get_focus_sessions(user_id):
    response = (
        supabase.table("focus_sessions")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    return response.data or []

def get_body_weights(user_id):
    response = (
        supabase.table("body_weights")
        .select("*")
        .eq("user_id", user_id)
        .order("log_date", desc=False)
        .execute()
    )
    return response.data or []

def save_body_weight(user_id, log_date, weight_kg):
    existing = first_row(
        "body_weights",
        {
            "user_id": user_id,
            "log_date": str(log_date),
        },
    )

    payload = {
        "user_id": user_id,
        "log_date": str(log_date),
        "weight_kg": float(weight_kg),
        "updated_at": datetime.utcnow().isoformat(),
    }

    if existing:
        (
            supabase.table("body_weights")
            .update(payload)
            .eq("id", existing["id"])
            .eq("user_id", user_id)
            .execute()
        )
    else:
        supabase.table("body_weights").insert(payload).execute()

def get_inbox(user_id):
    response = (
        supabase.table("lockin_inbox")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    return response.data or []

def add_inbox(user_id, content, category):
    supabase.table("lockin_inbox").insert(
        {
            "user_id": user_id,
            "content": content.strip(),
            "category": category,
            "status": "open",
        }
    ).execute()

def get_weekly_reviews(user_id):
    response = (
        supabase.table("weekly_reviews")
        .select("*")
        .eq("user_id", user_id)
        .order("week_start", desc=True)
        .execute()
    )
    return response.data or []

# =========================================================
# Calendar helpers
# =========================================================

def task_start(task):
    task_date = datetime.strptime(str(task["task_date"]), "%Y-%m-%d").date()
    if task.get("task_time"):
        raw = str(task["task_time"])
        try:
            task_time = datetime.strptime(raw[:8], "%H:%M:%S").time()
        except ValueError:
            task_time = datetime.strptime(raw[:5], "%H:%M").time()
    else:
        task_time = time(9, 0)
    return datetime.combine(task_date, task_time)

def task_end(task):
    start = task_start(task)
    raw = task.get("task_end_time")

    if not raw:
        return start + timedelta(minutes=30)

    try:
        end_time = datetime.strptime(str(raw)[:8], "%H:%M:%S").time()
    except ValueError:
        end_time = datetime.strptime(str(raw)[:5], "%H:%M").time()

    end = datetime.combine(start.date(), end_time)

    if end <= start:
        end += timedelta(days=1)

    return end

def google_calendar_url(task):
    start = task_start(task)
    end = task_end(task)
    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={quote(task['title'])}"
        f"&dates={start.strftime('%Y%m%dT%H%M%S')}/{end.strftime('%Y%m%dT%H%M%S')}"
        f"&details={quote(task.get('notes') or '')}"
    )

def outlook_calendar_url(task):
    start = task_start(task)
    end = task_end(task)
    return (
        "https://outlook.office.com/calendar/0/deeplink/compose?path=/calendar/action/compose"
        f"&subject={quote(task['title'])}"
        f"&body={quote(task.get('notes') or '')}"
        f"&startdt={quote(start.isoformat())}"
        f"&enddt={quote(end.isoformat())}"
    )

def task_ics(task):
    start = task_start(task)
    end = task_end(task)
    title = (task["title"] or "").replace("\n", " ")
    notes = (task.get("notes") or "").replace("\n", "\\n")
    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//LOCK IN 90//EN
BEGIN:VEVENT
SUMMARY:{title}
DESCRIPTION:{notes}
DTSTART:{start.strftime('%Y%m%dT%H%M%S')}
DTEND:{end.strftime('%Y%m%dT%H%M%S')}
END:VEVENT
END:VCALENDAR
"""

# =========================================================
# Scoring / logic
# =========================================================

def target(program, key, default):
    value = program.get(key) if program else None
    return int(value) if value is not None else default

def native_daily_score(log, program):
    """Match the iPhone's 9-part Lockzilla daily score."""
    if not log:
        return 0

    if log.get("daily_score") is not None:
        try:
            return max(0, min(100, int(log.get("daily_score"))))
        except (TypeError, ValueError):
            pass

    checks = [
        bool(log.get("wake_by_8")),
        bool(log.get("lunch_cardio")),
        bool(log.get("evening_training")),
        bool(log.get("cooked")),
        int(log.get("study_minutes") or 0) >= 60,
        int(log.get("business_minutes") or 0) >= 45,
        int(log.get("art_minutes") or 0) >= 30,
        bool(log.get("room_tidy")),
        bool(log.get("bed_by_23")),
    ]

    return int(sum(checks) / len(checks) * 100)


def score_log(log, program):
    """Compatibility helper for older UI code."""
    score = native_daily_score(log, program)
    return score, 100


def current_streak(logs, program):
    lookup = {
        date.fromisoformat(row["log_date"]): row
        for row in logs
    }

    d = now_local().date()

    # Match the iPhone: if today is not yet a strong day,
    # continue checking from yesterday.
    if native_daily_score(lookup.get(d), program) < 70:
        d -= timedelta(days=1)

    value = 0

    while d in lookup:
        if native_daily_score(lookup[d], program) < 70:
            break

        value += 1
        d -= timedelta(days=1)

    return value


def next_action(today_log, program):
    current = now_local().time()

    actions = [
        (time(8, 0), "Wake", "Start the day clean", bool(today_log.get("wake_by_8")), "Morning"),
        (time(12, 0), "Lunch movement", "20–30 minutes", bool(today_log.get("lunch_cardio")), "Training"),
        (time(17, 15), "Evening gym", "Your own session", bool(today_log.get("evening_training")), "Training"),
        (time(18, 30), "Cook", "Make dinner", bool(today_log.get("cooked")), "Life"),
        (time(19, 30), "Study", f"{target(program, 'study_target', 60)} minutes", int(today_log.get("study_minutes") or 0) >= target(program, "study_target", 60), "Focus"),
        (time(20, 45), "Business", f"{target(program, 'business_target', 45)} minutes", int(today_log.get("business_minutes") or 0) >= target(program, "business_target", 45), "Focus"),
        (time(21, 30), "Art", f"{target(program, 'art_target', 30)} minutes", int(today_log.get("art_minutes") or 0) >= target(program, "art_target", 30), "Focus"),
        (time(22, 0), "Room reset", f"{target(program, 'room_target', 15)} minutes", bool(today_log.get("room_tidy")), "Reset"),
        (time(23, 0), "Bed", "Protect tomorrow", bool(today_log.get("bed_by_23")), "Recovery"),
    ]

    # Prefer the first incomplete block whose scheduled time has arrived.
    for scheduled, name, detail, completed, category in actions:
        if scheduled <= current and not completed:
            return name, detail, scheduled.strftime("%H:%M"), category

    # Otherwise show the next upcoming incomplete block.
    for scheduled, name, detail, completed, category in actions:
        if not completed:
            return name, detail, scheduled.strftime("%H:%M"), category

    return "Day complete", "Everything planned is done", "✓", "Complete"

def routine_rows(today_log, program):
    return [
        ("08:00", "Wake", "Morning", bool(today_log.get("wake_by_8"))),
        ("09:00", "Work", "Work", now_local().time() >= time(17, 15)),
        ("12:30", "Lunch movement", "Training", bool(today_log.get("lunch_cardio"))),
        ("17:30", "Gym", "Training", bool(today_log.get("evening_training"))),
        ("18:30", "Cook", "Life", bool(today_log.get("cooked"))),
        ("19:30", "Study", "Focus", int(today_log.get("study_minutes") or 0) >= target(program, "study_target", 60)),
        ("20:45", "Business", "Focus", int(today_log.get("business_minutes") or 0) >= target(program, "business_target", 45)),
        ("21:30", "Art", "Focus", int(today_log.get("art_minutes") or 0) >= target(program, "art_target", 30)),
        ("22:00", "Room reset", "Reset", bool(today_log.get("room_tidy"))),
        ("23:00", "Sleep", "Recovery", bool(today_log.get("bed_by_23"))),
    ]

# =========================================================
# Components
# =========================================================

def nav():
    pages = ["Today", "Focus", "Training", "Tasks", "Review"]
    icons = {"Today": "⌂", "Focus": "◎", "Training": "◫", "Tasks": "✓", "Review": "↗"}
    cols = st.columns(len(pages), gap="small")
    for col, page in zip(cols, pages):
        with col:
            if st.button(
                f"{icons[page]}  {page}",
                key=f"nav_{page}",
                type="primary" if st.session_state.page == page else "secondary",
                use_container_width=True,
            ):
                st.session_state.page = page
                st.rerun()

def stat_grid(items):
    cards = []
    for label, value, hint in items:
        cards.append(
            (
                '<article class="mini-stat">'
                f'<div class="mini-stat-label">{safe(label)}</div>'
                f'<div class="mini-stat-value">{safe(value)}</div>'
                f'<div class="mini-stat-hint">{safe(hint)}</div>'
                '</article>'
            )
        )
    render_html('<section class="mini-stat-grid">' + "".join(cards) + '</section>')

def sync_strip():
    render_html(
        """
        <section class="sync-strip">
          <div class="sync-dot"></div>
          <div>
            <strong>LOCKZILLA CLOUD</strong>
            <span>iPhone + Streamlit · Supabase connected</span>
          </div>
          <b>SYNCED</b>
        </section>
        """
    )


def today_progress_card(day_num, day_pct, programme_pct, streak):
    ring = max(0, min(100, int(day_pct)))
    journey = max(0, min(100, int(programme_pct)))

    render_html(
        f"""
        <section class="today-progress">
          <div class="today-progress-copy">
            <div class="kicker">TODAY'S POSITION</div>
            <div class="today-score-line">
              <strong>{ring}%</strong>
              <span>daily score</span>
            </div>
            <div class="today-progress-meta">
              <span>DAY {int(day_num)} / 90</span>
              <span>{int(streak)} DAY STREAK</span>
            </div>
          </div>
          <div class="today-rings">
            <div class="score-ring" style="--score:{ring * 3.6}deg">
              <div><b>{ring}%</b><small>TODAY</small></div>
            </div>
            <div class="journey-bar">
              <div class="journey-label">
                <span>90-DAY JOURNEY</span>
                <b>{journey}%</b>
              </div>
              <div class="journey-track"><i style="width:{journey}%"></i></div>
            </div>
          </div>
        </section>
        """
    )


def review_momentum_hero(current_streak_value, best_streak_value, avg_score, strong_days, programme_day):
    render_html(
        f"""
        <section class="review-momentum">
          <div class="review-momentum-copy">
            <div class="kicker on-dark">MOMENTUM</div>
            <h2>{int(current_streak_value)} <span>DAY STREAK</span></h2>
            <p>Strong days are 70%+ completion. Keep stacking evidence.</p>
          </div>
          <div class="review-momentum-grid">
            <div><span>BEST</span><b>{int(best_streak_value)}</b><small>days</small></div>
            <div><span>AVG SCORE</span><b>{int(avg_score)}%</b><small>logged days</small></div>
            <div><span>STRONG</span><b>{int(strong_days)}</b><small>days</small></div>
            <div><span>PROGRAMME</span><b>D{int(programme_day)}</b><small>of 90</small></div>
          </div>
        </section>
        """
    )


def milestone_strip(programme_day):
    milestones = [7, 30, 60, 90]
    pieces = []

    for day in milestones:
        unlocked = programme_day >= day
        cls = "unlocked" if unlocked else "locked"
        icon = "✓" if unlocked else str(day)
        pieces.append(
            f"""
            <div class="milestone {cls}">
              <div>{icon}</div>
              <span>DAY {day}</span>
            </div>
            """
        )

    render_html(
        '<section class="milestone-card">'
        '<div class="milestone-copy"><span>MILESTONES</span><strong>The road to Day 90</strong></div>'
        '<div class="milestone-row">' + "".join(pieces) + '</div></section>'
    )


def activity_feed(focus_sessions, workouts, body_weights):
    events = []

    for row in focus_sessions[:8]:
        when = row.get("completed_at") or row.get("created_at") or row.get("session_date")
        events.append(
            (
                str(when or ""),
                "FOCUS",
                row.get("focus_type") or row.get("block_title") or "Focus",
                f"{int(row.get('minutes') or row.get('duration_minutes') or 0)} min",
            )
        )

    for row in workouts[:8]:
        when = row.get("created_at") or row.get("workout_date")
        events.append(
            (
                str(when or ""),
                "TRAINING",
                row.get("session") or "Workout",
                f"{int(row.get('duration_minutes') or 0)} min",
            )
        )

    for row in reversed(body_weights[-8:]):
        events.append(
            (
                str(row.get("log_date") or ""),
                "BODY",
                "Weigh-in",
                f"{float(row.get('weight_kg') or 0):.1f} kg",
            )
        )

    events = sorted(events, key=lambda x: x[0], reverse=True)[:8]

    if not events:
        return

    rows = []
    for _, category, title, detail in events:
        rows.append(
            f"""
            <div class="activity-row">
              <span>{safe(category)}</span>
              <strong>{safe(title)}</strong>
              <b>{safe(detail)}</b>
            </div>
            """
        )

    render_html(
        '<section class="activity-card">' + "".join(rows) + "</section>"
    )


def command_card(name, detail, when, category):
    render_html(
        f"""
        <section class="command-card">
          <div class="command-top">
            <div>
              <div class="command-kicker">NO NEGOTIATION · NEXT ACTION</div>
              <div class="command-title">{safe(name)}</div>
              <div class="command-detail">{safe(detail)}</div>
            </div>
            <div class="command-time">{safe(when)}</div>
          </div>
          <div class="command-footer">
            <span>{safe(category)}</span>
            <strong>Do the next thing. Nothing else.</strong>
          </div>
        </section>
        """
    )

def timeline_component(rows):
    pieces = []
    for when, label, category, done in rows:
        state = "done" if done else "pending"
        icon = "✓" if done else "•"
        pieces.append(
            (
                f'<div class="timeline-item {state}">'
                f'<div class="timeline-time">{safe(when)}</div>'
                f'<div class="timeline-rail"><span>{icon}</span></div>'
                '<div class="timeline-copy">'
                f'<strong>{safe(label)}</strong>'
                f'<small>{safe(category)}</small>'
                '</div>'
                '</div>'
            )
        )
    render_html('<section class="timeline-list">' + "".join(pieces) + '</section>')

def focus_cards(program):
    cards = [
        ("STUDY", target(program, "study_target", 60), "Learn"),
        ("BUSINESS", target(program, "business_target", 45), "Build"),
        ("ART", target(program, "art_target", 30), "Create"),
        ("ROOM", target(program, "room_target", 15), "Reset"),
    ]
    blocks = []
    for label, mins, verb in cards:
        blocks.append(
            (
                '<article class="focus-card">'
                f'<div class="focus-card-label">{safe(label)}</div>'
                f'<div class="focus-card-value">{mins}<span> min</span></div>'
                f'<div class="focus-card-verb">{safe(verb)}</div>'
                '</article>'
            )
        )
    render_html('<section class="focus-card-grid">' + "".join(blocks) + '</section>')

def focus_timer(program):
    study = target(program, "study_target", 60)
    business = target(program, "business_target", 45)
    art = target(program, "art_target", 30)
    room = target(program, "room_target", 15)

    components.html(
        f"""
        <div id="timer-shell">
          <style>
            *{{box-sizing:border-box;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
            body{{margin:0;background:transparent;color:#111318}}
            .timer{{background:#101216;border-radius:26px;padding:22px;color:#fff;box-shadow:0 20px 50px rgba(15,17,20,.18)}}
            .top{{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}}
            .eyebrow{{font-size:11px;font-weight:900;letter-spacing:.14em;color:rgba(255,255,255,.45)}}
            .mode{{font-size:20px;font-weight:850;margin-top:5px}}
            .clock{{font-size:46px;line-height:1;font-weight:950;letter-spacing:-2px}}
            .presets{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:20px}}
            button{{border:0;border-radius:13px;padding:11px 8px;font-weight:800;cursor:pointer}}
            .preset{{background:rgba(255,255,255,.08);color:#fff}}
            .preset:hover{{background:rgba(255,255,255,.14)}}
            .controls{{display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:8px;margin-top:10px}}
            .start{{background:#fff;color:#111318}}.secondary{{background:rgba(255,255,255,.08);color:#fff}}
            .quote{{margin-top:17px;color:rgba(255,255,255,.46);font-size:12px}}
            @media(max-width:560px){{
              .presets{{grid-template-columns:repeat(2,1fr)}}
              .clock{{font-size:38px}}
              .timer{{padding:18px}}
            }}
          </style>
          <div class="timer">
            <div class="top">
              <div>
                <div class="eyebrow">FOCUS MODE</div>
                <div class="mode" id="mode">Study · {study} minutes</div>
              </div>
              <div class="clock" id="clock">{study:02d}:00</div>
            </div>
            <div class="presets">
              <button class="preset" onclick="setTimer({study},'Study')">Study {study}</button>
              <button class="preset" onclick="setTimer({business},'Business')">Business {business}</button>
              <button class="preset" onclick="setTimer({art},'Art')">Art {art}</button>
              <button class="preset" onclick="setTimer({room},'Room reset')">Room {room}</button>
            </div>
            <div class="controls">
              <button class="start" onclick="startTimer()">Start now</button>
              <button class="secondary" onclick="pauseTimer()">Pause</button>
              <button class="secondary" onclick="resetTimer()">Reset</button>
            </div>
            <div class="quote">One block. One task. Finish before switching.</div>
          </div>
          <script>
            let initial={study}*60;
            let remaining=initial;
            let timer=null;

            function draw(){{
              const m=Math.floor(remaining/60).toString().padStart(2,'0');
              const s=(remaining%60).toString().padStart(2,'0');
              document.getElementById('clock').innerText=m+':'+s;
            }}

            function setTimer(mins,label){{
              pauseTimer();
              initial=mins*60;
              remaining=initial;
              document.getElementById('mode').innerText=label+' · '+mins+' minutes';
              draw();
            }}

            function startTimer(){{
              if(timer) return;
              timer=setInterval(()=>{{
                if(remaining>0){{remaining--;draw();}}
                else{{
                  pauseTimer();
                  document.getElementById('mode').innerText='Block complete ✓';
                }}
              }},1000);
            }}

            function pauseTimer(){{
              if(timer){{clearInterval(timer);timer=null;}}
            }}

            function resetTimer(){{
              pauseTimer();
              remaining=initial;
              draw();
            }}
          </script>
        </div>
        """,
        height=260,
        scrolling=False,
    )

def ninety_day_map(program, logs):
    start = date.fromisoformat(program["start_date"])
    by_date = {date.fromisoformat(row["log_date"]): row for row in logs}
    today = now_local().date()
    blocks = []

    for i in range(90):
        d = start + timedelta(days=i)
        day_num = i + 1

        if d > today:
            cls = "future"
            label = "Future"
        elif d in by_date:
            pct = native_daily_score(by_date[d], program)
            if pct >= 90:
                cls = "excellent"
            elif pct >= 75:
                cls = "strong"
            elif pct >= 50:
                cls = "partial"
            else:
                cls = "low"
            label = f"{pct}%"
        else:
            cls = "empty"
            label = "No log"

        today_cls = " today" if d == today else ""
        blocks.append(
            f'<div class="day-dot {cls}{today_cls}" title="Day {day_num} · {d.strftime("%d %b")} · {label}">{day_num}</div>'
        )

    render_html('<section class="day-map">' + "".join(blocks) + '</section>')

# =========================================================
# TODAY
# =========================================================

def render_today(user_id):
    program = get_program(user_id)

    if not program:
        render_html(
            """
            <section class="hero-main">
              <div>
                <div class="kicker on-dark">YOUR NEXT 90 DAYS</div>
                <h1>BUILD THE<br><span>SYSTEM.</span></h1>
                <p>Set the standards once. Then stop negotiating with yourself every day.</p>
              </div>
              <div class="hero-disc"><strong>90</strong><small>DAYS</small></div>
            </section>
            """
        )

        with st.container(border=True):
            st.markdown("### Set up your programme")
            start_date = st.date_input("Day 1", value=now_local().date())
            goal = st.text_area(
                "Main goal",
                placeholder="Build discipline, train consistently, study, build my business...",
            )
            left, right = st.columns(2)
            with left:
                calorie_target = st.number_input("Daily calories", 1000, 6000, 2200, 50)
                protein_target = st.number_input("Daily protein (g)", 40, 350, 150, 5)
                wake_target = st.time_input("Wake target", value=time(8, 0))
                bed_target = st.time_input("Bed target", value=time(23, 0))
            with right:
                study_target = st.number_input("Study (min)", 0, 300, 60, 5)
                business_target = st.number_input("Business (min)", 0, 300, 45, 5)
                art_target = st.number_input("Art (min)", 0, 300, 30, 5)
                room_target = st.number_input("Room reset (min)", 0, 120, 15, 5)

            if st.button("Start my 90 days", type="primary", use_container_width=True):
                create_program(
                    user_id,
                    {
                        "start_date": start_date,
                        "goal": goal,
                        "calorie_target": calorie_target,
                        "protein_target": protein_target,
                        "study_target": study_target,
                        "business_target": business_target,
                        "art_target": art_target,
                        "room_target": room_target,
                        "wake_target": wake_target,
                        "bed_target": bed_target,
                    },
                )
                st.rerun()
        return

    today = now_local().date()
    start = date.fromisoformat(program["start_date"])
    end = date.fromisoformat(program["end_date"])
    day_raw = (today - start).days + 1
    day_num = max(1, min(90, day_raw))
    programme_pct = max(0, min(100, round(day_raw / 90 * 100)))

    log = get_daily_log(user_id, today) or {}
    logs = get_logs(user_id)
    day_pct = native_daily_score(log, program)
    next_name, next_detail, next_time, next_category = next_action(log, program)

    render_html(
        f"""
        <section class="hero-main">
          <div>
            <div class="kicker on-dark">LOCK IN 90</div>
            <h1>DAY {day_num}<br><span>OF 90.</span></h1>
            <p>{safe(program.get("goal") or "Follow the system. Keep moving.")}</p>
          </div>
          <div class="hero-disc"><strong>{programme_pct}%</strong><small>JOURNEY</small></div>
        </section>
        """
    )

    streak_value = current_streak(logs, program)

    sync_strip()
    today_progress_card(
        day_num,
        day_pct,
        programme_pct,
        streak_value,
    )

    stat_grid(
        [
            ("SLEEP", f"{float(log.get('sleep_hours') or 0):.1f}h", "recovery"),
            (
                "FOCUS",
                f"{int(log.get('study_minutes') or 0) + int(log.get('business_minutes') or 0) + int(log.get('art_minutes') or 0)}m",
                "today",
            ),
            ("NEXT", next_time, next_name),
            ("FINISH", end.strftime("%d %b"), "day 90"),
        ]
    )

    command_card(next_name, next_detail, next_time, next_category)

    left, right = st.columns([1.15, .85], gap="large")

    with left:
        st.markdown('<div class="section-head"><span>TODAY</span><h2>Your timeline</h2></div>', unsafe_allow_html=True)
        timeline_component(routine_rows(log, program))

    with right:
        st.markdown('<div class="section-head"><span>QUICK CHECK-IN</span><h2>Log the day</h2></div>', unsafe_allow_html=True)

        with st.form("quick_today_form"):
            wake = st.checkbox("Wake on time", value=bool(log.get("wake_by_8")))
            cardio = st.checkbox("Lunch movement", value=bool(log.get("lunch_cardio")))
            training = st.checkbox("Evening training / recovery", value=bool(log.get("evening_training")))
            cooked = st.checkbox("Cooked / planned meal", value=bool(log.get("cooked")))
            room = st.checkbox("Room reset", value=bool(log.get("room_tidy")))
            bed = st.checkbox("Bed on time", value=bool(log.get("bed_by_23")))

            study = st.number_input("Study minutes", 0, 600, int(log.get("study_minutes") or 0), 5)
            business = st.number_input("Business minutes", 0, 600, int(log.get("business_minutes") or 0), 5)
            art = st.number_input("Art minutes", 0, 600, int(log.get("art_minutes") or 0), 5)
            calories_actual = st.number_input("Calories", 0, 10000, int(log.get("calories_actual") or 0), 50)
            protein_actual = st.number_input("Protein (g)", 0, 500, int(log.get("protein_actual") or 0), 5)
            sleep_hours = st.number_input("Sleep hours", 0.0, 14.0, float(log.get("sleep_hours") or 0.0), 0.25)

            cal_hit = calories_actual > 0 and abs(calories_actual - target(program, "calorie_target", 2200)) <= max(150, int(target(program, "calorie_target", 2200) * .08))
            protein_hit = protein_actual >= target(program, "protein_target", 150)

            notes = st.text_area(
                "Quick note",
                value=log.get("notes") or "",
                placeholder="One line is enough.",
            )

            if st.form_submit_button("Save today", type="primary", use_container_width=True):
                native_values = {
                    "wake_by_8": wake,
                    "lunch_cardio": cardio,
                    "evening_training": training,
                    "cooked": cooked,
                    "study_minutes": study,
                    "business_minutes": business,
                    "art_minutes": art,
                    "room_tidy": room,
                    "bed_by_23": bed,
                }

                preview_score = int(
                    sum(
                        [
                            native_values["wake_by_8"],
                            native_values["lunch_cardio"],
                            native_values["evening_training"],
                            native_values["cooked"],
                            native_values["study_minutes"] >= 60,
                            native_values["business_minutes"] >= 45,
                            native_values["art_minutes"] >= 30,
                            native_values["room_tidy"],
                            native_values["bed_by_23"],
                        ]
                    )
                    / 9
                    * 100
                )

                save_daily_log(
                    user_id,
                    today,
                    {
                        "wake_by_8": wake,
                        "lunch_cardio": cardio,
                        "evening_training": training,
                        "cooked": cooked,
                        "calorie_target_hit": cal_hit,
                        "protein_target_hit": protein_hit,
                        "calories_actual": calories_actual,
                        "protein_actual": protein_actual,
                        "study_minutes": study,
                        "business_minutes": business,
                        "art_minutes": art,
                        "room_tidy": room,
                        "bed_by_23": bed,
                        "sleep_hours": sleep_hours,
                        "notes": notes.strip(),
                        "daily_score": preview_score,
                    },
                )
                st.success("Day saved.")
                st.rerun()

    st.markdown(
        '<div class="section-head"><span>BODY</span><h2>Body weight</h2></div>',
        unsafe_allow_html=True,
    )

    weights = get_body_weights(user_id)
    latest_weight = weights[-1]["weight_kg"] if weights else None
    first_weight = weights[0]["weight_kg"] if weights else None

    if latest_weight is not None:
        change = float(latest_weight) - float(first_weight)
        recent_weights = [
            float(row["weight_kg"])
            for row in weights[-7:]
        ]
        seven_day_avg = (
            sum(recent_weights) / len(recent_weights)
            if recent_weights
            else float(latest_weight)
        )

        stat_grid(
            [
                ("CURRENT", f"{float(latest_weight):.1f} kg", "latest"),
                ("CHANGE", f"{change:+.1f} kg", "since first weigh-in"),
                ("7-DAY AVG", f"{seven_day_avg:.1f} kg", "trend"),
                ("WEIGH-INS", f"{len(weights)}", "synced entries"),
            ]
        )

    with st.form("body_weight_form"):
        weight_date = st.date_input(
            "Weight date",
            value=today,
            key="weight_date",
        )
        weight_kg = st.number_input(
            "Weight (kg)",
            min_value=20.0,
            max_value=400.0,
            value=float(latest_weight or 80.0),
            step=0.1,
        )

        if st.form_submit_button(
            "Save weight",
            type="primary",
            use_container_width=True,
        ):
            save_body_weight(
                user_id,
                weight_date,
                weight_kg,
            )
            st.success("Weight synced.")
            st.rerun()

    st.markdown('<div class="section-head"><span>INBOX</span><h2>Brain dump</h2></div>', unsafe_allow_html=True)
    st.caption("Get it out of your head. Decide what it is later.")

    with st.form("brain_dump_form"):
        c1, c2 = st.columns([4, 1])
        with c1:
            brain = st.text_input(
                "Brain dump",
                placeholder="Idea, thing to buy, study topic, business thought, reminder...",
                label_visibility="collapsed",
            )
        with c2:
            brain_category = st.selectbox(
                "Category",
                ["General", "Study", "Business", "Personal", "Idea"],
                label_visibility="collapsed",
            )
        if st.form_submit_button("Capture", use_container_width=True):
            if brain.strip():
                add_inbox(user_id, brain, brain_category)
                st.rerun()

    inbox = [x for x in get_inbox(user_id) if x.get("status") == "open"][:6]
    if inbox:
        chips = []
        for item in inbox:
            chips.append(
                f'<div class="inbox-chip"><span>{safe(item.get("category"))}</span>{safe(item.get("content"))}</div>'
            )
        render_html('<section class="inbox-grid">' + "".join(chips) + '</section>')

# =========================================================
# FOCUS
# =========================================================

def render_focus(user_id):
    program = get_program(user_id)
    if not program:
        st.info("Start the programme on Today first.")
        return

    render_html(
        """
        <section class="sub-hero focus-bg">
          <div class="kicker on-dark">FOCUS MODE</div>
          <h1>ONE THING.<br>UNTIL IT'S DONE.</h1>
          <p>Study, business, art and your room reset — without turning the evening into a complicated system.</p>
        </section>
        """
    )

    focus_cards(program)

    log = get_daily_log(user_id, now_local().date()) or {}
    name, detail, when, category = next_action(log, program)
    if category == "Focus" or name == "Room reset":
        command_card(name, detail, when, category)

    st.markdown('<div class="section-head"><span>TIMER</span><h2>Start the block</h2></div>', unsafe_allow_html=True)
    focus_timer(program)

    st.markdown('<div class="section-head"><span>LOG</span><h2>Finished a block?</h2></div>', unsafe_allow_html=True)
    with st.form("focus_log_form"):
        c1, c2 = st.columns(2)
        with c1:
            kind = st.selectbox("Type", ["Study", "Business", "Art", "Room reset"])
        with c2:
            minutes = st.number_input("Minutes", 0, 300, 30, 5)
        note = st.text_input("Optional note")

        if st.form_submit_button("Save focus block", type="primary", use_container_width=True):
            completed_at = now_local()

            supabase.table("focus_sessions").insert(
                {
                    "user_id": user_id,
                    "session_date": str(completed_at.date()),
                    "focus_type": kind,
                    "minutes": minutes,
                    "note": note.strip(),
                    "block_title": kind,
                    "duration_minutes": minutes,
                    "completed_at": completed_at.isoformat(),
                }
            ).execute()

            # Also update today's daily totals.
            today_log = get_daily_log(user_id, now_local().date()) or {}
            values = {
                "wake_by_8": bool(today_log.get("wake_by_8")),
                "lunch_cardio": bool(today_log.get("lunch_cardio")),
                "evening_training": bool(today_log.get("evening_training")),
                "cooked": bool(today_log.get("cooked")),
                "calorie_target_hit": bool(today_log.get("calorie_target_hit")),
                "protein_target_hit": bool(today_log.get("protein_target_hit")),
                "calories_actual": int(today_log.get("calories_actual") or 0),
                "protein_actual": int(today_log.get("protein_actual") or 0),
                "study_minutes": int(today_log.get("study_minutes") or 0),
                "business_minutes": int(today_log.get("business_minutes") or 0),
                "art_minutes": int(today_log.get("art_minutes") or 0),
                "room_tidy": bool(today_log.get("room_tidy")),
                "bed_by_23": bool(today_log.get("bed_by_23")),
                "sleep_hours": float(today_log.get("sleep_hours") or 0),
                "notes": today_log.get("notes") or "",
            }

            if kind == "Study":
                values["study_minutes"] += minutes
            elif kind == "Business":
                values["business_minutes"] += minutes
            elif kind == "Art":
                values["art_minutes"] += minutes
            elif kind == "Room reset":
                values["room_tidy"] = True

            values["daily_score"] = native_daily_score(
                values,
                program,
            )

            save_daily_log(user_id, now_local().date(), values)
            st.success("Block logged.")
            st.rerun()

    sessions = get_focus_sessions(user_id)[:8]
    if sessions:
        blocks = []
        for s in sessions:
            blocks.append(
                (
                    '<div class="history-row">'
                    f'<div><strong>{safe(s.get("focus_type") or s.get("block_title"))}</strong><span>{safe(s.get("session_date"))}</span></div>'
                    f'<b>{int(s.get("minutes") or s.get("duration_minutes") or 0)} min</b>'
                    '</div>'
                )
            )
        render_html('<section class="history-list">' + "".join(blocks) + '</section>')

# =========================================================
# TRAINING
# =========================================================

def render_training(user_id):
    render_html(
        """
        <section class="sub-hero training-bg">
          <div class="kicker on-dark">TRAINING</div>
          <h1>MOVE.<br>TRAIN. RECOVER.</h1>
          <p>The app gives you structure, not a workout you never asked for.</p>
        </section>
        """
    )

    render_html(
        """
        <section class="training-grid">
          <article class="training-card">
            <div class="training-tag">LUNCH</div>
            <h3>Move</h3>
            <p>Cardio, walking or light movement. Keep it short and sustainable.</p>
            <strong>20–30 min</strong>
          </article>
          <article class="training-card dark">
            <div class="training-tag">AFTER WORK</div>
            <h3>Train</h3>
            <p>Your own gym session. You choose the workout, exercises and intensity.</p>
            <strong>Your session</strong>
          </article>
          <article class="training-card">
            <div class="training-tag">RECOVERY</div>
            <h3>Recover</h3>
            <p>Rest, walk or stretch when recovery is the better choice.</p>
            <strong>Still locked in</strong>
          </article>
        </section>
        """
    )

    st.markdown('<div class="section-head"><span>QUICK LOG</span><h2>Training today</h2></div>', unsafe_allow_html=True)

    with st.form("training_form"):
        c1, c2 = st.columns(2)
        with c1:
            training_date = st.date_input("Date", value=now_local().date(), key="training_date")
            session = st.selectbox(
                "What did you do?",
                ["Lunch movement", "Evening gym", "Both", "Recovery / rest", "Other"],
            )
        with c2:
            duration = st.number_input("Total minutes", 0, 300, 30, 5)
            effort = st.select_slider("How did it feel?", ["Easy", "Good", "Hard", "Very hard"], value="Good")

        note = st.text_area("Optional note", placeholder="Keep it short.")

        if st.form_submit_button("Save training", type="primary", use_container_width=True):
            supabase.table("workouts").insert(
                {
                    "user_id": user_id,
                    "workout_date": str(training_date),
                    "session": session,
                    "exercise": "",
                    "sets": 0,
                    "reps": 0,
                    "weight": 0,
                    "duration_minutes": duration,
                    "notes": effort + (f" — {note.strip()}" if note.strip() else ""),
                }
            ).execute()

            program = get_program(user_id)

            if program:
                day_log = get_daily_log(
                    user_id,
                    training_date,
                ) or {}

                values = {
                    "wake_by_8": bool(day_log.get("wake_by_8")),
                    "lunch_cardio": bool(day_log.get("lunch_cardio")),
                    "evening_training": session not in ["Recovery / rest"],
                    "cooked": bool(day_log.get("cooked")),
                    "calorie_target_hit": bool(day_log.get("calorie_target_hit")),
                    "protein_target_hit": bool(day_log.get("protein_target_hit")),
                    "calories_actual": int(day_log.get("calories_actual") or 0),
                    "protein_actual": int(day_log.get("protein_actual") or 0),
                    "study_minutes": int(day_log.get("study_minutes") or 0),
                    "business_minutes": int(day_log.get("business_minutes") or 0),
                    "art_minutes": int(day_log.get("art_minutes") or 0),
                    "room_tidy": bool(day_log.get("room_tidy")),
                    "bed_by_23": bool(day_log.get("bed_by_23")),
                    "sleep_hours": float(day_log.get("sleep_hours") or 0),
                    "notes": day_log.get("notes") or "",
                }

                if session in ["Lunch movement", "Both"]:
                    values["lunch_cardio"] = True

                if session == "Both":
                    values["evening_training"] = True

                values["daily_score"] = native_daily_score(
                    values,
                    program,
                )

                save_daily_log(
                    user_id,
                    training_date,
                    values,
                )

            st.success("Training saved and daily progress synced.")
            st.rerun()

    workouts = get_workouts(user_id)[:8]
    if workouts:
        st.markdown('<div class="section-head"><span>RECENT</span><h2>Your training</h2></div>', unsafe_allow_html=True)
        blocks = []
        for row in workouts:
            blocks.append(
                (
                    '<div class="history-row">'
                    '<div>'
                    f'<strong>{safe(row.get("session"))}</strong>'
                    f'<span>{safe(row.get("workout_date"))} · {safe(row.get("notes") or "")}</span>'
                    '</div>'
                    f'<b>{int(row.get("duration_minutes") or 0)} min</b>'
                    '</div>'
                )
            )
        render_html('<section class="history-list">' + "".join(blocks) + '</section>')

# =========================================================
# TASKS
# =========================================================

def render_tasks(user_id):
    render_html(
        """
        <section class="sub-hero tasks-bg">
          <div class="kicker on-dark">TASKS + CALENDAR</div>
          <h1>PLAN IT ONCE.<br>PUT IT WHERE YOU USE IT.</h1>
          <p>Keep your task system simple and send important blocks straight to your calendar.</p>
        </section>
        """
    )

    with st.expander("＋ Add a task", expanded=True):
        with st.form("task_form"):
            left, right = st.columns([1.4, 1])
            with left:
                title = st.text_input("Task title")
                task_notes = st.text_area("Notes")
            with right:
                priority = st.selectbox("Priority", ["High", "Medium", "Low"], index=1)
                task_date = st.date_input("Date", value=now_local().date())
                use_time = st.checkbox("Add time range")
                task_time = st.time_input(
                    "Start time",
                    value=time(9, 0),
                    disabled=not use_time,
                )
                task_end_time = st.time_input(
                    "End time",
                    value=time(9, 30),
                    disabled=not use_time,
                )
                category = st.selectbox(
                    "Category",
                    ["Personal", "Work", "Study", "Business", "Gym", "Other"],
                )

            if st.form_submit_button("Save task", type="primary", use_container_width=True):
                if title.strip():
                    add_task(
                        user_id,
                        title,
                        task_notes,
                        priority,
                        task_date,
                        task_time if use_time else None,
                        task_end_time if use_time else None,
                        category,
                    )
                    st.rerun()

    tasks = get_tasks(user_id)
    search = st.text_input("Search", placeholder="Search tasks...")
    show_done = st.checkbox("Show completed", value=False)

    filtered = tasks
    if search.strip():
        needle = search.lower().strip()
        filtered = [
            t for t in filtered
            if needle in (t.get("title") or "").lower()
            or needle in (t.get("notes") or "").lower()
        ]
    if not show_done:
        filtered = [t for t in filtered if not t.get("completed")]

    for task in filtered[:30]:
        task_time_text = ""

        if task.get("task_time"):
            start_text = str(task["task_time"])[:5]
            end_text = (
                str(task.get("task_end_time"))[:5]
                if task.get("task_end_time")
                else None
            )

            task_time_text = (
                f" · {start_text}–{end_text}"
                if end_text
                else f" · {start_text}"
            )
        render_html(
            f"""
            <article class="task-card">
              <div class="task-meta">{safe(task.get("priority"))} · {safe(task.get("category"))} · {safe(task.get("task_date"))}{safe(task_time_text)}</div>
              <div class="task-name">{'✓ ' if task.get('completed') else ''}{safe(task.get("title"))}</div>
              <div class="task-note">{safe(task.get("notes") or "")}</div>
            </article>
            """
        )

        a, b = st.columns(2)
        with a:
            if st.button("Undo" if task.get("completed") else "Done", key=f"done_{task['id']}", use_container_width=True):
                (
                    supabase.table("lockin_tasks")
                    .update({"completed": not task.get("completed")})
                    .eq("id", task["id"])
                    .eq("user_id", user_id)
                    .execute()
                )
                st.rerun()
        with b:
            if st.button("Delete", key=f"delete_{task['id']}", use_container_width=True):
                (
                    supabase.table("lockin_tasks")
                    .delete()
                    .eq("id", task["id"])
                    .eq("user_id", user_id)
                    .execute()
                )
                st.rerun()

        g, o, i = st.columns(3)
        with g:
            st.link_button("Google Calendar", google_calendar_url(task), use_container_width=True)
        with o:
            st.link_button("Outlook", outlook_calendar_url(task), use_container_width=True)
        with i:
            st.download_button(
                "Apple / ICS",
                task_ics(task),
                file_name=f"{task['title'].replace(' ', '_')}.ics",
                mime="text/calendar",
                use_container_width=True,
                key=f"ics_{task['id']}",
            )

    st.markdown('<div class="section-head"><span>INBOX</span><h2>Unsorted thoughts</h2></div>', unsafe_allow_html=True)
    inbox = [x for x in get_inbox(user_id) if x.get("status") == "open"]

    for item in inbox[:20]:
        render_html(
            f"""
            <article class="inbox-row">
              <div><span>{safe(item.get("category"))}</span><strong>{safe(item.get("content"))}</strong></div>
            </article>
            """
        )
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("Plan today", key=f"plan_{item['id']}", use_container_width=True):
                add_task(
                    user_id,
                    item["content"],
                    "",
                    "Medium",
                    now_local().date(),
                    None,
                    None,
                    item.get("category") if item.get("category") in ["Study", "Business", "Personal"] else "Personal",
                )
                supabase.table("lockin_inbox").update({"status": "planned"}).eq("id", item["id"]).eq("user_id", user_id).execute()
                st.rerun()
        with c2:
            if st.button("Done", key=f"inbox_done_{item['id']}", use_container_width=True):
                supabase.table("lockin_inbox").update({"status": "done"}).eq("id", item["id"]).eq("user_id", user_id).execute()
                st.rerun()
        with c3:
            if st.button("Delete", key=f"inbox_delete_{item['id']}", use_container_width=True):
                supabase.table("lockin_inbox").delete().eq("id", item["id"]).eq("user_id", user_id).execute()
                st.rerun()

# =========================================================
# REVIEW
# =========================================================

def render_review(user_id):
    program = get_program(user_id)
    if not program:
        st.info("Start your programme first.")
        return

    render_html(
        """
        <section class="sub-hero review-bg">
          <div class="kicker on-dark">REVIEW</div>
          <h1>SEE THE WORK.<br>ADJUST THE SYSTEM.</h1>
          <p>The goal is not to judge yourself. It is to notice what is actually happening.</p>
        </section>
        """
    )

    logs = get_logs(user_id)
    workouts = get_workouts(user_id)
    focus_sessions = get_focus_sessions(user_id)
    body_weights = get_body_weights(user_id)

    total_focus_minutes = sum(
        int(
            row.get("minutes")
            or row.get("duration_minutes")
            or 0
        )
        for row in focus_sessions
    )

    total_workout_minutes = sum(
        int(row.get("duration_minutes") or 0)
        for row in workouts
    )

    today = now_local().date()
    start_date = date.fromisoformat(program["start_date"])
    programme_day = max(
        1,
        min(90, (today - start_date).days + 1),
    )

    score_values = [
        native_daily_score(row, program)
        for row in logs
    ]
    avg_score_all = (
        round(sum(score_values) / len(score_values))
        if score_values
        else 0
    )
    strong_days = sum(
        1 for value in score_values
        if value >= 70
    )

    lookup = {
        date.fromisoformat(row["log_date"]):
            native_daily_score(row, program)
        for row in logs
    }

    best_streak_value = 0
    running_streak = 0
    cursor = start_date

    while cursor <= today:
        if lookup.get(cursor, 0) >= 70:
            running_streak += 1
            best_streak_value = max(
                best_streak_value,
                running_streak,
            )
        else:
            running_streak = 0

        cursor += timedelta(days=1)

    review_momentum_hero(
        current_streak(logs, program),
        best_streak_value,
        avg_score_all,
        strong_days,
        programme_day,
    )

    stat_grid(
        [
            ("FOCUS", f"{total_focus_minutes} min", f"{len(focus_sessions)} blocks"),
            ("WORKOUTS", f"{len(workouts)}", f"{total_workout_minutes} total min"),
            (
                "WEIGHT",
                f"{float(body_weights[-1]['weight_kg']):.1f} kg"
                if body_weights
                else "—",
                "latest",
            ),
            ("LOGGED DAYS", f"{len(logs)}", "daily records"),
        ]
    )

    milestone_strip(programme_day)

    st.markdown('<div class="section-head"><span>90 DAYS</span><h2>Your map</h2></div>', unsafe_allow_html=True)
    ninety_day_map(program, logs)

    if logs:
        rows = []
        for row in logs:
            rows.append(
                {
                    "date": row["log_date"],
                    "completion": native_daily_score(row, program),
                    "study": int(row.get("study_minutes") or 0),
                    "business": int(row.get("business_minutes") or 0),
                    "art": int(row.get("art_minutes") or 0),
                    "sleep": float(row.get("sleep_hours") or 0),
                }
            )
        df = pd.DataFrame(rows)

        last7 = df.tail(7)
        stat_grid(
            [
                ("7-DAY SCORE", f"{round(last7['completion'].mean())}%", "consistency"),
                ("STUDY", f"{int(last7['study'].sum())} min", "last 7 logged days"),
                ("BUSINESS", f"{int(last7['business'].sum())} min", "last 7 logged days"),
                ("ART", f"{int(last7['art'].sum())} min", "last 7 logged days"),
            ]
        )

        st.markdown('<div class="section-head"><span>TREND</span><h2>Consistency</h2></div>', unsafe_allow_html=True)
        st.line_chart(df.set_index("date")["completion"])

    st.markdown(
        '<div class="section-head"><span>BODY</span><h2>Weight progression</h2></div>',
        unsafe_allow_html=True,
    )

    if body_weights:
        weight_df = pd.DataFrame(
            [
                {
                    "date": row["log_date"],
                    "weight_kg": float(row["weight_kg"]),
                }
                for row in body_weights
            ]
        )

        first_weight = float(body_weights[0]["weight_kg"])
        latest_weight = float(body_weights[-1]["weight_kg"])
        seven = weight_df.tail(7)

        stat_grid(
            [
                ("START", f"{first_weight:.1f} kg", "first weigh-in"),
                ("CURRENT", f"{latest_weight:.1f} kg", "latest weigh-in"),
                ("CHANGE", f"{latest_weight - first_weight:+.1f} kg", "overall"),
                ("7-DAY AVG", f"{seven['weight_kg'].mean():.1f} kg", "recent trend"),
            ]
        )

        st.line_chart(
            weight_df.set_index("date")["weight_kg"]
        )
    else:
        st.info(
            "No body-weight entries yet. Add one on Today or from the iPhone app."
        )

    st.markdown(
        '<div class="section-head"><span>RECENT</span><h2>Activity</h2></div>',
        unsafe_allow_html=True,
    )
    activity_feed(
        focus_sessions,
        workouts,
        body_weights,
    )

    st.markdown('<div class="section-head"><span>WEEKLY REVIEW</span><h2>Close the loop</h2></div>', unsafe_allow_html=True)
    today = now_local().date()
    week_start = today - timedelta(days=today.weekday())
    existing = first_row("weekly_reviews", {"user_id": user_id, "week_start": str(week_start)})

    with st.form("weekly_review_form"):
        win = st.text_area(
            "Biggest win",
            value=(existing or {}).get("biggest_win") or "",
            placeholder="What actually went well?",
        )
        friction = st.text_area(
            "What got in the way?",
            value=(existing or {}).get("friction") or "",
            placeholder="What kept repeating or making things harder?",
        )
        next_focus = st.text_area(
            "One focus for next week",
            value=(existing or {}).get("next_focus") or "",
            placeholder="Choose one improvement, not ten.",
        )
        rating = st.slider(
            "Week rating",
            1,
            10,
            int((existing or {}).get("rating") or 7),
        )

        if st.form_submit_button("Save weekly review", type="primary", use_container_width=True):
            payload = {
                "user_id": user_id,
                "week_start": str(week_start),
                "biggest_win": win.strip(),
                "friction": friction.strip(),
                "next_focus": next_focus.strip(),
                "rating": rating,
                "updated_at": datetime.utcnow().isoformat(),
            }
            if existing:
                supabase.table("weekly_reviews").update(payload).eq("id", existing["id"]).eq("user_id", user_id).execute()
            else:
                supabase.table("weekly_reviews").insert(payload).execute()
            st.success("Weekly review saved.")
            st.rerun()

    reviews = get_weekly_reviews(user_id)[:6]
    if reviews:
        cards = []
        for review in reviews:
            cards.append(
                (
                    '<article class="review-card">'
                    f'<div class="review-week">WEEK OF {safe(review.get("week_start"))}</div>'
                    f'<div class="review-rating">{int(review.get("rating") or 0)}/10</div>'
                    f'<p><strong>Win:</strong> {safe(review.get("biggest_win") or "—")}</p>'
                    f'<p><strong>Next:</strong> {safe(review.get("next_focus") or "—")}</p>'
                    '</article>'
                )
            )
        render_html('<section class="review-grid">' + "".join(cards) + '</section>')

    with st.expander("Edit programme targets"):
        c1, c2 = st.columns(2)
        with c1:
            goal = st.text_area("Goal", value=program.get("goal") or "")
            calories = st.number_input("Calories target", 1000, 6000, target(program, "calorie_target", 2200), 50)
            protein = st.number_input("Protein target", 40, 350, target(program, "protein_target", 150), 5)
            wake = st.time_input("Wake target", value=time.fromisoformat(str(program.get("wake_target") or "08:00:00")[:8]))
        with c2:
            study = st.number_input("Study target", 0, 300, target(program, "study_target", 60), 5)
            business = st.number_input("Business target", 0, 300, target(program, "business_target", 45), 5)
            art = st.number_input("Art target", 0, 300, target(program, "art_target", 30), 5)
            room = st.number_input("Room reset target", 0, 120, target(program, "room_target", 15), 5)
            bed = st.time_input("Bed target", value=time.fromisoformat(str(program.get("bed_target") or "23:00:00")[:8]))

        if st.button("Save programme targets", use_container_width=True):
            update_program(
                user_id,
                program["id"],
                {
                    "goal": goal,
                    "calorie_target": calories,
                    "protein_target": protein,
                    "study_target": study,
                    "business_target": business,
                    "art_target": art,
                    "room_target": room,
                    "wake_target": wake,
                    "bed_target": bed,
                },
            )
            st.rerun()

# =========================================================
# APP
# =========================================================

init_state()
restore_session()

if AUTH_REQUIRED and not st.session_state.user_email:
    render_login()
    st.stop()

user_id = current_user_id()
if not user_id:
    st.error(
        "No profile is configured. Add PUBLIC_PROFILE_ID in private mode, "
        "or enable authentication."
    )
    st.stop()

header_left, header_right = st.columns([4, 1])
with header_left:
    render_html(
        """
        <div class="brand">
          <div class="brand-icon">L90</div>
          <div>
            <div class="brand-title">LOCK IN 90</div>
            <div class="brand-sub">personal operating system</div>
          </div>
        </div>
        """
    )

with header_right:
    if AUTH_REQUIRED:
        if st.button("Log out", use_container_width=True):
            try:
                supabase.auth.sign_out()
            except Exception:
                pass
            clear_session()
            st.rerun()
    else:
        render_html('<div class="mode-pill">PRIVATE</div>')

nav()

page = st.session_state.page
if page == "Today":
    render_today(user_id)
elif page == "Focus":
    render_focus(user_id)
elif page == "Training":
    render_training(user_id)
elif page == "Tasks":
    render_tasks(user_id)
elif page == "Review":
    render_review(user_id)
