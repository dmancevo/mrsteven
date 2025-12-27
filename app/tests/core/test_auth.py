"""Tests for authentication and token management."""

import time

from fastapi.testclient import TestClient

from core.auth import generate_player_token, verify_player_token


class TestTokenGeneration:
    """Test token generation and verification."""

    def test_generate_and_verify_valid_token(self):
        """Test that a valid token can be generated and verified."""
        secret_key = "test_secret_key_12345"
        game_id = "game123"
        player_id = "player456"

        # Generate token
        token = generate_player_token(game_id, player_id, secret_key)
        assert isinstance(token, str)
        assert "." in token  # Should have payload.signature format

        # Verify token
        token_data = verify_player_token(token, secret_key)
        assert token_data is not None
        assert token_data["game_id"] == game_id
        assert token_data["player_id"] == player_id
        assert "expiry" in token_data

    def test_verify_invalid_token_returns_none(self):
        """Test that an invalid token returns None."""
        secret_key = "test_secret_key_12345"
        invalid_token = "invalid.token.format"

        token_data = verify_player_token(invalid_token, secret_key)
        assert token_data is None

    def test_verify_token_with_wrong_secret_fails(self):
        """Test that a token verified with wrong secret fails."""
        secret_key = "test_secret_key_12345"
        wrong_secret = "wrong_secret_key_12345"
        game_id = "game123"
        player_id = "player456"

        # Generate token with one secret
        token = generate_player_token(game_id, player_id, secret_key)

        # Try to verify with different secret
        token_data = verify_player_token(token, wrong_secret)
        assert token_data is None

    def test_expired_token_fails_verification(self):
        """Test that expired tokens fail verification."""
        import base64
        import hashlib
        import hmac

        secret_key = "test_secret_key_12345"
        game_id = "game123"
        player_id = "player456"

        # Create an expired token (expiry in the past)
        expiry = int(time.time()) - 3600  # 1 hour ago
        payload = f"{game_id}:{player_id}:{expiry}"

        # Generate signature
        signature = hmac.new(
            secret_key.encode(),
            payload.encode(),
            hashlib.sha256,
        ).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

        expired_token = f"{payload}.{signature_b64}"

        # Verify expired token should fail
        token_data = verify_player_token(expired_token, secret_key)
        assert token_data is None


class TestAuthenticationIntegration:
    """Test authentication integration with endpoints."""

    def test_authenticated_endpoint_requires_valid_token(self):
        """Test that authenticated endpoints require a valid token."""
        import secrets

        from app import app

        # Initialize secret key for testing (TestClient doesn't run lifespan)
        app.state.secret_key = secrets.token_hex(32)

        client = TestClient(app)

        # Create a game
        create_response = client.post("/api/games/create")
        assert create_response.status_code == 200
        game_id = create_response.json()["game_id"]

        # Join the game (this sets the auth cookie)
        join_response = client.post(
            f"/api/games/{game_id}/join",
            data={"nickname": "TestPlayer"},
        )
        assert join_response.status_code == 200
        player_id = join_response.json()["player_id"]

        # Access lobby with valid token (cookie set by join_game)
        lobby_response = client.get(f"/game/{game_id}/lobby?player_id={player_id}")
        assert lobby_response.status_code == 200

        # Try to access with different player_id (no cookie for that player)
        other_player_response = client.get(f"/game/{game_id}/lobby?player_id=different_player")
        assert other_player_response.status_code == 401  # No cookie for this player_id

        # Create new client without cookies (no token)
        client_no_auth = TestClient(app)
        no_auth_response = client_no_auth.get(f"/game/{game_id}/lobby?player_id={player_id}")
        assert no_auth_response.status_code == 401
