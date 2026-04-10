import uuid
from typing import Any

from app.models import OutboxEvent
from app.services.outbox_relay import OutboxRelay
from tests.fakes import FakeUnitOfWork


class FakeBroker:
    def __init__(self) -> None:
        self.published: list[tuple[Any, Any]] = []

    async def publish(self, payload: Any, queue: Any) -> None:
        self.published.append((payload, queue))


async def test_publish_pending_emits_events_and_marks_them(
    fake_uow: FakeUnitOfWork,
) -> None:
    event = OutboxEvent(
        id=uuid.uuid4(),
        aggregate_id=uuid.uuid4(),
        event_type="payment.created",
        payload={"hello": "world"},
    )
    await fake_uow.outbox.add(event)

    broker = FakeBroker()
    relay = OutboxRelay(broker=broker, uow_factory=lambda: fake_uow)  # type: ignore[arg-type]

    await relay.publish_pending()

    assert len(broker.published) == 1
    assert broker.published[0][0] == {"hello": "world"}

    pending = await fake_uow.outbox.get_pending()
    assert pending == []
    assert fake_uow.committed is True


async def test_publish_pending_does_nothing_when_no_events(
    fake_uow: FakeUnitOfWork,
) -> None:
    broker = FakeBroker()
    relay = OutboxRelay(broker=broker, uow_factory=lambda: fake_uow)  # type: ignore[arg-type]

    await relay.publish_pending()

    assert broker.published == []
    assert fake_uow.committed is True


async def test_publish_pending_marks_each_event_sequentially(
    fake_uow: FakeUnitOfWork,
) -> None:
    for i in range(3):
        await fake_uow.outbox.add(
            OutboxEvent(
                id=uuid.uuid4(),
                aggregate_id=uuid.uuid4(),
                event_type="payment.created",
                payload={"i": i},
            )
        )

    broker = FakeBroker()
    relay = OutboxRelay(broker=broker, uow_factory=lambda: fake_uow)  # type: ignore[arg-type]

    await relay.publish_pending()

    assert len(broker.published) == 3
    assert await fake_uow.outbox.get_pending() == []
