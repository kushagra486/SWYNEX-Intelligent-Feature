"""Design Agent v0: generate -> build -> test -> fix -> verify loop for a
single-file HTML page, closing the loop from the Project Report's flagship
demo scenario (RESEARCH -> DESIGN -> CODE -> BUILD -> TEST -> FIX -> VERIFY).

Generation goes through the model router (coding tier). Verification runs a
real headless Chromium (Playwright) in a separate subprocess (see
playwright_check_script.py for why: Playwright's sync API needs a Proactor
event loop for its Node driver subprocess, which conflicts with this app's
Selector loop) to load the page and check for JS errors — "evidence over
claims," not just "the model said it should work." All external network
requests are blocked during the check: this is a build/test loop, not a
live browsing session.
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import uuid

from .htmllint import lint_html
from .router import route_chat

CODE_FENCE_RE = re.compile(r"```(?:html)?\s*\n(.*?)```", re.DOTALL)

MAX_RETRIES = 2

_APP_DIR = os.path.dirname(__file__)
_BACKEND_DIR = os.path.dirname(_APP_DIR)
OUTPUT_ROOT = os.path.join(_BACKEND_DIR, "..", "workers", "generated_sites")
CHECK_SCRIPT = os.path.join(_APP_DIR, "playwright_check_script.py")

GENERATE_PROMPT = """You are a design + frontend agent. Build a complete, self-contained single-file HTML page for the following task.
Inline all CSS in a <style> tag and all JS in a <script> tag - no external resources, no CDN links, no fonts, no images from the network (the page will be tested with network access blocked).
Output ONLY a single html code block with the full page - no explanation before or after.

Task: {task}"""

FIX_PROMPT = """The following HTML page was tested in a headless browser and produced errors or invalid markup.

Page:
```html
{html}
```

Errors (HTML lint and browser console/JS):
{errors}

Fix the page so it loads without errors. Keep it self-contained (inline CSS/JS only, no network resources).
Output ONLY a single html code block with the corrected full page - no explanation."""


def _extract_code(text: str) -> str:
    match = CODE_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _check_page_sync(html_path: str, screenshot_path: str) -> list[str]:
    result = subprocess.run(
        [sys.executable, CHECK_SCRIPT, html_path, screenshot_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return [f"checker process failed: {result.stderr.strip() or result.stdout.strip()}"]
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])["errors"]
    except (json.JSONDecodeError, IndexError, KeyError):
        return [f"could not parse checker output: {result.stdout!r} {result.stderr!r}"]


async def generate_and_verify_page(task: str, max_retries: int = MAX_RETRIES) -> dict:
    site_id = uuid.uuid4().hex[:12]
    site_dir = os.path.join(OUTPUT_ROOT, site_id)
    os.makedirs(site_dir, exist_ok=True)
    html_path = os.path.join(site_dir, "index.html")
    screenshot_path = os.path.join(site_dir, "screenshot.png")

    llm_result = await route_chat(GENERATE_PROMPT.format(task=task), tier="coding")
    html = _extract_code(llm_result["text"])

    attempts = []
    for attempt_num in range(max_retries + 1):
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        browser_errors = await asyncio.to_thread(_check_page_sync, os.path.abspath(html_path), screenshot_path)
        errors = lint_html(html) + browser_errors
        attempts.append({"attempt": attempt_num + 1, "errors": errors, "ok": len(errors) == 0})

        if not errors:
            return {
                "success": True,
                "site_id": site_id,
                "html_path": html_path,
                "screenshot_path": screenshot_path,
                "attempts": attempts,
            }

        if attempt_num == max_retries:
            break

        llm_result = await route_chat(
            FIX_PROMPT.format(html=html, errors="\n".join(errors)), tier="coding"
        )
        html = _extract_code(llm_result["text"])

    return {
        "success": False,
        "site_id": site_id,
        "html_path": html_path,
        "screenshot_path": screenshot_path if os.path.exists(screenshot_path) else None,
        "attempts": attempts,
    }
