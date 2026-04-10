import uuid
from datetime import datetime, timezone
from types import TracebackType

from app.models import OutboxEvent, Payment
from app.uow import AbstractUnitOfWork


class FakePaymentRepository:
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, Payment] = {}
        self._by_key: dict[str, Payment] = {}

    async def add(self, payment: Payment) -> Payment:
        self._by_id[payment.id] = payment
        self._by_key[payment.idempotency_key] = payment
        return payment

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        return self._by_id.get(payment_id)

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        return self._by_key.get(key)

    async def update_status(self, payment_id: uuid.UUID, status: str) -> None:
        payment = self._by_id.get(payment_id)
        if payment is None:
            raise ValueError(f"Payment {payment_id} not found")
        payment.status = status
        payment.processed_at = datetime.now(timezone.utc)


class FakeOutboxRepository:
    def __init__(self) -> None:
        self._events: dict[uuid.UUID, OutboxEvent] = {}

    async def add(self, event: OutboxEvent) -> OutboxEvent:
        if event.id is None:
            event.id = uuid.uuid4()
        self._events[event.id] = event
        return event

    async def get_pending(self, limit: int = 100) -> list[OutboxEvent]:
        pending = [e for e in self._events.values() if e.published_at is None]
        return pending[:limit]

    async def mark_published(self, event_id: uuid.UUID) -> None:
        event = self._events.get(event_id)
        if event is None:
            raise ValueError(f"OutboxEvent {event_id} not found")
        event.published_at = datetime.now(timezone.utc)


class FakeUnitOfWork(AbstractUnitOfWork):
    def __init__(self) -> None:
        self.payments = FakePaymentRepository()  # type: ignore[assignment]
        self.outbox = FakeOutboxRepository()  # type: ignore[assignment]
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True
