
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st
from supabase import create_client, Client

BASE_DIR = Path(__file__).parent

st.set_page_config(
    page_title="LOCK IN 90",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

css_file = BASE_DIR / "style.css"
if css_file.exists():
    st.markdown(f"<style>{css_file.read_text()}</style>", unsafe_allow_html=True)

def get_secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return os.getenv(name, default)

@st.cache_resource
def get_supabase() -> Client:
    url = get_secret("SUPABASE_URL")
    key = get_secret("SUPABASE_KEY")
    if not url or not key:
        st.error("Missing SUPABASE_URL or SUPABASE_KEY in Streamlit secrets.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()
AUTH_REQUIRED = str(get_secret("AUTH_REQUIRED", "false")).lower() == "true"
PUBLIC_PROFILE_ID = get_secret("PUBLIC_PROFILE_ID", "")

def init_state():
    defaults = {
        "access_token": None,
        "refresh_token": None,
        "user_email": None,
        "active_page": "Today",
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
    for key in ["access_token", "refresh_token", "user_email"]:
        st.session_state[key] = None
    try:
        supabase.postgrest.auth(None)
    except Exception:
        pass

def restore_session():
    if st.session_state.access_token:
        try:
            supabase.postgrest.auth(st.session_state.access_token)
            return True
        except Exception:
            clear_session()
    return False

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

def show_auth_screen():
    st.markdown(
        """
        <section class="auth-shell">
          <div class="auth-copy">
            <div class="eyebrow">PERSONAL OPERATING SYSTEM</div>
            <h1>LOCK IN<br><span>FOR 90.</span></h1>
            <p>Training, food, study, business, art, room reset, tasks and calendar — one place.</p>
          </div>
          <div class="auth-art">
            <div class="orb outer"><div class="orb inner">90</div></div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.info("You can run privately with no login now. Turn login on before sharing the app with friends.")
    with right:
        t1, t2 = st.tabs(["Log in", "Create account"])
        with t1:
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            if st.button("Log in", type="primary", use_container_width=True):
                try:
                    result = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    save_session(result)
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")
        with t2:
            email = st.text_input("Email ", key="signup_email")
            password = st.text_input("Password ", type="password", key="signup_password")
            if st.button("Create account", use_container_width=True):
                try:
                    result = supabase.auth.sign_up({"email": email, "password": password})
                    if getattr(result, "session", None):
                        save_session(result)
                        st.rerun()
                    else:
                        st.success("Account created. Check your email if Supabase confirmation is enabled.")
                except Exception as e:
                    st.error(f"Sign up failed: {e}")

def fetch_one(table, filters):
    q = supabase.table(table).select("*")
    for col, value in filters.items():
        q = q.eq(col, value)
    r = q.limit(1).execute()
    return r.data[0] if r.data else None

def get_program(user_id):
    r = (
        supabase.table("lockin_programs")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "active")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return r.data[0] if r.data else None

def create_program(user_id, start_date, goal):
    supabase.table("lockin_programs").insert({
        "user_id": user_id,
        "start_date": str(start_date),
        "end_date": str(start_date + timedelta(days=89)),
        "goal": goal.strip(),
        "status": "active",
    }).execute()

def get_daily_log(user_id, log_date):
    return fetch_one("daily_lockin", {"user_id": user_id, "log_date": str(log_date)})

def upsert_daily_log(user_id, log_date, values):
    existing = get_daily_log(user_id, log_date)
    payload = {
        "user_id": user_id,
        "log_date": str(log_date),
        **values,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if existing:
        supabase.table("daily_lockin").update(payload).eq("id", existing["id"]).execute()
    else:
        supabase.table("daily_lockin").insert(payload).execute()

def get_daily_logs(user_id):
    r = (
        supabase.table("daily_lockin")
        .select("*")
        .eq("user_id", user_id)
        .order("log_date", desc=False)
        .execute()
    )
    return r.data or []

def get_tasks(user_id):
    r = (
        supabase.table("lockin_tasks")
        .select("*")
        .eq("user_id", user_id)
        .order("completed", desc=False)
        .order("task_date", desc=False)
        .order("task_time", desc=False)
        .execute()
    )
    return r.data or []

def add_task(user_id, title, notes, priority, task_date, task_time, category):
    supabase.table("lockin_tasks").insert({
        "user_id": user_id,
        "title": title,
        "notes": notes,
        "priority": priority,
        "task_date": str(task_date),
        "task_time": str(task_time) if task_time else None,
        "category": category,
        "completed": False,
    }).execute()

def get_workouts(user_id):
    r = (
        supabase.table("workouts")
        .select("*")
        .eq("user_id", user_id)
        .order("workout_date", desc=True)
        .limit(100)
        .execute()
    )
    return r.data or []

def get_focus_sessions(user_id):
    r = (
        supabase.table("focus_sessions")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return r.data or []

def parse_task_dt(task):
    d = datetime.strptime(str(task["task_date"]), "%Y-%m-%d").date()
    if task.get("task_time"):
        raw = str(task["task_time"])
        fmt = "%H:%M:%S" if len(raw) >= 8 else "%H:%M"
        t = datetime.strptime(raw[:8] if fmt == "%H:%M:%S" else raw[:5], fmt).time()
    else:
        t = time(9, 0)
    return datetime.combine(d, t)

def google_calendar_url(task):
    start = parse_task_dt(task)
    end = start + timedelta(minutes=60)
    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={quote(task['title'])}"
        f"&dates={start.strftime('%Y%m%dT%H%M%S')}/{end.strftime('%Y%m%dT%H%M%S')}"
        f"&details={quote(task.get('notes') or '')}"
    )

def outlook_calendar_url(task):
    start = parse_task_dt(task)
    end = start + timedelta(minutes=60)
    return (
        "https://outlook.office.com/calendar/0/deeplink/compose?path=/calendar/action/compose"
        f"&subject={quote(task['title'])}"
        f"&body={quote(task.get('notes') or '')}"
        f"&startdt={quote(start.isoformat())}"
        f"&enddt={quote(end.isoformat())}"
    )

def ics_content(task):
    start = parse_task_dt(task)
    end = start + timedelta(minutes=60)
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

def score_log(log):
    if not log:
        return 0, 11
    checks = [
        bool(log.get("wake_by_8")),
        bool(log.get("lunch_cardio")),
        bool(log.get("evening_training")),
        bool(log.get("cooked")),
        bool(log.get("calorie_target_hit")),
        bool(log.get("protein_target_hit")),
        int(log.get("study_minutes") or 0) >= 60,
        int(log.get("business_minutes") or 0) >= 45,
        int(log.get("art_minutes") or 0) >= 30,
        bool(log.get("room_tidy")),
        bool(log.get("bed_by_23")),
    ]
    return sum(checks), len(checks)

def streak(logs):
    lookup = {date.fromisoformat(x["log_date"]): x for x in logs}
    d = date.today()
    value = 0
    while d in lookup:
        complete, total = score_log(lookup[d])
        if complete / total < 0.80:
            break
        value += 1
        d -= timedelta(days=1)
    return value

def top_nav():
    pages = [("Today", "⌂"), ("Training", "◫"), ("Focus", "◉"), ("Tasks", "✓"), ("Progress", "↗")]
    cols = st.columns(len(pages))
    for col, (label, icon) in zip(cols, pages):
        with col:
            if st.button(f"{icon}  {label}", key=f"nav_{label}", use_container_width=True):
                st.session_state.active_page = label
                st.rerun()

def render_today(user_id):
    program = get_program(user_id)
    if not program:
        st.markdown("""
        <section class="hero-card">
          <div>
            <div class="eyebrow">YOUR NEXT 90 DAYS</div>
            <h1>START THE SYSTEM.</h1>
            <p>Make Day 1 deliberate. The app will calculate the rest.</p>
          </div>
          <div class="hero-illustration">90</div>
        </section>
        """, unsafe_allow_html=True)
        with st.container(border=True):
            start_date = st.date_input("Day 1", value=date.today())
            goal = st.text_area("Main goal", placeholder="Build discipline, train consistently, study, grow my business...")
            if st.button("Start my 90 days", type="primary", use_container_width=True):
                create_program(user_id, start_date, goal)
                st.rerun()
        return

    start = date.fromisoformat(program["start_date"])
    end = date.fromisoformat(program["end_date"])
    raw_day = (date.today() - start).days + 1
    day_no = max(1, min(90, raw_day))
    pct = max(0, min(100, round(raw_day / 90 * 100)))
    log = get_daily_log(user_id, date.today()) or {}
    logs = get_daily_logs(user_id)
    done, total = score_log(log)

    st.markdown(f"""
    <section class="hero-card">
      <div>
        <div class="eyebrow">LOCK IN 90</div>
        <h1>DAY {day_no}<span> / 90</span></h1>
        <p>{program.get("goal") or "Follow the plan. No daily negotiation."}</p>
      </div>
      <div class="hero-illustration">{pct}%</div>
    </section>
    """, unsafe_allow_html=True)
    st.progress(pct / 100)

    a, b, c, d = st.columns(4)
    a.metric("🔥 Streak", f"{streak(logs)} days")
    b.metric("✅ Today", f"{done}/{total}")
    c.metric("😴 Sleep", f"{float(log.get('sleep_hours') or 0):.1f}h")
    d.metric("🏁 Ends", end.strftime("%d %b"))

    st.markdown('<div class="section-title">Today</div>', unsafe_allow_html=True)
    with st.form("today_checklist"):
        l, r = st.columns(2, gap="large")
        with l:
            wake = st.checkbox("Wake by 08:00", value=bool(log.get("wake_by_8")))
            cardio = st.checkbox("Lunch cardio / movement", value=bool(log.get("lunch_cardio")))
            weights = st.checkbox("Evening weights / programmed recovery", value=bool(log.get("evening_training")))
            cooked = st.checkbox("Cook / planned meal", value=bool(log.get("cooked")))
            room = st.checkbox("15-minute room reset", value=bool(log.get("room_tidy")))
            bed = st.checkbox("In bed by 23:00", value=bool(log.get("bed_by_23")))
        with r:
            cal = st.checkbox("Calories on target", value=bool(log.get("calorie_target_hit")))
            protein = st.checkbox("Protein on target", value=bool(log.get("protein_target_hit")))
            study = st.number_input("Study minutes", 0, 600, int(log.get("study_minutes") or 0), 5)
            business = st.number_input("Business minutes", 0, 600, int(log.get("business_minutes") or 0), 5)
            art = st.number_input("Art minutes", 0, 600, int(log.get("art_minutes") or 0), 5)
            sleep = st.number_input("Sleep hours", 0.0, 14.0, float(log.get("sleep_hours") or 0), 0.25)
        notes = st.text_area("Notes", value=log.get("notes") or "", placeholder="What worked? What needs fixing tomorrow?")
        if st.form_submit_button("Save today", type="primary", use_container_width=True):
            upsert_daily_log(user_id, date.today(), {
                "wake_by_8": wake,
                "lunch_cardio": cardio,
                "evening_training": weights,
                "cooked": cooked,
                "calorie_target_hit": cal,
                "protein_target_hit": protein,
                "study_minutes": study,
                "business_minutes": business,
                "art_minutes": art,
                "room_tidy": room,
                "bed_by_23": bed,
                "sleep_hours": sleep,
                "notes": notes,
            })
            st.success("Saved.")
            st.rerun()

    st.markdown('<div class="section-title">Weekday rhythm</div>', unsafe_allow_html=True)
    rhythm = [
        ("08:00", "Wake + breakfast"),
        ("09:00–17:15", "Work"),
        ("Lunch", "20–30 min cardio / movement"),
        ("After work", "Weight training on programmed days"),
        ("18:30", "Home + cook"),
        ("19:30", "Study — 60 min"),
        ("20:45", "Business — 45 min"),
        ("21:30", "Art — 30 min"),
        ("22:00", "Room reset + prepare tomorrow"),
        ("23:00", "Bed"),
    ]
    for t, item in rhythm:
        st.markdown(f'<div class="timeline"><span>{t}</span><strong>{item}</strong></div>', unsafe_allow_html=True)

def render_training(user_id):
    st.markdown('<div class="section-title">Training</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="banner-photo training-banner">
      <div><div class="eyebrow">TWO-A-DAY STRUCTURE</div><h2>Condition at lunch.<br>Build after work.</h2></div>
    </div>
    """, unsafe_allow_html=True)

    plan = [
        ("MON", "20–30 min cardio", "Upper body"),
        ("TUE", "20–30 min cardio", "Lower body"),
        ("WED", "Easy walk / zone 2", "Recovery"),
        ("THU", "20–30 min cardio", "Upper body"),
        ("FRI", "20–30 min cardio", "Lower body"),
        ("SAT", "Optional activity", "Optional accessories / full body"),
        ("SUN", "Rest", "Rest"),
    ]
    for day, lunch, evening in plan:
        st.markdown(f"""
        <div class="workout-row">
          <div class="day-pill">{day}</div>
          <div><span>LUNCH</span><strong>{lunch}</strong></div>
          <div><span>EVENING</span><strong>{evening}</strong></div>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("Log a workout", expanded=True):
        with st.form("workout_log"):
            a, b = st.columns(2)
            with a:
                d = st.date_input("Date", value=date.today())
                session = st.selectbox("Session", ["Lunch cardio", "Upper body", "Lower body", "Full body", "Recovery", "Other"])
                duration = st.number_input("Duration (minutes)", 0, 300, 45, 5)
            with b:
                exercise = st.text_input("Exercise / activity")
                sets = st.number_input("Sets", 0, 20, 0)
                reps = st.number_input("Reps", 0, 200, 0)
                weight = st.number_input("Weight", 0.0, 500.0, 0.0, 0.5)
            notes = st.text_area("Workout notes")
            if st.form_submit_button("Save workout", type="primary", use_container_width=True):
                supabase.table("workouts").insert({
                    "user_id": user_id,
                    "workout_date": str(d),
                    "session": session,
                    "exercise": exercise,
                    "sets": sets,
                    "reps": reps,
                    "weight": weight,
                    "duration_minutes": duration,
                    "notes": notes,
                }).execute()
                st.rerun()

    workouts = get_workouts(user_id)
    if workouts:
        df = pd.DataFrame(workouts)
        cols = [c for c in ["workout_date", "session", "exercise", "sets", "reps", "weight", "duration_minutes"] if c in df.columns]
        st.dataframe(df[cols], use_container_width=True, hide_index=True)

def render_focus(user_id):
    st.markdown('<div class="section-title">Focus</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="banner-photo focus-banner">
      <div><div class="eyebrow">AFTER WORK</div><h2>Study first.<br>Then build.</h2></div>
    </div>
    """, unsafe_allow_html=True)
    a, b, c, d = st.columns(4)
    a.metric("Study", "60 min")
    b.metric("Business", "45 min")
    c.metric("Art", "30 min")
    d.metric("Room", "15 min")

    with st.form("focus_log"):
        kind = st.selectbox("Focus type", ["Study", "Business", "Art", "Room reset"])
        mins = st.number_input("Minutes completed", 0, 300, 30, 5)
        note = st.text_input("Optional note")
        if st.form_submit_button("Save focus block", type="primary", use_container_width=True):
            supabase.table("focus_sessions").insert({
                "user_id": user_id,
                "session_date": str(date.today()),
                "focus_type": kind,
                "minutes": mins,
                "note": note,
            }).execute()
            st.rerun()

    sessions = get_focus_sessions(user_id)
    if sessions:
        st.dataframe(pd.DataFrame(sessions), use_container_width=True, hide_index=True)

def render_tasks(user_id):
    st.markdown('<div class="section-title">Tasks + Calendar</div>', unsafe_allow_html=True)
    st.caption("Create once, then send the task to Google, Outlook, or Apple Calendar.")

    with st.expander("Add task", expanded=True):
        with st.form("task_form"):
            a, b = st.columns([1.4, 1])
            with a:
                title = st.text_input("Task title")
                notes = st.text_area("Notes")
            with b:
                priority = st.selectbox("Priority", ["High", "Medium", "Low"], index=1)
                d = st.date_input("Date", value=date.today())
                use_time = st.checkbox("Add time")
                t = st.time_input("Time", value=time(9, 0), disabled=not use_time)
                category = st.selectbox("Category", ["Personal", "Work", "Study", "Business", "Gym", "Other"])
            if st.form_submit_button("Save task", type="primary", use_container_width=True):
                if title.strip():
                    add_task(user_id, title.strip(), notes.strip(), priority, d, t if use_time else None, category)
                    st.rerun()

    tasks = get_tasks(user_id)
    if not tasks:
        st.info("No tasks yet.")
        return

    q = st.text_input("Search", placeholder="Search title or notes")
    if q.strip():
        ql = q.lower().strip()
        tasks = [x for x in tasks if ql in (x.get("title") or "").lower() or ql in (x.get("notes") or "").lower()]

    for task in tasks:
        with st.container(border=True):
            left, right = st.columns([3, 1])
            with left:
                icon = "✅" if task.get("completed") else "○"
                st.markdown(f"### {icon} {task['title']}")
                tm = f" · {str(task['task_time'])[:5]}" if task.get("task_time") else ""
                st.caption(f"{task['priority']} · {task['category']} · {task['task_date']}{tm}")
                if task.get("notes"):
                    st.write(task["notes"])
            with right:
                if st.button("Undo" if task.get("completed") else "Done", key=f"done_{task['id']}", use_container_width=True):
                    supabase.table("lockin_tasks").update({"completed": not task.get("completed")}).eq("id", task["id"]).execute()
                    st.rerun()
                if st.button("Delete", key=f"delete_{task['id']}", use_container_width=True):
                    supabase.table("lockin_tasks").delete().eq("id", task["id"]).execute()
                    st.rerun()

            c1, c2, c3 = st.columns(3)
            with c1:
                st.link_button("Google Calendar", google_calendar_url(task), use_container_width=True)
            with c2:
                st.link_button("Outlook", outlook_calendar_url(task), use_container_width=True)
            with c3:
                st.download_button(
                    "Apple / ICS",
                    ics_content(task),
                    file_name=f"{task['title'].replace(' ', '_')}.ics",
                    mime="text/calendar",
                    use_container_width=True,
                    key=f"ics_{task['id']}",
                )

def render_progress(user_id):
    st.markdown('<div class="section-title">Progress</div>', unsafe_allow_html=True)
    logs = get_daily_logs(user_id)
    workouts = get_workouts(user_id)
    if not logs:
        st.info("Your charts appear after you start saving days.")
        return

    rows = []
    for x in logs:
        done, total = score_log(x)
        rows.append({
            "date": x["log_date"],
            "completion": round(done / total * 100),
            "study": int(x.get("study_minutes") or 0),
            "business": int(x.get("business_minutes") or 0),
            "art": int(x.get("art_minutes") or 0),
            "sleep": float(x.get("sleep_hours") or 0),
        })
    df = pd.DataFrame(rows)
    a, b, c = st.columns(3)
    a.metric("Days logged", len(df))
    b.metric("Workouts", len(workouts))
    c.metric("Average score", f"{round(df['completion'].mean())}%")

    st.markdown("#### Consistency")
    st.line_chart(df.set_index("date")["completion"])
    st.markdown("#### Focus")
    st.bar_chart(df.set_index("date")[["study", "business", "art"]])
    st.markdown("#### Sleep")
    st.line_chart(df.set_index("date")["sleep"])

init_state()
restore_session()

if AUTH_REQUIRED and not st.session_state.user_email:
    show_auth_screen()
    st.stop()

user_id = current_user_id()
if not user_id:
    st.error(
        "No profile is configured. In private/no-login mode, add PUBLIC_PROFILE_ID to Streamlit secrets. "
        "Or set AUTH_REQUIRED=true and use Supabase login."
    )
    st.stop()

head_l, head_r = st.columns([4, 1])
with head_l:
    st.markdown("""
    <div class="brand">
      <div class="brand-mark">L90</div>
      <div><strong>LOCK IN 90</strong><span>personal operating system</span></div>
    </div>
    """, unsafe_allow_html=True)
with head_r:
    if AUTH_REQUIRED:
        if st.button("Log out", use_container_width=True):
            try:
                supabase.auth.sign_out()
            except Exception:
                pass
            clear_session()
            st.rerun()
    else:
        st.caption("Private mode")

top_nav()

page = st.session_state.active_page
if page == "Today":
    render_today(user_id)
elif page == "Training":
    render_training(user_id)
elif page == "Focus":
    render_focus(user_id)
elif page == "Tasks":
    render_tasks(user_id)
elif page == "Progress":
    render_progress(user_id)
