import asyncio
import logging

from faststream.rabbit import RabbitBroker

from app.broker.topology import declare_topology
from app.config import settings
from app.services.outbox_relay import OutboxRelay

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    broker = RabbitBroker(settings.rabbitmq.url)
    await broker.connect()
    await declare_topology(broker)
    logger.info("Outbox relay started")

    relay = OutboxRelay(broker)
    try:
        await relay.run()
    finally:
        await broker.close()


if __name__ == "__main__":
    asyncio.run(main())
