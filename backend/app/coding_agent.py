"""Coding agent: generate -> run in sandbox -> check -> retry loop.

This is deliberately the smallest version of the Autonomous Execution Loop
from the Project Report (observe -> plan -> execute -> verify -> retry):
generate code for the task, run it in the sandbox, and if it fails, feed the
error back to the model and ask for a fix, up to a bounded number of
retries. Every attempt is recorded so the outcome is auditable, not just
claimed.
"""

import re

from .router import route_chat
from .sandbox import run_python

CODE_FENCE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)

MAX_RETRIES = 2

GENERATE_PROMPT = """You are a coding agent. Write a complete, runnable Python 3 script for the following task.
Output ONLY a single python code block with the full script — no explanation before or after.

Task: {task}"""

FIX_PROMPT = """The following Python script was run and failed.

Script:
```python
{code}
```

stdout:
{stdout}

stderr:
{stderr}

Fix the script so it runs successfully and accomplishes the original task: {task}
Output ONLY a single python code block with the corrected full script — no explanation."""


def _extract_code(text: str) -> str:
    match = CODE_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


async def generate_and_run(task: str, max_retries: int = MAX_RETRIES) -> dict:
    attempts = []

    llm_result = await route_chat(GENERATE_PROMPT.format(task=task), tier="coding")
    code = _extract_code(llm_result["text"])

    for attempt_num in range(max_retries + 1):
        sandbox_result = await run_python(code)
        attempts.append(
            {
                "attempt": attempt_num + 1,
                "code": code,
                "stdout": sandbox_result.stdout,
                "stderr": sandbox_result.stderr,
                "exit_code": sandbox_result.exit_code,
                "timed_out": sandbox_result.timed_out,
                "ok": sandbox_result.ok,
            }
        )

        if sandbox_result.ok:
            return {"success": True, "final_code": code, "attempts": attempts}

        if attempt_num == max_retries:
            break

        fix_prompt = FIX_PROMPT.format(
            code=code,
            stdout=sandbox_result.stdout or "(empty)",
            stderr=sandbox_result.stderr or "(empty)",
            task=task,
        )
        llm_result = await route_chat(fix_prompt, tier="coding")
        code = _extract_code(llm_result["text"])

    return {"success": False, "final_code": code, "attempts": attempts}
