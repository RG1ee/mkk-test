from decimal import Decimal

import pytest

from app.schemas import PaymentCreate, PaymentEvent
from app.services.payment import PaymentService
from tests.fakes import FakeUnitOfWork


@pytest.fixture
def payment_data() -> PaymentCreate:
    return PaymentCreate(
        amount=Decimal("100.50"),
        currency="RUB",
        description="Test payment",
        metadata={"order_id": 42},
        webhook_url=None,
    )


async def test_create_payment_persists_to_payments_and_outbox(
    fake_uow: FakeUnitOfWork, payment_data: PaymentCreate
) -> None:
    service = PaymentService(fake_uow)

    payment = await service.create(payment_data, idempotency_key="key-1")

    assert payment.amount == Decimal("100.50")
    assert payment.currency == "RUB"
    assert payment.status == "pending"
    assert payment.idempotency_key == "key-1"
    assert fake_uow.committed is True

    stored = await fake_uow.payments.get_by_id(payment.id)
    assert stored is payment

    pending_events = await fake_uow.outbox.get_pending()
    assert len(pending_events) == 1
    event = pending_events[0]
    assert event.event_type == "payment.created"
    assert event.aggregate_id == payment.id

    parsed = PaymentEvent.model_validate(event.payload)
    assert parsed.payment_id == payment.id
    assert parsed.amount == Decimal("100.50")


async def test_create_payment_is_idempotent(
    fake_uow: FakeUnitOfWork, payment_data: PaymentCreate
) -> None:
    service = PaymentService(fake_uow)

    first = await service.create(payment_data, idempotency_key="dup-key")
    second = await service.create(payment_data, idempotency_key="dup-key")

    assert first.id == second.id

    events = await fake_uow.outbox.get_pending()
    assert len(events) == 1


async def test_get_by_id_returns_stored_payment(
    fake_uow: FakeUnitOfWork, payment_data: PaymentCreate
) -> None:
    service = PaymentService(fake_uow)
    created = await service.create(payment_data, idempotency_key="key-2")

    fetched = await service.get_by_id(created.id)

    assert fetched is not None
    assert fetched.id == created.id


async def test_get_by_id_returns_none_when_missing(fake_uow: FakeUnitOfWork) -> None:
    import uuid

    service = PaymentService(fake_uow)
    result = await service.get_by_id(uuid.uuid4())
    assert result is None
