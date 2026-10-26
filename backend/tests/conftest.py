from collections.abc import AsyncGenerator

import pytest

from backend.app.db.session import engine


@pytest.fixture(autouse=True)
async def cleanup_db_engine() -> AsyncGenerator[None, None]:
    """Ensures database connections in the connection pool are closed before loop closes."""
    yield
    await engine.dispose()
