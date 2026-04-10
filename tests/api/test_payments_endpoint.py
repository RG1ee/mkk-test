import uuid
from collections.abc import AsyncGenerator
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_payment_service
from app.main import app
from app.services.payment import PaymentService
from tests.fakes import FakeUnitOfWork


@pytest.fixture
def fake_service(fake_uow: FakeUnitOfWork) -> PaymentService:
    return PaymentService(fake_uow)


@pytest.fixture
async def client(fake_service: PaymentService) -> AsyncGenerator[AsyncClient, None]:
    async def override() -> AsyncGenerator[PaymentService, None]:
        yield fake_service

    app.dependency_overrides[get_payment_service] = override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


async def test_create_payment_returns_202(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/payments",
        headers={
            "X-API-Key": "secret",
            "Idempotency-Key": "test-key-1",
        },
        json={"amount": "100.50", "currency": "RUB"},
    )

    assert response.status_code == 202
    body = response.json()
    assert "id" in body
    assert body["status"] == "pending"
    assert "created_at" in body


async def test_create_payment_is_idempotent(client: AsyncClient) -> None:
    payload = {"amount": "100.50", "currency": "RUB"}
    headers = {"X-API-Key": "secret", "Idempotency-Key": "dup-1"}

    first = await client.post("/api/v1/payments", headers=headers, json=payload)
    second = await client.post("/api/v1/payments", headers=headers, json=payload)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]


async def test_create_payment_requires_api_key(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/payments",
        headers={"Idempotency-Key": "test-2"},
        json={"amount": "50", "currency": "RUB"},
    )
    assert response.status_code == 422


async def test_create_payment_rejects_wrong_api_key(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/payments",
        headers={"X-API-Key": "wrong", "Idempotency-Key": "test-3"},
        json={"amount": "50", "currency": "RUB"},
    )
    assert response.status_code == 401


async def test_create_payment_requires_idempotency_key(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/payments",
        headers={"X-API-Key": "secret"},
        json={"amount": "50", "currency": "RUB"},
    )
    assert response.status_code == 422


async def test_create_payment_validates_currency(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/payments",
        headers={"X-API-Key": "secret", "Idempotency-Key": "bad-cur"},
        json={"amount": "100", "currency": "GBP"},
    )
    assert response.status_code == 422


async def test_get_payment_returns_details(
    client: AsyncClient, fake_service: PaymentService
) -> None:
    from app.schemas import PaymentCreate

    created = await fake_service.create(
        PaymentCreate(amount=Decimal("25"), currency="USD"),
        idempotency_key="get-test",
    )

    response = await client.get(
        f"/api/v1/payments/{created.id}",
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(created.id)
    assert body["amount"] == "25"
    assert body["currency"] == "USD"


async def test_get_payment_returns_404_when_missing(client: AsyncClient) -> None:
    response = await client.get(
        f"/api/v1/payments/{uuid.uuid4()}",
        headers={"X-API-Key": "secret"},
    )
    assert response.status_code == 404
