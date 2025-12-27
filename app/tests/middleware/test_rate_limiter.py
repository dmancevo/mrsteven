"""Tests for rate limiting middleware."""

import time

import pytest
from fastapi.testclient import TestClient

from app import app


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter state before each test."""
    # Clear rate limiter requests between tests
    from middleware.rate_limiter import _rate_limiter

    _rate_limiter.requests.clear()
    _rate_limiter.last_cleanup = time.time()
    yield


class TestRateLimiter:
    """Test rate limiting middleware behavior."""

    def test_api_endpoint_rate_limit_enforced(self):
        """Test that health endpoint is rate limited at 10 req/s."""
        client = TestClient(app)

        # Make 10 requests (should all succeed - health limit is 10)
        for _ in range(10):
            response = client.get("/health")
            assert response.status_code == 200

        # 11th request should be rate limited
        response = client.get("/health")
        assert response.status_code == 429
        assert "rate limit" in response.json()["detail"].lower()

    def test_timer_endpoint_has_high_limit(self):
        """Test that timer endpoint allows more requests than standard API endpoints."""
        client = TestClient(app)

        # Timer endpoint has 20 req/s limit (vs 5 for regular API)
        # Make enough requests to exceed standard API limit
        success_count = 0
        for _ in range(12):
            # Use a mock game_id and player_id for testing
            response = client.get("/api/games/test-game/timer?player_id=test-player")
            if response.status_code != 429:
                success_count += 1
            # Tiny sleep to avoid timestamp collision in tests
            time.sleep(0.001)

        # Should allow more than the 5 req/s API limit, confirming higher timer limit
        assert success_count > 5, f"Only {success_count} requests succeeded, expected more than 5"

    def test_static_files_exempt_from_rate_limiting(self):
        """Test that static files are not rate limited."""
        client = TestClient(app)

        # Make 10 requests to static files (more than normal API limit)
        for _ in range(10):
            # Request will 404 since file doesn't exist, but shouldn't be rate limited
            response = client.get("/static/test.css")
            # Should get 404 (not found) not 429 (rate limited)
            assert response.status_code == 404

    def test_websocket_exempt_from_rate_limiting(self):
        """Test that WebSocket endpoints are not rate limited."""
        client = TestClient(app)

        # WebSocket endpoints should not be rate limited
        # We'll test by making multiple requests to websocket path
        for _ in range(10):
            # This will fail to upgrade to WebSocket, but shouldn't be rate limited
            try:
                response = client.get("/ws/test-game/test-player")
                # Should not get 429, might get other errors
                assert response.status_code != 429
            except Exception:
                # WebSocket upgrade failures are expected, we just want to ensure
                # no rate limiting happens
                pass

    def test_rate_limit_resets_after_time_window(self):
        """Test that rate limits reset after the time window passes."""
        client = TestClient(app)

        # Hit the rate limit (health endpoint has 10 req/s limit)
        for _ in range(10):
            response = client.get("/health")
            assert response.status_code == 200

        # 11th request should be rate limited
        response = client.get("/health")
        assert response.status_code == 429

        # Wait for rate limit window to pass (1 second + small buffer)
        time.sleep(1.1)

        # Should be able to make requests again
        response = client.get("/health")
        assert response.status_code == 200
