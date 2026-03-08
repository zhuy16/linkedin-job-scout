#!/usr/bin/env python3
"""
Entry point for the LinkedIn Job Scout Agent.

Usage:
    python run.py                   # full run (Chrome window visible)
    python run.py --headless        # no browser window (good for cron)
    python run.py --dry-run         # fetch + score but skip the email
    python run.py --days 3          # look back 3 days instead of 1
"""
from app.main import main

if __name__ == "__main__":
    main()
