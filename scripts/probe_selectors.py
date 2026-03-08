"""Probe a real LinkedIn job page to discover which CSS classes/IDs contain the job description."""
import os, time, re, subprocess
from dotenv import load_dotenv
load_dotenv("secrets/.env")
import undetected_chromedriver as uc

out = subprocess.check_output(
    ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"],
    stderr=subprocess.DEVNULL,
).decode()
version_main = int(re.search(r"(\d+)\.", out).group(1))

opts = uc.ChromeOptions()
opts.page_load_strategy = "eager"
driver = uc.Chrome(options=opts, use_subprocess=True, version_main=version_main)
driver.implicitly_wait(1)

# Login
driver.get("https://www.linkedin.com/login")
time.sleep(4)
driver.find_element("id", "username").send_keys(os.getenv("LINKEDIN_EMAIL"))
driver.find_element("id", "password").send_keys(os.getenv("LINKEDIN_PASSWORD"))
driver.find_element("css selector", '[type="submit"]').click()
time.sleep(6)

# Go to a specific job page
driver.get("https://www.linkedin.com/jobs/view/4381266069/")
time.sleep(8)   # wait longer so React can render

# 1. Dump all CSS classes containing 'job', 'description', or 'detail'
classes = driver.execute_script("""
    var els = document.querySelectorAll('[class]');
    var found = new Set();
    els.forEach(function(el) {
        el.className.toString().split(/\s+/).forEach(function(c) {
            if (c && (c.includes('job') || c.includes('description') || c.includes('detail')))
                found.add(c);
        });
    });
    return Array.from(found).sort();
""")
print("=== CLASSES WITH job/description/detail ===")
for c in classes:
    print(" ", c)

# 2. Check if the known selectors are present
selectors = [
    "#job-details",
    ".jobs-description-content__text",
    ".show-more-less-html__markup",
    ".jobs-box__html-content",
    ".jobs-description__content",
    ".description__text",
    "article.jobs-description__container",
]
print("\n=== SELECTOR PRESENCE CHECK ===")
for sel in selectors:
    found = driver.execute_script(
        "return !!document.querySelector(arguments[0]);", sel
    )
    print(f"  {'✓' if found else '✗'}  {sel}")

# 3. Show first 300 chars of body text to confirm page loaded
body = driver.execute_script("return document.body.innerText.slice(0, 400);")
print("\n=== BODY PREVIEW ===")
print(body)

driver.quit()
