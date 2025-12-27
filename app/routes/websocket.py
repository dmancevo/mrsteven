"""WebSocket routes for real-time game updates."""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.auth import get_secret_key, verify_player_token
from core.game_manager import game_manager

router = APIRouter()


@router.websocket("/ws/{game_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_id: str):
    """WebSocket endpoint for real-time game updates.

    Args:
        websocket: The WebSocket connection
        game_id: The game session ID
        player_id: The player's ID

    Flow:
        1. Validate game and player
        2. Accept WebSocket connection
        3. Register connection in game session
        4. Send initial state to player
        5. Keep connection alive with ping/pong
        6. Remove connection on disconnect
    """
    print(f"🔌 WebSocket connection attempt: game={game_id}, player={player_id}")

    # Authenticate player via cookie (use player-specific cookie name)
    cookie_name = f"player_token_{player_id}"
    player_token = websocket.cookies.get(cookie_name)
    secret_key = get_secret_key()
    token_data = verify_player_token(player_token, secret_key)

    if not token_data:
        print(f"❌ Invalid or expired token for player: {player_id}")
        await websocket.close(code=1008, reason="Invalid or expired authentication token")
        return

    if token_data["game_id"] != game_id or token_data["player_id"] != player_id:
        print(f"❌ Token mismatch for player: {player_id}")
        await websocket.close(code=1008, reason="Authentication token does not match player")
        return

    game = game_manager.get_game(game_id)

    # Validate game exists and player is in game
    if not game:
        print(f"❌ Game not found: {game_id}")
        await websocket.close(code=4004, reason="Game not found")
        return

    if player_id not in game.players:
        print(f"❌ Player not in game: {player_id}")
        await websocket.close(code=4004, reason="Player not in game")
        return

    # Accept connection
    await websocket.accept()
    print(f"✅ WebSocket connected: {player_id} in game {game_id}")

    # Register WebSocket connection
    game.connections[player_id] = websocket
    print(f"📊 Active connections in game {game_id}: {len(game.connections)}")

    try:
        # Send initial state to player
        initial_state = game.get_state_for_player(player_id)
        message = json.dumps({"type": "state_update", "data": initial_state})
        await websocket.send_text(message)
        print(f"📤 Sent initial state to {player_id}")

        # Keep connection alive and handle messages
        while True:
            try:
                # Receive messages (mainly for keep-alive pings)
                data = await websocket.receive_text()
                print(f"📥 Received from {player_id}: {data}")

                # Handle ping/pong
                if data == "ping":
                    await websocket.send_text("pong")

            except WebSocketDisconnect:
                print(f"🔌 WebSocket disconnected: {player_id}")
                break

    except Exception as e:
        print(f"❌ WebSocket error for player {player_id}: {e}")

    finally:
        # Remove connection when disconnected
        if player_id in game.connections:
            del game.connections[player_id]
            print(f"🗑️ Removed connection for {player_id}")
            print(f"📊 Remaining connections: {len(game.connections)}")
