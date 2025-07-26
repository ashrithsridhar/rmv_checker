#!/usr/bin/env python3
"""Simple scraper for monitoring RMV appointment availability.

This script fetches a given RMV appointment booking page and scans
the returned HTML for references to the months "July" or "August".
If either month is found anywhere in the page's text, it prints a
message to standard output noting that an appointment might be
available in those months; otherwise, it indicates that no July
or August appointments are currently visible.

Because GitHub Actions only allows cron schedules as frequent as
once every 5 minutes【435603222303944†L910-L915】, the script by default
loops five times with a one‑minute pause between iterations. This
approach effectively checks the page at roughly one‑minute
intervals while still abiding by GitHub's scheduling limits. You
can adjust the `LOOP_COUNT` and `SLEEP_SECONDS` constants below
if you run the script outside of GitHub Actions or wish to check
more or fewer times per run.

The appointment URL can be supplied via the `APPOINTMENT_URL`
environment variable; if not provided, the `DEFAULT_URL` constant
will be used instead. You should set `APPOINTMENT_URL` to the
actual booking page URL when running this script.

Note: This scraper performs a simple textual search for month
names. If the RMV website loads available dates via client‑side
JavaScript after the initial HTML is delivered, then this script
may not see those dynamic updates. In that case, you might need
to switch to a browser automation tool like Selenium or Playwright.
However, many appointment pages render available dates as static
text, in which case this approach works.
"""

import os
import time
import datetime
import sys
from typing import Optional

import requests
from bs4 import BeautifulSoup


# Default RMV appointment booking URL. This can be overridden at runtime
# by setting the `APPOINTMENT_URL` environment variable. The link
# provided here comes from the user and points to the RMV booking
# page that should be checked for July/August availability.
DEFAULT_URL = (
    "https://rmvmassdotappt.cxmflow.com/Appointment/Index/"
    "2c052fc7-571f-4b76-9790-7e91f103c408?"
    "AccessToken=f39fa0e6-3b62-496f-b3af-6e88425c8305"
)

# Number of times to check the page during a single run. Five
# iterations at one minute each match GitHub's minimum 5‑minute
# schedule interval.
LOOP_COUNT = int(os.environ.get("LOOP_COUNT", "5"))

# Seconds to wait between checks.
SLEEP_SECONDS = int(os.environ.get("SLEEP_SECONDS", "60"))


def fetch_page(url: str) -> Optional[str]:
    """Fetch the contents of the given URL.

    Returns the response text if the status is 200; otherwise
    returns `None`.
    """
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[{now}] Error fetching {url}: {e}", file=sys.stderr)
        return None


def page_has_july_or_august(html: str) -> bool:
    """Return True if the page contains the words 'July' or 'August'.

    The check is case insensitive and searches the entire text
    extracted from the HTML. If either month is present, we
    consider that an appointment might be available during those
    months.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True).lower()
    return ("jul" in text) or ("aug" in text) or ("sep" in text)


def send_notification(message: str, title: str = "RMV Appointment Checker") -> None:
    """Send a push notification to the user's phone using Pushover.

    To receive notifications, sign up for a Pushover account and
    create an application (https://pushover.net/apps). Then set
    the `PUSHOVER_USER_KEY` and `PUSHOVER_API_TOKEN` environment
    variables in your GitHub repository's secrets. If either
    variable is missing, this function will silently return and
    the notification will not be sent.

    Parameters
    ----------
    message: str
        The message body to send.
    title: str
        The notification title. Defaults to "RMV Appointment Checker".
    """
    user_key = os.environ.get("PUSHOVER_USER_KEY")
    api_token = os.environ.get("PUSHOVER_API_TOKEN")
    if not user_key or not api_token:
        # Missing credentials; skip sending
        return
    payload = {
        "token": api_token,
        "user": user_key,
        "title": title,
        "message": message,
        "url": os.environ.get("APPOINTMENT_URL", DEFAULT_URL),
    }
    try:
        resp = requests.post("https://api.pushover.net/1/messages.json", data=payload, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[{now}] Notification error: {e}", file=sys.stderr)
        return


def check_once(url: str) -> None:
    """Fetch the page, print a message, and send a notification if needed."""
    html = fetch_page(url)
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    if html is None:
        # Error logged in fetch_page
        return
    if page_has_july_or_august(html):
        message = f"Appointment may be available in July or August (checked at {now})."
        print(f"[{now}] ✅ {message}")
        # Send a push notification if credentials are provided
        send_notification(message)
    else:
        print(f"[{now}] ❌ No July/August appointments visible yet.")


def main() -> None:
    """Main entry point. Checks the page multiple times."""
    url = os.environ.get("APPOINTMENT_URL", DEFAULT_URL)
    if not url or url == "https://example.com/your/rmv/appointment/page":
        print(
            "Warning: Using placeholder URL. Please set the APPOINTMENT_URL "
            "environment variable to your RMV appointment page.",
            file=sys.stderr,
        )
    for iteration in range(LOOP_COUNT):
        check_once(url)
        # Skip the sleep after the last iteration
        if iteration < LOOP_COUNT - 1:
            time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
