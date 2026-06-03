from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random

app = FastAPI()

# Allow frontend calls (important!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Request model ---
class SweepstakeRequest(BaseModel):
    players: list[str]
    teams: list[str]


# --- Basic test route ---
@app.get("/")
def home():
    return {"message": "Sweepstake API is running ✅"}


# --- Generate sweepstake ---
@app.post("/generate")
def generate_sweepstake(data: SweepstakeRequest):
    players = data.players
    teams = data.teams

    if len(players) > len(teams):
        return {"error": "Not enough teams for all players"}

    shuffled_teams = teams[:]
    random.shuffle(shuffled_teams)

    results = []
    for i, player in enumerate(players):
        results.append({
            "player": player,
            "team": shuffled_teams[i]
        })

    return {"results": results}