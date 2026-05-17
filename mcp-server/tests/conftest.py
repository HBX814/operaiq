"""
pytest conftest for MCP server tests.

Provides:
  - mock_bq_client    : MagicMock replacing google.cloud.bigquery.Client
  - mock_chroma       : MagicMock replacing chromadb.PersistentClient
  - mock_firestore    : MagicMock replacing google.cloud.firestore.Client
  - mock_pubsub       : MagicMock replacing google.cloud.pubsub_v1.PublisherClient
  - test_app          : httpx.AsyncClient wired to the FastAPI app

Environment variables are set to "test" mode so BigQuery/Pub/Sub calls
are intercepted by the mocks without needing real GCP credentials.
"""

import os
import json
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

import pytest
import pytest_asyncio
import httpx

# Set test environment BEFORE importing app modules
os.environ.setdefault("ENV", "test")
os.environ.setdefault("GCP_PROJECT_ID", "operaiq-test")
os.environ.setdefault("BIGQUERY_DATASET", "operaiq")
os.environ.setdefault("TEST_TOKEN", "test-viewer-token")
os.environ.setdefault("TEST_OPERATOR_TOKEN", "test-operator-token")
os.environ.setdefault("CHROMADB_PERSIST_DIR", "/tmp/operaiq-test-chroma")

# ---------------------------------------------------------------------------
# Shared fake data
# ---------------------------------------------------------------------------

FAKE_INCIDENT = {
    "incident_id": "test-inc-001",
    "title": "Payment Gateway Timeout",
    "service": "payments",
    "severity": "critical",
    "status": "open",
    "timestamp": datetime(2024, 1, 15, 14, 32, 0, tzinfo=timezone.utc),
    "triggered_by_deployment_id": "dep-001",
}

FAKE_DEPLOYMENT = {
    "deployment_id": "dep-001",
    "service": "payments",
    "version": "2.3.7",
    "status": "failed",
    "timestamp": datetime(2024, 1, 15, 14, 17, 0, tzinfo=timezone.utc),
    "region": "us-central1",
}


def _make_bq_row(data: dict):
    """Create a mock BigQuery row that supports attribute access."""
    row = MagicMock()
    for key, value in data.items():
        setattr(row, key, value)
    return row


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_bq_client():
    """Replace BigQuery client globally for all tests."""
    mock_client = MagicMock()

    # Default query result: empty list (tests override as needed)
    mock_job = MagicMock()
    mock_job.result.return_value = iter([])
    mock_client.query.return_value = mock_job

    # For streaming inserts
    mock_client.insert_rows_json.return_value = []

    with patch("google.cloud.bigquery.Client", return_value=mock_client):
        yield mock_client


@pytest.fixture(autouse=True)
def mock_chroma():
    """Replace ChromaDB PersistentClient globally for all tests."""
    mock_collection = MagicMock()
    mock_collection.count.return_value = 3
    mock_collection.query.return_value = {
        "ids": [["rb-001", "rb-002", "rb-003"]],
        "documents": [
            [
                "Payments service high error rate: Step 1 - check recent deployments, "
                "Step 2 - verify downstream dependencies, Step 3 - trigger rollback if needed.",
                "Auth service latency spike: Step 1 - check DB connection pool, Step 2 - scale up.",
                "Search service: Step 1 - reindex, Step 2 - check ElasticSearch cluster health.",
            ]
        ],
        "metadatas": [
            [
                {"service": "payments", "title": "Payments High Error Rate Runbook", "last_updated": "2024-01-01"},
                {"service": "auth", "title": "Auth Latency Spike Runbook", "last_updated": "2024-01-01"},
                {"service": "search", "title": "Search Reindex Runbook", "last_updated": "2024-01-01"},
            ]
        ],
        "distances": [[0.1, 0.25, 0.4]],
    }
    mock_collection.get.return_value = {
        "documents": ["Step 1 - check recent deployments..."],
        "metadatas": [{"service": "payments", "title": "Payments High Error Rate Runbook"}],
    }

    mock_chroma_client = MagicMock()
    mock_chroma_client.get_or_create_collection.return_value = mock_collection

    with patch("chromadb.PersistentClient", return_value=mock_chroma_client):
        yield mock_chroma_client


