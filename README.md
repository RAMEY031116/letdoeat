# Lockzilla / Lock In 90 — Shared Data V4

This Streamlit build is designed to share the same Supabase data used by the native iPhone Lockzilla app.

## What V4 adds

- Task start + end time ranges (`task_time` + `task_end_time`)
- Google / Outlook / ICS calendar links use the saved task range
- Body-weight logging and progression from `body_weights`
- Focus history supports both the original Streamlit columns and the newer iPhone columns
- Workout history reads the same `workouts` rows written by iPhone
- Daily review uses `daily_score` and the native app's 9-part score model
- Strong-day streak rule aligned to 70%+

## Deploy

1. Keep your existing Streamlit Secrets unchanged:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `AUTH_REQUIRED`
   - `PUBLIC_PROFILE_ID`
   - `APP_TIMEZONE`
2. Your Supabase migrations have already been applied during the native-app work.
3. Replace your repository's `app.py` and `style.css` with the V4 files.
4. Keep your existing `requirements.txt` and `.streamlit/config.toml`.
5. Push to GitHub; Streamlit Community Cloud should redeploy automatically.

`schema_v4.sql` is included as a reference / safe additive migration. Because you already added these columns/tables while building the iPhone app, you should not need to run it again.
