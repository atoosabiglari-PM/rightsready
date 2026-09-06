"""
RightsReady Trusted Ingestion Tests
-----------------------------------
Verifies the strict governance boundary, idempotency logic,
and ClickHouse insertion mapping.

ClickHouse is mocked so these tests do not require a live database.
"""

import os
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.trusted_ingestion import TrustedIngestionService


FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "fixtures",
)

VALID_FIXTURE_PATH = os.path.join(
    FIXTURES_DIR,
    "project_aurora_valid.json",
)

QUARANTINE_FIXTURE_PATH = os.path.join(
    FIXTURES_DIR,
    "project_aurora_quarantine_test.json",
)


MOCK_ENV = {
    "CLICKHOUSE_HOST": "localhost",
    "CLICKHOUSE_USER": "test_user",
    "CLICKHOUSE_PASSWORD": "super_secret_password",
    "CLICKHOUSE_DATABASE": "rightsready",
}


@patch("src.trusted_ingestion.clickhouse_connect.get_client")
def test_governance_boundary_blocks_quarantined_data(mock_get_client):
    """
    Quarantined data must be blocked before any ClickHouse
    connection is created.
    """

    service = TrustedIngestionService(
        QUARANTINE_FIXTURE_PATH
    )

    result = service.process()

    assert result["status"] == "BLOCKED"
    assert result["validation_status"] == "QUARANTINED"
    assert result["inserted"] is False

    mock_get_client.assert_not_called()


@patch.dict(os.environ, MOCK_ENV, clear=True)
@patch("src.trusted_ingestion.clickhouse_connect.get_client")
def test_ready_fixture_is_eligible_for_ingestion(mock_get_client):
    """
    A valid package should connect and insert into
    all four warehouse tables.
    """

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Database is empty.
    mock_client.command.return_value = 0

    service = TrustedIngestionService(
        VALID_FIXTURE_PATH
    )

    result = service.process()

    assert result["status"] == "INGESTED"
    assert result["inserted"] is True

    assert result["row_counts"]["productions"] == 1
    assert result["row_counts"]["assets"] == 5
    assert result["row_counts"]["licenses"] == 5
    assert result["row_counts"]["asset_usage"] == 5

    mock_get_client.assert_called_once_with(
        host="localhost",
        username="test_user",
        password="super_secret_password",
        database="rightsready",
        secure=True,
    )

    assert mock_client.insert.call_count == 4

    inserted_tables = [
        call_args[0][0]
        for call_args in mock_client.insert.call_args_list
    ]

    assert set(inserted_tables) == {
        "productions",
        "assets",
        "licenses",
        "asset_usage",
    }


@patch.dict(os.environ, MOCK_ENV, clear=True)
@patch("src.trusted_ingestion.clickhouse_connect.get_client")
def test_batch_id_is_propagated_to_all_inserts(mock_get_client):
    """
    Every inserted warehouse row must contain the package batch_id.
    """

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.command.return_value = 0

    service = TrustedIngestionService(
        VALID_FIXTURE_PATH
    )

    service.process()

    expected_batch_id = "BATCH-2026-1049"

    for call_args in mock_client.insert.call_args_list:
        table_name = call_args[0][0]
        rows = call_args[0][1]
        columns = call_args[1]["column_names"]

        batch_id_index = columns.index("batch_id")

        for row in rows:
            assert (
                row[batch_id_index] == expected_batch_id
            ), f"Incorrect batch_id in {table_name}"


@patch.dict(os.environ, MOCK_ENV, clear=True)
@patch("src.trusted_ingestion.clickhouse_connect.get_client")
def test_temporal_type_mapping_for_clickhouse(mock_get_client):
    """
    ClickHouse Date and DateTime fields must receive
    Python date/datetime objects rather than raw strings.
    """

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.command.return_value = 0

    service = TrustedIngestionService(
        VALID_FIXTURE_PATH
    )

    service.process()

    for call_args in mock_client.insert.call_args_list:
        table_name = call_args[0][0]
        rows = call_args[0][1]
        columns = call_args[1]["column_names"]

        if table_name == "productions":
            release_date_index = columns.index(
                "release_date"
            )

            for row in rows:
                assert type(
                    row[release_date_index]
                ) is date

        elif table_name == "licenses":
            valid_from_index = columns.index(
                "valid_from"
            )
            valid_until_index = columns.index(
                "valid_until"
            )

            for row in rows:
                assert type(
                    row[valid_from_index]
                ) is date

                assert type(
                    row[valid_until_index]
                ) is date

        elif table_name == "assets":
            created_at_index = columns.index(
                "created_at"
            )

            for row in rows:
                assert type(
                    row[created_at_index]
                ) is datetime


@patch.dict(os.environ, MOCK_ENV, clear=True)
@patch("src.trusted_ingestion.clickhouse_connect.get_client")
def test_complete_duplicate_batch_is_prevented(mock_get_client):
    """
    A complete batch already in ClickHouse must not be inserted twice.
    """

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Expected complete batch:
    # 1 production
    # 5 assets
    # 5 licenses
    # 5 asset usages
    mock_client.command.side_effect = [
        1,
        5,
        5,
        5,
    ]

    service = TrustedIngestionService(
        VALID_FIXTURE_PATH
    )

    result = service.process()

    assert result["status"] == "ALREADY_INGESTED"
    assert result["inserted"] is False

    mock_client.insert.assert_not_called()


@patch.dict(os.environ, MOCK_ENV, clear=True)
@patch("src.trusted_ingestion.clickhouse_connect.get_client")
def test_partial_batch_state_halts_insertion(mock_get_client):
    """
    An incomplete existing batch is unsafe and must stop ingestion.
    """

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Simulate partial warehouse state.
    mock_client.command.side_effect = [
        1,
        5,
        0,
        5,
    ]

    service = TrustedIngestionService(
        VALID_FIXTURE_PATH
    )

    result = service.process()

    assert result["status"] == "PARTIAL_BATCH_EXISTS"
    assert result["inserted"] is False

    mock_client.insert.assert_not_called()


@patch.dict(os.environ, {}, clear=True)
def test_missing_environment_variables_fail_safely():
    """
    Database credentials must never silently default.
    """

    service = TrustedIngestionService(
        VALID_FIXTURE_PATH
    )

    with pytest.raises(ValueError) as exc_info:
        service.process()

    message = str(exc_info.value)

    assert (
        "Missing required connection environment variables"
        in message
    )

    assert "CLICKHOUSE_PASSWORD" in message