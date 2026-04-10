import asyncio
import logging
import random

from app.config import settings
from app.schemas import PaymentEvent
from app.services.webhook import send_webhook
from app.uow import UnitOfWork

logger = logging.getLogger(__name__)


class PaymentProcessingError(Exception):
    pass


class PaymentProcessor:
    async def process(self, event: PaymentEvent) -> str:
        for attempt in range(settings.payment.max_attempts):
            try:
                return await self._process_once(event)
            except Exception as exc:
                logger.warning(
                    "Attempt %d/%d failed for payment %s: %s",
                    attempt + 1,
                    settings.payment.max_attempts,
                    event.payment_id,
                    exc,
                )
                if attempt < settings.payment.max_attempts - 1:
                    await asyncio.sleep(2**attempt)

        raise PaymentProcessingError(
            f"Payment {event.payment_id} failed after "
            f"{settings.payment.max_attempts} attempts"
        )

    async def _process_once(self, event: PaymentEvent) -> str:
        succeeded = await self._call_gateway()
        status = "succeeded" if succeeded else "failed"

        async with UnitOfWork() as uow:
            await uow.payments.update_status(event.payment_id, status)
            await uow.commit()

        if event.webhook_url:
            await send_webhook(
                event.webhook_url,
                {"payment_id": str(event.payment_id), "status": status},
            )

        return status

    async def _call_gateway(self) -> bool:
        delay = random.uniform(
            settings.payment.gateway_min_delay,
            settings.payment.gateway_max_delay,
        )
        await asyncio.sleep(delay)
        return random.random() < settings.payment.gateway_success_rate
