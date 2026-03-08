# 🔍 LinkedIn Job Scout

![version](https://img.shields.io/badge/version-0.1.0-blue)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

A **privacy-first, agentic job search pipeline** that monitors LinkedIn daily, scores every new posting against your private candidate profile using **Claude Sonnet**, and emails you a curated digest of the best matches — fully automated, no manual browsing required.

```
LinkedIn (Selenium)
       ↓
  Deduplication (SQLite)   ← already-seen jobs are skipped
       ↓
  LLM Scoring (Claude)     ← each job scored 0–100 against your profile
       ↓
  Email Alert (SMTP)       ← one digest per day, only if score ≥ threshold
```

**Private by design** — your credentials, resume, and job history never leave your machine:

| File | What it contains | In git? |
|------|-----------------|---------|
| `secrets/.env` | LinkedIn + Anthropic + email credentials | ❌ gitignored |
| `private/profile_summary.txt` | Your background, preferences, salary range | ❌ gitignored |
| `data/jobs.db` | Seen jobs + LLM scores (SQLite) | ❌ gitignored |
| `secrets/.env.example` | Template with placeholder values | ✅ safe to commit |
| `private/profile_summary.example.txt` | Template profile structure | ✅ safe to commit |

---

## ✨ What you get in your inbox

One HTML email per day (only sent when qualifying jobs are found) showing each match with:

- **Fit score** (0–100) and verdict badge (*Strong Match* / *Possible Match* / *Weak Match*)
- Bullet-point reasons the job is a good fit
- Bullet-point concerns or gaps
- One-click **View on LinkedIn** button

---

## 🛠 How it works

### 1 · Fetch
[`app/linkedin_fetch.py`](app/linkedin_fetch.py) drives a real Chrome browser using `undetected-chromedriver` to:
- Log into LinkedIn with your credentials
- Run a boolean keyword search with a configurable time window (e.g. "posted in last 3 days")
- Scroll the results panel to collect all visible job card IDs
- Click each card to trigger LinkedIn's XHR load of the full job description into the right panel
- Wait for the actual description markup to appear (not the skeleton wrapper), expand "See more", and extract title / company / location / description text

### 2 · Deduplicate
[`app/db.py`](app/db.py) maintains a local SQLite database of every job URL ever seen. Jobs already in the database are skipped, so you never get alerted about the same posting twice.

### 3 · Score
[`app/score_jobs.py`](app/score_jobs.py) sends each new job to **Claude Sonnet** with:
- The full job description
- Your private `profile_summary.txt` (skills, experience, target roles, location, salary)

Claude returns structured JSON:
```json
{
  "fit_score": 72,
  "verdict": "maybe",
  "reasons": ["Strong domain alignment...", "..."],
  "concerns": ["Location mismatch...", "..."]
}
```
Jobs scoring below `fit_threshold` (default 60) are recorded in the DB but do not trigger an email.

### 4 · Notify
[`app/notify.py`](app/notify.py) builds a styled HTML email listing all qualifying jobs sorted by score, then sends it via Gmail SMTP. If no jobs meet the threshold, no email is sent.

---

## ✅ Before you run — checklist

### Prerequisites
- **macOS or Linux** (Windows untested)
- **Python 3.9+**
- **Google Chrome** installed (any recent version — ChromeDriver is managed automatically)
- A **Gmail account** with an [App Password](https://myaccount.google.com/apppasswords) (requires 2FA enabled)
- An **Anthropic API key** from [console.anthropic.com](https://console.anthropic.com/) with available credits

### Prepare these four things

#### 1. LinkedIn credentials
Your regular LinkedIn email and password. The scraper logs in as you in a real browser, so whatever account you use will appear in LinkedIn's login history.

#### 2. Anthropic API key
Create a key at [console.anthropic.com](https://console.anthropic.com) → API Keys. Make sure your workspace has a positive credit balance before running.

#### 3. Gmail App Password
Regular Gmail passwords won't work — you need an App Password:
1. Enable [2-Step Verification](https://myaccount.google.com/security) on your Google account
2. Go to [App Passwords](https://myaccount.google.com/apppasswords)
3. Create one (name it "Job Scout" or anything)
4. Copy the 16-character password — you won't see it again

#### 4. Your candidate profile
The quality of the LLM scoring depends entirely on how well you describe yourself in `private/profile_summary.txt`. Be specific: include skills, experience level, target roles, location constraints, and salary expectations. The more honest and detailed, the better the scores.

---

## 🚀 Setup

```bash
# 1. Clone
git clone https://github.com/zhuy16/linkedin-job-scout.git
cd linkedin-job-scout

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Fill in credentials
cp secrets/.env.example secrets/.env
# Open secrets/.env and fill in all six values

# 5. Write your candidate profile
cp private/profile_summary.example.txt private/profile_summary.txt
# Open private/profile_summary.txt and replace every placeholder with your real info

# 6. Optionally tweak search settings
# Open config/search.yaml — adjust query, threshold, days_back, max_jobs
```

---

## ▶️ Running

```bash
python run.py                # full run — Chrome window visible, email sent if jobs qualify
python run.py --headless     # no browser window (good for cron / background)
python run.py --dry-run      # fetch + score, print results, skip email
python run.py --days 3       # search jobs posted in the last 3 days
```

**First run tip:** run without `--headless` so you can see the browser. LinkedIn sometimes shows a security checkpoint (email verification / CAPTCHA) on the first login from a new session. The script pauses 90 seconds for you to complete it.

**Test scoring without LinkedIn:**
```bash
python scripts/test_score.py
```
Edit the `SAMPLE_JOB` dict in that script to test any description against your profile.

---

## ⚙️ Configuration

All tunable settings live in [`config/search.yaml`](config/search.yaml) — no secrets, safe to commit:

```yaml
# Boolean keyword query passed directly to LinkedIn search
query: '("Bioinformatics" OR "Computational Biology") NOT ("intern" OR "tutor")'

# Belt-and-suspenders filter: skip any job whose title/description contains these words
skip_keywords:
  - intern
  - internship
  - tutor
  - tutoring

# Only email jobs with LLM fit score >= this value (0–100)
fit_threshold: 60

# Search jobs posted in the last N days
days_back: 3

# Max jobs to score per run (controls API cost and run time)
max_jobs: 25

# Claude model to use — check https://docs.anthropic.com/en/docs/about-claude/models
llm_model: "claude-sonnet-4-5"
```

---

## 🗓 Scheduling (macOS — runs automatically every day)

The scheduler uses macOS **launchd** — no cron setup, survives reboots, runs in the background with no Chrome window.

```bash
# Install (one-time setup)
cp scheduler/com.jobscout.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jobscout.daily.plist

# Verify it registered
launchctl list | grep jobscout

# Run manually right now (without waiting for schedule)
launchctl start com.jobscout.daily

# Check logs
tail -f data/launchd.log

# Disable / remove
launchctl unload ~/Library/LaunchAgents/com.jobscout.daily.plist
```

**Default schedule:** 8:00 AM daily. To change it, edit [`scheduler/com.jobscout.daily.plist`](scheduler/com.jobscout.daily.plist):
```xml
<key>Hour</key>   <integer>8</integer>
<key>Minute</key> <integer>0</integer>
```

> **Note:** Your Mac must be awake at the scheduled time. If it's asleep, launchd will run the job the next time it wakes.

---

## 🗂 Project structure

```
linkedin-job-scout/
├── app/
│   ├── main.py              # orchestrator: fetch → dedup → score → notify
│   ├── linkedin_fetch.py    # Selenium scraper (login, search, card-click extraction)
│   ├── score_jobs.py        # LLM fit scoring via Anthropic Claude
│   ├── notify.py            # HTML email digest via Gmail SMTP
│   └── db.py                # SQLite deduplication & persistence
├── config/
│   └── search.yaml          # ← all tunable settings (no secrets)
├── private/                 # gitignored — your private files go here
│   └── profile_summary.example.txt   # template (copy → profile_summary.txt)
├── secrets/                 # gitignored — credentials go here
│   └── .env.example         # template (copy → .env and fill in)
├── data/                    # gitignored — runtime data
│   └── jobs.db              # SQLite: seen jobs + scores
├── scripts/
│   └── test_score.py        # test LLM scoring offline (no LinkedIn needed)
├── scheduler/
│   └── com.jobscout.daily.plist   # macOS launchd agent (daily at 8 AM)
├── run.py                   # entry point
└── requirements.txt
```

---

## ⚠️ Limitations & notes

- **LinkedIn TOS:** This tool automates a personal browser session for personal job searching. Review [LinkedIn's User Agreement](https://www.linkedin.com/legal/user-agreement) before use. Do not use for large-scale or commercial scraping.
- **Selector drift:** LinkedIn changes its page structure occasionally. If job descriptions stop extracting, CSS selectors in `app/linkedin_fetch.py` may need updating.
- **LLM scores are estimates:** Treat them as a triage signal, not a final verdict. A detailed, honest `profile_summary.txt` gives much better results.
- **Headless mode:** Some LinkedIn security checks only trigger on non-headless sessions. If you see errors in headless mode, run once with a visible browser to clear any checkpoint.

---

## 🗺 Roadmap

| Version | Status | What's included |
|---------|--------|----------------|
| **v0.1.0** | ✅ current | Fetch → score → deduplicate → email digest |
| v0.2 | planned | Vector store (embeddings of past jobs) for retrieval-augmented scoring |
| v0.3 | planned | Streamlit dashboard to review, label, and export past results |

---

## 📄 License

MIT — use and modify freely for personal job search automation.


- **Fit score** (0–100) and verdict badge (*Strong Match* / *Possible Match*)
- Key reasons for the match
- Notable concerns or gaps
- One-click link to the LinkedIn job posting

---

## 🚀 Quick start

### 1 · Clone and create a virtual environment

```bash
git clone https://github.com/YOUR_USERNAME/linkedin-job-scout.git
cd linkedin-job-scout

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> **Chrome must be installed.**  
> `undetected-chromedriver` manages ChromeDriver automatically — no manual download needed.

### 2 · Set up credentials

```bash
cp secrets/.env.example secrets/.env
# Open secrets/.env and fill in every value
```

**Gmail app password** (required for SMTP):
1. Enable [2-Step Verification](https://myaccount.google.com/security) on your Google account
2. Go to [App Passwords](https://myaccount.google.com/apppasswords)
3. Create a new app password (name it anything, e.g. *Job Scout*)
4. Paste the 16-character password into `SMTP_PASSWORD`

**Anthropic API key**: get one at [console.anthropic.com](https://console.anthropic.com/).

### 3 · Set up your candidate profile

```bash
cp private/profile_summary.example.txt private/profile_summary.txt
# Replace the placeholder text with your actual background, preferences,
# target roles, location constraints, and salary range.
# The more specific you are, the better the LLM scores.
```

### 4 · Test scoring (no LinkedIn needed)

```bash
python scripts/test_score.py
```

This scores a hardcoded sample job against your profile and prints the JSON result.  
Edit the `SAMPLE_JOB` dict inside the script to test any job description you like.

### 5 · Run the full pipeline

```bash
python run.py              # full run, Chrome window visible
python run.py --headless   # no visible browser window
python run.py --dry-run    # fetch + score, but skip the email
python run.py --days 3     # look back 3 days instead of 1
```

---

## ⚙️ Configuration

Edit **`config/search.yaml`** — this file *is* committed to git (no secrets inside):

```yaml
query: '("Bioinformatics" OR "Computational Biology") NOT ("intern" OR "tutor")'

skip_keywords:          # post-processing filter (belt-and-suspenders)
  - intern
  - internship
  - tutor
  - tutoring

fit_threshold: 60       # 0–100: only alert if LLM score >= this
days_back:     1        # search jobs posted in the last N days
max_jobs:      30       # cap on jobs scored per run
llm_model: "claude-sonnet-4-5"   # update to latest model as needed
```

Check [Anthropic's model page](https://docs.anthropic.com/en/docs/about-claude/models) for the latest model IDs.

---

## 🗓 Scheduling (macOS)

### Option A — cron (simplest)

```bash
crontab -e
```

Add this line (runs every day at 08:30 AM):

```
30 8 * * * cd /path/to/linkedin-job-scout && \
  /path/to/.venv/bin/python run.py --headless >> data/cron.log 2>&1
```

### Option B — launchd (macOS-native, survives reboots)

```bash
# 1. Edit the two paths marked ← UPDATE in the plist
nano scheduler/com.jobscout.daily.plist

# 2. Install
cp scheduler/com.jobscout.daily.plist ~/Library/LaunchAgents/

# 3. Load
launchctl load ~/Library/LaunchAgents/com.jobscout.daily.plist

# 4. Verify
launchctl list | grep jobscout

# Run immediately for a quick test
launchctl start com.jobscout.daily
```

---

## 🗂 Project structure

```
linkedin-job-scout/
├── app/
│   ├── main.py              # orchestrator (fetch → dedup → score → notify)
│   ├── linkedin_fetch.py    # Selenium-based LinkedIn scraper
│   ├── score_jobs.py        # LLM fit scoring (Anthropic Claude)
│   ├── notify.py            # HTML email notification (SMTP)
│   └── db.py                # SQLite deduplication & persistence
├── config/
│   └── search.yaml          # ← edit keywords, threshold, model here
├── private/                 # gitignored
│   └── profile_summary.txt  # your private candidate profile
├── secrets/                 # gitignored
│   └── .env                 # credentials (.env.example is the template)
├── data/                    # gitignored
│   └── jobs.db              # seen jobs + LLM scores
├── scripts/
│   └── test_score.py        # test scoring without touching LinkedIn
├── scheduler/
│   └── com.jobscout.daily.plist   # macOS launchd daily schedule
├── run.py                   # entry point
└── requirements.txt
```

---

## ⚠️ Limitations & notes

### LinkedIn automation

- LinkedIn may occasionally display a **security checkpoint** (CAPTCHA / email verification) on first login from a new session.  
  The script pauses **90 seconds** for you to complete it in the browser window (requires non-headless mode).
- LinkedIn's page structure changes regularly. If the scraper stops extracting data, check `app/linkedin_fetch.py` for outdated CSS selectors.
- Selectors that stop working will produce empty `title`/`description` fields; the job will be skipped and logged.
- **Personal use only.** Review [LinkedIn's Terms of Service](https://www.linkedin.com/legal/user-agreement) before any large-scale deployment.

### LLM scoring

- Scores are **estimates** — treat them as a triage signal, not a final verdict.
- Quality improves significantly with a detailed, honest `profile_summary.txt`.
- The model is called with `temperature=0` for deterministic, reproducible results.

---

## 🗺 Version roadmap

| Version | What's included |
|---------|----------------|
| **v1 (current)** | Fetch → score → email alert with deduplication |
| v2 | Small vector store (resume + accepted/rejected jobs) for retrieval-augmented scoring |
| v3 | Streamlit dashboard to review, label, and export past results |

---

## 📄 License

MIT — use and modify freely for personal job search automation.
