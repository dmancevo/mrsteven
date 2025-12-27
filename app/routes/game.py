"""Routes for game creation and joining."""

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.templating import Jinja2Templates

from core.auth import generate_player_token, get_secret_key
from core.game_manager import game_manager

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.post("/api/games/create")
async def create_game(response: Response):
    """Create a new game session.

    Returns:
        Redirect to the join page for the new game
    """
    game = game_manager.create_game()

    # Use HTMX's HX-Redirect header for client-side redirect
    response.headers["HX-Redirect"] = f"/game/{game.game_id}/join"

    return {"status": "created", "game_id": game.game_id}


@router.get("/game/{game_id}/join")
async def show_join_page(request: Request, game_id: str):
    """Show the join page where players enter their nickname.

    Args:
        request: The FastAPI request object
        game_id: The game session ID

    Returns:
        Rendered join page template

    Raises:
        HTTPException: If game not found
    """
    game = game_manager.get_game(game_id)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.state.value != "lobby":
        raise HTTPException(status_code=400, detail="Game has already started")

    return templates.TemplateResponse(
        request=request, name="join.html", context={"game_id": game_id}
    )


@router.post("/api/games/{game_id}/join")
async def join_game(game_id: str, response: Response, nickname: str = Form(...)):
    """Add a player to the game session.

    Args:
        game_id: The game session ID
        nickname: Player's nickname from form data
        response: FastAPI response object

    Returns:
        Success message with redirect header

    Raises:
        HTTPException: If game not found or cannot join
    """
    game = game_manager.get_game(game_id)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.state.value != "lobby":
        raise HTTPException(status_code=400, detail="Game has already started")

    # Validate nickname
    nickname = nickname.strip()
    if not nickname or len(nickname) > 20:
        raise HTTPException(status_code=400, detail="Invalid nickname")

    # Check for duplicate nicknames
    if any(p.nickname.lower() == nickname.lower() for p in game.players.values()):
        raise HTTPException(status_code=400, detail="Nickname already taken")

    # Add player
    player = game.add_player(nickname)

    # Generate authentication token
    secret_key = get_secret_key()
    token = generate_player_token(game_id, player.id, secret_key)

    # Set authentication cookie (HTTP-only for security)
    # Use player_id in cookie name to avoid collision when testing multiple players in same browser
    response.set_cookie(
        key=f"player_token_{player.id}",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,  # 24 hours
    )

    # Broadcast update to all connected players
    await game.broadcast_state()

    # Use HTMX's HX-Redirect header for client-side redirect
    response.headers["HX-Redirect"] = f"/game/{game_id}/lobby?player_id={player.id}"

    return {"status": "joined", "player_id": player.id}
