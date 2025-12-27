"""Routes for active gameplay (voting, guessing, etc.)."""

from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from core.auth import get_token_data, verify_token_matches
from core.game_manager import game_manager
from core.game_session import GameState
from core.roles import Role
from services.game_state import (
    can_start_voting,
    transition_to_finished,
    transition_to_playing,
    transition_to_voting,
)
from services.voting import all_votes_submitted, can_vote
from services.win_conditions import check_dragon_eliminated, determine_winner

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/game/{game_id}/play")
async def show_game(
    request: Request,
    game_id: str,
    player_id: str = Query(...),
    token_data: dict[str, Any] = Depends(get_token_data),  # noqa: B008
):
    """Show the active game interface.

    Args:
        request: The FastAPI request object
        game_id: The game session ID
        player_id: The player's ID
        token_data: Authenticated token data (injected)

    Returns:
        Rendered game page template or redirect

    Raises:
        HTTPException: If game or player not found or authentication fails
    """
    # Verify token matches the requested player
    verify_token_matches(token_data, game_id, player_id)

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

    # Determine which word to show based on player's role
    word = None
    if player.knows_word:
        if player.role == Role.KNIGHT.value:
            word = game.knight_word
        else:  # Villager
            word = game.villager_word

    return templates.TemplateResponse(
        request=request,
        name="game.html",
        context={"game": game, "player": player, "player_id": player_id, "word": word},
    )


@router.post("/api/games/{game_id}/start-voting")
async def start_voting(
    game_id: str,
    player_id: str = Query(...),
    token_data: dict[str, Any] = Depends(get_token_data),  # noqa: B008
):
    """Transition game to voting phase.

    Only callable by the host.

    Args:
        game_id: The game session ID
        player_id: The player's ID (must be host)
        token_data: Authenticated token data (injected)

    Returns:
        Success message

    Raises:
        HTTPException: If validation fails or authentication fails
    """
    # Verify token matches the requested player
    verify_token_matches(token_data, game_id, player_id)

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

    # Set voting start timestamp if timer configured
    if game.voting_timer_seconds is not None:
        from datetime import datetime

        game.voting_started_at = datetime.now()
        print(f"⏱️ Starting timer: {game.voting_timer_seconds}s at {game.voting_started_at}")
    else:
        print("⏱️ No timer configured (voting_timer_seconds is None)")

    # Broadcast state update
    await game.broadcast_state()

    return {"status": "voting_started", "timer_seconds": game.voting_timer_seconds}


@router.get("/api/games/{game_id}/timer")
async def get_timer(request: Request, game_id: str, player_id: str = Query(...)):
    """Get voting timer HTML (polled by HTMX every second).

    Note: No authentication required for performance (high-frequency polling).
    Rate limited to 20 req/s and validates player exists/is alive.

    Args:
        request: The FastAPI request object
        game_id: The game session ID
        player_id: The player's ID

    Returns:
        Rendered timer HTML snippet
    """
    game = game_manager.get_game(game_id)

    if not game:
        # Return empty div if game not found
        return templates.TemplateResponse(
            request=request,
            name="partials/timer.html",
            context={
                "show_timer": False,
                "expired": False,
                "game_id": game_id,
                "player_id": player_id,
            },
        )

    player = game.players.get(player_id)
    if not player or not player.is_alive:
        # Dead players don't see timer
        return templates.TemplateResponse(
            request=request,
            name="partials/timer.html",
            context={
                "show_timer": False,
                "expired": False,
                "game_id": game_id,
                "player_id": player_id,
            },
        )

    # Check if in voting state with timer
    if game.state != GameState.VOTING or not game.voting_timer_seconds:
        return templates.TemplateResponse(
            request=request,
            name="partials/timer.html",
            context={
                "show_timer": False,
                "expired": False,
                "game_id": game_id,
                "player_id": player_id,
            },
        )

    # Calculate time remaining
    time_remaining = game.get_voting_time_remaining()

    # Check if timer expired
    if time_remaining == 0:
        # End voting without elimination
        print("⏱️ Voting timer expired!")
        transition_to_playing(game)
        await game.broadcast_state()

        return templates.TemplateResponse(
            request=request,
            name="partials/timer.html",
            context={
                "show_timer": False,
                "expired": True,
                "game_id": game_id,
                "player_id": player_id,
            },
        )

    # Show countdown (time_remaining is guaranteed to be > 0 here)
    assert time_remaining is not None and time_remaining > 0
    minutes = time_remaining // 60
    seconds = time_remaining % 60

    return templates.TemplateResponse(
        request=request,
        name="partials/timer.html",
        context={
            "show_timer": True,
            "expired": False,
            "time_remaining": time_remaining,
            "minutes": minutes,
            "seconds": f"{seconds:02d}",  # Zero-pad seconds
            "game_id": game_id,
            "player_id": player_id,
        },
    )


