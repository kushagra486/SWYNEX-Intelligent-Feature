"""Standalone script run as a subprocess (not imported) to check a generated
HTML page in headless Chromium and report JS/console errors as JSON.

Runs as a fresh process rather than in-process because Playwright's sync API
launches its own Node driver via asyncio.create_subprocess_exec, which needs
a Proactor event loop on Windows. The main app's event loop is forced to
Selector (psycopg's async mode requires it) and that's a process-wide
asyncio policy, so a plain subprocess is the clean way to give Playwright
the loop it needs without disturbing the app's loop.

Usage: python playwright_check_script.py <html_path> <screenshot_path>
Prints a JSON object {"errors": [...]} to stdout.
"""

import json
import sys

from playwright.sync_api import sync_playwright


def main(html_path: str, screenshot_path: str) -> None:
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        page.on("console", lambda msg: errors.append(f"console: {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
        page.route(
            "**/*",
            lambda route: route.abort() if not route.request.url.startswith("file://") else route.continue_(),
        )

        try:
            page.goto(f"file:///{html_path}", wait_until="load", timeout=10000)
            page.wait_for_timeout(500)
            page.screenshot(path=screenshot_path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"navigation failed: {exc}")
        finally:
            browser.close()

    print(json.dumps({"errors": errors}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
