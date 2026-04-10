import asyncio
import logging
import random
import uuid

from faststream import FastStream
from faststream.rabbit import RabbitBroker

from app.broker import declare_topology, dlq_queue, payments_queue
from app.config import settings
from app.schemas import PaymentEvent
from app.services.webhook import send_webhook
from app.uow import UnitOfWork

logger = logging.getLogger(__name__)

broker = RabbitBroker(settings.rabbitmq_url)
app = FastStream(broker)

MAX_PROCESSING_ATTEMPTS = 3


class PaymentProcessingError(Exception):
    pass


async def _emulate_gateway_call() -> bool:
    delay = random.uniform(2, 5)
    await asyncio.sleep(delay)
    return random.random() < 0.9


async def _process_payment(event: PaymentEvent) -> str:
    succeeded = await _emulate_gateway_call()
    status = "succeeded" if succeeded else "failed"

    async with UnitOfWork() as uow:
        await uow.payments.update_status(event.payment_id, status)
        await uow.commit()

    if event.webhook_url:
        webhook_payload = {
            "payment_id": str(event.payment_id),
            "status": status,
        }
        await send_webhook(event.webhook_url, webhook_payload)

    return status


@broker.subscriber(payments_queue)
async def handle_payment(event: PaymentEvent) -> None:
    logger.info("Processing payment %s", event.payment_id)

    for attempt in range(MAX_PROCESSING_ATTEMPTS):
        try:
            status = await _process_payment(event)
            logger.info("Payment %s → %s", event.payment_id, status)
            return
        except Exception as exc:
            logger.warning(
                "Attempt %d/%d failed for payment %s: %s",
                attempt + 1,
                MAX_PROCESSING_ATTEMPTS,
                event.payment_id,
                exc,
            )
            if attempt < MAX_PROCESSING_ATTEMPTS - 1:
                await asyncio.sleep(2**attempt)

    logger.error(
        "Payment %s failed after %d attempts, rejecting to DLQ",
        event.payment_id,
        MAX_PROCESSING_ATTEMPTS,
    )
    raise PaymentProcessingError(f"Payment {event.payment_id} processing failed")


@broker.subscriber(dlq_queue)
async def handle_dlq(payload: dict) -> None:
    logger.error("DLQ message received: %s", payload)


@app.after_startup
async def setup() -> None:
    await declare_topology(broker)
    logger.info("Consumer started")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
