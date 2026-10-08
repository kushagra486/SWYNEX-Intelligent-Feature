"""Executes tool calls through the permission engine, logging every call
(auto or approved) so failures and actions taken are diagnosable later.
"""

import json
import logging

from psycopg.rows import dict_row
from psycopg.types.json import Json

from .db import get_pool
from .permissions import requires_approval
from .tools import TOOL_REGISTRY

logger = logging.getLogger("nexus.actions")


class UnknownTool(Exception):
    pass


async def request_action(tool: str, params: dict) -> dict:
    if tool not in TOOL_REGISTRY:
        raise UnknownTool(f"no such tool: {tool}")

    spec = TOOL_REGISTRY[tool]
    level = int(spec["level"])
    pool = await get_pool()

    if not requires_approval(spec["level"]):
        result = await _execute(tool, params)
        async with pool.connection() as conn:
            row = await conn.execute(
                """
                INSERT INTO actions (tool, params, level, status, result, resolved_at)
                VALUES (%s, %s, %s, 'executed', %s, now())
                RETURNING id
                """,
                (tool, Json(params), level, Json(result)),
            )
            action_id = (await row.fetchone())[0]
        logger.info("tool=%s level=%s -> auto-executed (action_id=%s)", tool, level, action_id)
        return {"action_id": action_id, "status": "executed", "result": result}

    async with pool.connection() as conn:
        row = await conn.execute(
            "INSERT INTO actions (tool, params, level, status) VALUES (%s, %s, %s, 'pending') RETURNING id",
            (tool, Json(params), level),
        )
        action_id = (await row.fetchone())[0]
    logger.info("tool=%s level=%s -> pending approval (action_id=%s)", tool, level, action_id)
    return {"action_id": action_id, "status": "pending", "result": None}


async def _execute(tool: str, params: dict) -> dict:
    handler = TOOL_REGISTRY[tool]["handler"]
    try:
        return await handler(params)
    except Exception as exc:  # noqa: BLE001
        logger.error("tool=%s failed: %s", tool, exc)
        return {"error": str(exc)}


async def list_pending() -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT id, tool, params, level, created_at FROM actions WHERE status = 'pending' ORDER BY created_at"
            )
            return await cur.fetchall()


async def approve_action(action_id: int) -> dict:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT tool, params, status FROM actions WHERE id = %s", (action_id,))
            row = await cur.fetchone()
        if row is None:
            return {"error": "action not found"}
        if row["status"] != "pending":
            return {"error": f"action is not pending (status={row['status']})"}

        result = await _execute(row["tool"], row["params"])
        await conn.execute(
            "UPDATE actions SET status = 'executed', result = %s, resolved_at = now() WHERE id = %s",
            (Json(result), action_id),
        )
    logger.info("action_id=%s approved and executed", action_id)
    return {"action_id": action_id, "status": "executed", "result": result}


async def reject_action(action_id: int) -> dict:
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "UPDATE actions SET status = 'rejected', resolved_at = now() WHERE id = %s AND status = 'pending' RETURNING id",
            (action_id,),
        )
        row = await cur.fetchone()
    if row is None:
        return {"error": "action not found or not pending"}
    logger.info("action_id=%s rejected", action_id)
    return {"action_id": action_id, "status": "rejected"}
