import uuid
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Base

ModelT = TypeVar("ModelT", bound=Base)


class AbstractRepository(ABC, Generic[ModelT]):
    @abstractmethod
    async def add(self, entity: ModelT) -> ModelT: ...

    @abstractmethod
    async def get_by_id(self, entity_id: uuid.UUID) -> ModelT | None: ...


class SQLAlchemyRepository(AbstractRepository[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entity: ModelT) -> ModelT:
        self._session.add(entity)
        return entity

    async def get_by_id(self, entity_id: uuid.UUID) -> ModelT | None:
        return await self._session.get(self.model, entity_id)

    async def find_one(self, **filters: object) -> ModelT | None:
        stmt = select(self.model).filter_by(**filters)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_all(self, **filters: object) -> list[ModelT]:
        stmt = select(self.model).filter_by(**filters)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
