import pytest

from app.infrastructure.db.session import dispose_engine


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy for all tests."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(autouse=True)
async def reset_engine():
    """Dispose engine after each test to avoid stale connections across event loops."""
    yield
    await dispose_engine()
