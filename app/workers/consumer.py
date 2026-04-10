import asyncio
import logging

from faststream import FastStream
from faststream.rabbit import RabbitBroker

from app.broker.topology import declare_topology, dlq_queue, payments_queue
from app.config import settings
from app.schemas import PaymentEvent
from app.services.payment_processor import PaymentProcessor

logger = logging.getLogger(__name__)

broker = RabbitBroker(settings.rabbitmq.url)
app = FastStream(broker)
processor = PaymentProcessor()


@broker.subscriber(payments_queue)
async def handle_payment(event: PaymentEvent) -> None:
    logger.info("Processing payment %s", event.payment_id)
    status = await processor.process(event)
    logger.info("Payment %s -> %s", event.payment_id, status)


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
