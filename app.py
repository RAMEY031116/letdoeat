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
st.caption("A simple personal dashboard for tasks, calendar routing, and notes.")

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

def fetch_tasks():
    response = (
        supabase.table("tasks")
        .select("*")
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

with st.container(border=True):
    st.subheader("Quick add")
    col1, col2 = st.columns([2, 1])

    with col1:
        title = st.text_input("Task title", placeholder="Example: Finish notes, Gym, Review tickets")
        notes = st.text_area("Notes", placeholder="Optional details...", height=100)

    with col2:
        priority = st.selectbox("Priority", ["High", "Medium", "Low"], index=1)
        task_date = st.date_input("Date", value=date.today())
        use_time = st.checkbox("Add time", value=False)
        task_time = st.time_input("Time", value=time(9, 0), disabled=not use_time)
        tag_options = st.multiselect("Tag this task as", ["Work", "Personal"], default=["Personal"])

    add_clicked = st.button("Add task", type="primary", use_container_width=True)

    if add_clicked:
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
    st.info("No tasks yet. Add your first task above.")
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

a, b, c, d = st.columns(4)
a.metric("Total", int(len(df)))
b.metric("Completed", int(df["completed"].sum()))
c.metric("Pending", int((~df["completed"]).sum()))
d.metric("Overdue", int(df["is_overdue"].sum()))

e, f, g = st.columns(3)
e.metric("High priority", int((df["priority"] == "High").sum()))
f.metric("Work tasks", int(df["is_work"].sum()))
g.metric("Personal tasks", int(df["is_personal"].sum()))

with st.container(border=True):
    st.subheader("Search and filters")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        search_text = st.text_input("Search", placeholder="Search title or notes")
    with c2:
        selected_date = st.date_input("Filter by date", value=None)
    with c3:
        tag_filter = st.selectbox("Filter by tag", ["All", "Work", "Personal", "Both"])
    with c4:
        status_filter = st.selectbox("Filter by status", ["All", "Pending", "Completed", "Overdue"])

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

with st.container(border=True):
    st.subheader("Calendar quick view")
    calendar_date = st.date_input("Click a date to jump to it", value=today, key="calendar_jump")
    if st.button("Show tasks for this date", use_container_width=True):
        filtered_df = filtered_df[filtered_df["task_date"] == calendar_date]

st.subheader("Tasks")

if filtered_df.empty:
    st.info("No tasks match your filters.")
else:
    for _, row in filtered_df.iterrows():
        overdue_text = "  •  OVERDUE" if row["is_overdue"] else ""
        complete_label = "✅ Completed" if row["completed"] else "⏳ Pending"

        with st.container(border=True):
            top1, top2 = st.columns([4, 2])

            with top1:
                st.markdown(f"### {row['title']}")
                st.write(
                    f"**Priority:** {row['priority']}  \n"
                    f"**Tag:** {row['tag_label']}  \n"
                    f"**Status:** {complete_label}{overdue_text}"
                )

                if row["task_time"] and row["task_time"] != "None":
                    st.write(f"**When:** {row['task_date']} at {str(row['task_time'])[:5]}")
                else:
                    st.write(f"**When:** {row['task_date']}")

                if safe_str(row["notes"]).strip():
                    with st.expander("Show notes"):
                        st.write(row["notes"])

            with top2:
                toggle_label = "Mark incomplete" if row["completed"] else "Mark complete"
                if st.button(toggle_label, key=f"complete_{row['id']}", use_container_width=True):
                    mark_complete(row["id"], not row["completed"])
                    st.rerun()

                if st.button("Delete", key=f"delete_{row['id']}", use_container_width=True):
                    delete_task(row["id"])
                    st.rerun()

                st.link_button(
                    "Add to Personal Calendar",
                    build_google_calendar_url({
                        "title": row["title"],
                        "notes": row["notes"],
                        "task_date": row["task_date"].strftime("%Y-%m-%d"),
                        "task_time": None if pd.isna(row["task_time"]) else str(row["task_time"]),
                    }),
                    use_container_width=True,
                )

                st.link_button(
                    "Add to Work Calendar",
                    build_outlook_calendar_url({
                        "title": row["title"],
                        "notes": row["notes"],
                        "task_date": row["task_date"].strftime("%Y-%m-%d"),
                        "task_time": None if pd.isna(row["task_time"]) else str(row["task_time"]),
                    }),
                    use_container_width=True,
                )
