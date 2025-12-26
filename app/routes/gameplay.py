"""Routes for active gameplay (voting, guessing, etc.)."""
from fastapi import APIRouter, HTTPException, Request, Query, Response, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from core.game_manager import game_manager
from core.game_session import GameState
from core.roles import Role
from models.requests import VoteRequest
from services.voting import can_vote, all_votes_submitted
from services.game_state import can_start_voting, transition_to_voting, transition_to_playing, transition_to_finished
from services.win_conditions import determine_winner, check_dragon_eliminated

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/game/{game_id}/play")
async def show_game(request: Request, game_id: str, player_id: str = Query(...)):
    """Show the active game interface.

    Args:
        request: The FastAPI request object
        game_id: The game session ID
        player_id: The player's ID

    Returns:
        Rendered game page template or redirect

    Raises:
        HTTPException: If game or player not found
    """
    game = game_manager.get_game(game_id)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    player = game.players.get(player_id)

    if not player:
        raise HTTPException(status_code=403, detail="Not in this game")

    # Redirect to lobby if game hasn't started
    if game.state == GameState.LOBBY:
        return RedirectResponse(url=f"/game/{game_id}/lobby?player_id={player_id}")

    # Redirect to results if game is finished
    if game.state == GameState.FINISHED:
        return RedirectResponse(url=f"/game/{game_id}/results?player_id={player_id}")

    return templates.TemplateResponse("game.html", {
        "request": request,
        "game": game,
        "player": player,
        "player_id": player_id,
        "word": game.word if player.knows_word else None
    })


@router.post("/api/games/{game_id}/start-voting")
async def start_voting(game_id: str, player_id: str = Query(...)):
    """Transition game to voting phase.

    Only callable by the host.

    Args:
        game_id: The game session ID
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
        raise HTTPException(status_code=403, detail="Only host can start voting")

    can_vote_now, error_msg = can_start_voting(game)
    if not can_vote_now:
        raise HTTPException(status_code=400, detail=error_msg)

    # Transition to voting
    transition_to_voting(game)

    # Broadcast state update
    await game.broadcast_state()

    return {"status": "voting_started"}


@router.post("/api/games/{game_id}/vote")
async def submit_vote(game_id: str, target_id: str = Form(...), player_id: str = Query(...), response: Response = None):
    """Submit a vote for player elimination.

    Args:
        game_id: The game session ID
        vote: The vote request with target player ID
        player_id: The voting player's ID

    Returns:
        Vote status or game result

    Raises:
        HTTPException: If validation fails
    """
    game = game_manager.get_game(game_id)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Check if player can vote
    can_submit, error_msg = can_vote(game, player_id)
    if not can_submit:
        raise HTTPException(status_code=400, detail=error_msg)

    # Submit the vote
    try:
        game.submit_vote(player_id, target_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Check if all votes are in
    if all_votes_submitted(game):
        # Tally votes
        result = game.tally_votes()

        # Check win condition
        winner = determine_winner(game)

        if check_dragon_eliminated(game):
            # Transition to dragon guess state
            game.state = GameState.DRAGON_GUESS
        elif winner:
            transition_to_finished(game, winner)
            # Redirect to results page when game is finished
            response.headers["HX-Redirect"] = f"/game/{game_id}/results?player_id={player_id}"
        else:
            # Continue playing
            transition_to_playing(game)

        # Broadcast final result
        await game.broadcast_state()

        return {
            "status": "vote_complete",
            "result": result,
            "winner": winner,
            "game_state": game.state.value
        }

    # Vote submitted, waiting for others
    await game.broadcast_state()

    alive_count = sum(1 for p in game.players.values() if p.is_alive)
    return {
        "status": "vote_submitted",
        "votes_submitted": len(game.votes),
        "total_players": alive_count
    }


@router.post("/api/games/{game_id}/guess-word")
async def guess_word(game_id: str, guess: str = Form(...), player_id: str = Query(...), response: Response = None):
    """Dragon attempts to guess the secret word after elimination.

    Args:
        game_id: The game session ID
        guess: The word guess from form data
        player_id: The player's ID (must be dragon)
        response: FastAPI response object

    Returns:
        Guess result and winner

    Raises:
        HTTPException: If validation fails
    """
    game = game_manager.get_game(game_id)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    player = game.players.get(player_id)

    if not player or player.role != Role.DRAGON.value:
        raise HTTPException(status_code=403, detail="Only Dragon can guess the word")

    if game.state != GameState.DRAGON_GUESS:
        raise HTTPException(status_code=400, detail="Not in dragon guess phase")

    # Clean and check if guess is correct
    guess = guess.strip().lower()
    correct = guess == game.word.lower()

    # Set winner
    winner = "dragon" if correct else "villagers"
    game.dragon_guess = guess

    transition_to_finished(game, winner)

    # Broadcast final state
    await game.broadcast_state()

    # Redirect to results page
    response.headers["HX-Redirect"] = f"/game/{game_id}/results?player_id={player_id}"

    return {
        "correct": correct,
        "winner": winner,
        "word": game.word
    }


@router.get("/game/{game_id}/results")
async def show_results(request: Request, game_id: str, player_id: str = Query(...)):
    """Show the game results page.

    Args:
        request: The FastAPI request object
        game_id: The game session ID
        player_id: The player's ID

    Returns:
        Rendered results page template

    Raises:
        HTTPException: If game or player not found
    """
    game = game_manager.get_game(game_id)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    player = game.players.get(player_id)

    if not player:
        raise HTTPException(status_code=403, detail="Not in this game")

    return templates.TemplateResponse("results.html", {
        "request": request,
        "game": game,
        "player": player,
        "player_id": player_id,
        "winner": game.winner,
        "word": game.word,
        "dragon_guess": game.dragon_guess
    })
