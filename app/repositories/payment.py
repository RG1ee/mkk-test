import uuid
from datetime import datetime, timezone

from app.models import Payment
from app.repositories.base import SQLAlchemyRepository


class PaymentRepository(SQLAlchemyRepository[Payment]):
    model = Payment

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        return await self.find_one(idempotency_key=key)

    async def update_status(self, payment_id: uuid.UUID, status: str) -> None:
        payment = await self.get_by_id(payment_id)
        if payment is None:
            raise ValueError(f"Payment {payment_id} not found")
        payment.status = status
        payment.processed_at = datetime.now(timezone.utc)
