
# LOCK IN 90

A mobile-first Streamlit + Supabase app built around a 90-day lock-in programme.

## Features
- Day X / 90 dashboard
- daily lock-in checklist
- sleep, study, business, art, room reset
- calories / protein target checks
- lunch cardio + evening weight-training structure
- workout logging
- focus-session logging
- tasks and priorities
- Google Calendar links
- Outlook Calendar links
- Apple / ICS downloads
- progress charts
- optional Supabase authentication

## Setup

### 1. Create tables
Run `schema.sql` in Supabase SQL Editor.

This creates new tables. It does not change your old Lets Do Eat tables.

### 2. Private / no-login mode
Use this while it is only for you.

Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and add your real values:

```toml
SUPABASE_URL = "..."
SUPABASE_KEY = "..."
AUTH_REQUIRED = "false"
PUBLIC_PROFILE_ID = "a-random-uuid"
```

Important: no-login mode has RLS disabled, so do not publicly share the deployed app.

### 3. Multi-user mode later
Before sharing with friends:

1. Run `enable_auth_rls.sql` in Supabase.
2. Set:

```toml
AUTH_REQUIRED = "true"
```

3. Remove `PUBLIC_PROFILE_ID`.

Then each person signs up and only sees their own data.

### 4. Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

### 5. Deploy
Push the folder to a new GitHub repo, for example `lockin90`, then deploy it on Streamlit Community Cloud and add the same secrets there.

### Mobile
Open the deployed URL on your phone and use Add to Home Screen.
