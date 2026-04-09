from collections.abc import AsyncGenerator

from fastapi import Header, HTTPException

from app.config import settings
from app.services.payment import PaymentService
from app.uow import UnitOfWork


async def verify_api_key(x_api_key: str = Header(...)) -> None:
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


async def get_payment_service() -> AsyncGenerator[PaymentService, None]:
    async with UnitOfWork() as uow:
        yield PaymentService(uow)
