import asyncio
import logging
import random
from collections.abc import Awaitable, Callable

from app.config import settings
from app.schemas import PaymentEvent
from app.services.webhook import send_webhook
from app.uow import AbstractUnitOfWork, UnitOfWork

logger = logging.getLogger(__name__)

UowFactory = Callable[[], AbstractUnitOfWork]
WebhookSender = Callable[[str, dict], Awaitable[bool]]


class PaymentProcessingError(Exception):
    pass


class PaymentProcessor:
    def __init__(
        self,
        uow_factory: UowFactory = UnitOfWork,
        webhook_sender: WebhookSender = send_webhook,
    ) -> None:
        self._uow_factory = uow_factory
        self._webhook_sender = webhook_sender

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

        async with self._uow_factory() as uow:
            await uow.payments.update_status(event.payment_id, status)
            await uow.commit()

        if event.webhook_url:
            await self._webhook_sender(
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
