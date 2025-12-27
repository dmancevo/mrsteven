"""Tests for voting timer functionality."""

from datetime import datetime, timedelta

import pytest


class TestVotingTimer:
    """Tests for voting timer functionality."""

    def test_set_timer_in_lobby(self, game_with_players):
        """Test that timer can be set in lobby."""
        game, _ = game_with_players
        game.set_voting_timer(60)
        assert game.voting_timer_seconds == 60

    def test_cannot_set_timer_after_start(self, started_game):
        """Test that timer cannot be set after game starts."""
        with pytest.raises(ValueError, match="Can only set timer in lobby"):
            started_game.set_voting_timer(60)

    def test_timer_validation(self, game_with_players):
        """Test timer value validation."""
        game, _ = game_with_players

        # Too low
        with pytest.raises(ValueError, match="between 30 and 180"):
            game.set_voting_timer(20)

        # Too high
        with pytest.raises(ValueError, match="between 30 and 180"):
            game.set_voting_timer(200)

        # None should work
        game.set_voting_timer(None)
        assert game.voting_timer_seconds is None

    def test_get_voting_time_remaining(self, voting_game):
        """Test timestamp-based timer calculation."""
        voting_game.voting_timer_seconds = 60
        voting_game.voting_started_at = datetime.now()

        # Should have close to 60 seconds remaining
        remaining = voting_game.get_voting_time_remaining()
        assert remaining is not None
        assert 59 <= remaining <= 60

    def test_get_voting_time_remaining_expired(self, voting_game):
        """Test that expired timer returns 0."""
        voting_game.voting_timer_seconds = 60
        voting_game.voting_started_at = datetime.now() - timedelta(seconds=65)

        remaining = voting_game.get_voting_time_remaining()
        assert remaining == 0

    def test_get_voting_time_remaining_no_timer(self, voting_game):
        """Test that no timer returns None."""
        voting_game.voting_timer_seconds = None

        remaining = voting_game.get_voting_time_remaining()
        assert remaining is None
