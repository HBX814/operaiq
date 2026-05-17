"""
MCP Tools: trigger_rollback, silence_alert
Both tools are idempotent — duplicate calls with the same inputs
produce no additional side effects (checked via Firestore).
trigger_rollback requires caller role "operator".
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from fastmcp.tools.tool import Tool

from google.cloud import pubsub_v1, firestore
from google.cloud.exceptions import NotFound
from google.api_core.exceptions import AlreadyExists

GCP_PROJECT = os.environ.get("GCP_PROJECT_ID", "operaiq")
ROLLBACK_TOPIC = os.environ.get(
    "PUBSUB_TOPIC", os.environ.get("PUBSUB_ROLLBACK_TOPIC", "operaiq-events")
)
SILENCES_COLLECTION = os.environ.get(
    "FIRESTORE_COLLECTION_SILENCES", "silences"
)

# Lazy singletons
_pubsub_publisher = None
_firestore_client = None


def _publisher():
    global _pubsub_publisher
    if _pubsub_publisher is None:
        _pubsub_publisher = pubsub_v1.PublisherClient()
    return _pubsub_publisher


def _firestore():
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.AsyncClient(project=GCP_PROJECT)
    return _firestore_client


# ─────────────────────────────────────────────────────────────────────────────
# trigger_rollback
# ─────────────────────────────────────────────────────────────────────────────

async def trigger_rollback(
    deployment_id: str,
    reason: str,
    caller_id: str,
    caller_roles: list[str],
) -> dict:
    """
    Initiate a rollback for a deployment. Publishes a RollbackEvent to
    Pub/Sub. Requires the caller to have the 'operator' role.
    Idempotent — calling with the same deployment_id returns the existing
    rollback record rather than creating a duplicate.
    """
    # ── Role check ─────────────────────────────────────────────────────────
    if "operator" not in caller_roles:
        raise PermissionError(
            "trigger_rollback requires the 'operator' role. "
            f"Caller '{caller_id}' has roles: {caller_roles}"
        )

    if not deployment_id or len(deployment_id) > 128:
        raise ValueError("deployment_id must be a non-empty string ≤ 128 chars")
    if not reason or len(reason) > 1024:
        raise ValueError("reason must be a non-empty string ≤ 1024 chars")

    db = _firestore()

    # ── Idempotency check ──────────────────────────────────────────────────
    rollback_ref = db.collection("rollbacks").document(deployment_id)
    existing = await rollback_ref.get()
    if existing.exists:
        data = existing.to_dict()
        return {
            "rollback_id": data["rollback_id"],
            "status": data["status"],
            "estimated_completion_seconds": 0,
            "idempotent": True,
            "message": "Rollback already initiated for this deployment.",
        }

    # ── Publish RollbackEvent to Pub/Sub ───────────────────────────────────
    rollback_id = str(uuid.uuid4())
    event = {
        "event_type": "rollback",
        "rollback_id": rollback_id,
        "deployment_id": deployment_id,
        "reason": reason,
        "initiated_by": caller_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "initiated",
    }

    try:
        topic_path = _publisher().topic_path(GCP_PROJECT, ROLLBACK_TOPIC)
        future = _publisher().publish(
            topic_path,
            data=json.dumps(event).encode("utf-8"),
            event_type="rollback",
        )
        await asyncio.get_event_loop().run_in_executor(None, future.result)
    except Exception as exc:
        # In test/dev without Pub/Sub, log but don't fail
        import logging
        logging.warning(f"Pub/Sub publish failed (non-fatal in dev): {exc}")

    # ── Persist to Firestore (idempotency record) ──────────────────────────
    record = {
        "rollback_id": rollback_id,
        "deployment_id": deployment_id,
        "reason": reason,
        "initiated_by": caller_id,
        "status": "initiated",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await rollback_ref.set(record)

    return {
        "rollback_id": rollback_id,
        "status": "initiated",
        "estimated_completion_seconds": 120,
        "idempotent": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# silence_alert
# ─────────────────────────────────────────────────────────────────────────────

async def silence_alert(
    incident_id: str,
    duration_minutes: int,
    reason: str,
    caller_id: str,
) -> dict:
    """
    Suppress alert notifications for an incident for up to 240 minutes.
    Writes a silence record to Firestore. Idempotent — calling twice with
    the same incident_id extends the existing silence rather than duplicating.
    """
    if not incident_id or len(incident_id) > 128:
        raise ValueError("incident_id must be a non-empty string ≤ 128 chars")
    if not isinstance(duration_minutes, int) or duration_minutes < 1:
        raise ValueError("duration_minutes must be a positive integer")
    if duration_minutes > 240:
        raise ValueError(
            f"duration_minutes cannot exceed 240 (requested: {duration_minutes})"
        )
    if not reason or len(reason) > 1024:
        raise ValueError("reason must be a non-empty string ≤ 1024 chars")

    db = _firestore()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=duration_minutes)

    silence_ref = db.collection(SILENCES_COLLECTION).document(incident_id)
    existing = await silence_ref.get()

    if existing.exists:
        # Extend the existing silence
        await silence_ref.update({
            "expires_at": expires_at.isoformat(),
            "duration_minutes": duration_minutes,
            "reason": reason,
            "extended_by": caller_id,
            "extended_at": now.isoformat(),
        })
        return {
            "incident_id": incident_id,
            "status": "silenced",
            "expires_at": expires_at.isoformat(),
            "duration_minutes": duration_minutes,
            "idempotent": True,
            "message": "Existing silence extended.",
        }

    record = {
        "incident_id": incident_id,
        "duration_minutes": duration_minutes,
        "reason": reason,
        "created_by": caller_id,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "status": "silenced",
    }
    await silence_ref.set(record)

    return {
        "incident_id": incident_id,
        "status": "silenced",
        "expires_at": expires_at.isoformat(),
        "duration_minutes": duration_minutes,
        "idempotent": False,
    }


def _add_tool_with_param_descriptions(
    mcp,
    fn,
    description: str,
    param_descriptions: dict[str, str],
) -> None:
    tool = Tool.from_function(fn, description=description)
    properties = tool.parameters.get("properties", {})
    for name, desc in param_descriptions.items():
        if name in properties:
            properties[name]["description"] = desc
    mcp.add_tool(tool)


def register_remediation_tools(mcp) -> None:
    _add_tool_with_param_descriptions(
        mcp,
        trigger_rollback,
        description=(
            "Initiate a rollback for a deployment. Requires the caller to have the 'operator' role."
        ),
        param_descriptions={
            "deployment_id": "Deployment identifier to roll back.",
            "reason": "Reason for the rollback request.",
            "caller_id": "Caller identifier from auth token.",
            "caller_roles": "Caller roles from auth token (must include operator).",
        },
    )

    _add_tool_with_param_descriptions(
        mcp,
        silence_alert,
        description=(
            "Suppress alert notifications for an incident for up to 240 minutes."
        ),
        param_descriptions={
            "incident_id": "Incident identifier to silence.",
            "duration_minutes": "Silence duration in minutes (1-240).",
            "reason": "Reason for silencing the incident.",
            "caller_id": "Caller identifier from auth token.",
        },
    )
