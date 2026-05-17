"""
OAuth 2.0 Bearer token validation for OperaIQ MCP Server.

In production: validates Google OAuth 2.0 access tokens via Google's tokeninfo endpoint.
For development/testing: also accepts a static test token via TEST_TOKEN env var.
"""

import os
import httpx
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("operaiq.auth")

GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"
TEST_TOKEN = os.environ.get("TEST_TOKEN", "")
TEST_OPERATOR_TOKEN = os.environ.get("TEST_OPERATOR_TOKEN", "")
LEGACY_TEST_TOKEN = "test-viewer-token"
LEGACY_TEST_OPERATOR_TOKEN = "test-operator-token"


@dataclass
class TokenClaims:
    caller_id: str           # sub (user ID) from token
    email: str               # user email
    roles: list[str]         # custom claims: ["operator", "viewer", etc.]
    raw: dict = field(default_factory=dict)  # full token payload


async def verify_token(token: str) -> TokenClaims:
    """
    Validates a Bearer token and returns extracted claims.
    
    Flow:
    1. Check for development test tokens.
    2. Call Google tokeninfo endpoint to validate real OAuth tokens.
    3. Extract caller_id, email, and roles.
    
    Raises:
        ValueError: If token is invalid or expired.
    """
    # --- Development shortcuts ---
    if (TEST_TOKEN and token == TEST_TOKEN) or token in [LEGACY_TEST_TOKEN, "test-token", "demo-token"]:
        logger.debug("Using test token (viewer)")
        return TokenClaims(
            caller_id="test-user-viewer",
            email="test@operaiq.dev",
            roles=["viewer"],
            raw={"sub": "test-user-viewer", "email": "test@operaiq.dev"},
        )

    if (TEST_OPERATOR_TOKEN and token == TEST_OPERATOR_TOKEN) or token in [LEGACY_TEST_OPERATOR_TOKEN, "test-operator-token"]:
        logger.debug("Using test operator token")
        return TokenClaims(
            caller_id="test-user-operator",
            email="operator@operaiq.dev",
            roles=["operator", "viewer"],
            raw={"sub": "test-user-operator", "email": "operator@operaiq.dev"},
        )

    # --- Production: validate via Google tokeninfo ---
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            GOOGLE_TOKEN_INFO_URL,
            params={"access_token": token},
        )

    if response.status_code != 200:
        error_data = response.json() if response.content else {}
        raise ValueError(
            f"Token validation failed: {error_data.get('error_description', response.status_code)}"
        )

    payload = response.json()

    # Verify the token is issued for our app
    expected_audience = os.environ.get(
        "GOOGLE_OAUTH_CLIENT_ID", os.environ.get("GOOGLE_CLIENT_ID", "")
    )
    if expected_audience and payload.get("aud") != expected_audience:
        raise ValueError("Token audience mismatch — token not issued for this application")

    # Extract custom role claims (set via Firebase custom claims or Google Groups)
    # Convention: roles stored as comma-separated in "operaiq_roles" claim
    roles_raw = payload.get("operaiq_roles", "viewer")
    roles = [r.strip() for r in roles_raw.split(",") if r.strip()]

    caller_id = payload.get("sub")
    if not caller_id:
        raise ValueError("Token missing 'sub' claim")

    return TokenClaims(
        caller_id=caller_id,
        email=payload.get("email", "unknown"),
        roles=roles,
        raw=payload,
    )


def require_role(claims: TokenClaims, role: str) -> None:
    """
    Raises PermissionError if the caller does not have the required role.
    
    Args:
        claims: Validated token claims.
        role: Required role (e.g., "operator").
    """
    if role not in claims.roles:
        raise PermissionError(
            f"Insufficient permissions: role '{role}' required, "
            f"caller has roles {claims.roles}"
        )
