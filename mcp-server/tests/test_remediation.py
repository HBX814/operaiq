import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from tools.remediation import trigger_rollback, silence_alert

@pytest.mark.asyncio
async def test_trigger_rollback_requires_operator():
    with pytest.raises(PermissionError) as exc_info:
        await trigger_rollback(
            deployment_id="dep-123",
            reason="Test",
            caller_id="user1",
            caller_roles=["viewer"]
        )
    assert "requires the 'operator' role" in str(exc_info.value)

@pytest.mark.asyncio
@patch("tools.remediation._firestore")
@patch("tools.remediation._publisher")
async def test_trigger_rollback_success(mock_publisher, mock_firestore):
    # Mock Firestore
    mock_db = MagicMock()
    mock_firestore.return_value = mock_db
    
    mock_doc = AsyncMock()
    mock_db.collection.return_value.document.return_value = mock_doc
    
    # Mock existing doc so we test idempotency miss first
    mock_existing = MagicMock()
    mock_existing.exists = False
    mock_doc.get.return_value = mock_existing

    # Mock PubSub
    mock_pub = MagicMock()
    mock_publisher.return_value = mock_pub
    
    mock_future = MagicMock()
    mock_future.result = MagicMock()
    mock_pub.publish.return_value = mock_future

    result = await trigger_rollback(
        deployment_id="dep-123",
        reason="Test",
        caller_id="operator1",
        caller_roles=["operator"]
    )
    
    assert result["status"] == "initiated"
    assert result["idempotent"] is False
    assert "rollback_id" in result

@pytest.mark.asyncio
@patch("tools.remediation._firestore")
async def test_trigger_rollback_idempotent(mock_firestore):
    mock_db = MagicMock()
    mock_firestore.return_value = mock_db
    
    mock_doc = AsyncMock()
    mock_db.collection.return_value.document.return_value = mock_doc
    
    # Mock existing doc
    mock_existing = MagicMock()
    mock_existing.exists = True
    mock_existing.to_dict.return_value = {"rollback_id": "rb-456", "status": "initiated"}
    mock_doc.get.return_value = mock_existing

    result = await trigger_rollback(
        deployment_id="dep-123",
        reason="Test",
        caller_id="operator1",
        caller_roles=["operator"]
    )
    
    assert result["status"] == "initiated"
    assert result["idempotent"] is True
    assert result["rollback_id"] == "rb-456"

@pytest.mark.asyncio
async def test_silence_alert_invalid_duration():
    with pytest.raises(ValueError) as exc_info:
        await silence_alert(
            incident_id="inc-123",
            duration_minutes=300,
            reason="Test",
            caller_id="operator1"
        )
    assert "cannot exceed 240" in str(exc_info.value)

@pytest.mark.asyncio
@patch("tools.remediation._firestore")
async def test_silence_alert_success(mock_firestore):
    mock_db = MagicMock()
    mock_firestore.return_value = mock_db
    
    mock_doc = AsyncMock()
    mock_db.collection.return_value.document.return_value = mock_doc
    
    mock_existing = MagicMock()
    mock_existing.exists = False
    mock_doc.get.return_value = mock_existing

    result = await silence_alert(
        incident_id="inc-123",
        duration_minutes=60,
        reason="Test",
        caller_id="operator1"
    )
    
    assert result["status"] == "silenced"
    assert result["idempotent"] is False
    assert result["duration_minutes"] == 60

@pytest.mark.asyncio
@patch("tools.remediation._firestore")
async def test_silence_alert_extend(mock_firestore):
    mock_db = MagicMock()
    mock_firestore.return_value = mock_db
    
    mock_doc = AsyncMock()
    mock_db.collection.return_value.document.return_value = mock_doc
    
    mock_existing = MagicMock()
    mock_existing.exists = True
    mock_doc.get.return_value = mock_existing

    result = await silence_alert(
        incident_id="inc-123",
        duration_minutes=120,
        reason="Test extend",
        caller_id="operator1"
    )
    
    assert result["status"] == "silenced"
    assert result["idempotent"] is True
    assert result["duration_minutes"] == 120
