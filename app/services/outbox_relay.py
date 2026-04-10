import asyncio
import logging
from collections.abc import Callable

from faststream.rabbit import RabbitBroker

from app.broker.topology import payments_queue
from app.config import settings
from app.uow import AbstractUnitOfWork, UnitOfWork

logger = logging.getLogger(__name__)

UowFactory = Callable[[], AbstractUnitOfWork]


class OutboxRelay:
    def __init__(
        self,
        broker: RabbitBroker,
        uow_factory: UowFactory = UnitOfWork,
    ) -> None:
        self._broker = broker
        self._uow_factory = uow_factory

    async def run(self) -> None:
        while True:
            try:
                await self.publish_pending()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Outbox relay error")

            await asyncio.sleep(settings.outbox.poll_interval)

    async def publish_pending(self) -> None:
        async with self._uow_factory() as uow:
            events = await uow.outbox.get_pending(limit=settings.outbox.batch_size)
            for event in events:
                await self._broker.publish(event.payload, queue=payments_queue)
                await uow.outbox.mark_published(event.id)
                logger.info("Published outbox event %s", event.id)
            await uow.commit()
