import asyncio
import logging

from faststream.rabbit import RabbitBroker

from app.broker import payments_queue
from app.config import settings
from app.uow import UnitOfWork

logger = logging.getLogger(__name__)


async def outbox_relay(broker: RabbitBroker) -> None:
    while True:
        try:
            async with UnitOfWork() as uow:
                events = await uow.outbox.get_pending()
                for event in events:
                    await broker.publish(event.payload, queue=payments_queue)
                    await uow.outbox.mark_published(event.id)
                    logger.info("Published outbox event %s", event.id)
                await uow.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Outbox relay error")

        await asyncio.sleep(settings.outbox_poll_interval)
