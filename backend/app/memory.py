"""Conversation + semantic memory: pgvector-backed storage and retrieval.

Every message is stored with an embedding. Before answering, we pull the
top-K most relevant past messages for this session (cosine similarity) and
fold them into the prompt as context, so Nexus remembers things across
sessions rather than starting fresh every call.
"""

from psycopg.rows import dict_row

from . import config
from .db import get_pool
from .providers import embed_text


def _to_pgvector(embedding: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"


async def create_session(title: str | None = None) -> int:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO sessions (title) VALUES (%s) RETURNING id", (title,)
            )
            row = await cur.fetchone()
            return row[0]


async def session_exists(session_id: int) -> bool:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM sessions WHERE id = %s", (session_id,))
            return await cur.fetchone() is not None


async def save_message(session_id: int, role: str, content: str) -> None:
    embedding = await embed_text(content)
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO messages (session_id, role, content, embedding) VALUES (%s, %s, %s, %s::vector)",
            (session_id, role, content, _to_pgvector(embedding)),
        )


async def retrieve_context(session_id: int, query: str, k: int | None = None) -> list[dict]:
    k = k or config.MEMORY_RETRIEVAL_K
    query_embedding = await embed_text(query)
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT role, content, created_at, embedding <=> %s::vector AS distance
                FROM messages
                WHERE session_id = %s
                ORDER BY distance ASC
                LIMIT %s
                """,
                (_to_pgvector(query_embedding), session_id, k),
            )
            rows = await cur.fetchall()
    return rows


async def recent_history(session_id: int, limit: int = 20) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT role, content, created_at FROM messages
                WHERE session_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (session_id, limit),
            )
            rows = await cur.fetchall()
    return list(reversed(rows))
