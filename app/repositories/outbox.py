import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.models import OutboxEvent
from app.repositories.base import SQLAlchemyRepository


class OutboxRepository(SQLAlchemyRepository[OutboxEvent]):
    model = OutboxEvent

    async def get_pending(self, limit: int = 100) -> list[OutboxEvent]:
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_published(self, event_id: uuid.UUID) -> None:
        event = await self.get_by_id(event_id)
        if event is None:
            raise ValueError(f"OutboxEvent {event_id} not found")
        event.published_at = datetime.now(timezone.utc)
