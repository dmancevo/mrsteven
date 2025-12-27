"""Custom rate limiting middleware using only built-in Python features."""

import time
from collections import defaultdict

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class RateLimiter:
    """Track request rates per IP address using sliding window."""

    def __init__(self):
        """Initialize rate limiter with request tracking."""
        # Dictionary: IP -> list of request timestamps
        self.requests: dict[str, list[float]] = defaultdict(list)
        self.last_cleanup = time.time()
        self.cleanup_interval = 60  # Clean up every 60 seconds

    def is_allowed(self, ip: str, limit: int, window: float = 1.0) -> bool:
        """Check if request is allowed under rate limit.

        Args:
            ip: Client IP address
            limit: Maximum requests allowed in window
            window: Time window in seconds (default: 1.0)

        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        now = time.time()
        cutoff = now - window

        # Clean up old requests for this IP
        self.requests[ip] = [ts for ts in self.requests[ip] if ts > cutoff]

        # Check if under limit
        if len(self.requests[ip]) >= limit:
            return False

        # Record this request
        self.requests[ip].append(now)
        return True

    def cleanup_old_entries(self):
        """Remove stale IP entries to prevent memory leaks."""
        now = time.time()

        # Only run cleanup periodically
        if now - self.last_cleanup < self.cleanup_interval:
            return

        cutoff = now - 60  # Remove IPs with no requests in last 60 seconds

        # Find IPs to remove
        to_remove = [
            ip
            for ip, timestamps in self.requests.items()
            if not timestamps or max(timestamps) < cutoff
        ]

        # Remove stale entries
        for ip in to_remove:
            del self.requests[ip]

        self.last_cleanup = now


def get_rate_limit(path: str) -> int | None:
    """Get rate limit for endpoint.

    Args:
        path: Request path

    Returns:
        Requests per second limit, or None to skip rate limiting
    """
    # No rate limiting for WebSocket connections
    if path.startswith("/ws"):
        return None

    # No rate limiting for static files
    if path.startswith("/static"):
        return None

    # Timer endpoint needs high limit (1 req/sec per player)
    # With max 12 players from same IP: 20 req/s is safe
    if "/timer" in path:
        return 20

    # Health check gets moderate limit
    if path == "/health":
        return 10

    # API endpoints get stricter limit
    if path.startswith("/api"):
        return 5

    # Page views get moderate limit
    if path.startswith("/game/"):
        return 10

    # Default limit for other endpoints
    return 5


# Shared rate limiter instance
_rate_limiter = RateLimiter()


class RateLimitMiddleware:
    """Pure ASGI middleware to enforce rate limits per IP address."""

    def __init__(self, app: ASGIApp):
        """Initialize middleware with rate limiter.

        Args:
            app: ASGI application
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process ASGI request with rate limiting.

        Args:
            scope: ASGI scope dictionary
            receive: ASGI receive callable
            send: ASGI send callable
        """
        # Only apply rate limiting to HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Get client IP from scope
        client_ip = scope.get("client", ["unknown"])[0] if scope.get("client") else "unknown"

        # Get rate limit for this path
        path = scope.get("path", "")
        limit = get_rate_limit(path)

        # Skip rate limiting if no limit configured
        if limit is None:
            await self.app(scope, receive, send)
            return

        # Check rate limit
        if not _rate_limiter.is_allowed(client_ip, limit):
            # Send rate limit exceeded response
            response = JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
            )
            await response(scope, receive, send)
            return

        # Periodic cleanup
        _rate_limiter.cleanup_old_entries()

        # Process request
        await self.app(scope, receive, send)