@pytest.fixture(autouse=True)
def mock_firestore():
    """Replace Firestore client globally for all tests."""
    mock_doc_ref = MagicMock()
    mock_doc_ref.id = "test-doc-id"
    mock_doc_ref.set = AsyncMock(return_value=None)
    mock_doc_ref.update = AsyncMock(return_value=None)
    mock_doc_ref.get = AsyncMock()
    mock_doc_ref.get.return_value.exists = True
    mock_doc_ref.get.return_value.to_dict.return_value = {
        "incident_id": "test-inc-001",
        "status": "silenced",
    }

    mock_collection_ref = MagicMock()
    mock_collection_ref.document.return_value = mock_doc_ref
    mock_collection_ref.add.return_value = (None, mock_doc_ref)

    mock_fs = MagicMock()
    mock_fs.collection.return_value = mock_collection_ref

    with patch("google.cloud.firestore.AsyncClient", return_value=mock_fs):
        with patch("google.cloud.firestore.Client", return_value=mock_fs):
            yield mock_fs


@pytest.fixture(autouse=True)
def mock_pubsub():
    """Replace Pub/Sub publisher globally for all tests."""
    mock_pub = MagicMock()
    mock_future = MagicMock()
    mock_future.result.return_value = "projects/operaiq-test/topics/operaiq-events/messages/1"
    mock_pub.publish.return_value = mock_future

    with patch("google.cloud.pubsub_v1.PublisherClient", return_value=mock_pub):
        yield mock_pub


@pytest.fixture(autouse=True)
def mock_auth():
    """
    Mock auth.verify_token so test tokens work without real Firebase.
    We patch both 'auth.verify_token' (source) and 'main.verify_token' (usage)
    so the middleware intercepts the mock regardless of how it was imported.
    - 'test-viewer-token'   → caller_id='test-viewer',   roles=['viewer']
    - 'test-operator-token' → caller_id='test-operator', roles=['operator', 'viewer']
    - anything else         → raises ValueError (401)
    """
    from auth import TokenClaims

    async def fake_verify(token: str) -> TokenClaims:
        if token == os.environ.get("TEST_TOKEN", "test-viewer-token"):
            return TokenClaims(
                caller_id="test-viewer",
                email="viewer@test.com",
                roles=["viewer"],
            )
        if token == os.environ.get("TEST_OPERATOR_TOKEN", "test-operator-token"):
            return TokenClaims(
                caller_id="test-operator",
                email="operator@test.com",
                roles=["operator", "viewer"],
            )
        raise ValueError(f"Invalid token: {token!r}")

    # Patch both import paths so the middleware always sees the mock
    with patch("auth.verify_token", side_effect=fake_verify):
        with patch("main.verify_token", side_effect=fake_verify):
            yield


@pytest_asyncio.fixture
async def test_client():
    """httpx.AsyncClient bound to the FastAPI app (no real network)."""
    # Import app after all mocks are active
    from main import app
    try:
        # httpx >= 0.27 requires explicit ASGITransport
        from httpx import ASGITransport
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            follow_redirects=True,
        ) as client:
            yield client
    except ImportError:
        # Older httpx — fallback to deprecated app= kwarg
        async with httpx.AsyncClient(
            app=app, base_url="http://test", follow_redirects=True
        ) as client:
            yield client


def viewer_headers():
    return {
        "Authorization": f"Bearer {os.environ['TEST_TOKEN']}",
        "Content-Type": "application/json",
    }


def operator_headers():
    return {
        "Authorization": f"Bearer {os.environ['TEST_OPERATOR_TOKEN']}",
        "Content-Type": "application/json",
    }
