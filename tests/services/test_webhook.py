from unittest.mock import patch

import httpx
import pytest

from app.services import webhook as webhook_module
from app.services.webhook import send_webhook


@pytest.fixture
def noop_sleep():
    async def _sleep(_seconds: float) -> None:
        return None

    with patch.object(webhook_module.asyncio, "sleep", _sleep):
        yield


def _mock_client(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


async def test_send_webhook_returns_true_on_success(noop_sleep) -> None:
    received: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        received.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    client = _mock_client(handler)
    with patch.object(webhook_module.httpx, "AsyncClient", return_value=client):
        result = await send_webhook("https://example.com/hook", {"key": "value"})

    assert result is True
    assert received == [{"key": "value"}]


async def test_send_webhook_retries_on_5xx_and_eventually_fails(noop_sleep) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(500)

    client = _mock_client(handler)
    with patch.object(webhook_module.httpx, "AsyncClient", return_value=client):
        result = await send_webhook("https://example.com/hook", {})

    assert result is False
    assert attempts == 3


async def test_send_webhook_succeeds_on_retry(noop_sleep) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            return httpx.Response(503)
        return httpx.Response(200)

    client = _mock_client(handler)
    with patch.object(webhook_module.httpx, "AsyncClient", return_value=client):
        result = await send_webhook("https://example.com/hook", {})

    assert result is True
    assert attempts == 2
