"""
test_audit.py — Unit tests for AuditLogger.
Tests the AuditLogger.log() method directly without going through HTTP.
The audit logger writes to BigQuery; BQ client is mocked.
"""

import json
import os
import time
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_bq():
    """Mock BigQuery client that records insert_rows_json calls."""
    client = MagicMock()
    client.insert_rows_json = MagicMock(return_value=[])  # [] = no errors
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_log_writes_to_bq(mock_bq):
    """AuditLogger.log() should call insert_rows_json with correct fields."""
    with patch("google.cloud.bigquery.Client", return_value=mock_bq):
        from audit import AuditLogger
        import importlib
        import audit as audit_mod
        importlib.reload(audit_mod)

        logger = audit_mod.AuditLogger()
        logger._client = mock_bq  # inject directly after construction

        await logger.log(
            caller_id="test-viewer",
            tool_name="list_active_alerts",
            input_params={"severity_filter": "all"},
            result_status="success",
            latency_ms=42,
        )

    assert mock_bq.insert_rows_json.called, "insert_rows_json should have been called"
    rows = mock_bq.insert_rows_json.call_args[0][1]
    assert len(rows) >= 1
    row = rows[0]
    assert row["tool_name"] == "list_active_alerts"
    assert row["caller_id"] == "test-viewer"
    assert row["result_status"] == "success"
    assert row["latency_ms"] == 42


@pytest.mark.asyncio
async def test_audit_log_input_params_is_json_string(mock_bq):
    """input_params should be stored as a JSON string, not a dict."""
    from audit import AuditLogger
    logger = AuditLogger()
    logger._client = mock_bq

    await logger.log(
        caller_id="test-viewer",
        tool_name="search_runbooks",
        input_params={"query": "payments error rate", "top_k": 2},
        result_status="success",
        latency_ms=100,
    )

    rows = mock_bq.insert_rows_json.call_args[0][1]
    row = rows[0]
    ip = row.get("input_params", "")
    assert isinstance(ip, str), f"input_params must be a JSON string, got {type(ip)}"
    parsed = json.loads(ip)
    assert parsed.get("query") == "payments error rate"


@pytest.mark.asyncio
async def test_audit_log_error_status(mock_bq):
    """AuditLogger should accept result_status='error' with an error message."""
    from audit import AuditLogger
    logger = AuditLogger()
    logger._client = mock_bq

    await logger.log(
        caller_id="test-viewer",
        tool_name="list_active_alerts",
        input_params={"severity_filter": "invalid"},
        result_status="error",
        latency_ms=5,
        error_message="ValueError: invalid severity",
    )

    rows = mock_bq.insert_rows_json.call_args[0][1]
    row = rows[0]
    assert row["result_status"] == "error"
    assert "error_message" in row


@pytest.mark.asyncio
async def test_audit_log_latency_is_non_negative(mock_bq):
    """latency_ms stored in the row must be >= 0."""
    from audit import AuditLogger
    logger = AuditLogger()
    logger._client = mock_bq

    await logger.log(
        caller_id="test-operator",
        tool_name="trigger_rollback",
        input_params={},
        result_status="success",
        latency_ms=0,
    )

    rows = mock_bq.insert_rows_json.call_args[0][1]
    row = rows[0]
    assert row.get("latency_ms", -1) >= 0


@pytest.mark.asyncio
async def test_audit_log_records_timestamp(mock_bq):
    """Each audit row must contain an ISO timestamp field."""
    from audit import AuditLogger
    logger = AuditLogger()
    logger._client = mock_bq

    await logger.log(
        caller_id="test-viewer",
        tool_name="query_metrics",
        input_params={"service": "payments", "metric_type": "error_rate"},
        result_status="success",
        latency_ms=200,
    )

    rows = mock_bq.insert_rows_json.call_args[0][1]
    row = rows[0]
    assert "timestamp" in row, "Audit row must contain a timestamp field"
    assert isinstance(row["timestamp"], str)


@pytest.mark.asyncio
async def test_audit_log_failure_is_non_fatal(mock_bq):
    """If BQ insert fails, AuditLogger should not raise an exception."""
    mock_bq.insert_rows_json = MagicMock(side_effect=Exception("BQ unavailable"))
    from audit import AuditLogger
    logger = AuditLogger()
    logger._client = mock_bq

    # Should not raise even though BQ insert fails
    await logger.log(
        caller_id="test-viewer",
        tool_name="list_active_alerts",
        input_params={},
        result_status="success",
        latency_ms=10,
    )
    # No assertion needed — test passes if no exception was raised
