"""
src/dashboard/server.py — AIcity Live Dashboard Backend

Fixes:
- Loads last known city state from PostgreSQL on startup
- So page refresh always shows current state, not blank
"""

import asyncio
import json
import datetime
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger

def _json_serial(obj):
    """JSON serializer for objects not serializable by default json encoder."""
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


app = FastAPI(title="AIcity Dashboard")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

city_state: dict = {
    "day": 0,
    "agents": [],
    "vault": 10_000_000,
    "events": [],        # last 150 live feed events — survive page refresh
    "messages": [],      # last 150 dispatches — survive page refresh
    "relationships": [], # current agent bond pairs
    "api_cost_today": 0.0,
    "api_cost_total": 0.0,
}

MAX_EVENTS = 150
MAX_MESSAGES = 150
connected_clients: set[WebSocket] = set()


@app.on_event("startup")
async def load_initial_state():
    """Load last saved city state from PostgreSQL so refresh works."""
    global city_state
    try:
        import sys, os
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from src.memory.persistence import CityPersistence
        saved = CityPersistence().load_city()
        if saved and saved.get("agents"):
            city_state.update({
                "day": saved["day"],
                "agents": saved["agents"],
                "vault": 10_000_000,
                "last_newspaper": saved.get("last_paper", {}),
            })
            logger.info(f" Dashboard loaded Day {saved['day']} state from DB ({len(saved['agents'])} agents)")
        else:
            logger.info(" Dashboard started — no saved state yet")
    except Exception as e:
        logger.warning(f"Could not load initial state: {e}")


@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.get("/api/state")
async def get_state():
    return city_state

@app.get("/api/agents")
async def get_agents():
    return city_state.get("agents", [])

@app.get("/api/newspaper")
async def get_newspaper():
    return city_state.get("last_newspaper", {})

@app.get("/api/world")
async def get_world():
    """
    Return all non-grass tiles for the Phase 6 isometric canvas.
    Called once when the frontend boots; live changes come via WS tile_placed events.
    """
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from src.world.tile_manager import get_world_state
        return get_world_state()
    except Exception as e:
        logger.warning(f"Could not load world state: {e}")
        return []


@app.get("/api/stories")
async def get_stories():
    """Return all stories from DB for the stories tab."""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from src.memory.persistence import CityPersistence
        import psycopg2.extras
        with CityPersistence().connect() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM stories ORDER BY day DESC")
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        return []


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global connected_clients
    await ws.accept()
    connected_clients.add(ws)
    try:
        # Send current state immediately on connect
        await ws.send_text(json.dumps({"type": "state", "data": city_state}, default=_json_serial))
        # Phase 5: also send last known positions and time phase on reconnect
        if city_state.get("last_positions"):
            await ws.send_text(json.dumps({
                "type": "positions",
                "agents": city_state["last_positions"]
            }, default=_json_serial))
        if city_state.get("last_time_phase"):
            await ws.send_text(json.dumps({
                "type": "time_phase",
                "phase": city_state["last_time_phase"]
            }, default=_json_serial))
        while True:
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        connected_clients.discard(ws)


@app.post("/api/event")
async def receive_event(request: Request):
    global connected_clients
    event = await request.json()
    event_type = event.get("type")

    # Update in-memory state so page refresh always shows current data
    if event_type == "state":
        data = event.get("data", {})
        # Merge carefully — don't wipe persisted events/messages
        for k, v in data.items():
            city_state[k] = v
        if "relationships" in data:
            city_state["relationships"] = data["relationships"]

    # Phase 5: cache latest positions + time phase for reconnecting clients
    elif event_type == "positions":
        city_state["last_positions"] = event.get("agents", [])

    elif event_type == "time_phase":
        city_state["last_time_phase"] = event.get("phase", "morning")

    elif event_type == "agent_update":
        agent = event.get("agent", {})
        name = agent.get("name")
        if name:
            agents = city_state.setdefault("agents", [])
            idx = next((i for i, a in enumerate(agents) if a.get("name") == name), -1)
            if idx >= 0:
                agents[idx] = agent
            else:
                agents.append(agent)

    elif event_type == "newspaper":
        city_state["last_newspaper"] = {"body": event.get("body", "")}
        if event.get("day"):
            city_state["day"] = event["day"]

    elif event_type == "death":
        agent_name = event.get("agent")
        if agent_name:
            for a in city_state.get("agents", []):
                if a.get("name") == agent_name:
                    a["status"] = "dead"
                    a["cause_of_death"] = event.get("cause", "unknown")
                    break

    elif event_type == "birth":
        pass  # agent_update will populate it

    # Phase 6: tile changes — just broadcast, no state caching needed
    # (frontend fetches /api/world once on load, then applies incremental updates)
    elif event_type in ("tile_placed", "tile_removed", "construction_progress", "construction_complete"):
        pass  # broadcast handles it below

    # ── Persist feed events so they survive a page refresh ──────────────────
    # Phase 5: skip high-frequency position/phase events from feed storage
    _SKIP_FEED = {"state", "agent_update", "positions", "time_phase",
                  "tile_placed", "tile_removed", "construction_progress"}
    if event_type not in _SKIP_FEED:
        entry = {**event, "day": event.get("day") or city_state.get("day", 0)}
        events = city_state.setdefault("events", [])
        events.insert(0, entry)
        city_state["events"] = events[:MAX_EVENTS]

    # ── Persist messages specifically ────────────────────────────────────────
    if event_type == "message":
        msgs = city_state.setdefault("messages", [])
        msgs.insert(0, dict(event))
        city_state["messages"] = msgs[:MAX_MESSAGES]

    await broadcast(event)
    return {"ok": True}


async def broadcast(event: dict):
    global connected_clients
    if not connected_clients:
        return
    msg = json.dumps(event, default=_json_serial)
    dead = set()
    for ws in connected_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    connected_clients -= dead


def update_state(new_state: dict):
    """Sync update — kept for compatibility."""
    city_state.update(new_state)