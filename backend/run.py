"""Entry point that sets the Windows event loop policy before anything else
imports asyncio/uvicorn/psycopg, since psycopg's async mode requires a
selector loop and Windows defaults to Proactor.
"""

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
