import uuid

from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.dependencies import get_payment_service, verify_api_key
from app.schemas import PaymentCreate, PaymentCreatedResponse, PaymentResponse
from app.services.payment import PaymentService

router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(verify_api_key)],
)


@router.post("/payments", response_model=PaymentCreatedResponse, status_code=202)
async def create_payment_endpoint(
    body: PaymentCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    service: PaymentService = Depends(get_payment_service),
) -> PaymentCreatedResponse:
    payment = await service.create(body, idempotency_key)
    return PaymentCreatedResponse.model_validate(payment)


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment_endpoint(
    payment_id: uuid.UUID,
    service: PaymentService = Depends(get_payment_service),
) -> PaymentResponse:
    payment = await service.get_by_id(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return PaymentResponse.model_validate(payment)
