import pytest

from tests.fakes import FakeUnitOfWork


@pytest.fixture
def fake_uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()
