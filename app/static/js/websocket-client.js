/**
 * Native WebSocket client for game state updates
 * Handles connection management, auto-reconnection, and state updates
 */

class GameWebSocket {
    constructor(gameId, playerId) {
        this.gameId = gameId;
        this.playerId = playerId;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000; // Start with 1 second
        this.isConnecting = false;
        this.previousState = null; // Track previous state to detect transitions

        console.log(`🎮 Initializing WebSocket for game ${gameId}, player ${playerId}`);
        this.connect();
    }

    connect() {
        if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
            console.log('Already connected or connecting');
            return;
        }

        this.isConnecting = true;

        // Determine WebSocket protocol (ws:// or wss://)
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${this.gameId}/${this.playerId}`;

        console.log(`🔌 Connecting to WebSocket: ${wsUrl}`);
        this.showConnectionStatus('connecting');

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = (event) => {
                console.log('✅ WebSocket connected successfully');
                this.reconnectAttempts = 0;
                this.reconnectDelay = 1000;
                this.isConnecting = false;
                this.showConnectionStatus('connected');

                // Start heartbeat
                this.startHeartbeat();
            };

            this.ws.onmessage = (event) => {
                // Skip logging for timer updates to reduce console noise
                if (!event.data.includes('timer_update')) {
                    console.log('📨 WebSocket message received:', event.data);
                }

                try {
                    const message = JSON.parse(event.data);

                    if (message.type === 'state_update') {
                        console.log('📦 Parsed state update:', message);
                        this.handleStateUpdate(message.data);
                    }
                } catch (error) {
                    console.error('❌ Error parsing WebSocket message:', error);
                }
            };

            this.ws.onerror = (error) => {
                console.error('❌ WebSocket error:', error);
                this.showConnectionStatus('error');
            };

            this.ws.onclose = (event) => {
                console.log(`🔌 WebSocket closed. Code: ${event.code}, Reason: ${event.reason}`);
                this.isConnecting = false;
                this.stopHeartbeat();
                this.showConnectionStatus('disconnected');

                // Attempt to reconnect
                this.attemptReconnect();
            };

        } catch (error) {
            console.error('❌ Error creating WebSocket:', error);
            this.isConnecting = false;
            this.attemptReconnect();
        }
    }

    startHeartbeat() {
        // Send ping every 25 seconds to keep connection alive
        this.heartbeatInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                console.log('💓 Sending heartbeat ping');
                this.ws.send('ping');
            }
        }, 25000);
    }

    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('❌ Max reconnection attempts reached');
            this.showConnectionStatus('failed');
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1), 30000);

        console.log(`🔄 Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        this.showConnectionStatus('reconnecting');

