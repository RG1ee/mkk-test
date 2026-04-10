import asyncio
import logging

from faststream.rabbit import RabbitBroker

from app.broker.topology import payments_queue
from app.config import settings
from app.uow import UnitOfWork

logger = logging.getLogger(__name__)


class OutboxRelay:
    def __init__(self, broker: RabbitBroker) -> None:
        self._broker = broker

    async def run(self) -> None:
        while True:
            try:
                await self._publish_pending()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Outbox relay error")

            await asyncio.sleep(settings.outbox.poll_interval)

    async def _publish_pending(self) -> None:
        async with UnitOfWork() as uow:
            events = await uow.outbox.get_pending(limit=settings.outbox.batch_size)
            for event in events:
                await self._broker.publish(event.payload, queue=payments_queue)
                await uow.outbox.mark_published(event.id)
                logger.info("Published outbox event %s", event.id)
            await uow.commit()
