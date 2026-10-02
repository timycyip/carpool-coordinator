"""Runtime configuration helpers for backend infrastructure resources."""

from __future__ import annotations

import os


def get_table_name(environment_variable: str, default: str) -> str:
    """Read a DynamoDB table name at runtime, falling back for local use."""
    return os.environ.get(environment_variable) or default


def app_data_table_name() -> str:
    """Return the configured single-table data table name."""
    return get_table_name("APP_DATA_TABLE_NAME", "app_data")


__all__ = ["app_data_table_name", "get_table_name"]
