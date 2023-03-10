from typing import Optional, TYPE_CHECKING, Any
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from app.store.database.sqlalchemy_base import db

if TYPE_CHECKING:
    from app.web.app import Application


class Database:
    def __init__(self, app: "Application"):
        self.app = app
        self._engine: Optional[AsyncEngine] = None
        self._db: Optional[declarative_base] = None
        self.session: Optional[AsyncSession] = None

    async def connect(self, *_: list, **__: dict) -> None:
        self._db = db
        self._engine = create_async_engine(
            "postgresql+asyncpg://kts_user:kts_pass@db:5432/kts",
            echo=True,
        )
        self.session = sessionmaker(
            self._engine,
            expire_on_commit=False,
            future=True,
            class_=AsyncSession,
        )

    async def disconnect(self, *_: list, **__: dict) -> None:
        if self._engine:
            await self._engine.dispose()
