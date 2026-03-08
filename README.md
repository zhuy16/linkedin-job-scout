# 🔍 LinkedIn Job Scout Agent

A local, privacy-first job-monitoring pipeline powered by **Claude Sonnet**.

Every day it:
1. Logs into LinkedIn with your credentials and searches for new bioinformatics / computational biology roles
2. Scores each job against **your private candidate profile** using an LLM
3. Emails you only the jobs above your fit threshold (default **60 / 100**)
4. Remembers what it has already seen — no duplicate alerts

```
LinkedIn (Selenium) → dedup (SQLite) → LLM scoring (Claude) → email alert (SMTP)
```

Private files — **gitignored, never uploaded**:
| File | Contents |
|------|----------|
| `secrets/.env` | LinkedIn + Anthropic + email credentials |
| `private/profile_summary.txt` | Your background, preferences, salary range |
| `data/jobs.db` | Seen jobs + LLM scores |

---

## ✨ What you get in your inbox

A formatted HTML email showing, for each qualifying job:

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
