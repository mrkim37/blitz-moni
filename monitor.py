import os
import sys
import time
import logging
import urllib.request
from datetime import datetime

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

EMAIL = os.getenv("BLITZ_EMAIL", "siamehosun@gmail.com")
PASSWORD = os.getenv("BLITZ_PASSWORD", "")
APP_DASH_URL = os.getenv(
    "APP_DASH_URL",
    "https://dashboard.blitz.cloud/apps/e1fadfc4-06d8-41db-ae68-f013609eeed0",
)
APP_URL = os.getenv("APP_URL", "https://hyperdl.sunxsiam.prod.page")
INTERVAL = int(os.getenv("CHECK_INTERVAL_MIN", "15")) * 60
WAKE_TIMEOUT = int(os.getenv("WAKE_TIMEOUT_SEC", "120"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("blitz-waker")

# The primary button on the app page, shown only while the app is asleep.
WAKE_BTN = 'button.btn-primary:text-is("Wake it")'


def login_if_needed(page):
    """Open the app page; if Blitz bounces us to Keycloak, sign in."""
    page.goto(APP_DASH_URL, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector("#username, .detail-head-sub", timeout=30000)
    except PWTimeout:
        raise RuntimeError("Neither login form nor app page appeared")

    if page.locator("#username").count():
        log.info("Login form detected, signing in as %s", EMAIL)
        page.fill("#username", EMAIL)
        page.fill("#password", PASSWORD)
        page.click("#kc-login")
        page.wait_for_url("**/dashboard.blitz.cloud/**", timeout=60000)
        if "/apps/" not in page.url:
            page.goto(APP_DASH_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".detail-head-sub", timeout=30000)
        if page.locator("#username").count():
            raise RuntimeError("Login failed - check email/password")


def check_once(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    try:
        login_if_needed(page)
        page.wait_for_timeout(2500)  # let the client-side app render

        status = page.locator(".detail-head-sub span:nth-of-type(2)").first
        try:
            log.info("Dashboard status text: %s", status.inner_text(timeout=3000))
        except Exception:
            pass

        btn = page.locator(WAKE_BTN)
        if btn.count() and btn.first.is_visible():
            log.info('"Wake it" button visible -> app is asleep, clicking')
            btn.first.click()
            try:
                btn.first.wait_for(state="hidden", timeout=WAKE_TIMEOUT * 1000)
                log.info('Button is gone -> app is awake')
            except PWTimeout:
                log.warning('Button still visible after %ss - will retry next cycle', WAKE_TIMEOUT)
        else:
            log.info('No "Wake it" button -> app is already awake')
    finally:
        ctx.close()

    # Real internet visit also counts as activity for Blitz and keeps it warm.
    try:
        with urllib.request.urlopen(APP_URL, timeout=30) as r:
            log.info("Ping %s -> HTTP %s", APP_URL, r.status)
    except Exception as e:
        log.warning("Ping %s failed: %s", APP_URL, e)


def main():
    if not PASSWORD:
        log.error("BLITZ_PASSWORD is empty. Set it in .env")
        sys.exit(1)
    log.info("Starting. Checking every %s min", INTERVAL // 60)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        while True:
            started = time.time()
            try:
                check_once(browser)
            except Exception as e:
                log.error("Check failed: %s", e)
            sleep_for = max(30, INTERVAL - (time.time() - started))
            log.info("Next check at %s", datetime.fromtimestamp(time.time() + sleep_for).strftime("%H:%M:%S"))
            time.sleep(sleep_for)


if __name__ == "__main__":
    main()