@router.post("/api/games/{game_id}/vote")
async def submit_vote(
    game_id: str,
    response: Response,
    target_id: str = Form(...),
    player_id: str = Query(...),
    token_data: dict[str, Any] = Depends(get_token_data),  # noqa: B008
):
    """Submit a vote for player elimination.

    Args:
        game_id: The game session ID
        vote: The vote request with target player ID
        player_id: The voting player's ID
        token_data: Authenticated token data (injected)

    Returns:
        Vote status or game result

    Raises:
        HTTPException: If validation fails or authentication fails
    """
    # Verify token matches the requested player
    verify_token_matches(token_data, game_id, player_id)

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
        raise HTTPException(status_code=400, detail=str(e)) from e

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
            "game_state": game.state.value,
        }

    # Vote submitted, waiting for others
    await game.broadcast_state()

    alive_count = sum(1 for p in game.players.values() if p.is_alive)
    return {
        "status": "vote_submitted",
        "votes_submitted": len(game.votes),
        "total_players": alive_count,
    }


@router.post("/api/games/{game_id}/guess-word")
async def guess_word(
    game_id: str,
    response: Response,
    guess: str = Form(...),
    player_id: str = Query(...),
    token_data: dict[str, Any] = Depends(get_token_data),  # noqa: B008
):
    """Dragon attempts to guess the secret word after elimination.

    Args:
        game_id: The game session ID
        guess: The word guess from form data
        player_id: The player's ID (must be dragon)
        response: FastAPI response object
        token_data: Authenticated token data (injected)

    Returns:
        Guess result and winner

    Raises:
        HTTPException: If validation fails or authentication fails
    """
    # Verify token matches the requested player
    verify_token_matches(token_data, game_id, player_id)

    game = game_manager.get_game(game_id)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    player = game.players.get(player_id)

    if not player or player.role != Role.DRAGON.value:
        raise HTTPException(status_code=403, detail="Only Dragon can guess the word")

    if game.state != GameState.DRAGON_GUESS:
        raise HTTPException(status_code=400, detail="Not in dragon guess phase")

    if not game.villager_word:
        raise HTTPException(status_code=500, detail="Game state error: word not set")

    # Clean and validate guess
    guess = guess.strip().lower()

    # Validate guess length (word pairs are typically < 20 chars)
    if len(guess) > 50:
        raise HTTPException(status_code=400, detail="Guess too long (max 50 characters)")

    if not guess:
        raise HTTPException(status_code=400, detail="Guess cannot be empty")

    # Check if guess is correct (check against villager word)
    correct = guess == game.villager_word.lower()

    # Set winner
    winner = "dragon" if correct else "villagers"
    game.dragon_guess = guess

    transition_to_finished(game, winner)

    # Broadcast final state
    await game.broadcast_state()

    # Redirect to results page
    response.headers["HX-Redirect"] = f"/game/{game_id}/results?player_id={player_id}"

    return {"correct": correct, "winner": winner}


@router.get("/game/{game_id}/results")
async def show_results(
    request: Request,
    game_id: str,
    player_id: str = Query(...),
    token_data: dict[str, Any] = Depends(get_token_data),  # noqa: B008
):
    """Show the game results page.

    Args:
        request: The FastAPI request object
        game_id: The game session ID
        player_id: The player's ID
        token_data: Authenticated token data (injected)

    Returns:
        Rendered results page template

    Raises:
        HTTPException: If game or player not found or authentication fails
    """
    # Verify token matches the requested player
    verify_token_matches(token_data, game_id, player_id)

    game = game_manager.get_game(game_id)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    player = game.players.get(player_id)

    if not player:
        raise HTTPException(status_code=403, detail="Not in this game")

    return templates.TemplateResponse(
        request=request,
        name="results.html",
        context={
            "game": game,
            "player": player,
            "player_id": player_id,
            "winner": game.winner,
            "villager_word": game.villager_word,
            "knight_word": game.knight_word,
            "dragon_guess": game.dragon_guess,
        },
    )
