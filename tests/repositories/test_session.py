from typing import Any

import pytest

from app.repositories.session import SessionRepository


@pytest.fixture()
def session_repo(ddb_client: Any) -> SessionRepository:
    return SessionRepository(table_name="app_data", client=ddb_client)


@pytest.mark.asyncio
async def test_create_session(session_repo: SessionRepository) -> None:
    attrs = {"title": "Sunday Service", "status": "draft", "created_by": "user1"}
    item = await session_repo.create("ABC123", attrs)
    assert item["PK"] == "SESSION#ABC123"
    assert item["SK"] == "METADATA"
    assert item["title"] == "Sunday Service"


@pytest.mark.asyncio
async def test_get_by_code(session_repo: SessionRepository) -> None:
    await session_repo.create("ABC123", {"title": "Test", "status": "draft"})
    result = await session_repo.get_by_code("ABC123")
    assert result is not None
    assert result["title"] == "Test"


@pytest.mark.asyncio
async def test_get_nonexistent_returns_none(
    session_repo: SessionRepository,
) -> None:
    result = await session_repo.get_by_code("NOPE")
    assert result is None


@pytest.mark.asyncio
async def test_update_session(session_repo: SessionRepository) -> None:
    await session_repo.create("ABC123", {"title": "Old", "status": "draft"})
    await session_repo.update("ABC123", {"title": "New", "status": "registration_open"})
    result = await session_repo.get_by_code("ABC123")
    assert result is not None
    assert result["title"] == "New"
    assert result["status"] == "registration_open"


@pytest.mark.asyncio
async def test_delete_session(session_repo: SessionRepository) -> None:
    await session_repo.create("ABC123", {"title": "Test"})
    await session_repo.delete("ABC123")
    result = await session_repo.get_by_code("ABC123")
    assert result is None


@pytest.mark.asyncio
async def test_create_duplicate_raises(session_repo: SessionRepository) -> None:
    from botocore.exceptions import ClientError

    await session_repo.create("ABC123", {"title": "First"})
    with pytest.raises(ClientError, match="ConditionalCheckFailed"):
        await session_repo.create("ABC123", {"title": "Second"})
