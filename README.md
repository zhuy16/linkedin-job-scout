# 🔍 LinkedIn Job Scout

![version](https://img.shields.io/badge/version-0.1.0-blue)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

Monitors LinkedIn daily, scores each new job against your private candidate profile using **Claude Sonnet**, and emails you a digest of the best matches — fully automated, no manual browsing.

```
LinkedIn (Selenium) → Dedup (SQLite) → LLM Scoring (Claude) → Email Digest (SMTP)
```

Your credentials, resume, and job history **never leave your machine** — all private files are gitignored.

---

## 🚀 Setup (one time)

**Prerequisites:** Python 3.9+, Google Chrome, an Anthropic API key, a Gmail App Password.

```bash
git clone https://github.com/zhuy16/linkedin-job-scout.git
cd linkedin-job-scout
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash scripts/setup.sh          # copies template files, installs daily scheduler
```

`setup.sh` creates the two private files for you to fill in (see below).

---

## ✏️ What to personalise (three files)

### 1 · `secrets/.env` — credentials

| Variable | What to put | Where to get it |
|----------|-------------|-----------------|
| `LINKEDIN_EMAIL` | Your LinkedIn login email | Your LinkedIn account |
| `LINKEDIN_PASSWORD` | Your LinkedIn password | Your LinkedIn account |
| `ANTHROPIC_API_KEY` | `sk-ant-...` key | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| `SMTP_USER` | Your Gmail address | Your Google account |
| `SMTP_PASSWORD` | 16-character App Password | [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) (requires 2FA) |
| `ALERT_EMAIL` | Where to send the digest | Any email you check |

**Anthropic cost:** ~$0.003 per job scored · 25 jobs/day ≈ $2.25/month. Load $5 to start at [console.anthropic.com/billing](https://console.anthropic.com/billing).

> `secrets/.env` is gitignored — it will never be committed or pushed.

---

### 2 · `config/search.yaml` — search preferences & schedule

```yaml
# ── What jobs to look for ────────────────────────────────────────────────────
query: '("Your Field" OR "Your Role Type") NOT ("intern" OR "unwanted")'
#       Replace with your own keywords using LinkedIn boolean syntax

skip_keywords: [intern, internship, tutor]
#              Jobs containing these words are dropped after fetching

# ── Scoring ──────────────────────────────────────────────────────────────────
fit_threshold: 60      # only email jobs scoring >= this (0–100)
days_back: 3           # look back N days in search results
max_jobs: 25           # cap per run (~$0.075/day at 25 jobs)

# ── Daily schedule (re-run setup.sh after changing) ──────────────────────────
schedule_hour: 8       # 24-hour clock
schedule_minute: 0     # → runs silently at 08:00 every day

# ── LLM model ────────────────────────────────────────────────────────────────
llm_model: "claude-sonnet-4-5"
```

After changing `schedule_hour` or `schedule_minute`, re-run `bash scripts/setup.sh` to apply.

---

### 3 · `private/profile_summary.txt` — your background

This is what Claude reads when scoring each job. The more specific and honest it is, the more useful the scores. Fill in:

- Skills, tools, languages, domain expertise
- Career history (titles, companies, focus areas, key achievements)
- Target roles and industries
- Location / remote preferences and constraints
- Salary expectations
- What you are **not** interested in

`setup.sh` copies the template (`private/profile_summary.example.txt`) for you to edit.

> `private/profile_summary.txt` is gitignored — it will never be committed or pushed.

---

## ▶️ Running manually

```bash
python run.py                  # full run — email sent if jobs qualify
python run.py --headless       # no browser window (same as scheduled run)
python run.py --dry-run        # score jobs and print results, skip email
python run.py --days N         # override days_back for this run only
```

**First run tip:** run without `--headless` so you can see the browser. LinkedIn may show a security checkpoint on first login — the script pauses 90 s for you to complete it. After that, `--headless` works reliably.

**Test scoring without opening LinkedIn:**
```bash
python scripts/test_score.py
```

---

## 🗓 Scheduled run (macOS)

The daily run is completely silent — no browser window, no notifications, nothing visible.
You will only know it ran when the email arrives (or doesn't, if nothing qualified that day).

```bash
launchctl list | grep jobscout      # confirm it's registered
launchctl start com.jobscout.daily  # trigger it right now without waiting
tail -f data/launchd.log            # watch the log
```

---

## 📖 Full documentation

See [docs/SETUP.md](docs/SETUP.md) for pipeline internals, troubleshooting, project structure, and roadmap.

---

## 📄 License

MIT — personal use only. Review [LinkedIn's User Agreement](https://www.linkedin.com/legal/user-agreement) before use.
