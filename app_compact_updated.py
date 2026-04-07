import os
from datetime import date, datetime, time, timedelta
from urllib.parse import quote

import pandas as pd
import streamlit as st
from supabase import create_client, Client

st.set_page_config(
    page_title="Lets Do Eat",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("🗂️ Lets Do Eat")
st.caption("A cleaner personal dashboard for tasks, notes, and calendar routing.")


@st.cache_resource
def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")

    if not url or not key:
        st.error("Missing SUPABASE_URL or SUPABASE_KEY in your secrets/environment.")
        st.stop()

    return create_client(url, key)


supabase = get_supabase()


def safe_str(value):
    return "" if value is None else str(value)


def format_dt_for_google(start_dt: datetime, end_dt: datetime) -> str:
    return start_dt.strftime("%Y%m%dT%H%M%S"), end_dt.strftime("%Y%m%dT%H%M%S")


def build_google_calendar_url(task_row: dict) -> str:
    task_date = datetime.strptime(task_row["task_date"], "%Y-%m-%d").date()
    if task_row.get("task_time"):
        task_time = datetime.strptime(task_row["task_time"], "%H:%M:%S").time()
    else:
        task_time = time(9, 0)

    start_dt = datetime.combine(task_date, task_time)
    end_dt = start_dt + timedelta(minutes=60)
    start_text, end_text = format_dt_for_google(start_dt, end_dt)

    title = quote(safe_str(task_row.get("title", "")))
    details = quote(safe_str(task_row.get("notes", "")))
    dates = f"{start_text}/{end_text}"

    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={title}&dates={dates}&details={details}"
    )


def build_outlook_calendar_url(task_row: dict) -> str:
    task_date = datetime.strptime(task_row["task_date"], "%Y-%m-%d").date()
    if task_row.get("task_time"):
        task_time = datetime.strptime(task_row["task_time"], "%H:%M:%S").time()
    else:
        task_time = time(9, 0)

    start_dt = datetime.combine(task_date, task_time)
    end_dt = start_dt + timedelta(minutes=60)

    title = quote(safe_str(task_row.get("title", "")))
    body = quote(safe_str(task_row.get("notes", "")))
    start_iso = quote(start_dt.isoformat())
    end_iso = quote(end_dt.isoformat())

    return (
        "https://outlook.office.com/calendar/0/deeplink/compose?path=/calendar/action/compose"
        f"&subject={title}&body={body}&startdt={start_iso}&enddt={end_iso}"
    )


def create_ics_content(task_row: dict) -> str:
    task_date = datetime.strptime(task_row["task_date"], "%Y-%m-%d").date()

    if task_row.get("task_time"):
        task_time = datetime.strptime(task_row["task_time"], "%H:%M:%S").time()
    else:
        task_time = time(9, 0)

    start_dt = datetime.combine(task_date, task_time)
    end_dt = start_dt + timedelta(minutes=60)

    start_ics = start_dt.strftime("%Y%m%dT%H%M%S")
    end_ics = end_dt.strftime("%Y%m%dT%H%M%S")

    title = safe_str(task_row.get("title", "")).replace("\n", " ")
    notes = safe_str(task_row.get("notes", "")).replace("\n", "\\n")

    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Lets Do Eat//EN
