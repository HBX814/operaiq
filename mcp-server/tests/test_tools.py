"""
MCP Server Integration Tests — uses httpx to test against a running local MCP server.
Run with: pytest mcp-server/tests/test_tools.py -v

Requires:
  - MCP server running at http://localhost:8080
  - TEST_TOKEN env var set to a valid test token

These tests are marked with @pytest.mark.integration and are EXCLUDED from the
standard CI run (-k "not integration"). They are run manually or in a dedicated
integration test step against a live or containerized server.
"""

import os
import json
import uuid
import pytest
import httpx

pytestmark = pytest.mark.integration  # Skip all tests in this file unless -m integration

BASE_URL = os.environ.get("MCP_TEST_URL", "http://localhost:8080")
VIEWER_TOKEN = os.environ.get("TEST_TOKEN", "test-viewer-token")
OPERATOR_TOKEN = os.environ.get("TEST_OPERATOR_TOKEN", "test-operator-token")


def viewer_headers():
    return {"Authorization": f"Bearer {VIEWER_TOKEN}", "Content-Type": "application/json"}


def operator_headers():
    return {"Authorization": f"Bearer {OPERATOR_TOKEN}", "Content-Type": "application/json"}


def mcp_call(tool_name: str, arguments: dict, token_type: str = "viewer") -> dict:
    """Make a JSON-RPC 2.0 call to the MCP server."""
    headers = viewer_headers() if token_type == "viewer" else operator_headers()
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    response = httpx.post(f"{BASE_URL}/mcp", json=payload, headers=headers, timeout=30)
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────────────────────

def test_health_endpoint():
    """Health endpoint returns 200 without auth."""
    response = httpx.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "operaiq-mcp-server"


# ─────────────────────────────────────────────────────────────────────────────
# Auth Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_no_auth_returns_401():
    """Requests without Authorization header should fail."""
    response = httpx.post(
        f"{BASE_URL}/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert response.status_code == 401


def test_invalid_token_returns_401():
    """Requests with an invalid token should fail."""
    response = httpx.post(
        f"{BASE_URL}/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={"Authorization": "Bearer invalid-garbage-token"},
    )
    assert response.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# Tool: query_metrics
# ─────────────────────────────────────────────────────────────────────────────

def test_query_metrics_valid():
    """query_metrics returns a list of {timestamp, value} dicts."""
    response = mcp_call("query_metrics", {
        "service": "payments",
        "metric_type": "error_rate",
        "minutes_back": 60,
    })
    assert response.status_code == 200
    result = response.json()
    # Result should be a list
    content = result.get("result", {}).get("content", [])
    assert len(content) > 0
    data = json.loads(content[0]["text"])
    assert isinstance(data, list)
    if data:
        assert "timestamp" in data[0]
        assert "value" in data[0]


def test_query_metrics_invalid_minutes():
    """query_metrics rejects out-of-range minutes_back."""
    response = mcp_call("query_metrics", {
        "service": "payments",
        "metric_type": "error_rate",
        "minutes_back": 99999,  # exceeds max
    })
    # Should return an error result
    result = response.json()
    assert "error" in result or "error" in str(result.get("result", ""))


# ─────────────────────────────────────────────────────────────────────────────
# Tool: list_active_alerts
# ─────────────────────────────────────────────────────────────────────────────

def test_list_active_alerts_all():
    """list_active_alerts returns a list with severity and status."""
    response = mcp_call("list_active_alerts", {"severity_filter": "all"})
    assert response.status_code == 200
    result = response.json()
    content = result.get("result", {}).get("content", [])
    data = json.loads(content[0]["text"]) if content else []
    assert isinstance(data, list)
    for item in data:
        assert "incident_id" in item
        assert "severity" in item
        assert item["status"] == "open"


def test_list_active_alerts_invalid_severity():
    """list_active_alerts rejects invalid severity values."""
    response = mcp_call("list_active_alerts", {"severity_filter": "extreme"})
    result = response.json()
    assert "error" in result or "error" in str(result.get("result", ""))


# ─────────────────────────────────────────────────────────────────────────────
# Tool: search_runbooks
# ─────────────────────────────────────────────────────────────────────────────

def test_search_runbooks_returns_results():
    """search_runbooks returns relevant documents."""
    response = mcp_call("search_runbooks", {
        "query": "payment service high error rate",
        "top_k": 3,
    })
    assert response.status_code == 200
    result = response.json()
    content = result.get("result", {}).get("content", [])
    data = json.loads(content[0]["text"]) if content else []
    assert isinstance(data, list)
    assert len(data) > 0
    assert "title" in data[0]
    assert "similarity_score" in data[0]
    # Top result should be payment-related
    assert "payment" in data[0]["title"].lower() or "payment" in data[0]["service"].lower()


def test_search_runbooks_invalid_top_k():
    """search_runbooks rejects top_k out of range."""
    response = mcp_call("search_runbooks", {"query": "test", "top_k": 100})
    result = response.json()
    assert "error" in result or "error" in str(result.get("result", ""))


# ─────────────────────────────────────────────────────────────────────────────
# Tool: trigger_rollback (operator-required)
# ─────────────────────────────────────────────────────────────────────────────

def test_trigger_rollback_requires_operator():
    """trigger_rollback should be rejected for viewer role."""
    response = mcp_call("trigger_rollback", {
        "deployment_id": str(uuid.uuid4()),
        "reason": "test rollback",
        "caller_id": "test-viewer",
        "caller_roles": ["viewer"],  # NOT operator
    }, token_type="viewer")
    result = response.json()
    # Should contain PermissionError in result
    content_text = str(result.get("result", "")) + str(result.get("error", ""))
    assert "permission" in content_text.lower() or "operator" in content_text.lower()


def test_trigger_rollback_operator_succeeds():
    """trigger_rollback succeeds with operator role."""
    dep_id = str(uuid.uuid4())
    response = mcp_call("trigger_rollback", {
        "deployment_id": dep_id,
        "reason": "Automated test rollback",
        "caller_id": "test-operator",
        "caller_roles": ["operator", "viewer"],
    }, token_type="operator")
    assert response.status_code == 200
    result = response.json()
    content = result.get("result", {}).get("content", [])
    data = json.loads(content[0]["text"]) if content else {}
    assert "rollback_id" in data
    assert data["status"] == "initiated"
    assert data["estimated_completion_seconds"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# Tool: silence_alert
# ─────────────────────────────────────────────────────────────────────────────

def test_silence_alert_valid():
    """silence_alert creates a silence record."""
    response = mcp_call("silence_alert", {
        "incident_id": str(uuid.uuid4()),
        "duration_minutes": 30,
        "reason": "Investigating, not a real issue",
        "caller_id": "test-operator",
    }, token_type="operator")
    assert response.status_code == 200
    result = response.json()
    content = result.get("result", {}).get("content", [])
    data = json.loads(content[0]["text"]) if content else {}
    assert data.get("status") == "silenced"
    assert "expires_at" in data


def test_silence_alert_invalid_duration():
    """silence_alert rejects duration > 240 minutes."""
    response = mcp_call("silence_alert", {
        "incident_id": str(uuid.uuid4()),
        "duration_minutes": 500,  # too long
        "reason": "Test",
        "caller_id": "test-user",
    })
    result = response.json()
    content_text = str(result.get("result", "")) + str(result.get("error", ""))
    assert "240" in content_text or "error" in content_text.lower()
