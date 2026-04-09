import uuid
from abc import ABC, abstractmethod

from app.models import OutboxEvent, Payment
from app.schemas import PaymentCreate, PaymentEvent
from app.uow import AbstractUnitOfWork


class AbstractPaymentService(ABC):
    @abstractmethod
    async def create(
        self, data: PaymentCreate, idempotency_key: str
    ) -> Payment: ...

    @abstractmethod
    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None: ...


class PaymentService(AbstractPaymentService):
    def __init__(self, uow: AbstractUnitOfWork) -> None:
        self._uow = uow

    async def create(
        self, data: PaymentCreate, idempotency_key: str
    ) -> Payment:
        existing = await self._uow.payments.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing

        payment_id = uuid.uuid4()
        payment = Payment(
            id=payment_id,
            amount=data.amount,
            currency=data.currency,
            description=data.description,
            metadata_=data.metadata,
            idempotency_key=idempotency_key,
            webhook_url=str(data.webhook_url) if data.webhook_url else None,
        )
        await self._uow.payments.add(payment)

        event_payload = PaymentEvent(
            payment_id=payment_id,
            amount=data.amount,
            currency=data.currency,
            description=data.description,
            metadata=data.metadata,
            webhook_url=str(data.webhook_url) if data.webhook_url else None,
        )
        event = OutboxEvent(
            aggregate_id=payment_id,
            event_type="payment.created",
            payload=event_payload.model_dump(mode="json"),
        )
        await self._uow.outbox.add(event)

        await self._uow.commit()
        return payment

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        return await self._uow.payments.get_by_id(payment_id)
