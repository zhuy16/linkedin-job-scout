# Setup Guide

Complete instructions for first-time setup, credential preparation, and understanding how the pipeline works.

---

## How it works

### 1 · Fetch
`app/linkedin_fetch.py` drives a real Chrome browser (via `undetected-chromedriver`) to:
- Log into LinkedIn with your credentials
- Run a boolean keyword search with a configurable time window
- Scroll the results panel to collect all visible job card IDs
- Click each card to trigger LinkedIn's XHR load of the full description into the right panel
- Wait for the actual description markup (not the skeleton wrapper), expand "See more", extract title / company / location / description

### 2 · Deduplicate
`app/db.py` maintains a local SQLite database of every job URL ever seen. Already-seen jobs are skipped — you never get alerted about the same posting twice.

### 3 · Score
`app/score_jobs.py` sends each new job to Claude Sonnet with:
- The full job description
- Your private `private/profile_summary.txt`

Claude returns structured JSON at `temperature=0`:
```json
{
  "fit_score": 72,
  "verdict": "maybe",
  "reasons": ["Strong domain alignment...", "..."],
  "concerns": ["Location mismatch...", "..."]
}
```
Jobs below `fit_threshold` are recorded in the DB but never emailed.

### 4 · Notify
`app/notify.py` builds a styled HTML email with all qualifying jobs sorted by score, then sends it via Gmail SMTP. If nothing qualifies, no email is sent.

---

## Prerequisites

- **macOS or Linux** (Windows untested)
- **Python 3.9+**
- **Google Chrome** installed — ChromeDriver is managed automatically, no manual download
- A **Gmail account** with an App Password (requires 2FA)
- An **Anthropic API key** with available credits

---

## What to prepare before running

### 1. LinkedIn credentials
Your regular LinkedIn email and password. The scraper logs in as you in a real browser — the login will appear in your LinkedIn session history like any other device.

### 2. Anthropic API key
1. Go to [console.anthropic.com](https://console.anthropic.com) → API Keys
2. Create a new key
3. Make sure the workspace tied to that key has a positive credit balance (workspaces are separate — credits in one workspace don't apply to keys from another)

### 3. Gmail App Password
Standard Gmail passwords are blocked by SMTP. You need an App Password:
1. Enable [2-Step Verification](https://myaccount.google.com/security) on your Google account
2. Go to [App Passwords](https://myaccount.google.com/apppasswords)
3. Create one — name it anything (e.g. "Job Scout")
4. Copy the 16-character password immediately — Google only shows it once

### 4. Your candidate profile (`private/profile_summary.txt`)
This is the most important input. The LLM scores each job by comparing the job description against what you write here. The more specific and honest you are, the more useful the scores:
- Skills and tools (languages, frameworks, platforms)
- Career history summary (titles, companies, focus areas)
- Target roles and industries
- Location constraints and remote preferences
- Salary expectations
- What you're *not* interested in

Use `private/profile_summary.example.txt` as a template.

---

## Installation

```bash
git clone https://github.com/zhuy16/linkedin-job-scout.git
cd linkedin-job-scout

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Credential setup

```bash
cp secrets/.env.example secrets/.env
```

Open `secrets/.env` and fill in all six values:

```dotenv
LINKEDIN_EMAIL=you@example.com
LINKEDIN_PASSWORD=your_linkedin_password

ANTHROPIC_API_KEY=sk-ant-...

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx   # 16-char Gmail App Password
ALERT_EMAIL=you@example.com         # where to send the digest (can be same as SMTP_USER)
```

`secrets/.env` is gitignored — it will never be committed.

---

## Profile setup

```bash
cp private/profile_summary.example.txt private/profile_summary.txt
# Edit private/profile_summary.txt — replace every placeholder with your real info
```

`private/profile_summary.txt` is gitignored — it will never be committed.

---

## Verifying the setup

Test LLM scoring without touching LinkedIn:
```bash
python scripts/test_score.py
```
This scores a hardcoded sample job against your profile and prints the JSON result. Edit `SAMPLE_JOB` inside the script to test any description you like.

---

## First run tips

- Run **without `--headless`** the first time so you can see the browser window. LinkedIn occasionally shows a security checkpoint (email verification / CAPTCHA) on first login from a new session. The script pauses 90 seconds for you to complete it.
- After passing the checkpoint once, `--headless` works reliably for subsequent runs.

---

## Scheduling (macOS launchd)

Runs silently at 8:00 AM every day — no Chrome window, zero interruption to your work:

```bash
# Register (one-time)
cp scheduler/com.jobscout.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jobscout.daily.plist

# Verify
launchctl list | grep jobscout

# Trigger manually without waiting for the schedule
launchctl start com.jobscout.daily

# View logs
tail -f data/launchd.log

# Remove
launchctl unload ~/Library/LaunchAgents/com.jobscout.daily.plist
rm ~/Library/LaunchAgents/com.jobscout.daily.plist
```

To change the time, edit the `StartCalendarInterval` block in `scheduler/com.jobscout.daily.plist`:
```xml
<key>Hour</key>   <integer>8</integer>
<key>Minute</key> <integer>0</integer>
```

> Your Mac must be awake at the scheduled time. If asleep, launchd runs the job the next time the machine wakes.

---

## Project structure

```
linkedin-job-scout/
├── app/
│   ├── main.py              # orchestrator: fetch → dedup → score → notify
│   ├── linkedin_fetch.py    # Selenium scraper (login, search, card-click extraction)
│   ├── score_jobs.py        # LLM fit scoring via Anthropic Claude
│   ├── notify.py            # HTML email digest via Gmail SMTP
│   └── db.py                # SQLite deduplication & persistence
├── config/
│   └── search.yaml          # all tunable settings — no secrets, safe to commit
├── docs/
│   └── SETUP.md             # this file
├── private/                 # gitignored
│   └── profile_summary.example.txt
├── secrets/                 # gitignored
│   └── .env.example
├── data/                    # gitignored — runtime data (DB, logs)
├── scripts/
│   └── test_score.py        # offline scoring test
├── scheduler/
│   └── com.jobscout.daily.plist
├── run.py
└── requirements.txt
```

---

## Limitations

- **LinkedIn TOS:** This automates a personal browser session for personal use. Review [LinkedIn's User Agreement](https://www.linkedin.com/legal/user-agreement). Do not use for large-scale or commercial scraping.
- **Selector drift:** LinkedIn occasionally changes its page structure. If descriptions stop extracting, the CSS selectors in `app/linkedin_fetch.py` may need updating — check the `_DESCRIPTION` and `_TITLE` lists near the top of the file.
- **LLM scores are estimates:** Use them as a triage signal. A thorough, honest `profile_summary.txt` dramatically improves quality.

---

## Roadmap

| Version | Status | What's included |
|---------|--------|----------------|
| **v0.1.0** | ✅ current | Fetch → score → deduplicate → email digest |
| v0.2 | planned | Vector store of past jobs for retrieval-augmented scoring |
| v0.3 | planned | Streamlit dashboard to review, label, and export results |
