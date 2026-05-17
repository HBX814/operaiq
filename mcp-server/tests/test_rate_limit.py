"""
test_rate_limit.py — Unit tests for the token bucket rate limiter.
Tests the _check_rate_limit() function directly without HTTP.
Rate limit: 60 requests/min per caller_id (refills at 1 token/sec).
"""

import asyncio
import time
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_buckets():
    """Reset the global rate bucket state between tests."""
    import main as mcp_main
    mcp_main._rate_buckets.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_rate_limit_first_call_succeeds():
    """A fresh caller should be allowed on the first call."""
    _reset_buckets()
    from main import _check_rate_limit
    assert _check_rate_limit("fresh-caller") is True


def test_rate_limit_60_calls_succeed():
    """The first 60 calls from a single caller should all succeed."""
    _reset_buckets()
    from main import _check_rate_limit
    successes = sum(1 for _ in range(60) if _check_rate_limit("caller-60"))
    assert successes == 60, f"Expected 60 successes, got {successes}"


def test_rate_limit_61st_call_blocked():
    """The 61st call from the same caller within a window should be blocked."""
    _reset_buckets()
    from main import _check_rate_limit
    # Exhaust the bucket
    for _ in range(60):
        _check_rate_limit("caller-61st")
    # 61st should be rejected
    result = _check_rate_limit("caller-61st")
    assert result is False, "Expected 61st call to be rate-limited"


def test_rate_limit_different_callers_independent():
    """Two different caller_ids should have independent rate buckets."""
    _reset_buckets()
    from main import _check_rate_limit
    # Exhaust caller-A
    for _ in range(60):
        _check_rate_limit("caller-A")
    # caller-B should still have a full budget
    assert _check_rate_limit("caller-B") is True, (
        "caller-B should not be rate-limited by caller-A's calls"
    )


def test_rate_limit_bucket_refills():
    """After waiting ~1 second, at least 1 new token should be available."""
    _reset_buckets()
    from main import _check_rate_limit, _rate_buckets

    caller = "caller-refill"
    # Exhaust the bucket
    for _ in range(60):
        _check_rate_limit(caller)
    assert _check_rate_limit(caller) is False, "Should be rate-limited at start"

    # Simulate 1.1 seconds of time passing by directly manipulating the bucket
    _rate_buckets[caller]["last_refill"] = time.monotonic() - 1.1

    # Now one more call should succeed
    result = _check_rate_limit(caller)
    assert result is True, "Expected 1 token to be available after 1.1 seconds"


def test_rate_limit_returns_bool():
    """_check_rate_limit should always return a bool."""
    _reset_buckets()
    from main import _check_rate_limit
    result = _check_rate_limit("test-bool-caller")
    assert isinstance(result, bool)


def test_rate_limit_empty_caller_id_still_works():
    """Rate limiter should work even with an empty string caller_id."""
    _reset_buckets()
    from main import _check_rate_limit
    # Should not raise; empty string is a valid dict key
    result = _check_rate_limit("")
    assert isinstance(result, bool)
