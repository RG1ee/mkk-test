import uuid
from decimal import Decimal

import pytest

from app.models import Payment
from app.schemas import PaymentEvent
from app.services.payment_processor import (
    PaymentProcessingError,
    PaymentProcessor,
)
from tests.fakes import FakeUnitOfWork


@pytest.fixture
def payment(fake_uow: FakeUnitOfWork) -> Payment:
    p = Payment(
        id=uuid.uuid4(),
        amount=Decimal("100.00"),
        currency="RUB",
        description=None,
        metadata_=None,
        status="pending",
        idempotency_key="test",
        webhook_url=None,
    )
    fake_uow.payments._by_id[p.id] = p  # type: ignore[attr-defined]
    return p


@pytest.fixture
def event(payment: Payment) -> PaymentEvent:
    return PaymentEvent(
        payment_id=payment.id,
        amount=payment.amount,
        currency=payment.currency,
        description=None,
        metadata=None,
        webhook_url=None,
    )


async def test_process_marks_payment_succeeded_when_gateway_ok(
    fake_uow: FakeUnitOfWork, payment: Payment, event: PaymentEvent
) -> None:
    processor = PaymentProcessor(uow_factory=lambda: fake_uow)
    processor._call_gateway = _always(True)  # type: ignore[method-assign]

    status = await processor.process(event)

    assert status == "succeeded"
    assert payment.status == "succeeded"
    assert payment.processed_at is not None
    assert fake_uow.committed is True


async def test_process_marks_payment_failed_when_gateway_fails(
    fake_uow: FakeUnitOfWork, payment: Payment, event: PaymentEvent
) -> None:
    processor = PaymentProcessor(uow_factory=lambda: fake_uow)
    processor._call_gateway = _always(False)  # type: ignore[method-assign]

    status = await processor.process(event)

    assert status == "failed"
    assert payment.status == "failed"


async def test_process_calls_webhook_when_url_present(
    fake_uow: FakeUnitOfWork, payment: Payment
) -> None:
    event_with_url = PaymentEvent(
        payment_id=payment.id,
        amount=payment.amount,
        currency=payment.currency,
        description=None,
        metadata=None,
        webhook_url="https://example.com/callback",
    )

    calls: list[tuple[str, dict]] = []

    async def fake_sender(url: str, payload: dict) -> bool:
        calls.append((url, payload))
        return True

    processor = PaymentProcessor(
        uow_factory=lambda: fake_uow,
        webhook_sender=fake_sender,
    )
    processor._call_gateway = _always(True)  # type: ignore[method-assign]

    await processor.process(event_with_url)

    assert len(calls) == 1
    assert calls[0][0] == "https://example.com/callback"
    assert calls[0][1]["status"] == "succeeded"
    assert calls[0][1]["payment_id"] == str(payment.id)


async def test_process_skips_webhook_when_url_absent(
    fake_uow: FakeUnitOfWork, payment: Payment, event: PaymentEvent
) -> None:
    calls: list = []

    async def fake_sender(url: str, payload: dict) -> bool:
        calls.append((url, payload))
        return True

    processor = PaymentProcessor(
        uow_factory=lambda: fake_uow,
        webhook_sender=fake_sender,
    )
    processor._call_gateway = _always(True)  # type: ignore[method-assign]

    await processor.process(event)
    assert calls == []


async def test_process_retries_and_raises_after_max_attempts(
    fake_uow: FakeUnitOfWork, payment: Payment, event: PaymentEvent, monkeypatch
) -> None:
    # speed up exponential backoff
    monkeypatch.setattr("app.services.payment_processor.asyncio.sleep", _noop_sleep)

    attempts = 0

    async def always_raise() -> bool:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("boom")

    processor = PaymentProcessor(uow_factory=lambda: fake_uow)
    processor._call_gateway = always_raise  # type: ignore[method-assign]

    with pytest.raises(PaymentProcessingError):
        await processor.process(event)

    assert attempts == 3


async def test_process_returns_on_second_attempt_if_first_fails(
    fake_uow: FakeUnitOfWork, payment: Payment, event: PaymentEvent, monkeypatch
) -> None:
    monkeypatch.setattr("app.services.payment_processor.asyncio.sleep", _noop_sleep)

    attempts = 0

    async def flaky_gateway() -> bool:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transient")
        return True

    processor = PaymentProcessor(uow_factory=lambda: fake_uow)
    processor._call_gateway = flaky_gateway  # type: ignore[method-assign]

    status = await processor.process(event)

    assert status == "succeeded"
    assert attempts == 2


def _always(value: bool):
    async def _inner() -> bool:
        return value

    return _inner


async def _noop_sleep(_seconds: float) -> None:
    return None
