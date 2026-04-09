import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, HttpUrl


class PaymentCreate(BaseModel):
    amount: Decimal
    currency: Literal["RUB", "USD", "EUR"]
    description: str | None = None
    metadata: dict[str, Any] | None = None
    webhook_url: HttpUrl | None = None


class PaymentCreatedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    created_at: datetime


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: Decimal
    currency: str
    description: str | None
    metadata: dict[str, Any] | None
    status: str
    idempotency_key: str
    webhook_url: str | None
    created_at: datetime
    processed_at: datetime | None


class PaymentEvent(BaseModel):
    payment_id: uuid.UUID
    amount: Decimal
    currency: str
    description: str | None
    metadata: dict[str, Any] | None
    webhook_url: str | None
