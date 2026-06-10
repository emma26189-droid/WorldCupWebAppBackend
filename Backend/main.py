import asyncio
import random

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()
DRAW_INTERVAL_SECONDS = 10

# Allow frontend calls (important!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Player(BaseModel):
    name: str
    email: str = ""


class AddPlayerRequest(BaseModel):
    name: str
    email: str = ""


class ReplacePlayersRequest(BaseModel):
    players: list[Player]


class AssignmentRequest(BaseModel):
    team: str
    player: str


class DrawRequest(BaseModel):
    teams: list[str]


class DrawState:
    def __init__(self):
        self.players: list[Player] = []
        self.assignments: dict[str, str] = {}
        self.current_draw_pair: dict[str, str] = {"player": "", "team": ""}
        self.is_drawing: bool = False


draw_state = DrawState()
active_connections: list[WebSocket] = []
draw_task: asyncio.Task | None = None


def serialize_state() -> dict:
    return {
        "players": [player.model_dump() for player in draw_state.players],
        "assignments": draw_state.assignments,
        "currentDrawPair": draw_state.current_draw_pair,
        "isDrawing": draw_state.is_drawing,
    }


async def broadcast_state():
    if not active_connections:
        return

    payload = {"type": "state", "payload": serialize_state()}
    stale_connections: list[WebSocket] = []

    for connection in active_connections:
        try:
            await connection.send_json(payload)
        except Exception:
            stale_connections.append(connection)

    for connection in stale_connections:
        if connection in active_connections:
            active_connections.remove(connection)


def remaining_draw_items(teams: list[str]) -> tuple[list[str], list[Player]]:
    assigned_teams = set(draw_state.assignments.keys())
    assigned_players = set(draw_state.assignments.values())

    remaining_teams = [team for team in teams if team not in assigned_teams]
    remaining_players = [player for player in draw_state.players if player.name not in assigned_players]
    return remaining_teams, remaining_players


async def run_draw_sequence(teams: list[str]):
    try:
        while draw_state.is_drawing:
            remaining_teams, remaining_players = remaining_draw_items(teams)

            if len(draw_state.players) > len(teams):
                break

            if not remaining_teams or not remaining_players:
                break

            team = random.choice(remaining_teams)
            player = random.choice(remaining_players)

            draw_state.assignments[team] = player.name
            draw_state.current_draw_pair = {"player": player.name, "team": team}
            await broadcast_state()

            if len(draw_state.assignments) >= len(teams):
                break

            await asyncio.sleep(DRAW_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        raise
    finally:
        draw_state.is_drawing = False
        await broadcast_state()


# --- Basic test route ---
@app.get("/")
def home():
    return {"message": "Sweepstake API is running ✅"}


@app.get("/state")
def get_state():
    return serialize_state()


@app.post("/players")
async def add_player(data: AddPlayerRequest):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Player name is required")

    draw_state.players.append(Player(name=name, email=data.email.strip()))
    await broadcast_state()
    return serialize_state()


@app.post("/players/replace")
async def replace_players(data: ReplacePlayersRequest):
    normalized_players = [
        Player(name=player.name.strip(), email=player.email.strip())
        for player in data.players
        if player.name.strip()
    ]

    draw_state.players = normalized_players
    draw_state.assignments = {}
    draw_state.current_draw_pair = {"player": "", "team": ""}
    await broadcast_state()
    return serialize_state()


@app.post("/assignments")
async def update_assignment(data: AssignmentRequest):
    team = data.team.strip()
    player = data.player.strip()
    if not team:
        raise HTTPException(status_code=400, detail="Team is required")

    if player:
        draw_state.assignments[team] = player
    elif team in draw_state.assignments:
        del draw_state.assignments[team]

    await broadcast_state()
    return serialize_state()


@app.post("/draw")
async def draw_next_pair(data: DrawRequest):
    if draw_state.is_drawing:
        raise HTTPException(status_code=409, detail="Draw is currently running")

    teams = [team.strip() for team in data.teams if team.strip()]
    if not teams:
        raise HTTPException(status_code=400, detail="Teams list cannot be empty")

    remaining_teams, remaining_players = remaining_draw_items(teams)

    if len(draw_state.players) > len(teams):
        raise HTTPException(status_code=400, detail="Not enough teams for all players")

    if not remaining_teams or not remaining_players:
        raise HTTPException(status_code=400, detail="No remaining teams or players for draw")

    team = random.choice(remaining_teams)
    player = random.choice(remaining_players)

    draw_state.assignments[team] = player.name
    draw_state.current_draw_pair = {"player": player.name, "team": team}

    await broadcast_state()
    return serialize_state()


@app.post("/draw/start")
async def start_draw_sequence(data: DrawRequest):
    global draw_task

    if draw_state.is_drawing:
        raise HTTPException(status_code=409, detail="Draw is already running")

    teams = [team.strip() for team in data.teams if team.strip()]
    if not teams:
        raise HTTPException(status_code=400, detail="Teams list cannot be empty")

    if len(draw_state.players) > len(teams):
        raise HTTPException(status_code=400, detail="Not enough teams for all players")

    remaining_teams, remaining_players = remaining_draw_items(teams)
    if not remaining_teams or not remaining_players:
        raise HTTPException(status_code=400, detail="No remaining teams or players for draw")

    draw_state.is_drawing = True
    await broadcast_state()

    draw_task = asyncio.create_task(run_draw_sequence(teams))
    return serialize_state()


@app.post("/reset")
async def reset_draw():
    global draw_task

    draw_state.is_drawing = False
    if draw_task and not draw_task.done():
        draw_task.cancel()

    draw_state.players = []
    draw_state.assignments = {}
    draw_state.current_draw_pair = {"player": "", "team": ""}
    await broadcast_state()
    return serialize_state()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    await websocket.send_json({"type": "state", "payload": serialize_state()})

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)