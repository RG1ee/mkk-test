import asyncio
import logging

from faststream.rabbit import RabbitBroker

from app.broker import declare_topology
from app.config import settings
from app.outbox import outbox_relay

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    broker = RabbitBroker(settings.rabbitmq_url)
    await broker.connect()
    await declare_topology(broker)
    logger.info("Outbox worker started")

    try:
        await outbox_relay(broker)
    finally:
        await broker.close()


if __name__ == "__main__":
    asyncio.run(main())
