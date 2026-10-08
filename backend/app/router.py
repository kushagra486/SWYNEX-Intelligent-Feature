"""Model router: local-first, cloud-assisted, per the hybrid routing strategy
in the build plan (Section 6) — classify -> try local -> escalate to cloud if
the tier exceeds local capacity or the local call fails -> fall back to local
if cloud fails too.
"""

import logging

from . import config
from .providers import call_ollama, call_groq, ProviderError

logger = logging.getLogger("nexus.router")

# Tiers our 4GB-VRAM local fleet can reasonably serve.
LOCAL_CAPABLE_TIERS = {"fast", "general", "coding"}
# Tiers deliberately routed to cloud first (70B reasoning, vision — too big for local).
CLOUD_PREFERRED_TIERS = {"reasoning", "vision"}


async def route_chat(prompt: str, tier: str = "general") -> dict:
    tier = tier if tier in (LOCAL_CAPABLE_TIERS | CLOUD_PREFERRED_TIERS) else "general"

    if tier in CLOUD_PREFERRED_TIERS:
        try:
            result = await call_groq(prompt, config.GROQ_MODEL)
            logger.info("routed tier=%s -> cloud (%sms)", tier, result["latency_ms"])
            return result
        except (ProviderError, Exception) as exc:  # noqa: BLE001 - deliberate broad fallback
            logger.warning("cloud call failed for tier=%s (%s); falling back to local", tier, exc)
            model = config.LOCAL_MODELS["general"]
            result = await call_ollama(prompt, model)
            result["fallback_from"] = "cloud"
            return result

    # Local-capable tier: try local first.
    model = config.LOCAL_MODELS.get(tier, config.LOCAL_MODELS["general"])
    try:
        result = await call_ollama(prompt, model)
        logger.info("routed tier=%s -> local:%s (%sms)", tier, model, result["latency_ms"])
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("local call failed for tier=%s (%s); escalating to cloud", tier, exc)
        try:
            result = await call_groq(prompt, config.GROQ_MODEL)
            result["fallback_from"] = "local"
            return result
        except (ProviderError, Exception) as exc2:  # noqa: BLE001
            logger.error("both local and cloud failed: local=%s cloud=%s", exc, exc2)
            raise
