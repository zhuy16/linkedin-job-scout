"""
linkedin_fetch.py — Selenium-based LinkedIn job scraper.

Strategy:
  1. Log in with email + password (undetected-chromedriver bypasses basic bot checks)
  2. Search jobs with the configured query and time filter
  3. Scroll the results panel to collect all visible job IDs
  4. Visit each full job page (linkedin.com/jobs/view/<id>/) to extract details
  5. Post-filter to remove internship / tutor roles missed by the query

Notes:
  - LinkedIn occasionally shows a security checkpoint on first login from a new
    session. The script pauses 90 s for you to complete it manually (headless=False).
  - CSS selectors change from time to time; multiple fallbacks are provided.
  - Chrome must be installed. undetected-chromedriver manages ChromeDriver automatically.
"""
import logging
import os
import random
import re
import time
import urllib.parse
from typing import Dict, List, Optional

import undetected_chromedriver as uc
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _sleep(lo: float = 1.0, hi: float = 3.0) -> None:
    time.sleep(random.uniform(lo, hi))


def _try_text(driver, selectors: List[str]) -> str:
    """Try a list of CSS selectors; return the text of the first match.
    Uses a single JS call to avoid repeated implicit-wait penalties."""
    selector_list = ", ".join(selectors)
    try:
        result = driver.execute_script(
            "var el = document.querySelector(arguments[0]); "
            "return el ? (el.innerText || el.textContent || '').trim() : '';",
            selector_list,
        )
        return result or ""
    except Exception:
        return ""


def _try_attr(driver, selectors: List[str], attr: str) -> str:
    selector_list = ", ".join(selectors)
    try:
        result = driver.execute_script(
            "var el = document.querySelector(arguments[0]); "
            "return el ? (el.getAttribute(arguments[1]) || '').trim() : '';",
            selector_list, attr,
        )
        return result or ""
    except Exception:
        return ""


# ── selectors (multi-fallback because LinkedIn changes them regularly) ─────────

_TITLE = [
    "h1.job-details-jobs-unified-top-card__job-title",
    "h2.job-details-jobs-unified-top-card__job-title",
    "h1.jobs-unified-top-card__job-title",
    "h2.jobs-unified-top-card__job-title",
    ".jobs-unified-top-card__job-title h1",
    ".jobs-unified-top-card__job-title h2",
    ".job-details-jobs-unified-top-card__job-title",
    "h2.t-24.t-bold.inline",
    "a.job-card-list__title",
    ".topcard__title",
]
_COMPANY = [
    ".job-details-jobs-unified-top-card__company-name a",
    ".jobs-unified-top-card__company-name a",
    ".job-details-jobs-unified-top-card__company-name",
    ".topcard__org-name-link",
]
_LOCATION = [
    ".job-details-jobs-unified-top-card__bullet",
    ".jobs-unified-top-card__bullet",
    ".topcard__flavor--bullet",
]
# Ordered from most-specific to least; deliberately excludes outer skeleton
# wrappers (#job-details, div[class*='description']) which appear before the
# description XHR finishes, causing empty extractions.
_DESCRIPTION = [
    ".show-more-less-html__markup",
    ".jobs-description-content__text--stretch",
    ".jobs-description-content__text",
    ".jobs-description__content .mt4",
    ".jobs-description__content",
    ".description__text--rich",
    ".description__text",
    ".jobs-box__html-content",
]
# Comma-joined for a single document.querySelector() call
_DESCRIPTION_CSS = ", ".join(_DESCRIPTION)
_SEE_MORE = [
    "button.jobs-description__footer-button",
    "button[aria-label*='more description']",
    "button[aria-label*='Show more']",
]


# ── main class ────────────────────────────────────────────────────────────────

