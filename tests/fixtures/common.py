import logging
import os
from unittest.mock import AsyncMock

import pytest
from aiohttp.test_utils import loop_context, TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.store import Database
from app.store import Store
from app.web.app import setup_app


@pytest.fixture(scope="session")
def event_loop():
    with loop_context() as _loop:
        yield _loop


@pytest.fixture(scope="session")
def server():
    app = setup_app(
        config_path=os.path.join(
            os.path.abspath(os.path.dirname(__file__)), "..", "config.yml"
        )
    )
    app.on_startup.clear()
    app.on_shutdown.clear()
    app.store.vk_api.make_userlist = AsyncMock()
    app.store.vk_api.send_message = AsyncMock()
    app.store.vk_api.send_photo = AsyncMock()

    app.database = Database(app)
    app.on_startup.append(app.database.connect)
    app.on_shutdown.append(app.database.disconnect)
    # make_grid = AsyncMock(return_values=[])

    return app


@pytest.fixture
def store(server) -> Store:
    return server.store


@pytest.fixture
def db_session(server):
    return server.database.session

@pytest.fixture(autouse=True, scope="function")
def clear_send(server):
    server.store.vk_api.send_message.reset_mock()


@pytest.fixture(autouse=True)
def cli(aiohttp_client, event_loop, server) -> TestClient:
    return event_loop.run_until_complete(aiohttp_client(server))
@pytest.fixture(autouse=True, scope="function")
async def clear_db(server):
    yield
    try:
        session = AsyncSession(server.database._engine)
        connection = session.connection()
        for table in server.database._db.metadata.tables:
            await session.execute(text(f"TRUNCATE {table} CASCADE"))
            await session.execute(text(f"ALTER SEQUENCE {table}_id_seq RESTART WITH 1"))

        await session.commit()
        connection.close()

    except Exception as err:
        logging.warning(err)



