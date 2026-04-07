# Task Router - beginner guide

## What this app does
- Add tasks
- Add notes
- Set date and optional time
- Mark complete or incomplete
- Delete tasks
- Filter by date, tag, status, and search
- Open Google Calendar for personal
- Open Outlook Calendar for work

## Files included
- app.py
- requirements.txt
- schema.sql
- .streamlit/config.toml
- secrets-example.toml

## Step 1 - Create a Supabase project
1. Go to Supabase
2. Create a new project
3. Open SQL Editor
4. Paste the contents from schema.sql
5. Run it

## Step 2 - Get your keys
In Supabase:
1. Go to Project Settings
2. Open API
3. Copy the Project URL
4. Copy the anon public key

## Step 3 - Add secrets
Create this file:

.streamlit/secrets.toml

Paste:

SUPABASE_URL = "https://YOUR-PROJECT-ID.supabase.co"
SUPABASE_KEY = "YOUR-ANON-KEY"

## Step 4 - Install packages
Run:

pip install -r requirements.txt

## Step 5 - Run the app
Run:

streamlit run app.py

## Step 6 - Deploy later
Push to GitHub and connect it to Streamlit Community Cloud.

## Next upgrades later
- edit task
- login
- recurring tasks
- workout section
- charts
