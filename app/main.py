"""
main.py — Orchestrator for the LinkedIn Job Scout Agent.

Pipeline:
    LinkedIn (Selenium) → dedup (SQLite) → LLM scoring (Claude) → email alert (SMTP)

Run via:
    python run.py [--dry-run] [--headless] [--days N]
"""
import argparse
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
import yaml

from app.db             import init_db, is_seen, save_job, mark_notified
from app.linkedin_fetch import LinkedInJobFetcher
from app.score_jobs     import score_job
from app.notify         import send_alert


# ── logging setup ─────────────────────────────────────────────────────────────

os.makedirs("data", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/job_agent.log"),
    ],
)
logger = logging.getLogger("main")


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_env() -> None:
    for candidate in ("secrets/.env", ".env"):
        p = Path(candidate)
        if p.exists():
            load_dotenv(p)
            logger.info("Loaded credentials from %s", p)
            return
    logger.warning("No .env file found — relying on shell environment variables")


def _require_env(keys: list) -> None:
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        logger.error("Copy  secrets/.env.example  →  secrets/.env  and fill it in")
        sys.exit(1)


def _load_profile() -> str:
    p = Path("private/profile_summary.txt")
    if not p.exists():
        logger.error("private/profile_summary.txt not found")
        logger.error(
            "Copy  private/profile_summary.example.txt  →  private/profile_summary.txt  "
            "and replace the placeholder text with your actual background."
        )
        sys.exit(1)
    text = p.read_text().strip()
    if not text:
        logger.error("private/profile_summary.txt is empty — please fill it in")
        sys.exit(1)
    return text


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="LinkedIn Job Scout Agent")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch and score jobs but do NOT send the email alert",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run Chrome in headless mode (no visible browser window)",
    )
    parser.add_argument(
        "--days", type=int, default=None,
        help="Override the days_back setting from config/search.yaml",
    )
    args = parser.parse_args()

    _load_env()
    _require_env([
        "LINKEDIN_EMAIL", "LINKEDIN_PASSWORD",
        "ANTHROPIC_API_KEY",
        "SMTP_USER", "SMTP_PASSWORD", "ALERT_EMAIL",
    ])

    # ── load config ───────────────────────────────────────────────────────────
    with open("config/search.yaml") as f:
        cfg = yaml.safe_load(f)

    query     = cfg["query"]
    threshold = int(cfg.get("fit_threshold", 60))
    days_back = args.days or int(cfg.get("days_back", 1))
    max_jobs  = int(cfg.get("max_jobs", 30))
    model     = cfg.get("llm_model", "claude-sonnet-4-5")
    skip_kw   = cfg.get("skip_keywords", [])

    profile = _load_profile()

    init_db()

    logger.info("═" * 65)
    logger.info(
        "Job Scout starting  |  threshold=%d  days=%d  max_jobs=%d  model=%s",
        threshold, days_back, max_jobs, model,
    )
    logger.info("Query: %s", query)
    if args.dry_run:
        logger.info("DRY RUN — email will NOT be sent")

    # ── 1. Fetch from LinkedIn ────────────────────────────────────────────────
    fetcher = LinkedInJobFetcher(
        email=os.getenv("LINKEDIN_EMAIL"),
        password=os.getenv("LINKEDIN_PASSWORD"),
        headless=args.headless,
    )
    logger.info("Fetching jobs from LinkedIn…")
    raw_jobs = fetcher.fetch_jobs(
        query=query,
        days_back=days_back,
        max_jobs=max_jobs,
        skip_keywords=skip_kw,
    )
    logger.info("Fetched %d job(s)", len(raw_jobs))

    if not raw_jobs:
        logger.warning(
            "No jobs fetched. Possible causes: bad credentials, LinkedIn challenge, "
            "no new postings, or scraper selectors need updating."
        )
        return

    # ── 2. Dedup ──────────────────────────────────────────────────────────────
    new_jobs = [j for j in raw_jobs if j.get("url") and not is_seen(j["url"])]
    skipped  = len(raw_jobs) - len(new_jobs)
    logger.info("%d new job(s) to score  (%d already seen / skipped)", len(new_jobs), skipped)

    if not new_jobs:
        logger.info("Nothing new to score today.")
        return

    # ── 3. Score with LLM ────────────────────────────────────────────────────
    qualified: list = []

    for i, job in enumerate(new_jobs, 1):
        logger.info(
            "[%d/%d] Scoring: %s @ %s",
            i, len(new_jobs), job.get("title", "?"), job.get("company", "?"),
        )
        result = score_job(job, profile, model=model)
        save_job(job, result)

        if result:
            fit   = result.get("fit_score", 0)
            verd  = result.get("verdict", "?")
            logger.info("  → %3d/100  verdict=%s", fit, verd)
            if fit >= threshold:
                qualified.append({**job, **result})
        else:
            logger.warning("  → scoring failed — job saved to DB but not scored")

        time.sleep(1)  # light rate-limit on Anthropic API

    logger.info(
        "%d qualifying job(s) at or above threshold=%d", len(qualified), threshold
    )

    # ── 4. Notify ─────────────────────────────────────────────────────────────
    if not qualified:
        logger.info("No qualifying jobs today — no email sent.")
        return

    qualified.sort(key=lambda x: x.get("fit_score", 0), reverse=True)

    if args.dry_run:
        logger.info("DRY RUN results:")
        for j in qualified:
            logger.info("  [%d] %s @ %s  →  %s",
                        j.get("fit_score"), j.get("title"),
                        j.get("company"),  j.get("url"))
    else:
        send_alert(
            jobs=qualified,
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER"),
            smtp_password=os.getenv("SMTP_PASSWORD"),
            from_email=os.getenv("SMTP_USER"),
            to_email=os.getenv("ALERT_EMAIL"),
            threshold=threshold,
        )
        for j in qualified:
            mark_notified(j["url"])

    logger.info("Job Scout complete.")


if __name__ == "__main__":
    main()