class LinkedInJobFetcher:
    def __init__(self, email: str, password: str, headless: bool = False):
        self.email    = email
        self.password = password
        self.headless = headless
        self.driver: Optional[uc.Chrome] = None
        self._search_url: str = ""

    # ── driver lifecycle ──────────────────────────────────────────────────────

    def _start_driver(self) -> None:
        opts = uc.ChromeOptions()
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1440,900")
        opts.add_argument("--lang=en-US")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--no-first-run")
        opts.add_argument("--no-default-browser-check")
        opts.add_argument("--disable-default-apps")
        # Detect installed Chrome version and pass it explicitly so
        # undetected-chromedriver downloads a matching ChromeDriver.
        import subprocess, re
        try:
            out = subprocess.check_output(
                ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"],
                stderr=subprocess.DEVNULL,
            ).decode()
            version_main = int(re.search(r"(\d+)\.", out).group(1))
            logger.info("Detected Chrome version: %s (major=%d)", out.strip(), version_main)
        except Exception:
            version_main = None  # let undetected-chromedriver auto-detect
        self.driver = uc.Chrome(options=opts, use_subprocess=True, version_main=version_main)
        self.driver.implicitly_wait(1)  # keep short — fallback loops multiply this

    def _quit(self) -> None:
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def _screenshot(self, tag: str) -> None:
        try:
            os.makedirs("data/screenshots", exist_ok=True)
            path = f"data/screenshots/{tag}_{int(time.time())}.png"
            self.driver.save_screenshot(path)
            logger.info("Screenshot saved: %s", path)
        except Exception:
            pass

    # ── human-like typing ─────────────────────────────────────────────────────

    def _type(self, element, text: str) -> None:
        element.clear()
        for ch in text:
            element.send_keys(ch)
            time.sleep(random.uniform(0.04, 0.13))

    # ── login ─────────────────────────────────────────────────────────────────

    def _login(self) -> bool:
        logger.info("Navigating to LinkedIn login page…")
        self.driver.get("https://www.linkedin.com/login")
        _sleep(2, 4)

        try:
            email_field = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            self._type(email_field, self.email)
            _sleep(0.5, 1.2)

            pw_field = self.driver.find_element(By.ID, "password")
            self._type(pw_field, self.password)
            _sleep(0.3, 0.8)

            self.driver.find_element(By.CSS_SELECTOR, '[type="submit"]').click()
            _sleep(4, 7)

        except TimeoutException:
            logger.error("Login form not found — is LinkedIn down?")
            self._screenshot("login_timeout")
            return False

        url = self.driver.current_url
        if any(x in url for x in ("feed", "mynetwork", "/home", "/jobs")):
            logger.info("✓ Logged in successfully")
            return True

        if any(x in url for x in ("checkpoint", "challenge", "verification", "captcha")):
            logger.warning(
                "⚠  Security challenge detected.  "
                "You have 90 s to complete it in the browser, then the script will continue."
            )
            self._screenshot("checkpoint")
            time.sleep(90)
            url = self.driver.current_url
            if any(x in url for x in ("feed", "mynetwork", "/home", "/jobs")):
                logger.info("✓ Challenge cleared — continuing")
                return True
            logger.error("Still on challenge page after 90 s — aborting")
            return False

        if "login" in url:
            logger.error("Login failed — wrong credentials or account locked")
            self._screenshot("login_failed")
            return False

        # Some redirects land on an unexpected page but login succeeded
        logger.info("Login result URL: %s (continuing)", url)
        return True

    # ── collect job IDs ───────────────────────────────────────────────────────

    def _collect_job_ids(self, query: str, days_back: int) -> List[str]:
        tpr = f"r{days_back * 86400}"
        enc = urllib.parse.quote(query)
        self._search_url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={enc}&f_TPR={tpr}&sortBy=DD"
        )
        logger.info("Job search URL: %s", self._search_url)
        self.driver.get(self._search_url)
        _sleep(3, 5)

        job_ids: List[str] = []
        seen: set = set()
        stale_scrolls = 0

        while stale_scrolls < 8:
            # Collect job IDs from visible cards
            cards = self.driver.find_elements(
                By.CSS_SELECTOR,
                ".jobs-search-results__list-item, .scaffold-layout__list-item",
            )
            prev_len = len(job_ids)

            for card in cards:
                jid = (
                    card.get_attribute("data-occludable-job-id")
                    or card.get_attribute("data-job-id")
                    or ""
                )
                if not jid:
                    try:
                        a = card.find_element(By.CSS_SELECTOR, "a[href*='/jobs/view/']")
                        m = re.search(r"/jobs/view/(\d+)", a.get_attribute("href") or "")
                        jid = m.group(1) if m else ""
                    except NoSuchElementException:
                        pass

                if jid and jid not in seen:
                    seen.add(jid)
                    job_ids.append(jid)

            # Scroll the list panel
            try:
                panel = self.driver.find_element(
                    By.CSS_SELECTOR,
                    ".jobs-search-results-list, .scaffold-layout__list",
                )
                self.driver.execute_script("arguments[0].scrollBy(0, 1200);", panel)
                _sleep(1.5, 2.5)
            except NoSuchElementException:
                break

            if len(job_ids) == prev_len:
                stale_scrolls += 1
            else:
                stale_scrolls = 0

        logger.info("Collected %d job IDs from search results", len(job_ids))
        return job_ids

    # ── fetch one job page ────────────────────────────────────────────────────

    def _fetch_detail(self, job_id: str) -> Optional[Dict]:
        url = f"https://www.linkedin.com/jobs/view/{job_id}/"
        try:
            # Ensure we are on the search results page so the card is clickable.
            # LinkedIn loads job descriptions via XHR into the right panel when
            # a card is clicked — navigating directly to /jobs/view/<id>/ often
            # gives an empty skeleton.
            if self._search_url not in (self.driver.current_url or ""):
                self.driver.get(self._search_url)
                _sleep(2, 3)

            try:
                card = self.driver.find_element(
                    By.CSS_SELECTOR,
                    f'[data-occludable-job-id="{job_id}"], '
                    f'[data-job-id="{job_id}"]',
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", card)
                _sleep(0.3, 0.6)
                card.click()
                # Wait for the URL / panel to update to this specific job ID
                # before reading the DOM — prevents stale content from previous card.
                try:
                    WebDriverWait(self.driver, 8).until(EC.url_contains(job_id))
                except TimeoutException:
                    pass  # some LinkedIn layouts don't update the URL; continue anyway
            except NoSuchElementException:
                # Card not in DOM — fall back to direct navigation
                logger.debug("Card not found in panel for job %s, navigating directly", job_id)
                self.driver.get(url)
                _sleep(3, 4)

            # Wait for the INNER description markup (not the outer skeleton wrapper
            # #job-details which appears immediately before the XHR finishes).
            # Allow up to 12 s for the right panel to populate.
            try:
                WebDriverWait(self.driver, 12).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR, _DESCRIPTION_CSS
                    ))
                )
            except TimeoutException:
                logger.warning("Description markup not found for job %s after 12 s", job_id)

            # Expand "See more" — wait for the button to render, then click it
            try:
                see_more = WebDriverWait(self.driver, 4).until(
                    EC.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        "button.jobs-description__footer-button, "
                        "button.show-more-less-html__button--more, "
                        "button[aria-label*='more description'], "
                        "button[aria-label*='Show more']",
                    ))
                )
                self.driver.execute_script("arguments[0].click();", see_more)
                _sleep(0.8, 1.2)   # wait for expanded content to render
            except TimeoutException:
                pass  # no "See more" button — content already fully visible

            title       = _try_text(self.driver, _TITLE)
            company     = _try_text(self.driver, _COMPANY)
            location    = _try_text(self.driver, _LOCATION)
            description = _try_text(self.driver, _DESCRIPTION)

            logger.info("Job %s — title=%r  desc_len=%d  desc_preview=%r",
                        job_id, title, len(description), description[:120])

            # If description is suspiciously short the right-panel didn't fully
            # render — fall back to direct navigation and try once more.
            if len(description) < 150:
                logger.info("Short description (%d chars) for %s — retrying via direct URL",
                            len(description), job_id)
                self.driver.get(url)
                _sleep(3, 4)
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((
                            By.CSS_SELECTOR, _DESCRIPTION_CSS
                        ))
                    )
                    try:
                        see_more2 = WebDriverWait(self.driver, 4).until(
                            EC.element_to_be_clickable((
                                By.CSS_SELECTOR,
                                "button.jobs-description__footer-button, "
                                "button.show-more-less-html__button--more",
                            ))
                        )
                        self.driver.execute_script("arguments[0].click();", see_more2)
                        _sleep(0.8, 1.2)
                    except TimeoutException:
                        pass
                    title2       = _try_text(self.driver, _TITLE) or title
                    company2     = _try_text(self.driver, _COMPANY) or company
                    location2    = _try_text(self.driver, _LOCATION) or location
                    description2 = _try_text(self.driver, _DESCRIPTION)
                    if len(description2) > len(description):
                        title, company, location, description = \
                            title2, company2, location2, description2
                        logger.info("Fallback succeeded — desc_len=%d", len(description))
                except TimeoutException:
                    logger.warning("Fallback direct-nav also timed out for %s", job_id)

            if not title and not description:
                logger.warning("Could not extract content for job %s — skipping", job_id)
                return None
            if not description:
                logger.warning("No description for job %s — will score with title only", job_id)

            return {
                "title":       title,
                "company":     company,
                "location":    location,
                "url":         url,
                "description": description[:4000],
            }

        except Exception as e:
            logger.warning("Error fetching job %s: %s", job_id, e)
            return None

    # ── post-processing filter ────────────────────────────────────────────────

    @staticmethod
    def _keep(job: Dict, skip_keywords: List[str]) -> bool:
        combined = f"{job.get('title', '')} {job.get('description', '')}".lower()
        for kw in skip_keywords:
            if kw.lower() in combined:
                logger.info("Filtered out '%s' (matched '%s')", job.get("title"), kw)
                return False
        return True

    # ── public entry point ────────────────────────────────────────────────────

    def fetch_jobs(
        self,
        query:         str,
        days_back:     int       = 1,
        max_jobs:      int       = 30,
        skip_keywords: List[str] = None,
    ) -> List[Dict]:
        """
        Log in, search jobs, fetch details, apply filters.
        Returns a list of job dicts (title, company, location, url, description).
        """
        if skip_keywords is None:
            skip_keywords = ["intern", "internship", "tutor", "tutoring"]

        try:
            self._start_driver()
            if not self._login():
                return []

            job_ids = self._collect_job_ids(query, days_back)
            if not job_ids:
                logger.warning("No job IDs found — try a broader query or longer days_back")
                return []

            jobs: List[Dict] = []
            for i, jid in enumerate(job_ids[:max_jobs], 1):
                logger.info("Fetching detail %d/%d — job %s", i, min(len(job_ids), max_jobs), jid)
                job = self._fetch_detail(jid)
                if job and self._keep(job, skip_keywords):
                    jobs.append(job)
                _sleep(1.0, 2.0)  # polite delay between page loads

            logger.info("Final job count after filtering: %d", len(jobs))
            return jobs

        except Exception as e:
            logger.error("Unexpected error in fetch_jobs: %s", e, exc_info=True)
            self._screenshot("fetch_error")
            return []

        finally:
            self._quit()
