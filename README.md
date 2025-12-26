# 🎮 Villagers, Knights & Dragon

A social deduction party game built with FastAPI, HTMX, Tailwind CSS, and DaisyUI. Inspired by the classic "Mr. White" game, players must work together to identify the Dragon among them!

## 🎯 Game Overview

**Villagers, Knights & Dragon** is a real-time multiplayer social deduction game where players are assigned secret roles:
- **Villagers**: Know the secret word and must identify the Dragon
- **Knights**: Know a similar (but different) word and must identify the Dragon. Knights don't know they are knights - they think they are villagers!
- **Dragon**: Doesn't know the word and must blend in to survive

### How to Play

1. **Create Game**: Host creates a new game and receives a unique shareable link
2. **Invite Players**: Share the link with 2-11 friends (3-12 players total)
3. **Join Lobby**: Players enter their nicknames to join the game
4. **Start Game**: Host starts when everyone has joined
5. **Roles Assigned**: Each player sees their role and word (Dragon sees "???")
6. **Say a Word**: Each player takes turns saying ONE word that is similar to their secret word (but NOT the actual word itself). The Dragon must try to blend in by guessing what the word might be!
7. **Discussion Phase**: Players discuss and analyze the words that were said to figure out who the Dragon is
8. **Voting Phase**: Host initiates voting, everyone votes to eliminate a player
9. **Win Conditions**:
   - **Villagers/Knights win** if they eliminate the Dragon
   - **Dragon wins** if they survive until ≤2 players remain OR correctly guess the word after elimination

## ✨ Features

- 🔗 **Private Game Links** - Each game gets a unique shareable URL
- ⚡ **Real-time Updates** - WebSocket-powered live game state
- ⚖️ **Auto-balanced Roles** - Fair distribution for 3-12 players
- 🗳️ **Voting System** - Democratic elimination with tie-breaker
- 🐉 **Dragon Guess Mechanic** - Last chance redemption
- 📱 **Mobile Responsive** - Works great on all devices
- 🎨 **Modern UI** - Beautiful interface with Tailwind + DaisyUI

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager

### Run Locally

```bash
cd app
uv run fastapi dev app.py
```

Then open your browser to: **http://localhost:8000**

### Production Mode

```bash
cd app
uv run fastapi run app.py
```

## 🏗️ Architecture

### Tech Stack

- **Backend**: FastAPI 0.118.0 + WebSockets 15.0.1
- **Frontend**: HTMX 2.0.4 + Tailwind CSS + DaisyUI 4.12
- **Templates**: Jinja2 3.1.6
- **Deployment**: Docker + Digital Ocean App Platform
- **Package Manager**: uv (Astral)

### Project Structure

```
app/
├── app.py                      # Main FastAPI application
├── core/                       # Game logic
│   ├── constants.py           # Game settings & word list
│   ├── player.py              # Player model
│   ├── roles.py               # Role assignment
│   ├── game_session.py        # Game state machine
│   └── game_manager.py        # Multi-game coordinator
├── routes/                     # API endpoints
│   ├── game.py                # Create/join game
│   ├── lobby.py               # Lobby management
│   ├── gameplay.py            # Voting & gameplay
│   └── websocket.py           # WebSocket handler
├── models/                     # Pydantic models
│   ├── requests.py            # Request DTOs
│   └── responses.py           # Response DTOs
├── services/                   # Business logic
│   ├── voting.py              # Vote tallying
│   ├── win_conditions.py      # Win detection
│   └── game_state.py          # State transitions
├── static/                     # Frontend assets
│   ├── css/custom.css         # Custom styles
│   ├── js/websocket-client.js # WebSocket manager
│   └── js/htmx-config.js      # HTMX setup
└── templates/                  # Jinja2 HTML
    ├── base.html              # Base template
    ├── index.html             # Landing page
    ├── join.html              # Join page
    ├── lobby.html             # Game lobby
    ├── game.html              # Active game
    └── results.html           # Game over
```

### Game State Machine

```
LOBBY → (host starts) → PLAYING → (host votes) → VOTING
  → (all voted) → DRAGON_GUESS or FINISHED
  → (check win) → FINISHED or PLAYING
```

### Role Distribution

| Players | Dragon | Knights | Villagers |
|---------|--------|---------|-----------|
| 3-4     | 1      | 0       | 2-3       |
| 5-6     | 1      | 1       | 3-4       |
| 7-8     | 1      | 2       | 4-5       |
| 9-10    | 1      | 3       | 5-6       |
| 11-12   | 1      | 4       | 6-7       |

## 🎮 API Endpoints

### Game Management
- `GET /` - Landing page
- `POST /api/games/create` - Create new game
- `GET /game/{game_id}/join` - Join page
- `POST /api/games/{game_id}/join` - Join game

### Lobby
- `GET /game/{game_id}/lobby` - Lobby page
- `POST /api/games/{game_id}/start` - Start game (host only)

### Gameplay
- `GET /game/{game_id}/play` - Game interface
- `POST /api/games/{game_id}/start-voting` - Start voting phase
- `POST /api/games/{game_id}/vote` - Submit vote
- `POST /api/games/{game_id}/guess-word` - Dragon word guess
- `GET /game/{game_id}/results` - Results page

### WebSocket
- `WS /ws/{game_id}/{player_id}` - Real-time game updates

### Health
- `GET /health` - Health check endpoint

## 🚢 Deployment

### Docker

The project includes a Dockerfile for containerized deployment:

```bash
docker build -t villagers-knights-dragon .
docker run -p 8000:8000 villagers-knights-dragon
```

### Digital Ocean App Platform

The app is configured for automatic deployment:
1. Push to your GitHub repository
2. Digital Ocean auto-deploys on push to `main` branch
3. Configuration in `.do/app.yaml`

## 🧪 Testing

Run the built-in tests:

```bash
cd app
uv run python -c "
from core.game_manager import game_manager
game = game_manager.create_game()
game.add_player('Alice')
game.add_player('Bob')
game.add_player('Charlie')
game.start_game()
print(f'Game started! Word: {game.word}')
for p in game.players.values():
    print(f'{p.nickname}: {p.role}')
"
```

## 🎨 Customization

### Adding Custom Words

Edit `app/core/constants.py` to add or modify the word list:

```python
WORD_LIST = [
    "elephant", "giraffe", "telescope",
    # Add your words here...
]
```

### Changing Game Settings

Modify `app/core/constants.py`:

```python
MIN_PLAYERS = 3          # Minimum players to start
MAX_PLAYERS = 12         # Maximum players allowed
GAME_TTL_SECONDS = 3600  # Game cleanup time (1 hour)
```

## 🎯 Future Enhancements

Potential features to add:
- ⏱️ Discussion timer with countdown
- 💬 In-game text chat for remote play
- 📊 Game history and statistics
- 📚 Custom word lists by category
- 👀 Spectator mode
- 🔊 Sound effects and animations
- 📱 Progressive Web App (PWA) for mobile
- 🌐 Multi-language support
- 🎭 Custom role abilities (e.g., Knights get hints)

## 📝 License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0). See [LICENSE.md](LICENSE.md) for details.

The AGPL-3.0 is a strong copyleft license that requires anyone who runs a modified version of this software as a network service to make the source code available to users of that service.

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest new features
- Submit pull requests

## 🎮 Play Now!

Start the server and visit http://localhost:8000 to begin playing!

```bash
cd app
uv run fastapi dev app.py
```

Enjoy the game! 🐉⚔️🏘️
