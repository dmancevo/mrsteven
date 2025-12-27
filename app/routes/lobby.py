"""Routes for lobby management."""

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from core.game_manager import game_manager
from services.game_state import can_start_game

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/game/{game_id}/lobby")
async def show_lobby(request: Request, game_id: str, player_id: str = Query(...)):
    """Show the lobby page with player list and start button.

    Args:
        request: The FastAPI request object
        game_id: The game session ID
        player_id: The player's ID (from query param)

    Returns:
        Rendered lobby page template

    Raises:
        HTTPException: If game or player not found
    """
    game = game_manager.get_game(game_id)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    player = game.players.get(player_id)

    if not player:
        # Player not in game, redirect to join page
        return RedirectResponse(url=f"/game/{game_id}/join")

    # Build share URL
    share_url = str(request.base_url).rstrip("/") + f"/game/{game_id}/join"

    return templates.TemplateResponse(
        "lobby.html",
        {
            "request": request,
            "game": game,
            "player": player,
            "player_id": player_id,
            "is_host": player.is_host,
            "share_url": share_url,
            "min_players": 3,
        },
    )


@router.post("/api/games/{game_id}/start")
async def start_game(game_id: str, response: Response, player_id: str = Query(...)):
    """Start the game (assign roles and transition to playing).

    Only callable by the host.

    Args:
        game_id: The game session ID
        player_id: The player's ID (must be host)
        response: FastAPI response object

    Returns:
        Success message with redirect header

    Raises:
        HTTPException: If validation fails
    """
    game = game_manager.get_game(game_id)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    player = game.players.get(player_id)

    if not player or not player.is_host:
        raise HTTPException(status_code=403, detail="Only host can start the game")

    can_start, error_msg = can_start_game(game)
    if not can_start:
        raise HTTPException(status_code=400, detail=error_msg)

    # Start the game
    game.start_game()

    # Broadcast state update to all players
    await game.broadcast_state()

    # Redirect to game page
    response.headers["HX-Redirect"] = f"/game/{game_id}/play?player_id={player_id}"

    return {"status": "started", "game_id": game_id}


@router.post("/api/games/{game_id}/set-timer")
async def set_timer(game_id: str, request: Request, player_id: str = Query(...)):
    """Set voting timer for all rounds (host only).

    Args:
        game_id: The game session ID
        request: Request with timer_seconds in JSON body
        player_id: The player's ID (must be host)

    Returns:
        Success message

    Raises:
        HTTPException: If validation fails
    """
    game = game_manager.get_game(game_id)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    player = game.players.get(player_id)

    if not player or not player.is_host:
        raise HTTPException(status_code=403, detail="Only host can set timer")

    body = await request.json()
    timer_seconds = body.get("timer_seconds")

    print(f"⏱️ Setting timer for game {game_id}: {timer_seconds}s")

    try:
        game.set_voting_timer(timer_seconds)
        print(f"⏱️ Timer set successfully: game.voting_timer_seconds = {game.voting_timer_seconds}")
    except ValueError as e:
        print(f"⏱️ Timer validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {"status": "timer_set", "timer_seconds": timer_seconds}
