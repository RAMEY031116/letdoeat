
# Lock In 90 — rebuilt version

This is a clean rebuild of the app.

## What is fixed
- Focus target values are NOT Streamlit metrics anymore.
- `60 min`, `45 min`, `30 min`, `15 min` are custom HTML with explicit dark text.
- Cleaner mobile layout.
- More consistent button/input contrast.
- Better Today, Training, Focus, Tasks, and Progress sections.
- Focus timer added.
- Calories/protein actual values + targets added.
- Quick notes added.
- Existing calendar functionality retained.

## Supabase
Run `schema_v2.sql` in Supabase SQL Editor.

It is safe to run if you already ran the earlier schema:
- it uses `create table if not exists`
- it uses `add column if not exists`
- it does not delete your existing Lock In data

Do NOT run `enable_auth_rls.sql` while you are still using private/no-login mode.

## Streamlit secrets
Use your real Supabase URL and publishable key.

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-publishable-key"
AUTH_REQUIRED = "false"
PUBLIC_PROFILE_ID = "your-existing-public-profile-id"
```

Keep the SAME PUBLIC_PROFILE_ID you are already using so the new version continues to see your existing data.

## GitHub
Replace the old app files with:
- `app.py`
- `style.css`
- `requirements.txt`

Then run `schema_v2.sql` once in Supabase.

You do not need to change your existing Streamlit secrets if they already work.
