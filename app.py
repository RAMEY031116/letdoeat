
import os
import html
import textwrap
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import quote

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

# ----------------------------
# Style
# ----------------------------
style_file = BASE_DIR / "style.css"
if style_file.exists():
    st.markdown(f"<style>{style_file.read_text()}</style>", unsafe_allow_html=True)

# ----------------------------
# Secrets + Supabase
# ----------------------------
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
        st.error("SUPABASE_URL is not a valid URL. It must start with https://")
        st.stop()

    return create_client(url, key)

supabase = get_supabase()
AUTH_REQUIRED = str(secret("AUTH_REQUIRED", "false")).lower() == "true"
PUBLIC_PROFILE_ID = str(secret("PUBLIC_PROFILE_ID", "")).strip()

# ----------------------------
# App state + auth
# ----------------------------
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
    st.markdown(
        """
        <section class="login-hero">
          <div>
            <div class="kicker on-dark">PERSONAL OPERATING SYSTEM</div>
            <h1>LOCK IN<br><span>90</span></h1>
            <p>Training, nutrition, focus, tasks and calendar — in one place.</p>
          </div>
          <div class="login-orb">90</div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2, gap="large")
    with c1:
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

    with c2:
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

# ----------------------------
# Database helpers
# ----------------------------
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
    start_date = values["start_date"]
    payload = {
        "user_id": user_id,
        "start_date": str(start_date),
        "end_date": str(start_date + timedelta(days=89)),
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

def add_task(user_id, title, notes, priority, task_date, task_time, category):
    supabase.table("lockin_tasks").insert(
        {
            "user_id": user_id,
            "title": title.strip(),
            "notes": notes.strip(),
            "priority": priority,
            "task_date": str(task_date),
            "task_time": str(task_time) if task_time else None,
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

def get_notes(user_id):
    response = (
        supabase.table("lockin_notes")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return response.data or []

# ----------------------------
# Calendar
# ----------------------------
def task_start(task):
    task_date = datetime.strptime(str(task["task_date"]), "%Y-%m-%d").date()

    if task.get("task_time"):
        raw = str(task["task_time"])
        raw = raw[:8]
        try:
            task_time = datetime.strptime(raw, "%H:%M:%S").time()
        except ValueError:
            task_time = datetime.strptime(raw[:5], "%H:%M").time()
    else:
        task_time = time(9, 0)

    return datetime.combine(task_date, task_time)

def google_calendar_url(task):
    start = task_start(task)
    end = start + timedelta(hours=1)

    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={quote(task['title'])}"
        f"&dates={start.strftime('%Y%m%dT%H%M%S')}/{end.strftime('%Y%m%dT%H%M%S')}"
        f"&details={quote(task.get('notes') or '')}"
    )

def outlook_calendar_url(task):
    start = task_start(task)
    end = start + timedelta(hours=1)

    return (
        "https://outlook.office.com/calendar/0/deeplink/compose?path=/calendar/action/compose"
        f"&subject={quote(task['title'])}"
        f"&body={quote(task.get('notes') or '')}"
        f"&startdt={quote(start.isoformat())}"
        f"&enddt={quote(end.isoformat())}"
    )

def task_ics(task):
    start = task_start(task)
    end = start + timedelta(hours=1)
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

# ----------------------------
# Score logic
# ----------------------------
def target(program, key, default):
    value = program.get(key)
    return int(value) if value is not None else default

def score_log(log, program):
    if not log:
        return 0, 11

    checks = [
        bool(log.get("wake_by_8")),
        bool(log.get("lunch_cardio")),
        bool(log.get("evening_training")),
        bool(log.get("cooked")),
        bool(log.get("calorie_target_hit")),
        bool(log.get("protein_target_hit")),
        int(log.get("study_minutes") or 0) >= target(program, "study_target", 60),
        int(log.get("business_minutes") or 0) >= target(program, "business_target", 45),
        int(log.get("art_minutes") or 0) >= target(program, "art_target", 30),
        bool(log.get("room_tidy")),
        bool(log.get("bed_by_23")),
    ]
    return sum(checks), len(checks)

def current_streak(logs, program):
    lookup = {date.fromisoformat(row["log_date"]): row for row in logs}
    check_date = date.today()
    value = 0

    while check_date in lookup:
        completed, total = score_log(lookup[check_date], program)
        if completed / total < 0.80:
            break
        value += 1
        check_date -= timedelta(days=1)

    return value

# ----------------------------
# Safe HTML rendering
# ----------------------------
def render_html(markup: str):
    """Render custom HTML without Markdown treating indented lines as code."""
    st.markdown(textwrap.dedent(markup).strip(), unsafe_allow_html=True)


# ----------------------------
# Display components
# ----------------------------
def nav():
    pages = ["Today", "Training", "Focus", "Tasks", "Progress"]
    icons = {"Today": "⌂", "Training": "◫", "Focus": "◎", "Tasks": "✓", "Progress": "↗"}

    st.markdown('<div class="nav-label">LOCK IN 90</div>', unsafe_allow_html=True)
    columns = st.columns(5, gap="small")

    for column, page in zip(columns, pages):
        with column:
            active = "active" if st.session_state.page == page else ""
            if st.button(
                f"{icons[page]}  {page}",
                key=f"nav_{page}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                st.session_state.page = page
                st.rerun()

def stat_cards(items):
    cards = []
    for label, value, hint in items:
        cards.append(
            (
                '<div class="stat-card">'
                f'<div class="stat-label">{html.escape(str(label))}</div>'
                f'<div class="stat-value">{html.escape(str(value))}</div>'
                f'<div class="stat-hint">{html.escape(str(hint))}</div>'
                '</div>'
            )
        )
    render_html('<div class="stat-grid">' + "".join(cards) + '</div>')


def focus_target_cards(program):
    cards = [
        ("STUDY", target(program, "study_target", 60), "Deep work"),
        ("BUSINESS", target(program, "business_target", 45), "Build"),
        ("ART", target(program, "art_target", 30), "Create"),
        ("ROOM RESET", target(program, "room_target", 15), "Reset"),
    ]

    html_cards = []
    for label, minutes, subtitle in cards:
        html_cards.append(
            (
                '<article class="focus-target-card">'
                '<div class="focus-target-top">'
                f'<span class="focus-target-label">{html.escape(str(label))}</span>'
                '<span class="focus-target-dot"></span>'
                '</div>'
                f'<div class="focus-target-number">{int(minutes)}<span> min</span></div>'
                f'<div class="focus-target-sub">{html.escape(str(subtitle))}</div>'
                '</article>'
            )
        )

    render_html('<section class="focus-target-grid">' + "".join(html_cards) + '</section>')


def focus_timer():
    components.html(
        """
        <div id="lockin-timer">
          <style>
            *{box-sizing:border-box;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
            body{margin:0;background:transparent;color:#111318}
            .timer{border:1px solid rgba(17,19,24,.08);border-radius:24px;background:#fff;padding:20px;box-shadow:0 16px 38px rgba(17,19,24,.06)}
            .top{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:16px}
            .title{font-weight:850;font-size:18px}.sub{font-size:12px;color:#747b86;margin-top:3px}
            .clock{font-size:42px;font-weight:900;letter-spacing:-1.6px}
            .presets{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px}
            button{border:0;border-radius:12px;padding:10px 8px;font-weight:750;cursor:pointer}
            .preset{background:#f1f3f5;color:#111318}.preset:hover{background:#e7e9ed}
            .actions{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
            .start{background:#111318;color:#fff}.pause,.reset{background:#f1f3f5;color:#111318}
            @media(max-width:520px){.presets{grid-template-columns:repeat(2,1fr)}.clock{font-size:34px}}
          </style>
          <div class="timer">
            <div class="top">
              <div><div class="title">Focus timer</div><div class="sub" id="mode">Study · 60 minutes</div></div>
              <div class="clock" id="clock">60:00</div>
            </div>
            <div class="presets">
              <button class="preset" onclick="setTimer(60,'Study')">Study 60</button>
              <button class="preset" onclick="setTimer(45,'Business')">Business 45</button>
              <button class="preset" onclick="setTimer(30,'Art')">Art 30</button>
              <button class="preset" onclick="setTimer(15,'Room reset')">Room 15</button>
            </div>
            <div class="actions">
              <button class="start" onclick="startTimer()">Start</button>
              <button class="pause" onclick="pauseTimer()">Pause</button>
              <button class="reset" onclick="resetTimer()">Reset</button>
            </div>
          </div>
          <script>
            let initial = 60*60;
            let remaining = initial;
            let handle = null;
            function draw(){
              const m=Math.floor(remaining/60).toString().padStart(2,'0');
              const s=(remaining%60).toString().padStart(2,'0');
              document.getElementById('clock').innerText=m+':'+s;
            }
            function setTimer(mins,label){
              pauseTimer();
              initial=mins*60;remaining=initial;draw();
              document.getElementById('mode').innerText=label+' · '+mins+' minutes';
            }
            function startTimer(){
              if(handle) return;
              handle=setInterval(()=>{
                if(remaining>0){remaining--;draw();}
                else{pauseTimer();document.getElementById('mode').innerText='Session complete ✓';}
              },1000);
            }
            function pauseTimer(){if(handle){clearInterval(handle);handle=null;}}
            function resetTimer(){pauseTimer();remaining=initial;draw();}
            draw();
          </script>
        </div>
        """,
        height=215,
        scrolling=False,
    )

# ----------------------------
# Today
# ----------------------------
def render_today(user_id):
    program = get_program(user_id)

    if not program:
        st.markdown(
            """
            <section class="page-hero">
              <div class="hero-copy">
                <div class="kicker on-dark">YOUR NEXT 90 DAYS</div>
                <h1>BUILD THE<br><span>SYSTEM.</span></h1>
                <p>Set the standards once. Then follow them every day.</p>
              </div>
              <div class="hero-ring"><strong>90</strong><small>DAYS</small></div>
            </section>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.markdown("### Set up your 90 days")
            start_date = st.date_input("Day 1", value=date.today())
            goal = st.text_area(
                "Main goal",
                placeholder="Build discipline, train consistently, study, build my business...",
            )
            c1, c2 = st.columns(2)
            with c1:
                calorie_target = st.number_input("Daily calorie target", 1000, 6000, 2200, 50)
                protein_target = st.number_input("Daily protein target (g)", 40, 350, 150, 5)
                wake_target = st.time_input("Wake target", value=time(8, 0))
                bed_target = st.time_input("Bed target", value=time(23, 0))
            with c2:
                study_target = st.number_input("Study target (min)", 0, 300, 60, 5)
                business_target = st.number_input("Business target (min)", 0, 300, 45, 5)
                art_target = st.number_input("Art target (min)", 0, 300, 30, 5)
                room_target = st.number_input("Room reset target (min)", 0, 120, 15, 5)

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

    start_date = date.fromisoformat(program["start_date"])
    end_date = date.fromisoformat(program["end_date"])
    raw_day = (date.today() - start_date).days + 1
    display_day = max(1, min(90, raw_day))
    progress_pct = max(0, min(100, round((raw_day / 90) * 100)))

    today_log = get_daily_log(user_id, date.today()) or {}
    logs = get_logs(user_id)
    complete, total = score_log(today_log, program)

    goal = html.escape(program.get("goal") or "Follow the plan. No daily negotiation.")

    st.markdown(
        f"""
        <section class="page-hero">
          <div class="hero-copy">
            <div class="kicker on-dark">LOCK IN 90</div>
            <h1>DAY {display_day}<br><span>OF 90.</span></h1>
            <p>{goal}</p>
          </div>
          <div class="hero-ring"><strong>{progress_pct}%</strong><small>COMPLETE</small></div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.progress(progress_pct / 100)

    stat_cards(
        [
            ("STREAK", f"{current_streak(logs, program)} days", "80%+ keeps it alive"),
            ("TODAY", f"{complete}/{total}", "daily standards"),
            ("SLEEP", f"{float(today_log.get('sleep_hours') or 0):.1f} h", f"bed {str(program.get('bed_target') or '23:00')[:5]}"),
            ("FINISH", end_date.strftime("%d %b"), "day 90"),
        ]
    )

    st.markdown('<div class="section-heading"><span>TODAY</span><h2>Daily standards</h2></div>', unsafe_allow_html=True)

    with st.form("today_form"):
        left, right = st.columns(2, gap="large")

        with left:
            wake = st.checkbox("Wake on time", value=bool(today_log.get("wake_by_8")))
            cardio = st.checkbox("Lunch cardio / planned movement", value=bool(today_log.get("lunch_cardio")))
            weights = st.checkbox("Weights / programmed recovery", value=bool(today_log.get("evening_training")))
            cooked = st.checkbox("Cook / planned meal", value=bool(today_log.get("cooked")))
            room = st.checkbox("Room reset completed", value=bool(today_log.get("room_tidy")))
            bed = st.checkbox("Bed on time", value=bool(today_log.get("bed_by_23")))

        with right:
            calories = st.number_input(
                "Calories eaten",
                0,
                10000,
                int(today_log.get("calories_actual") or 0),
                50,
            )
            protein_g = st.number_input(
                "Protein (g)",
                0,
                500,
                int(today_log.get("protein_actual") or 0),
                5,
            )
            cal_hit = st.checkbox(
                f"Calories on target ({target(program, 'calorie_target', 2200)})",
                value=bool(today_log.get("calorie_target_hit")),
            )
            protein_hit = st.checkbox(
                f"Protein on target ({target(program, 'protein_target', 150)}g)",
                value=bool(today_log.get("protein_target_hit")),
            )
            study = st.number_input(
                "Study minutes",
                0,
                600,
                int(today_log.get("study_minutes") or 0),
                5,
            )
            business = st.number_input(
                "Business minutes",
                0,
                600,
                int(today_log.get("business_minutes") or 0),
                5,
            )
            art = st.number_input(
                "Art minutes",
                0,
                600,
                int(today_log.get("art_minutes") or 0),
                5,
            )
            sleep_hours = st.number_input(
                "Sleep hours",
                0.0,
                14.0,
                float(today_log.get("sleep_hours") or 0.0),
                0.25,
            )

        notes = st.text_area(
            "Day note",
            value=today_log.get("notes") or "",
            placeholder="What worked? What needs adjusting tomorrow?",
        )

        if st.form_submit_button("Save today", type="primary", use_container_width=True):
            save_daily_log(
                user_id,
                date.today(),
                {
                    "wake_by_8": wake,
                    "lunch_cardio": cardio,
                    "evening_training": weights,
                    "cooked": cooked,
                    "calorie_target_hit": cal_hit,
                    "protein_target_hit": protein_hit,
                    "calories_actual": calories,
                    "protein_actual": protein_g,
                    "study_minutes": study,
                    "business_minutes": business,
                    "art_minutes": art,
                    "room_tidy": room,
                    "bed_by_23": bed,
                    "sleep_hours": sleep_hours,
                    "notes": notes.strip(),
                },
            )
            st.success("Today saved.")
            st.rerun()

    st.markdown('<div class="section-heading"><span>WEEKDAY</span><h2>Your rhythm</h2></div>', unsafe_allow_html=True)

    rhythm = [
        ("08:00", "Wake", "Breakfast + get ready"),
        ("09:00", "Work", "Start work"),
        ("Lunch", "Cardio", "20–30 min, mostly moderate"),
        ("17:15", "Finish work", "Move into training"),
        ("After work", "Weights", "4 programmed strength days"),
        ("18:30", "Home + cook", "Around 45 minutes"),
        ("19:30", "Study", f"{target(program, 'study_target', 60)} minutes"),
        ("20:45", "Business", f"{target(program, 'business_target', 45)} minutes"),
        ("21:30", "Art", f"{target(program, 'art_target', 30)} minutes"),
        ("22:00", "Room reset", f"{target(program, 'room_target', 15)} minutes"),
        ("23:00", "Bed", "Protect recovery"),
    ]

    rows = []
    for when, title, detail in rhythm:
        rows.append(
            (
                '<div class="rhythm-row">'
                f'<div class="rhythm-time">{html.escape(str(when))}</div>'
                '<div>'
                f'<strong>{html.escape(str(title))}</strong>'
                f'<span>{html.escape(str(detail))}</span>'
                '</div>'
                '</div>'
            )
        )

    render_html('<div class="rhythm-card">' + "".join(rows) + '</div>')

    with st.expander("Edit my targets"):
        c1, c2 = st.columns(2)
        with c1:
            edit_goal = st.text_area("Goal", value=program.get("goal") or "")
            edit_cal = st.number_input("Calories target", 1000, 6000, target(program, "calorie_target", 2200), 50)
            edit_pro = st.number_input("Protein target (g)", 40, 350, target(program, "protein_target", 150), 5)
            edit_wake = st.time_input(
                "Wake target",
                value=datetime.strptime(str(program.get("wake_target") or "08:00:00")[:8], "%H:%M:%S").time(),
            )
        with c2:
            edit_study = st.number_input("Study target", 0, 300, target(program, "study_target", 60), 5)
            edit_business = st.number_input("Business target", 0, 300, target(program, "business_target", 45), 5)
            edit_art = st.number_input("Art target", 0, 300, target(program, "art_target", 30), 5)
            edit_room = st.number_input("Room target", 0, 120, target(program, "room_target", 15), 5)
            edit_bed = st.time_input(
                "Bed target",
                value=datetime.strptime(str(program.get("bed_target") or "23:00:00")[:8], "%H:%M:%S").time(),
            )

        if st.button("Save targets", use_container_width=True):
            update_program(
                user_id,
                program["id"],
                {
                    "goal": edit_goal,
                    "calorie_target": edit_cal,
                    "protein_target": edit_pro,
                    "study_target": edit_study,
                    "business_target": edit_business,
                    "art_target": edit_art,
                    "room_target": edit_room,
                    "wake_target": edit_wake,
                    "bed_target": edit_bed,
                },
            )
            st.success("Targets updated.")
            st.rerun()

# ----------------------------
# Training
# ----------------------------
def render_training(user_id):
    render_html(
        """
        <section class="image-hero training-hero">
          <div>
            <div class="kicker on-dark">TRAINING</div>
            <h1>YOUR TRAINING.<br>YOUR CHOICE.</h1>
            <p>The app keeps the structure simple. You decide what workout you actually do.</p>
          </div>
        </section>
        """
    )

    st.markdown(
        '<div class="section-heading"><span>THE SIMPLE SYSTEM</span><h2>Two sessions, different jobs</h2></div>',
        unsafe_allow_html=True,
    )

    render_html(
        """
        <section class="training-simple-grid">
          <article class="training-simple-card">
            <div class="training-simple-icon">☀</div>
            <div class="training-simple-kicker">LUNCH</div>
            <div class="training-simple-title">Move</div>
            <div class="training-simple-copy">
              Cardio, walking or light movement. Keep it short enough that you can return to work feeling good.
            </div>
            <div class="training-simple-time">20–30 min</div>
          </article>

          <article class="training-simple-card training-simple-card-dark">
            <div class="training-simple-icon">◫</div>
            <div class="training-simple-kicker">AFTER WORK</div>
            <div class="training-simple-title">Train</div>
            <div class="training-simple-copy">
              Do your own gym workout. The app does not choose your exercises or split for you.
            </div>
            <div class="training-simple-time">Your session</div>
          </article>

          <article class="training-simple-card">
            <div class="training-simple-icon">↺</div>
            <div class="training-simple-kicker">WHEN NEEDED</div>
            <div class="training-simple-title">Recover</div>
            <div class="training-simple-copy">
              Rest, walk, stretch or skip the second session when recovery is the better choice.
            </div>
            <div class="training-simple-time">Part of the plan</div>
          </article>
        </section>
        """
    )

    st.markdown(
        '<div class="section-heading"><span>TODAY</span><h2>Quick training log</h2></div>',
        unsafe_allow_html=True,
    )
    st.caption("Only log what is useful. No sets, reps or exercise tracking unless you decide you want that later.")

    with st.form("workout_form"):
        c1, c2 = st.columns(2)
        with c1:
            workout_date = st.date_input("Date", value=date.today(), key="workout_date")
            session = st.selectbox(
                "What did you do?",
                [
                    "Lunch cardio / movement",
                    "Evening gym",
                    "Both",
                    "Recovery / rest",
                    "Other",
                ],
            )
        with c2:
            duration = st.number_input("Total minutes", 0, 300, 30, 5)
            effort = st.select_slider(
                "How did it feel?",
                options=["Easy", "Good", "Hard", "Very hard"],
                value="Good",
            )

        notes = st.text_area(
            "Optional note",
            placeholder="Example: good session, legs tired, treadmill + gym, rest day...",
        )

        if st.form_submit_button("Save training", type="primary", use_container_width=True):
            supabase.table("workouts").insert(
                {
                    "user_id": user_id,
                    "workout_date": str(workout_date),
                    "session": session,
                    "exercise": "",
                    "sets": 0,
                    "reps": 0,
                    "weight": 0,
                    "duration_minutes": duration,
                    "notes": f"{effort}" + (f" — {notes.strip()}" if notes.strip() else ""),
                }
            ).execute()
            st.success("Training saved.")
            st.rerun()

    workouts = get_workouts(user_id)
    if workouts:
        st.markdown(
            '<div class="section-heading"><span>RECENT</span><h2>Your sessions</h2></div>',
            unsafe_allow_html=True,
        )

        recent = workouts[:8]
        cards = []
        for row in recent:
            raw_note = row.get("notes") or ""
            cards.append(
                (
                    '<div class="training-history-card">'
                    f'<div class="training-history-date">{html.escape(str(row.get("workout_date", "")))}</div>'
                    f'<div class="training-history-title">{html.escape(str(row.get("session", "Training")))}</div>'
                    f'<div class="training-history-meta">{int(row.get("duration_minutes") or 0)} min'
                    + (f' · {html.escape(raw_note)}' if raw_note else '')
                    + '</div>'
                    '</div>'
                )
            )

        render_html('<div class="training-history-grid">' + "".join(cards) + '</div>')


# ----------------------------
# Focus
# ----------------------------
def render_focus(user_id):
    program = get_program(user_id)

    if not program:
        st.info("Start your 90-day programme on the Today page first.")
        return

    render_html(
        """
        <section class="image-hero focus-hero">
          <div>
            <div class="kicker on-dark">AFTER WORK</div>
            <h1>STUDY FIRST.<br>THEN BUILD.</h1>
            <p>One evening, four clear blocks. No guessing what comes next.</p>
          </div>
        </section>
        """
    )

    # IMPORTANT:
    # These are custom HTML cards, NOT st.metric().
    # This avoids the Streamlit theme bug that made the values white.
    focus_target_cards(program)

    st.markdown('<div class="section-heading"><span>TIMER</span><h2>Run the block</h2></div>', unsafe_allow_html=True)
    focus_timer()

    st.markdown('<div class="section-heading"><span>LOG</span><h2>Record what you did</h2></div>', unsafe_allow_html=True)

    with st.form("focus_form"):
        c1, c2 = st.columns([1, 1])
        with c1:
            focus_type = st.selectbox("Focus type", ["Study", "Business", "Art", "Room reset"])
        with c2:
            minutes = st.number_input("Minutes completed", 0, 300, 30, 5)
        note = st.text_input("Optional note")

        if st.form_submit_button("Save focus block", type="primary", use_container_width=True):
            supabase.table("focus_sessions").insert(
                {
                    "user_id": user_id,
                    "session_date": str(date.today()),
                    "focus_type": focus_type,
                    "minutes": minutes,
                    "note": note.strip(),
                }
            ).execute()
            st.success("Focus block saved.")
            st.rerun()

    sessions = get_focus_sessions(user_id)
    if sessions:
        df = pd.DataFrame(sessions)
        columns = [c for c in ["session_date", "focus_type", "minutes", "note"] if c in df.columns]
        st.dataframe(df[columns], use_container_width=True, hide_index=True)

# ----------------------------
# Tasks + Calendar
# ----------------------------
def render_tasks(user_id):
    render_html(
        """
        <section class="image-hero tasks-hero">
          <div>
            <div class="kicker on-dark">TASKS + CALENDAR</div>
            <h1>PLAN IT ONCE.<br>PUT IT WHERE YOU USE IT.</h1>
            <p>Create tasks here, then push them into Google, Outlook or Apple Calendar.</p>
          </div>
        </section>
        """
    )

    with st.expander("＋ Add a task", expanded=True):
        with st.form("task_form"):
            c1, c2 = st.columns([1.4, 1])
            with c1:
                title = st.text_input("Task title")
                task_notes = st.text_area("Notes")
            with c2:
                priority = st.selectbox("Priority", ["High", "Medium", "Low"], index=1)
                task_date = st.date_input("Date", value=date.today())
                use_time = st.checkbox("Add time")
                task_time = st.time_input("Time", value=time(9, 0), disabled=not use_time)
                category = st.selectbox(
                    "Category",
                    ["Personal", "Work", "Study", "Business", "Gym", "Other"],
                )

            if st.form_submit_button("Save task", type="primary", use_container_width=True):
                if not title.strip():
                    st.warning("Give the task a title.")
                else:
                    add_task(
                        user_id,
                        title,
                        task_notes,
                        priority,
                        task_date,
                        task_time if use_time else None,
                        category,
                    )
                    st.success("Task saved.")
                    st.rerun()

    tasks = get_tasks(user_id)

    if not tasks:
        st.info("No tasks yet.")
    else:
        search = st.text_input("Search tasks", placeholder="Gym, study, work...")
        show_completed = st.checkbox("Show completed", value=False)

        filtered = tasks
        if search.strip():
            needle = search.lower().strip()
            filtered = [
                task
                for task in filtered
                if needle in (task.get("title") or "").lower()
                or needle in (task.get("notes") or "").lower()
            ]

        if not show_completed:
            filtered = [task for task in filtered if not task.get("completed")]

        for task in filtered:
            task_title = html.escape(task["title"])
            task_notes = html.escape(task.get("notes") or "")
            task_time_text = f" · {str(task['task_time'])[:5]}" if task.get("task_time") else ""

            task_html = (
                '<div class="task-card">'
                f'<div class="task-meta">{html.escape(task["priority"])} · {html.escape(task["category"])} · {task["task_date"]}{task_time_text}</div>'
                f'<div class="task-title">{"✓ " if task.get("completed") else ""}{task_title}</div>'
                + (f'<div class="task-note">{task_notes}</div>' if task_notes else '')
                + '</div>'
            )
            render_html(task_html)

            action1, action2 = st.columns(2)
            with action1:
                if st.button(
                    "Undo" if task.get("completed") else "Mark done",
                    key=f"done_{task['id']}",
                    use_container_width=True,
                ):
                    (
                        supabase.table("lockin_tasks")
                        .update({"completed": not task.get("completed")})
                        .eq("id", task["id"])
                        .eq("user_id", user_id)
                        .execute()
                    )
                    st.rerun()
            with action2:
                if st.button("Delete", key=f"delete_{task['id']}", use_container_width=True):
                    (
                        supabase.table("lockin_tasks")
                        .delete()
                        .eq("id", task["id"])
                        .eq("user_id", user_id)
                        .execute()
                    )
                    st.rerun()

            cal1, cal2, cal3 = st.columns(3)
            with cal1:
                st.link_button("Google Calendar", google_calendar_url(task), use_container_width=True)
            with cal2:
                st.link_button("Outlook", outlook_calendar_url(task), use_container_width=True)
            with cal3:
                st.download_button(
                    "Apple / ICS",
                    task_ics(task),
                    file_name=f"{task['title'].replace(' ', '_')}.ics",
                    mime="text/calendar",
                    use_container_width=True,
                    key=f"ics_{task['id']}",
                )

            st.markdown("<div class='task-gap'></div>", unsafe_allow_html=True)

    st.markdown('<div class="section-heading"><span>NOTES</span><h2>Quick capture</h2></div>', unsafe_allow_html=True)
    with st.form("note_form"):
        note = st.text_area("Quick note", placeholder="Idea, reminder, thought...")
        if st.form_submit_button("Save note", use_container_width=True):
            if note.strip():
                supabase.table("lockin_notes").insert(
                    {
                        "user_id": user_id,
                        "content": note.strip(),
                    }
                ).execute()
                st.rerun()

    notes = get_notes(user_id)
    if notes:
        cards = []
        for note in notes[:8]:
            cards.append(
                f'<div class="note-card">{html.escape(note.get("content") or "")}</div>'
            )
        render_html('<div class="note-grid">' + "".join(cards) + '</div>')

# ----------------------------
# Progress
# ----------------------------
def render_progress(user_id):
    program = get_program(user_id)
    if not program:
        st.info("Start your 90-day programme first.")
        return

    render_html(
        """
        <section class="image-hero progress-hero">
          <div>
            <div class="kicker on-dark">PROGRESS</div>
            <h1>MAKE THE WORK<br>VISIBLE.</h1>
            <p>Look for consistency, not a perfect day.</p>
          </div>
        </section>
        """
    )

    logs = get_logs(user_id)
    workouts = get_workouts(user_id)
    sessions = get_focus_sessions(user_id)

    if not logs:
        st.info("Your charts will appear after you save your first day.")
        return

    rows = []
    for row in logs:
        complete, total = score_log(row, program)
        rows.append(
            {
                "date": row["log_date"],
                "completion": round((complete / total) * 100),
                "study": int(row.get("study_minutes") or 0),
                "business": int(row.get("business_minutes") or 0),
                "art": int(row.get("art_minutes") or 0),
                "sleep": float(row.get("sleep_hours") or 0),
                "calories": int(row.get("calories_actual") or 0),
                "protein": int(row.get("protein_actual") or 0),
            }
        )

    df = pd.DataFrame(rows)

    stat_cards(
        [
            ("DAYS LOGGED", len(df), "entries"),
            ("AVG SCORE", f"{round(df['completion'].mean())}%", "consistency"),
            ("WORKOUTS", len(workouts), "logged"),
            ("FOCUS BLOCKS", len(sessions), "logged"),
        ]
    )

    st.markdown('<div class="section-heading"><span>CONSISTENCY</span><h2>Daily score</h2></div>', unsafe_allow_html=True)
    st.line_chart(df.set_index("date")["completion"])

    st.markdown('<div class="section-heading"><span>FOCUS</span><h2>Minutes</h2></div>', unsafe_allow_html=True)
    st.bar_chart(df.set_index("date")[["study", "business", "art"]])

    st.markdown('<div class="section-heading"><span>RECOVERY</span><h2>Sleep</h2></div>', unsafe_allow_html=True)
    st.line_chart(df.set_index("date")["sleep"])

    st.markdown('<div class="section-heading"><span>NUTRITION</span><h2>Calories + protein</h2></div>', unsafe_allow_html=True)
    st.dataframe(
        df[["date", "calories", "protein"]],
        use_container_width=True,
        hide_index=True,
    )

# ----------------------------
# Run app
# ----------------------------
init_state()
restore_session()

if AUTH_REQUIRED and not st.session_state.user_email:
    render_login()
    st.stop()

user_id = current_user_id()

if not user_id:
    st.error(
        "No profile is configured. In private mode, add PUBLIC_PROFILE_ID to Streamlit Secrets. "
        "Or set AUTH_REQUIRED=true and use Supabase login."
    )
    st.stop()

header_left, header_right = st.columns([4, 1])
with header_left:
    st.markdown(
        """
        <div class="brand">
          <div class="brand-icon">L90</div>
          <div>
            <div class="brand-name">LOCK IN 90</div>
            <div class="brand-sub">personal operating system</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
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
        st.markdown('<div class="private-badge">PRIVATE MODE</div>', unsafe_allow_html=True)

nav()

if st.session_state.page == "Today":
    render_today(user_id)
elif st.session_state.page == "Training":
    render_training(user_id)
elif st.session_state.page == "Focus":
    render_focus(user_id)
elif st.session_state.page == "Tasks":
    render_tasks(user_id)
elif st.session_state.page == "Progress":
    render_progress(user_id)
