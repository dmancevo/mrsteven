"""Authentication and token management for player sessions."""

import base64
import hashlib
import hmac
import time
from typing import Any

from fastapi import HTTPException, Request


def generate_player_token(game_id: str, player_id: str, secret_key: str) -> str:
    """Generate a signed token for player authentication.

    Args:
        game_id: The game session ID
        player_id: The player's unique ID
        secret_key: Secret key for signing

    Returns:
        Signed token string
    """
    # Create payload with expiry (24 hours from now)
    expiry = int(time.time()) + 86400  # 24 hours
    payload = f"{game_id}:{player_id}:{expiry}"

    # Generate HMAC signature
    signature = hmac.new(
        secret_key.encode(),
        payload.encode(),
        hashlib.sha256,
    ).digest()

    # Encode signature as base64
    signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

    # Return token as payload.signature
    return f"{payload}.{signature_b64}"


def verify_player_token(token: str | None, secret_key: str) -> dict[str, Any] | None:
    """Verify a player token and extract its data.

    Args:
        token: The token to verify
        secret_key: Secret key used for signing

    Returns:
        Dictionary with game_id, player_id, and expiry if valid, None otherwise
    """
    if not token:
        return None

    try:
        # Split token into payload and signature
        parts = token.split(".")
        if len(parts) != 2:
            return None

        payload, signature_b64 = parts

        # Parse payload
        payload_parts = payload.split(":")
        if len(payload_parts) != 3:
            return None

        game_id, player_id, expiry_str = payload_parts

        # Check expiry
        expiry = int(expiry_str)
        if time.time() > expiry:
            return None

        # Verify signature
        expected_signature = hmac.new(
            secret_key.encode(),
            payload.encode(),
            hashlib.sha256,
        ).digest()

        # Decode provided signature (add padding if needed)
        padding = "=" * (4 - len(signature_b64) % 4)
        provided_signature = base64.urlsafe_b64decode(signature_b64 + padding)

        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(expected_signature, provided_signature):
            return None

        return {
            "game_id": game_id,
            "player_id": player_id,
            "expiry": expiry,
        }

    except (ValueError, KeyError):
        return None


def get_secret_key() -> str:
    """Get the secret key from app state.

    Returns:
        Secret key string

    Raises:
        RuntimeError: If secret key is not initialized
    """
    from app import app

    if not hasattr(app.state, "secret_key"):
        raise RuntimeError("Secret key not initialized")

    return app.state.secret_key


def get_token_data(request: Request) -> dict[str, Any]:
    """Extract and validate player token from cookie.

    Args:
        request: FastAPI request object containing cookies and query parameters

    Returns:
        Token data dictionary with game_id, player_id, expiry

    Raises:
        HTTPException: If token is invalid or expired
    """
    # Extract player_id from query parameters
    player_id = request.query_params.get("player_id")
    if not player_id:
        raise HTTPException(status_code=400, detail="Missing player_id parameter")

    # Get token from player-specific cookie
    cookie_name = f"player_token_{player_id}"
    player_token = request.cookies.get(cookie_name)

    secret_key = get_secret_key()
    token_data = verify_player_token(player_token, secret_key)

    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token")

    return token_data


def verify_token_matches(token_data: dict[str, Any], game_id: str, player_id: str) -> None:
    """Verify that token data matches expected game and player.

    Args:
        token_data: Token data from get_token_data
        game_id: Expected game ID
        player_id: Expected player ID

    Raises:
        HTTPException: If token doesn't match expected values
    """
    if token_data["game_id"] != game_id or token_data["player_id"] != player_id:
        raise HTTPException(status_code=403, detail="Authentication token does not match player")
