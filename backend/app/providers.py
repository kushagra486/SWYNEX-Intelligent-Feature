"""Provider adapters: local Ollama and cloud Groq, behind one interface."""

import time
import httpx

from . import config


class ProviderError(Exception):
    pass


async def call_ollama(prompt: str, model: str, timeout: float = 240.0) -> dict:
    start = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{config.OLLAMA_URL}/api/generate",
            # think=False: qwen3's reasoning trace adds 10-15x latency on this GPU
            # for little benefit on short factual/code tasks (2s vs 30s+ observed).
            json={"model": model, "prompt": prompt, "stream": False, "think": False},
        )
        resp.raise_for_status()
        data = resp.json()
    return {
        "provider": "local",
        "model": model,
        "text": data.get("response", ""),
        "latency_ms": int((time.monotonic() - start) * 1000),
    }


async def embed_text(text: str, timeout: float = 30.0) -> list[float]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{config.OLLAMA_URL}/api/embeddings",
            json={"model": config.EMBEDDING_MODEL, "prompt": text},
        )
        resp.raise_for_status()
        data = resp.json()
    return data["embedding"]


async def call_groq(prompt: str, model: str, timeout: float = 30.0) -> dict:
    if not config.GROQ_API_KEY:
        raise ProviderError("GROQ_API_KEY is not set")

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            config.GROQ_URL,
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
    text = data["choices"][0]["message"]["content"]
    return {
        "provider": "cloud",
        "model": model,
        "text": text,
        "latency_ms": int((time.monotonic() - start) * 1000),
    }
