"""Main FastAPI application for Dragonseeker game."""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from routes import game, lobby, gameplay, websocket
from core.game_manager import game_manager

# Initialize FastAPI app
app = FastAPI(
    title="Dragonseeker",
    description="A social deduction party game",
    version="1.0.0"
)

# Configure CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure templates
templates = Jinja2Templates(directory="templates")

# Include routers
app.include_router(game.router, tags=["game"])
app.include_router(lobby.router, tags=["lobby"])
app.include_router(gameplay.router, tags=["gameplay"])
app.include_router(websocket.router, tags=["websocket"])


@app.get("/")
async def index(request: Request):
    """Landing page - create new game."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    stats = game_manager.get_stats()
    return {
        "status": "healthy",
        "active_games": stats["active_games"],
        "total_players": stats["total_players"]
    }


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    print("🎮 Dragonseeker game server starting...")
    print("🔗 Game manager initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    print("👋 Shutting down game server...")