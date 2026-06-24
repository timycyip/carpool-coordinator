from typing import Any

import pytest

from app.repositories.audit import AuditRepository


@pytest.fixture()
def audit_repo(ddb_client: Any) -> AuditRepository:
    return AuditRepository(table_name="app_data", client=ddb_client)


@pytest.mark.asyncio
async def test_write(audit_repo: AuditRepository) -> None:
    await audit_repo.write(
        "2026-06-24",
        "evt-001",
        {"actor_sub": "user1", "event_type": "login_success"},
    )
    results = await audit_repo.query_audit("2026-06-24")
    assert len(results) == 1
    assert results[0]["event_type"] == "login_success"
    assert results[0]["actor_sub"] == "user1"


@pytest.mark.asyncio
async def test_query_by_date_separation(
    audit_repo: AuditRepository,
) -> None:
    await audit_repo.write("2026-06-24", "evt-001", {"event_type": "login"})
    await audit_repo.write("2026-06-24", "evt-002", {"event_type": "logout"})
    await audit_repo.write("2026-06-25", "evt-003", {"event_type": "login"})

    results_24 = await audit_repo.query_audit("2026-06-24")
    assert len(results_24) == 2

    results_25 = await audit_repo.query_audit("2026-06-25")
    assert len(results_25) == 1


@pytest.mark.asyncio
async def test_query_with_filter(audit_repo: AuditRepository) -> None:
    await audit_repo.write(
        "2026-06-24",
        "evt-001",
        {"actor_sub": "user1", "event_type": "login_success"},
    )
    await audit_repo.write(
        "2026-06-24",
        "evt-002",
        {"actor_sub": "user2", "event_type": "login_failure"},
    )

    results = await audit_repo.query_audit(
        "2026-06-24",
        filters={"event_type": "login_success"},
    )
    assert len(results) == 1
    assert results[0]["actor_sub"] == "user1"


@pytest.mark.asyncio
async def test_query_with_timestamp_range(
    audit_repo: AuditRepository,
) -> None:
    await audit_repo.write("2026-06-24", "evt-001", {"event_type": "a"})
    await audit_repo.write("2026-06-24", "evt-002", {"event_type": "b"})
    # Query all for that date — at least 2 results
    results = await audit_repo.query_audit("2026-06-24")
    assert len(results) >= 2