BEGIN:VEVENT
SUMMARY:{title}
DESCRIPTION:{notes}
DTSTART:{start_ics}
DTEND:{end_ics}
END:VEVENT
END:VCALENDAR
"""


def fetch_tasks():
    response = (
        supabase.table("tasks")
        .select("*")
        .order("completed", desc=False)
        .order("task_date", desc=False)
        .order("task_time", desc=False)
        .execute()
    )
    return response.data if response.data else []


def add_task(title, notes, priority, task_date, task_time, is_work, is_personal):
    payload = {
        "title": title,
        "notes": notes,
        "priority": priority,
        "task_date": str(task_date),
        "task_time": str(task_time) if task_time else None,
        "is_work": is_work,
        "is_personal": is_personal,
        "completed": False,
    }
    supabase.table("tasks").insert(payload).execute()


def mark_complete(task_id, completed_value):
    (
        supabase.table("tasks")
        .update({"completed": completed_value})
        .eq("id", task_id)
        .execute()
    )


def delete_task(task_id):
    supabase.table("tasks").delete().eq("id", task_id).execute()


# ---------------------------
# small style tweaks
# ---------------------------
st.markdown(
    """
    <style>
    .small-muted {
        font-size: 0.85rem;
        color: #6b7280;
    }
    .task-card {
        padding: 0.35rem 0.2rem;
        margin-bottom: 0.2rem;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.35rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------
# quick add in expander
# ---------------------------
with st.expander("➕ Quick add task", expanded=False):
    col1, col2 = st.columns([2, 1])

    with col1:
        title = st.text_input("Task title", placeholder="Example: Finish notes, Gym, Review tickets")
        notes = st.text_area("Notes", placeholder="Optional details...", height=80)

    with col2:
        priority = st.selectbox("Priority", ["High", "Medium", "Low"], index=1)
        task_date = st.date_input("Date", value=date.today())
        use_time = st.checkbox("Add time", value=False)
        task_time = st.time_input("Time", value=time(9, 0), disabled=not use_time)
        tag_options = st.multiselect("Tag this task as", ["Work", "Personal"], default=["Personal"])

    if st.button("Add task", type="primary", use_container_width=True):
        if not title.strip():
            st.warning("Please enter a task title.")
        elif len(tag_options) == 0:
            st.warning("Pick at least one tag: Work or Personal.")
        else:
            add_task(
                title=title.strip(),
                notes=notes.strip(),
                priority=priority,
                task_date=task_date,
                task_time=task_time if use_time else None,
                is_work="Work" in tag_options,
                is_personal="Personal" in tag_options,
            )
            st.success("Task added.")
            st.rerun()


tasks = fetch_tasks()
df = pd.DataFrame(tasks)

if df.empty:
    st.info("No tasks yet. Open 'Quick add task' above and add your first one.")
    st.stop()

df["task_date"] = pd.to_datetime(df["task_date"]).dt.date
df["tag_label"] = df.apply(
    lambda row: "Both" if row["is_work"] and row["is_personal"]
    else "Work" if row["is_work"]
    else "Personal",
    axis=1
)
today = date.today()
df["is_overdue"] = (df["task_date"] < today) & (~df["completed"])

priority_order = {"High": 0, "Medium": 1, "Low": 2}
df["priority_sort"] = df["priority"].map(priority_order).fillna(9)

# ---------------------------
# compact top dashboard
# ---------------------------
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Total", int(len(df)))
m2.metric("Done", int(df["completed"].sum()))
m3.metric("Pending", int((~df["completed"]).sum()))
m4.metric("Overdue", int(df["is_overdue"].sum()))
m5.metric("High", int((df["priority"] == "High").sum()))
m6.metric("Today", int((df["task_date"] == today).sum()))

# ---------------------------
# compact filters
# ---------------------------
with st.container(border=True):
    f1, f2, f3, f4, f5, f6 = st.columns([2, 1, 1, 1, 1, 1])

    with f1:
        search_text = st.text_input("Search", placeholder="Search title or notes", label_visibility="collapsed")
        st.caption("Search")

    with f2:
        selected_date = st.date_input("Date", value=None, label_visibility="collapsed")
        st.caption("Date")

    with f3:
        tag_filter = st.selectbox("Tag", ["All", "Work", "Personal", "Both"], label_visibility="collapsed")
        st.caption("Tag")

    with f4:
        status_filter = st.selectbox("Status", ["All", "Pending", "Completed", "Overdue"], label_visibility="collapsed")
        st.caption("Status")

    with f5:
        sort_by = st.selectbox("Sort", ["Due date", "Priority", "Newest first"], label_visibility="collapsed")
        st.caption("Sort")

    with f6:
        hide_completed = st.checkbox("Hide done", value=False)

quick1, quick2, quick3, quick4 = st.columns(4)
with quick1:
    if st.button("Today only", use_container_width=True):
        st.session_state["quick_filter"] = "today"
with quick2:
    if st.button("High priority", use_container_width=True):
        st.session_state["quick_filter"] = "high"
with quick3:
    if st.button("Overdue", use_container_width=True):
        st.session_state["quick_filter"] = "overdue"
with quick4:
    if st.button("Clear quick filter", use_container_width=True):
        st.session_state["quick_filter"] = "all"

quick_filter = st.session_state.get("quick_filter", "all")

filtered_df = df.copy()

if search_text.strip():
    search_value = search_text.strip().lower()
    filtered_df = filtered_df[
        filtered_df["title"].str.lower().str.contains(search_value, na=False)
        | filtered_df["notes"].fillna("").str.lower().str.contains(search_value, na=False)
    ]

if selected_date:
    filtered_df = filtered_df[filtered_df["task_date"] == selected_date]

if tag_filter != "All":
    filtered_df = filtered_df[filtered_df["tag_label"] == tag_filter]

if status_filter == "Pending":
    filtered_df = filtered_df[filtered_df["completed"] == False]
elif status_filter == "Completed":
    filtered_df = filtered_df[filtered_df["completed"] == True]
elif status_filter == "Overdue":
    filtered_df = filtered_df[filtered_df["is_overdue"] == True]

if hide_completed:
    filtered_df = filtered_df[filtered_df["completed"] == False]

if quick_filter == "today":
    filtered_df = filtered_df[filtered_df["task_date"] == today]
elif quick_filter == "high":
    filtered_df = filtered_df[filtered_df["priority"] == "High"]
elif quick_filter == "overdue":
    filtered_df = filtered_df[filtered_df["is_overdue"] == True]

if sort_by == "Due date":
    filtered_df = filtered_df.sort_values(by=["completed", "task_date", "priority_sort"])
elif sort_by == "Priority":
    filtered_df = filtered_df.sort_values(by=["completed", "priority_sort", "task_date"])
elif sort_by == "Newest first":
    filtered_df = filtered_df.sort_values(by=["created_at"], ascending=False)

# ---------------------------
# mini calendar area
# ---------------------------
with st.expander("📅 Calendar quick jump", expanded=False):
    calendar_date = st.date_input("Click a date", value=today, key="calendar_jump")
    if st.button("Show tasks for this date", use_container_width=True):
        filtered_df = filtered_df[filtered_df["task_date"] == calendar_date]

# ---------------------------
# task list
# ---------------------------
st.subheader(f"Tasks ({len(filtered_df)})")

if filtered_df.empty:
    st.info("No tasks match your filters.")
else:
    for _, row in filtered_df.iterrows():
        status_icon = "✅" if row["completed"] else "⏳"
        overdue_text = " • OVERDUE" if row["is_overdue"] else ""

        with st.container(border=True):
            top_left, top_right = st.columns([5, 2])

            with top_left:
                st.markdown(f"**{status_icon} {row['title']}**")
                when_text = f"{row['task_date']}"
                if row["task_time"] and row["task_time"] != "None":
                    when_text += f" at {str(row['task_time'])[:5]}"

                st.markdown(
                    f"<div class='small-muted'>"
                    f"{row['priority']} • {row['tag_label']} • {when_text}{overdue_text}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                if safe_str(row["notes"]).strip():
                    with st.expander("Notes"):
                        st.write(row["notes"])

            with top_right:
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(
                        "Undo" if row["completed"] else "Done",
                        key=f"complete_{row['id']}",
                        use_container_width=True,
                    ):
                        mark_complete(row["id"], not row["completed"])
                        st.rerun()

                with c2:
                    if st.button("Delete", key=f"delete_{row['id']}", use_container_width=True):
                        delete_task(row["id"])
                        st.rerun()

                task_payload = {
                    "title": row["title"],
                    "notes": row["notes"],
                    "task_date": row["task_date"].strftime("%Y-%m-%d"),
                    "task_time": None if pd.isna(row["task_time"]) else str(row["task_time"]),
                }

                with st.expander("Calendar options"):
                    ics_content = create_ics_content(task_payload)

                    st.download_button(
                        "Apple Calendar",
                        data=ics_content,
                        file_name=f"{row['title']}.ics",
                        mime="text/calendar",
                        key=f"apple_{row['id']}",
                        use_container_width=True,
                    )

                    st.link_button(
                        "Google Calendar",
                        build_google_calendar_url(task_payload),
                        use_container_width=True,
                    )

                    st.link_button(
                        "Work Calendar",
                        build_outlook_calendar_url(task_payload),
                        use_container_width=True,
                    )
