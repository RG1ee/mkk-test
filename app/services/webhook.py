import asyncio
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def send_webhook(url: str, payload: dict[str, Any]) -> bool:
    async with httpx.AsyncClient(timeout=settings.webhook.timeout) as client:
        for attempt in range(settings.webhook.max_retries):
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                logger.info("Webhook delivered to %s (attempt %d)", url, attempt + 1)
                return True
            except httpx.HTTPError as exc:
                logger.warning(
                    "Webhook attempt %d/%d failed for %s: %s",
                    attempt + 1,
                    settings.webhook.max_retries,
                    url,
                    exc,
                )
                if attempt < settings.webhook.max_retries - 1:
                    await asyncio.sleep(2**attempt)

    logger.error(
        "Webhook delivery failed after %d attempts: %s",
        settings.webhook.max_retries,
        url,
    )
    return False
