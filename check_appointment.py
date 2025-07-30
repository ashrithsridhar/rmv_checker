#!/usr/bin/env python3
import os
import sys
import time
import asyncio
import datetime
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# ── CONFIG ────────────────────────────────────────────────────────────────────
DEFAULT_URL = (
    "https://rmvmassdotappt.cxmflow.com/Appointment/Index/"
    "2c052fc7-571f-4b76-9790-7e91f103c408?"
    "AccessToken=32a318aa-213e-4dd8-acc6-df063cb9fcd7"
)
DATA_ID = "20"  # Worcester button data-id

# ── LOOP SETTINGS ──────────────────────────────────────────────────────────────
LOOP_COUNT    = int(os.getenv("LOOP_COUNT", "5"))     # how many times to retry
SLEEP_SECONDS = int(os.getenv("SLEEP_SECONDS", "60")) # wait between attempts

# ── PUSHOVER CONFIG ──────────────────────────────────────────────────────────
PUSHOVER_API_URL   = "https://api.pushover.net/1/messages.json"
PUSHOVER_USER_KEY  = os.getenv("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.getenv("PUSHOVER_API_TOKEN")

# ── FUNCTIONS ──────────────────────────────────────────────────────────────────
async def fetch_after_click() -> str:
    """Headless‑click the Worcester button and return the resulting HTML."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(DEFAULT_URL)
        await page.click(f"button[data-id='{DATA_ID}']")
        await page.wait_for_timeout(2000)  # allow calendar tiles to render
        html = await page.content()
        await browser.close()
        return html

def page_has_july_or_august(html: str) -> bool:
    """Return True if 'Jul', 'Aug', or 'Sep' appears in the HTML text."""
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).lower()
    return any(m in text for m in ("jul", "aug"))

def send_notification(message: str, title: str = "RMV Checker"):
    """Send a push via Pushover, if credentials are set."""
    if not (PUSHOVER_USER_KEY and PUSHOVER_API_TOKEN):
        print("⚠️ Pushover keys missing; skipping notification", file=sys.stderr)
        return

    payload = {
        "token":   PUSHOVER_API_TOKEN,
        "user":    PUSHOVER_USER_KEY,
        "title":   title,
        "message": message,
        "url":     DEFAULT_URL,
    }
    try:
        r = requests.post(PUSHOVER_API_URL, data=payload, timeout=10)
        r.raise_for_status()
        print("📲 Pushover notification sent")
    except requests.RequestException as e:
        print(f"❌ Notification error: {e}", file=sys.stderr)

def main():
    for attempt in range(LOOP_COUNT):
        now = datetime.datetime.utcnow().isoformat()
        try:
            html = asyncio.run(fetch_after_click())
            print(f"[{now}] Attempt {attempt+1}/{LOOP_COUNT} — fetched {len(html)} chars")
            snippet = html[:200].replace("\n"," ")
            print("  Snippet:", snippet, "…")
            if page_has_july_or_august(html):
                msg = f"Slots in July/August detected at {now}!"
                print("✅", msg)
                send_notification(msg)
                # return  # stop further loops once found
            else:
                print("❌ No July/August slots this time.")
        except Exception as e:
            print(f"[{now}] ❌ Error in fetch attempt: {e}", file=sys.stderr)

        # only sleep if more attempts remain
        if attempt < LOOP_COUNT - 1:
            print(f"⏳ Sleeping {SLEEP_SECONDS}s before next check...\n")
            time.sleep(SLEEP_SECONDS)

if __name__ == "__main__":
    main()