        setTimeout(() => {
            this.connect();
        }, delay);
    }

    handleStateUpdate(state) {
        console.log('🎮 Handling state update:', state);

        // Update player count if element exists
        const playerCountEl = document.getElementById('player-count');
        if (playerCountEl) {
            playerCountEl.textContent = state.player_count;
        }

        // Update alive count if element exists
        const aliveCountEl = document.getElementById('alive-count');
        if (aliveCountEl) {
            aliveCountEl.textContent = `${state.alive_count} alive`;
        }

        // Update player list if function exists
        if (typeof updatePlayerList === 'function' && state.players) {
            updatePlayerList(state.players);
        }

        // Update players grid if function exists
        if (typeof updatePlayersGrid === 'function' && state.players) {
            updatePlayersGrid(state.players, state.player_order);
        }

        // Update status bar if function exists
        if (typeof updateStatusBar === 'function' && state.state) {
            updateStatusBar(state.state);
        }

        // Update start button if function exists (lobby page)
        if (typeof updateStartButton === 'function' && state.can_start !== undefined) {
            updateStartButton(state.can_start);
        }

        // Show elimination notification if present
        const eliminationNotification = document.getElementById('elimination-notification');
        const eliminationText = document.getElementById('elimination-text');
        if (eliminationNotification && eliminationText && state.last_elimination) {
            const elim = state.last_elimination;
            const roleEmoji = elim.eliminated_role === 'dragon' ? '🐉' :
                             elim.eliminated_role === 'knight' ? '⚔️' : '🏘️';
            const roleClass = elim.eliminated_role === 'dragon' ? 'text-error' :
                             elim.eliminated_role === 'knight' ? 'text-secondary' : 'text-success';

            eliminationText.innerHTML = `
                <strong>${elim.eliminated_nickname}</strong> was eliminated!
                They were a <span class="${roleClass} font-bold">${roleEmoji} ${elim.eliminated_role.toUpperCase()}</span>
                ${elim.was_tie ? ' (decided by tie-breaker)' : ''}
            `;
            eliminationNotification.style.display = 'flex';
        } else if (eliminationNotification && !state.last_elimination) {
            // Hide notification if no elimination data
            eliminationNotification.style.display = 'none';
        }

        // Show/hide voting area and spectator message based on player state
        const votingArea = document.getElementById('voting-area');
        const spectatorMessage = document.getElementById('spectator-message');
        const voteButtons = document.getElementById('vote-buttons');
        const voteStatus = document.getElementById('vote-status');

        // Handle dragon guess state
        const guessArea = document.getElementById('guess-area');
        const dragonGuessingMessage = document.getElementById('dragon-guessing-message');

        if (state.state === 'dragon_guess') {
            // Hide voting and spectator areas
            if (votingArea) votingArea.style.display = 'none';

            if (state.your_role === 'dragon') {
                // Dragon sees the guess form
                if (guessArea) guessArea.style.display = 'block';
                if (spectatorMessage) spectatorMessage.style.display = 'none';
                if (dragonGuessingMessage) dragonGuessingMessage.style.display = 'none';
            } else {
                // Other players see waiting message
                if (guessArea) guessArea.style.display = 'none';
                if (dragonGuessingMessage) dragonGuessingMessage.style.display = 'block';
                if (spectatorMessage) spectatorMessage.style.display = 'none';
            }
        } else {
            // Not in dragon guess state - hide dragon guess elements
            if (guessArea) guessArea.style.display = 'none';
            if (dragonGuessingMessage) dragonGuessingMessage.style.display = 'none';
        }

        // Update voting UI based on player alive status and game state
        if (state.state === 'voting') {
            if (state.is_alive) {
                // Alive player - show voting area
                if (votingArea) votingArea.style.display = 'block';
                if (spectatorMessage) spectatorMessage.style.display = 'none';

                // Only update vote buttons when transitioning to voting (not on every timer tick)
                const isTransitionToVoting = !this.previousState || this.previousState !== 'voting';
                if (isTransitionToVoting && typeof updateVoteButtons === 'function' && state.players) {
                    updateVoteButtons(state.players, state.game_id, state.your_id);
                }

                // Handle vote status
                if (state.has_voted) {
                    if (voteButtons) voteButtons.style.display = 'none';
                    if (voteStatus) voteStatus.style.display = 'block';
                } else {
                    if (voteButtons) voteButtons.style.display = 'block';
                    if (voteStatus) voteStatus.style.display = 'none';
                }
            } else {
                // Dead player - show spectator message
                if (votingArea) votingArea.style.display = 'none';
                if (spectatorMessage) spectatorMessage.style.display = 'block';

                // Update spectator status
                const spectatorStatus = document.getElementById('spectator-status');
                if (spectatorStatus) {
                    spectatorStatus.textContent = `Voting in progress... ${state.votes_submitted} of ${state.alive_count} players have voted`;
                }
            }
        } else {
            // Not in voting state - hide both
            if (votingArea) votingArea.style.display = 'none';
            if (spectatorMessage && state.is_alive) spectatorMessage.style.display = 'none';

            // Update spectator message for eliminated players during discussion
            if (spectatorMessage && !state.is_alive && state.state === 'playing') {
                spectatorMessage.style.display = 'block';
                const spectatorStatus = document.getElementById('spectator-status');
                if (spectatorStatus) {
                    spectatorStatus.textContent = 'Players are discussing... waiting for voting to start';
                }
            }
        }

        // Handle state transitions with redirects
        if (state.state === 'playing' && window.location.pathname.includes('/lobby')) {
            console.log('🎮 Game started! Redirecting to game page...');
            window.location.href = `/game/${state.game_id}/play?player_id=${state.your_id}`;
        } else if (state.state === 'finished' && !window.location.pathname.includes('/results')) {
            console.log('🏁 Game finished! Redirecting to results page...');
            window.location.href = `/game/${state.game_id}/results?player_id=${state.your_id}`;
        }

        // Save current state for next update (to detect transitions)
        this.previousState = state.state;
    }

    showConnectionStatus(status) {
        const statusDiv = document.getElementById('ws-status');
        if (!statusDiv) return;

        statusDiv.classList.remove('hidden', 'badge-success', 'badge-error', 'badge-warning', 'badge-info');

        if (status === 'connected') {
            statusDiv.classList.add('badge-success');
            statusDiv.textContent = '● Connected';
        } else if (status === 'disconnected' || status === 'failed') {
            statusDiv.classList.add('badge-error');
            statusDiv.textContent = '● Disconnected';
        } else if (status === 'reconnecting') {
            statusDiv.classList.add('badge-warning');
            statusDiv.textContent = '● Reconnecting...';
        } else if (status === 'connecting') {
            statusDiv.classList.add('badge-info');
            statusDiv.textContent = '● Connecting...';
        }
    }

    disconnect() {
        console.log('🔌 Manually disconnecting WebSocket');
        this.stopHeartbeat();
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// Add connection status indicator to navbar
function addConnectionStatus() {
    const navbar = document.querySelector('.navbar .flex-none');
    if (!navbar || document.getElementById('ws-status')) return;

    const statusDiv = document.createElement('div');
    statusDiv.id = 'ws-status';
    statusDiv.className = 'badge badge-sm mr-2 hidden';
    navbar.prepend(statusDiv);
}

// Initialize connection status indicator on page load
document.addEventListener('DOMContentLoaded', function() {
    addConnectionStatus();
});

// Global variable to store WebSocket instance
window.gameWebSocket = null;

// Function to initialize WebSocket (called from templates)
function initGameWebSocket(gameId, playerId) {
    console.log('🚀 Initializing game WebSocket');

    // Close existing connection if any
    if (window.gameWebSocket) {
        window.gameWebSocket.disconnect();
    }

    // Create new connection
    window.gameWebSocket = new GameWebSocket(gameId, playerId);
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (window.gameWebSocket) {
        window.gameWebSocket.disconnect();
    }
});
