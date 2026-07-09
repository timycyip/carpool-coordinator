from typing import Any

import pytest

from app.repositories.match import MatchRepository


@pytest.fixture()
def match_repo(ddb_client: Any) -> MatchRepository:
    return MatchRepository(table_name="app_data", client=ddb_client)


@pytest.mark.asyncio
async def test_create_versioned(match_repo: MatchRepository) -> None:
    item = await match_repo.create("S1", 1, {"status": "proposed", "assignments": {}})
    assert item["PK"] == "SESSION#S1"
    assert item["SK"] == "MATCH#V0001"
    assert item["version"] == 1


@pytest.mark.asyncio
async def test_get_latest_returns_highest_version(
    match_repo: MatchRepository,
) -> None:
    await match_repo.create("S1", 1, {"status": "proposed", "assignments": {}})
    await match_repo.create("S1", 2, {"status": "proposed", "assignments": {}})
    await match_repo.create("S1", 3, {"status": "proposed", "assignments": {}})
    latest = await match_repo.get_latest("S1")
    assert latest is not None
    assert latest["version"] == 3


@pytest.mark.asyncio
async def test_get_latest_none_when_empty(
    match_repo: MatchRepository,
) -> None:
    result = await match_repo.get_latest("S1")
    assert result is None


@pytest.mark.asyncio
async def test_list_versions(match_repo: MatchRepository) -> None:
    await match_repo.create("S1", 1, {"status": "proposed", "assignments": {}})
    await match_repo.create("S1", 2, {"status": "approved", "assignments": {}})
    versions = await match_repo.list_versions("S1")
    assert len(versions) == 2
    version_nums = sorted(v["version"] for v in versions)
    assert version_nums == [1, 2]


@pytest.mark.asyncio
async def test_update_status_to_approved(
    match_repo: MatchRepository,
) -> None:
    await match_repo.create("S1", 1, {"status": "proposed", "assignments": {}})
    await match_repo.update_status("S1", 1, "approved", "admin1")
    latest = await match_repo.get_latest("S1")
    assert latest is not None
    assert latest["status"] == "approved"
    assert latest["approved_by"] == "admin1"
    assert "approved_at" in latest


@pytest.mark.asyncio
async def test_version_sort_order(match_repo: MatchRepository) -> None:
    """Zero-padded SKs must sort lexicographically in numeric order."""
    await match_repo.create("S1", 1, {"status": "proposed", "assignments": {}})
    await match_repo.create("S1", 9, {"status": "proposed", "assignments": {}})
    await match_repo.create("S1", 10, {"status": "proposed", "assignments": {}})
    latest = await match_repo.get_latest("S1")
    assert latest is not None
    assert latest["version"] == 10


@pytest.mark.asyncio
async def test_update_status_rejects_none_approved_by(
    match_repo: MatchRepository,
) -> None:
    await match_repo.create("S1", 1, {"status": "proposed", "assignments": {}})
    with pytest.raises(ValueError, match="approved_by is required"):
        await match_repo.update_status("S1", 1, "approved", None)


@pytest.mark.asyncio
async def test_negative_version_rejected(match_repo: MatchRepository) -> None:
    with pytest.raises(ValueError, match="version must be >= 1"):
        await match_repo.create("S1", -1, {"status": "proposed", "assignments": {}})


@pytest.mark.asyncio
async def test_status_demotion_removes_approval_fields(
    match_repo: MatchRepository,
) -> None:
    await match_repo.create("S1", 1, {"status": "proposed", "assignments": {}})
    await match_repo.update_status("S1", 1, "approved", "admin1")
    # Verify approved fields exist
    item = await match_repo.get_latest("S1")
    assert item is not None
    assert "approved_at" in item
    assert "approved_by" in item
    # Now demote status (e.g. re-proposing after override)
    await match_repo.update_status("S1", 1, "proposed", None)
    item = await match_repo.get_latest("S1")
    assert item is not None
    assert item["status"] == "proposed"
    assert "approved_at" not in item
    assert "approved_by" not in item
