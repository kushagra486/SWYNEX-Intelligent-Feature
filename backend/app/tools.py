"""Tool registry: each tool declares a permission level and an async handler.
Research Agent's first tool (web_search) lives here, plus a level-2 example
(clear_session_memory) to exercise the approval flow end to end.
"""

import httpx

from . import config
from .permissions import PermissionLevel


async def web_search(params: dict) -> dict:
    query = params.get("query", "")
    if not query:
        return {"error": "missing 'query' parameter"}
    if not config.TAVILY_API_KEY:
        return {
            "error": "TAVILY_API_KEY is not set. Get a free key at tavily.com and "
            "add it to .env to enable live web search.",
            "query": query,
        }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={"api_key": config.TAVILY_API_KEY, "query": query, "max_results": 5},
        )
        resp.raise_for_status()
        data = resp.json()
    results = [
        {"title": r.get("title"), "url": r.get("url"), "content": r.get("content")}
        for r in data.get("results", [])
    ]
    return {"query": query, "results": results}


async def coding_task(params: dict) -> dict:
    from .coding_agent import generate_and_run  # local import to avoid a cycle at module load

    task = params.get("task", "")
    if not task:
        return {"error": "missing 'task' parameter"}
    return await generate_and_run(task)


async def build_webpage(params: dict) -> dict:
    from .webagent import generate_and_verify_page  # local import to avoid a cycle at module load

    task = params.get("task", "")
    if not task:
        return {"error": "missing 'task' parameter"}
    return await generate_and_verify_page(task)


async def clear_session_memory(params: dict) -> dict:
    from .db import get_pool  # local import to avoid a cycle at module load

    session_id = params.get("session_id")
    if session_id is None:
        return {"error": "missing 'session_id' parameter"}
    pool = await get_pool()
    async with pool.connection() as conn:
        result = await conn.execute("DELETE FROM messages WHERE session_id = %s", (session_id,))
    return {"session_id": session_id, "deleted": True}


TOOL_REGISTRY = {
    "web_search": {
        "level": PermissionLevel.READ,
        "description": "Search the web for current information.",
        "handler": web_search,
    },
    "clear_session_memory": {
        "level": PermissionLevel.SYSTEM_CHANGE,
        "description": "Permanently delete all stored messages for a session.",
        "handler": clear_session_memory,
    },
    "coding_task": {
        "level": PermissionLevel.GENERATE,
        "description": "Generate and run Python code for a task in a sandboxed, network-isolated container, retrying on failure.",
        "handler": coding_task,
    },
    "build_webpage": {
        "level": PermissionLevel.GENERATE,
        "description": "Generate a self-contained HTML page for a task, verify it loads error-free in headless Chromium, retrying on failure.",
        "handler": build_webpage,
    },
}
