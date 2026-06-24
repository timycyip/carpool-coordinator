from typing import Any

import pytest

from app.repositories.registration import RegistrationRepository


@pytest.fixture()
def reg_repo(ddb_client: Any) -> RegistrationRepository:
    return RegistrationRepository(table_name="app_data", client=ddb_client)


@pytest.mark.asyncio
async def test_create_with_gsi_population(
    reg_repo: RegistrationRepository,
) -> None:
    attrs = {"role": "driver", "name": "Alice", "email": "alice@example.com"}
    item = await reg_repo.create("S1", "user1", attrs)
    assert item["PK"] == "SESSION#S1"
    assert item["SK"] == "REG#user1"
    assert item["gsi1_pk"] == "USER#user1"
    assert item["gsi1_sk"] == "SESSION#S1"
    assert item["role"] == "driver"


@pytest.mark.asyncio
async def test_get_registration(reg_repo: RegistrationRepository) -> None:
    await reg_repo.create("S1", "user1", {"role": "passenger", "name": "Bob"})
    result = await reg_repo.get("S1", "user1")
    assert result is not None
    assert result["role"] == "passenger"


@pytest.mark.asyncio
async def test_list_by_session(reg_repo: RegistrationRepository) -> None:
    await reg_repo.create("S1", "user1", {"role": "driver", "name": "A"})
    await reg_repo.create("S1", "user2", {"role": "passenger", "name": "B"})
    await reg_repo.create("S2", "user3", {"role": "driver", "name": "C"})
    results = await reg_repo.list_by_session("S1")
    assert len(results) == 2
    subs = {r["SK"] for r in results}
    assert subs == {"REG#user1", "REG#user2"}


@pytest.mark.asyncio
async def test_update_registration(reg_repo: RegistrationRepository) -> None:
    await reg_repo.create("S1", "user1", {"role": "driver", "name": "Alice"})
    await reg_repo.update("S1", "user1", {"role": "passenger"})
    result = await reg_repo.get("S1", "user1")
    assert result is not None
    assert result["role"] == "passenger"


@pytest.mark.asyncio
async def test_delete_registration(reg_repo: RegistrationRepository) -> None:
    await reg_repo.create("S1", "user1", {"role": "driver", "name": "Alice"})
    await reg_repo.delete("S1", "user1")
    result = await reg_repo.get("S1", "user1")
    assert result is None
