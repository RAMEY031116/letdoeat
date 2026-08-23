
# Lock In 90 v3

This is the bigger "personal operating system" version.

## New in v3

### Today Command Centre
- Day X / 90
- today's score
- streak
- sleep
- automatic "Next Action"
- daily visual timeline
- one quick check-in form

### No Negotiation
The app looks at the time and what you have already completed, then shows the next incomplete block.

### Focus Mode
- Study / Business / Art / Room target cards
- large focus timer
- completed focus blocks add to today's totals automatically

### Brain Dump
Capture anything quickly.
Later, on Tasks, turn it into today's task, mark it done, or delete it.

### Training
Very simple:
- lunch movement
- your own evening gym
- recovery when needed
No invented workout split.

### Tasks + Calendar
- normal task list
- Google Calendar
- Outlook
- Apple / ICS
- Brain Dump inbox

### Review
- 90-day visual map
- last-seven-day numbers
- consistency chart
- weekly review
- programme target editor

## Upgrade steps

1. Replace your GitHub `app.py` and `style.css`.
2. Replace/update `requirements.txt`.
3. Run `schema_v3.sql` once in Supabase SQL Editor.
4. Keep the SAME `PUBLIC_PROFILE_ID` you already use.
5. Add this optional secret:
   `APP_TIMEZONE = "Europe/London"`

Do not run `enable_auth_rls.sql` while you are still in no-login/private mode.
