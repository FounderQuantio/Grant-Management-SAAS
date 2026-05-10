"""
GovGuard™ — pytest configuration and fixtures
"""
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from unittest.mock import AsyncMock, patch

# Test database URL (use PostgreSQL testcontainer in CI)
TEST_DB_URL = "postgresql+asyncpg://govguard_app:testpass@localhost:5432/govguard_test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Provide a transactional DB session that rolls back after each test."""
    async with test_engine.begin() as conn:
        session_factory = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with session_factory() as session:
            yield session
            await session.rollback()


@pytest.fixture
def mock_cognito():
    """Mock Cognito JWT validation."""
    import uuid
    fake_claims = {
        "sub": "cognito-sub-123",
        "custom:tenant_id": str(uuid.uuid4()),
        "custom:user_id": str(uuid.uuid4()),
        "custom:role": "compliance_officer",
        "name": "Test User",
        "email": "test@agency.gov",
        "exp": 9999999999,
    }
    with patch("core.auth.decode_cognito_jwt", new=AsyncMock(return_value=fake_claims)):
        yield fake_claims


@pytest_asyncio.fixture
async def client(mock_cognito):
    """Async HTTP test client with auth mocked."""
    from main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer fake-test-token"},
    ) as c:
        yield c
