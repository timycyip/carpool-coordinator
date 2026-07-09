from typing import Any

import pytest

from app.repositories.user import UserRepository


@pytest.fixture()
def user_repo(ddb_client: Any) -> UserRepository:
    return UserRepository(table_name="app_data", client=ddb_client)


@pytest.mark.asyncio
async def test_get_by_sub_returns_none_when_not_found(
    user_repo: UserRepository,
) -> None:
    result = await user_repo.get_by_sub("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_upsert_creates_user(user_repo: UserRepository) -> None:
    item = await user_repo.upsert(
        sub="google-sub-123",
        email="test@example.com",
        name="Test User",
    )
    assert item["PK"] == "USER#google-sub-123"
    assert item["SK"] == "METADATA"
    assert item["email"] == "test@example.com"
    assert item["name"] == "Test User"
    assert item["global_roles"] == []


@pytest.mark.asyncio
async def test_get_by_sub_returns_user(user_repo: UserRepository) -> None:
    await user_repo.upsert(sub="sub1", email="test@example.com", name="Test")
    result = await user_repo.get_by_sub("sub1")
    assert result is not None
    assert result["PK"] == "USER#sub1"
    assert result["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_upsert_is_idempotent(user_repo: UserRepository) -> None:
    await user_repo.upsert(sub="sub1", email="a@example.com", name="A")
    await user_repo.upsert(sub="sub1", email="b@example.com", name="B")
    result = await user_repo.get_by_sub("sub1")
    assert result is not None
    assert result["email"] == "b@example.com"
    assert result["name"] == "B"


@pytest.mark.asyncio
async def test_upsert_preserves_global_roles(user_repo: UserRepository) -> None:
    await user_repo.upsert(sub="sub1", email="a@example.com", name="A")
    # Simulate admin granting a role (direct put_item)
    user_repo.client.update_item(
        TableName="app_data",
        Key=user_repo._to_dynamo({"PK": "USER#sub1", "SK": "METADATA"}),
        UpdateExpression="SET global_roles = :roles",
        ExpressionAttributeValues=user_repo._to_dynamo({":roles": ["manager"]}),
    )
    await user_repo.upsert(sub="sub1", email="b@example.com", name="B")
    result = await user_repo.get_by_sub("sub1")
    assert result is not None
    assert result["global_roles"] == ["manager"]
    assert result["email"] == "b@example.com"
