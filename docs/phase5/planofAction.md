# AIcity Phase 5 — The Living City
## Plan of Action: Full Visual Simulation

**Author:** Claude (acting as lead developer)
**Status:** Planning
**Depends on:** Phase 4 complete (event log, gangs, projects, assets, mood)

---

## 1. The Vision

AIcity is not a dashboard. It is not a feed of text events. It is a **living city** that the public watches like a reality show — except nothing is scripted. Every building that appears, every crime that happens, every family that forms, every funeral that is held — all of it emerges from what 15 AI agents decide to do each day.

The public can only **watch**. They cannot intervene. They see agents waking up in the morning, walking to work, stealing from each other in dark alleys, building hospitals together, patrolling streets, sitting in parks, raising children. They watch the city grow from empty lots into a real place with history. They watch agents die and see their gravestones. They watch gangs form and get busted. They watch the city's economy rise and fall through the wealth distribution chart.

**The simulation is already running.** Phase 5 makes it visible.

### What exists right now that Phase 5 must show
- A police officer (Dario Cole) built an informant network with an explorer (Felix Hart) over 30+ days
- A blackmailer (Asha Rivers) tried to flip that informant and failed — Felix reported her to Dario instead
- A gang leader (Ayla Drake) and a blackmailer formed a secret criminal alliance that has been "meeting" at The Whispering Caves for 17 days with no mechanical outcome
- A builder (Orion Cross) has been trying to complete the city Archive for 40 days — the building exists in the database but not visually
- A journalist (Iris Wren) secretly warned a criminal that the police were watching her

**None of this is visible. Phase 5 makes all of it real.**

---

## 2. Core Design Principles

1. **Agent decisions drive visual behavior.** The LLM says "patrol the eastern district" — the police officer sprite physically walks a patrol route. The LLM says "steal from Marcus" — the thief sprite moves toward Marcus.

2. **The city grows with its people.** The city starts as mostly open land. Buildings appear when the project system completes them. Homes are claimed when agents earn enough. Gravestones appear when agents die.

3. **One simulate_day() = one full visual day.** Morning, afternoon, evening, night — all happen within one simulation tick, displayed as a compressed time cycle (roughly 30 seconds of visual animation per phase).

4. **The public only watches.** No controls. No intervention. Pure observation. The camera can pan and zoom but nothing else.

5. **The city is organic, not a box.** Streets curve. Buildings are different sizes. Green spaces are irregular. It looks like a real small town, not a grid.

---

## 3. The City — Layout & Design

### Philosophy
Think of a small riverside town with a population of 150–200 people. Not GTA (no highways, no skyscrapers, no scale). Not a box (no walls, no perfect grid). Organic like a real place that grew over time — with a commercial center, residential clusters spreading outward, a river on one edge, wilderness at the boundaries.

Reference: Stardew Valley's Pelican Town meets a real European village — irregular streets, natural landmarks, buildings of different sizes, hidden corners.

### The Map

**Grid size:** 96 × 72 tiles
**Tile size:** 16 × 16 pixels
**Rendered size:** 1536 × 1152 pixels (camera viewport: 960 × 720, panning allowed)
**Coordinate system:** (0,0) = top-left, x increases right, y increases down

```
NORTH — Wilderness / Exploration Boundary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Dense Forest         Open Field                 Forest Edge
  (tiles 0-15,0-12)    (tiles 16-60, 0-10)        (tiles 61-96, 0-12)
        |                     |                         |
        |          [EXPLORATION TRAIL →→→→→→→→→→→→→→→] |
        |          dirt path, Felix roams here          |
        |                                               |

  RIVER (flows north-south, tiles x=3-5)
  ≋≋≋≋≋   [Stone Bridge at y=20]   ≋≋≋≋≋

WEST                                                                        EAST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  River   Riverside     RESIDENTIAL NORTH          Builder Yard     Outskirts
  ≋≋≋≋≋   Path         [House 01] [House 02]       (workshop,       (rubble,
  ≋≋≋≋≋   (cobble)     [House 03] [House 04]       scaffolding,     empty lots)
  ≋≋≋≋≋                [House 05] [House 06]       lumber stacks)
  Bridge ←─────────────── Elm Street (curved, cobblestone) ──────────────────→

                            TOWN SQUARE & PARK
                       [Fountain] [Benches] [Trees]
                        [Grass paths, flowers]
                        [Notice board — city news posted here]

  River              Market District           Police Station
  ≋≋≋≋≋   [Market Stall]  [Merchant Shop]     [★ STATION ★]
  ≋≋≋≋≋   [Open Stalls]   [Trading Post]      [Patrol start]
  ≋≋≋≋≋
           ══════════════ MAIN STREET (cobblestone) ══════════════════════════

  River   [Healer's Clinic]    RESIDENTIAL SOUTH       [School]
  ≋≋≋≋≋   [Hospital ▲]        [House 07] [House 08]   [Classroom]
  ≋≋≋≋≋   (built by project)  [House 09] [House 10]   [Yard]
  ≋≋≋≋≋
           ══════════ SOUTH ROAD (dirt path, wider) ═══════════════════════════

  River   [Archive/Library]    [The Vault]           Dark Alley District
  ≋≋≋≋≋   (stone building)     (imposing structure,  [Back passages]
  ≋≋≋≋≋   (built by project)   gold trim)            [Shadowed corners]
  ≋≋≋≋≋                                             [Whispering Caves →]

SOUTH — Open Fields / Farm Land / City Boundary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Named Locations & Tile Coordinates

All positions are tile coordinates (col, row). Each location is a zone (bounding box), not a single tile.

| Location ID | Name | Tile Zone (x1,y1)→(x2,y2) | Notes |
|---|---|---|---|
| `LOC_WILDERNESS_N` | Northern Wilderness | (0,0)→(96,12) | Explorer roams here |
| `LOC_RIVER` | The River | (3,0)→(6,72) | Impassable except bridge |
| `LOC_BRIDGE` | Stone Bridge | (3,20)→(6,23) | Crossing point |
| `LOC_RESIDENTIAL_N` | Northern Homes | (18,14)→(58,26) | 6 home lots |
| `LOC_TOWN_SQUARE` | Town Square & Park | (28,26)→(52,34) | Fountain, benches |
| `LOC_MARKET` | Market District | (8,32)→(28,44) | Nova Bright's domain |
| `LOC_POLICE_STATION` | Police Station | (54,30)→(68,40) | Dario's base |
| `LOC_BUILDER_YARD` | Builder's Yard | (64,14)→(82,28) | Construction staging |
| `LOC_CLINIC` | Healer's Clinic | (8,44)→(22,56) | Iris Stone's base |
| `LOC_RESIDENTIAL_S` | Southern Homes | (28,44)→(58,56) | 4 home lots |
| `LOC_SCHOOL` | School | (62,44)→(80,56) | Teacher + newborns |
| `LOC_ARCHIVE` | Archive / Library | (8,58)→(22,68) | Built by project |
| `LOC_VAULT` | The City Vault | (30,58)→(44,68) | Token treasury |
| `LOC_DARK_ALLEY` | Dark Alley | (64,58)→(82,68) | Criminal zone |
| `LOC_WHISPERING_CAVES` | Whispering Caves | (84,62)→(96,72) | Secret meeting spot |
| `LOC_OUTSKIRTS_E` | Eastern Outskirts | (82,14)→(96,58) | Exploration staging |
| `LOC_EXPLORATION_TRAIL` | Exploration Trail | (20,0)→(96,14) | Felix's routes |

### Street Network

| Street Name | Path | Type |
|---|---|---|
| Elm Street | (7,25) → (82,25), slight curve at (35,24) | Cobblestone, main residential |
| Main Street | (7,36) → (82,36) | Cobblestone, commercial |
| South Road | (7,50) → (82,50) | Dirt-cobble mix |
| River Road | (7,25) → (7,64) | Riverside path |
| Alley Cut | (64,36) → (64,64) | Dark, narrow |

### Buildings — Predefined Lot Positions (Fixed Grid)

These lots exist from Day 1 as empty foundations. Buildings appear as projects complete.

| Building | Lot Position | Size (tiles) | Built When |
|---|---|---|---|
| Market Stall | (10,33) | 6×4 | `market_stall` project completes |
| Hospital | (9,45) | 8×6 | `hospital` project completes |
| School | (63,45) | 10×6 | `school` project completes |
| Watchtower | (56,29) | 4×6 | `watchtower` project completes |
| Archive | (9,59) | 8×6 | `archive` project completes |
| Road (visual) | Elm St extension | — | `road` project completes |
| Homes 01–10 | See residential lots | 5×4 each | Claimed by agent earning 500+ tokens |

---

## 4. Agent System — Positions, Movement, Roles

### Agent Position State

Add to every agent broadcast in WebSocket events:
```json
{
  "name": "Dario Cole",
  "role": "police",
  "x": 58.5,
  "y": 34.2,
  "destination_x": 42.0,
  "destination_y": 36.0,
  "facing": "left",
  "animation_state": "walk",
  "time_phase": "day",
  "home_tile": [32, 48],
  "work_zone": "LOC_POLICE_STATION"
}
```

### Role → Work Zone → Home Zone Mapping

| Role | Work Zone | Patrol/Movement Pattern | Night Behavior |
|---|---|---|---|
| `builder` | `LOC_BUILDER_YARD` | Walks to active construction lot | Goes home |
| `explorer` | `LOC_EXPLORATION_TRAIL` | Random walk into wilderness | Goes home |
| `police` | `LOC_POLICE_STATION` | Patrol loop: Station→Market→Alley→Square→back | Extended patrol |
| `merchant` | `LOC_MARKET` | Stays near market, walks stalls | Goes home |
| `teacher` | `LOC_SCHOOL` | School interior, walks to square midday | Goes home |
| `healer` | `LOC_CLINIC` | Clinic, responds to events (rushes to injured) | On-call — goes home but wakes |
| `messenger` | `LOC_TOWN_SQUARE` | Walks all districts, posts newspaper at notice board | Goes home early |
| `lawyer` | `LOC_VAULT` | Near vault/courthouse, visits police station | Goes home |
| `thief` | `LOC_DARK_ALLEY` (daytime: `LOC_MARKET` blending in) | Stalks target agent | Night: active in alleys |
| `newborn` | `LOC_SCHOOL` | Follows teacher | Goes home with teacher |
| `gang_leader` | `LOC_DARK_ALLEY` (daytime blend varies) | Moves between dark alley and recruiting targets | Night: active |
| `blackmailer` | Blends anywhere | Moves near target agents | Night: `LOC_WHISPERING_CAVES` |
| `saboteur` | `LOC_BUILDER_YARD` (disguised) | Works near assets, targets them | Night: asset attack |

### Pixel Art Sprites

**Sprite sheet:** One PNG per role. Each sprite: 16×16px base tile with 3-frame walk cycle per direction (12 frames total per character).

| Role | Sprite Description | Color Palette |
|---|---|---|
| `builder` | Hard hat, tool belt, work boots | Orange/brown |
| `explorer` | Backpack, boots, compass | Green/tan |
| `police` | Badge, dark uniform, cap | Navy blue/gold |
| `merchant` | Apron, satchel, friendly posture | Purple/cream |
| `teacher` | Glasses, book, casual clothing | Warm yellow/brown |
| `healer` | White coat, satchel with cross | White/red cross |
| `messenger` | Satchel, notepad, quick posture | Teal/grey |
| `lawyer` | Coat, briefcase, formal posture | Dark grey/white |
| `thief` | Hood, dark clothing, crouched idle | Dark red/black |
| `newborn` | Small, childlike proportions, no tool | Light blue/white |
| `gang_leader` | Jacket, confident posture, scar | Dark orange/black |
| `blackmailer` | Long coat, hat, shifty posture | Dark purple/grey |
| `saboteur` | Worker disguise but darker tones | Brown/dark red |

**Asset source:** LPC (Liberated Pixel Cup) base character sheets — free, CC-BY-SA licensed. Available at: https://opengameart.org/content/lpc-base-tiles-and-sprites

**Additional tiles needed:**
- LPC Terrain tiles (grass, cobblestone, dirt, water)
- LPC Buildings (house fronts, shop, station, clinic)
- LPC Nature (trees, flowers, bushes, river tiles)
- Custom: Vault, Whispering Caves, Dark Alley backing tiles

---

## 5. The Day/Night Cycle

Each `simulate_day()` call = one full visual 24-hour cycle, displayed in ~30 real seconds.

### Time Phases

| Phase | Visual Time | Duration (real) | Sky Color | Lighting |
|---|---|---|---|---|
| `dawn` | 5:00–7:00 AM | 3 seconds | Pink/orange gradient | Soft warm glow |
| `morning` | 7:00–12:00 PM | 7 seconds | Bright blue | Full daylight |
| `afternoon` | 12:00–5:00 PM | 8 seconds | Warm blue | High sun, short shadows |
| `evening` | 5:00–9:00 PM | 6 seconds | Orange/purple | Street lamps flicker on |
| `night` | 9:00 PM–5:00 AM | 6 seconds | Deep navy | Only lamp glow, crime time |

**Implementation:** A full-screen dark overlay `Rectangle` in Phaser with alpha that changes:
- Dawn: alpha 0.5 (warm orange tint)
- Morning/Afternoon: alpha 0.0 (clear)
- Evening: alpha 0.3 (orange tint)
- Night: alpha 0.7 (dark navy, near-black)

Street lamp sprites emit a point light (Phaser 3 lights pipeline). Agents outside at night carry a small lantern glow (explorer, police).

### Agent Schedule by Phase

```
DAWN:     Agents wake. Sprites appear at their home tile. Stretch animation.
MORNING:  All agents walk from home → work zone. Movement is simultaneous.
          Police begins patrol route.
AFTERNOON: Agents work. Crimes can happen. Meetings happen.
           Builder walks to construction site. Progress bar fills.
           Thief stalks target (follows them at distance).
EVENING:  Work ends. Agents walk home. Social messages sent.
          Criminals more active near alley.
NIGHT:    Most agents in homes (lights on in windows).
          Police patrols with lantern.
          Thief/gang_leader/blackmailer move in dark alley zone.
          Whispering Caves: criminal meetings happen here.
```

---

## 6. Backend Changes Required

### 6a. New agent fields (agent.py)

```python
# Phase 5: position tracking
x: float = 0.0          # current tile x (float for smooth movement)
y: float = 0.0          # current tile y
home_tile_x: int = 0    # assigned home lot x
home_tile_y: int = 0    # assigned home lot y
home_claimed: bool = False   # True once agent buys a home
```

### 6b. New migration: 009_phase5_positions.sql

```sql
ALTER TABLE agents
  ADD COLUMN IF NOT EXISTS x FLOAT DEFAULT 0.0,
  ADD COLUMN IF NOT EXISTS y FLOAT DEFAULT 0.0,
  ADD COLUMN IF NOT EXISTS home_tile_x INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS home_tile_y INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS home_claimed BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS city_map_state (
  id SERIAL PRIMARY KEY,
  day INT NOT NULL,
  time_phase VARCHAR(16) NOT NULL,  -- dawn/morning/afternoon/evening/night
  standing_assets JSONB DEFAULT '[]',
  claimed_homes JSONB DEFAULT '[]',
  recorded_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS meeting_events (
  id SERIAL PRIMARY KEY,
  day INT NOT NULL,
  participants TEXT[] NOT NULL,     -- agent names
  location VARCHAR(64) NOT NULL,    -- LOC_* constant
  outcome VARCHAR(256),             -- what happened mechanically
  recorded_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS criminal_alliances (
  id SERIAL PRIMARY KEY,
  initiator_name TEXT NOT NULL,
  partner_name TEXT NOT NULL,
  day_formed INT NOT NULL,
  alliance_type VARCHAR(64),        -- 'gang_blackmail', 'dual_theft', etc.
  status VARCHAR(32) DEFAULT 'active',
  total_operations INT DEFAULT 0,
  known_to_police BOOLEAN DEFAULT FALSE
);
```

### 6c. New module: src/city/position_manager.py

Manages all agent positions, home assignments, location routing.

```python
class PositionManager:
    WORK_ZONES = {
        "builder":     "LOC_BUILDER_YARD",
        "explorer":    "LOC_EXPLORATION_TRAIL",
        "police":      "LOC_POLICE_STATION",
        "merchant":    "LOC_MARKET",
        "teacher":     "LOC_SCHOOL",
        "healer":      "LOC_CLINIC",
        "messenger":   "LOC_TOWN_SQUARE",
        "lawyer":      "LOC_VAULT",
        "thief":       "LOC_DARK_ALLEY",
        "newborn":     "LOC_SCHOOL",
        "gang_leader": "LOC_DARK_ALLEY",
        "blackmailer": "LOC_DARK_ALLEY",
        "saboteur":    "LOC_BUILDER_YARD",
    }

    def assign_starting_positions(self, agents: list[Agent]) -> None
        """Called at big_bang. Each agent gets a starting tile in their work zone."""

    def assign_home(self, agent: Agent, tokens_threshold: int = 500) -> bool
        """If agent.tokens > threshold and no home claimed, assign next free home lot."""

    def get_work_destination(self, agent: Agent, time_phase: str) -> tuple[float, float]
        """Returns (x, y) tile destination based on role + time of day."""

    def get_patrol_waypoints(self, step: int) -> list[tuple]
        """Returns the next waypoint for a police patrol loop."""

    def get_zone_center(self, zone_id: str) -> tuple[float, float]
        """Returns center tile of a named zone."""

    def agents_at_same_zone(self, agent_a: str, agent_b: str, radius: float = 3.0) -> bool
        """True if two agents are within radius tiles of each other."""
```

### 6d. Meeting Mechanic (src/city/meeting_manager.py)

This is the piece that makes "let's meet" actually mean something.

```python
class MeetingManager:
    """
    When two agents exchange messages about meeting AND both are in the
    same zone on the same day → trigger a meeting event with real outcomes.
    """

    MEETING_OUTCOMES = {
        ("gang_leader", "blackmailer"): "_form_criminal_alliance",
        ("gang_leader", "thief"):       "_expand_gang",
        ("blackmailer", "explorer"):    "_attempt_compromise",
        ("police", "explorer"):         "_debrief_informant",
        ("builder", "merchant"):        "_start_project",
        ("builder", "teacher"):         "_start_project",
        ("builder", "explorer"):        "_start_project",
        ("merchant", "healer"):         "_trade_goods",
    }

    def check_meetings(self, day: int, all_agents: list[dict],
                       position_manager: PositionManager) -> list[dict]:
        """
        Called once per day after all agent turns.
        Checks message pairs for meeting intent + proximity.
        Fires appropriate outcome if conditions met.
        Returns list of meeting events for broadcast.
        """

    def _form_criminal_alliance(self, agent_a: dict, agent_b: dict, day: int)
        """Creates criminal_alliances DB record. Private event log entry."""

    def _debrief_informant(self, police: dict, informant: dict, day: int)
        """Police learns about criminal agents informant has observed.
        Elevates event_log visibility on known suspects."""

    def _attempt_compromise(self, criminal: dict, target: dict, day: int)
        """Criminal tries to flip target. Target rolls loyalty check.
        If fails: target joins alliance. If succeeds: criminal reported."""
```

### 6e. Home System (src/city/home_manager.py)

```python
HOME_LOTS = [
    {"id": "home_01", "x": 20, "y": 16, "owner": None},
    {"id": "home_02", "x": 26, "y": 16, "owner": None},
    {"id": "home_03", "x": 32, "y": 16, "owner": None},
    {"id": "home_04", "x": 38, "y": 16, "owner": None},
    {"id": "home_05", "x": 44, "y": 16, "owner": None},
    {"id": "home_06", "x": 50, "y": 16, "owner": None},
    {"id": "home_07", "x": 30, "y": 47, "owner": None},
    {"id": "home_08", "x": 36, "y": 47, "owner": None},
    {"id": "home_09", "x": 42, "y": 47, "owner": None},
    {"id": "home_10", "x": 48, "y": 47, "owner": None},
]

class HomeManager:
    def check_home_purchases(self, agents: list[Agent], token_engine) -> list[dict]
        """Agents with >500 tokens and no home → buy next available lot.
        Costs 300 tokens. Broadcasts home_claimed event."""

    def get_home(self, agent_name: str) -> dict | None
        """Returns the home lot owned by this agent."""

    def light_on(self, agent_name: str) -> bool
        """Returns True if agent is home (night phase). Used for window light sprites."""
```

### 6f. Criminal Alliance formalization

`criminal_alliances` is the DB record for Ayla-Asha style partnerships. The `MeetingManager` creates it. Effects:
- Both agents get `ally_name` context injected into their LLM prompt
- Coordinated actions get a small bonus (similar to gang bonus)
- If one is arrested and talks: alliance `known_to_police = TRUE`
- Police investigation now checks `criminal_alliances` table for leads

### 6g. city_v3.py changes

Add to `simulate_day()`:

```python
# Phase 5: update agent positions based on time of day
self._update_positions(time_phase="morning")
# ... after agent turns ...
self._update_positions(time_phase="afternoon")

# Phase 5: check meetings
meeting_events = self.meeting_manager.check_meetings(
    day=self.day,
    all_agents=agent_dicts,
    position_manager=self.position_manager,
)

# Phase 5: check home purchases
home_events = self.home_manager.check_home_purchases(
    agents=self.agents,
    token_engine=token_engine,
)

# Phase 5: broadcast positions
_broadcast_sync({"type": "positions", "agents": [
    {"name": a.name, "x": a.x, "y": a.y, "facing": ..., "anim": ...}
    for a in self.agents if a.status == AgentStatus.ALIVE
]})
```

---

## 7. Frontend — Phaser 3 Implementation

### File Structure

```
src/dashboard/
├── static/
│   ├── index.html           ← modified: add game canvas div
│   ├── app.css              ← modified: layout for side panel + game
│   ├── app.js               ← modified: handle new event types
│   └── game/
│       ├── main.js          ← Phaser game config + boot
│       ├── scenes/
│       │   ├── BootScene.js      ← preload all assets
│       │   ├── CityScene.js      ← main game scene
│       │   └── UIScene.js        ← overlaid UI (agent names, token counts)
│       ├── systems/
│       │   ├── AgentManager.js   ← sprite creation, movement, animation
│       │   ├── MapManager.js     ← tilemap, building spawning
│       │   ├── DayNight.js       ← sky, lighting, lamp system
│       │   ├── EventAnimator.js  ← theft flash, arrest chase, death fade
│       │   └── AmbientSystem.js  ← animals, weather, idle world
│       ├── data/
│       │   ├── citymap.json      ← Tiled tilemap export
│       │   ├── zones.js          ← LOC_* constants with tile coordinates
│       │   └── roleConfig.js     ← role → sprite frame, work zone, color
│       └── assets/
│           ├── tilesets/
│           │   ├── terrain.png   ← grass, cobble, dirt, water
│           │   ├── buildings.png ← house, shop, station, clinic tiles
│           │   └── nature.png    ← trees, flowers, river decorations
│           ├── sprites/
│           │   ├── agents.png    ← all 13 role sprite sheets combined
│           │   └── ambient.png   ← cat, dog, bird sprites
│           └── fx/
│               ├── particles.png ← token particle, dust, sparkle
│               └── lights.png    ← lamp glow, fire, moonlight
```

### Phaser Game Config

```javascript
// game/main.js
const config = {
  type: Phaser.AUTO,
  width: 960,
  height: 720,
  parent: 'game-canvas',
  backgroundColor: '#1a1a2e',
  pixelArt: true,          // crisp pixel rendering — no anti-alias
  zoom: 2,                 // each 16px tile renders at 32px
  physics: { default: 'arcade', arcade: { debug: false } },
  scene: [BootScene, CityScene, UIScene],
  plugins: {
    scene: [{ key: 'rexMoveTo', plugin: RexMoveToPlugin, start: true }]
    // rexMoveTo: smooth tile-based movement
  }
};
```

### CityScene — Core

```javascript
// game/scenes/CityScene.js
class CityScene extends Phaser.Scene {

  create() {
    this.map = this.make.tilemap({ key: 'citymap' });
    // Layers: ground, paths, buildings_base, buildings_top, decoration, agents, overlay
    this.groundLayer    = this.map.createLayer('ground', terrainTileset);
    this.pathLayer      = this.map.createLayer('paths', terrainTileset);
    this.buildingLayer  = this.map.createLayer('buildings', buildingTileset);
    this.decorLayer     = this.map.createLayer('decoration', natureTileset);

    this.agentManager   = new AgentManager(this);
    this.dayNight       = new DayNight(this);
    this.eventAnimator  = new EventAnimator(this);
    this.ambientSystem  = new AmbientSystem(this);

    // Camera — follows action, panning enabled on mouse drag
    this.cameras.main.setBounds(0, 0, 96*16*2, 72*16*2);
    this.setupWebSocket();
    this.setupCameraControls();
  }

  setupWebSocket() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.ws = new WebSocket(`${proto}//${location.host}/ws`);
    this.ws.onmessage = (e) => this.handleServerEvent(JSON.parse(e.data));
  }

  handleServerEvent(event) {
    switch(event.type) {
      case 'state':          this.agentManager.initFromState(event.data); break;
      case 'positions':      this.agentManager.updatePositions(event.agents); break;
      case 'time_phase':     this.dayNight.setPhase(event.phase); break;
      case 'agent_update':   this.agentManager.updateAgent(event.agent); break;
      case 'theft':          this.eventAnimator.playTheft(event); break;
      case 'arrest':         this.eventAnimator.playArrest(event); break;
      case 'death':          this.eventAnimator.playDeath(event); break;
      case 'birth':          this.agentManager.spawnAgent(event); break;
      case 'asset_built':    this.mapManager.placeBuilding(event); break;
      case 'home_claimed':   this.mapManager.placeHome(event); break;
      case 'meeting':        this.eventAnimator.playMeeting(event); break;
      case 'gang_formed':    this.eventAnimator.playGangForm(event); break;
      case 'heart_attack':   this.eventAnimator.playHeartAttack(event); break;
      case 'newspaper':      this.uiSystem.postNewspaper(event); break;
    }
  }
}
```

### AgentManager — Sprite & Movement

```javascript
class AgentManager {
  constructor(scene) {
    this.scene = scene;
    this.agents = new Map();  // name → { sprite, nameLabel, tokenLabel }
  }

  spawnAgent(agentData) {
    const { name, role, x, y } = agentData;
    const frameConfig = ROLE_CONFIG[role];

    const sprite = this.scene.physics.add.sprite(
      x * 32, y * 32,          // pixel position (tile * zoom)
      'agents',
      frameConfig.idleFrame
    );

    sprite.setDepth(5);
    sprite.anims.play(`${role}_idle_down`);

    // Name tag floating above sprite
    const label = this.scene.add.text(x*32, y*32 - 18, name.split(' ')[0], {
      fontSize: '6px', fill: '#ffffff', fontFamily: 'Share Tech Mono'
    }).setDepth(6).setOrigin(0.5);

    this.agents.set(name, { sprite, label, data: agentData });
  }

  moveTo(name, targetX, targetY, onComplete) {
    const agent = this.agents.get(name);
    if (!agent) return;

    const { sprite } = agent;
    const dx = targetX - sprite.x / 32;
    const dy = targetY - sprite.y / 32;

    // Set walking animation based on direction
    const dir = Math.abs(dx) > Math.abs(dy)
      ? (dx > 0 ? 'right' : 'left')
      : (dy > 0 ? 'down' : 'up');

    sprite.anims.play(`${agent.data.role}_walk_${dir}`, true);

    // Move over ~2 seconds per tile
    this.scene.tweens.add({
      targets: [sprite, agent.label],
      x: targetX * 32,
      y: targetY * 32,
      duration: Math.sqrt(dx*dx + dy*dy) * 600,
      ease: 'Linear',
      onComplete: () => {
        sprite.anims.play(`${agent.data.role}_idle_${dir}`, true);
        if (onComplete) onComplete();
      }
    });
  }

  updatePositions(positionArray) {
    positionArray.forEach(pos => {
      this.moveTo(pos.name, pos.x, pos.y);
    });
  }
}
```

### EventAnimator — All Visual Events

```javascript
class EventAnimator {

  playTheft(event) {
    // 1. Thief sprite runs toward victim
    // 2. Token particles fly from victim to thief (Phaser particle emitter)
    // 3. Victim sprite flashes red briefly
    // 4. "−{amount} tokens" floating text rises from victim

    const thief  = this.agents.get(event.agent);
    const victim = this.agents.get(event.target);
    if (!thief || !victim) return;

    this.scene.agentManager.moveTo(event.agent, victim.sprite.x/32, victim.sprite.y/32, () => {
      this.scene.add.particles('particles').createEmitter({
        x: victim.sprite.x, y: victim.sprite.y,
        speed: { min: 50, max: 150 },
        angle: { min: -45, max: -135 },
        tint: 0xFFD700,
        lifespan: 800,
        quantity: 12,
        on: false
      }).explode(12, victim.sprite.x, victim.sprite.y);

      victim.sprite.setTint(0xFF3131);
      this.scene.time.delayedCall(500, () => victim.sprite.clearTint());

      this.floatingText(victim.sprite.x, victim.sprite.y, `-${event.tokens}`, '#FF3131');
    });
  }

  playArrest(event) {
    // Police sprite runs toward criminal
    // Handcuff particle effect on criminal
    // Criminal sprite turns grey (imprisoned)
    // "ARRESTED" banner briefly appears above criminal
  }

  playDeath(event) {
    // Agent sprite fades out over 2 seconds
    // Gravestone tile appears at their last known position
    // Funeral bell sound (if audio enabled)
    // Other nearby agents turn to face the gravestone briefly
  }

  playMeeting(event) {
    // Both agents walk to the same zone center
    // A subtle glow circle appears around them
    // Small icons show outcome: handshake (alliance), badge (informant debrief)
    // Agents then resume normal movement
  }

  playHeartAttack(event) {
    // Agent sprite collapses animation
    // Red pulse circle expands from agent
    // Healer sprite rushes over if alive
    // Token loss text floats up
  }

  floatingText(x, y, text, color) {
    const t = this.scene.add.text(x, y, text, {
      fontSize: '8px', fill: color, fontFamily: 'Share Tech Mono'
    }).setDepth(10).setOrigin(0.5);
    this.scene.tweens.add({
      targets: t, y: y - 24, alpha: 0,
      duration: 1200, ease: 'Cubic.Out',
      onComplete: () => t.destroy()
    });
  }
}
```

### MapManager — Building Spawning

```javascript
class MapManager {
  BUILDING_TILES = {
    'market_stall': { x: 10, y: 33, width: 6, height: 4, tileFrame: 'market' },
    'hospital':     { x:  9, y: 45, width: 8, height: 6, tileFrame: 'hospital' },
    'school':       { x: 63, y: 45, width:10, height: 6, tileFrame: 'school' },
    'watchtower':   { x: 56, y: 29, width: 4, height: 6, tileFrame: 'watchtower' },
    'archive':      { x:  9, y: 59, width: 8, height: 6, tileFrame: 'archive' },
  };

  placeBuilding(event) {
    const spec = this.BUILDING_TILES[event.project_type];
    if (!spec) return;

    // Play construction dust particles at location first
    this.playConstructionEffect(spec.x * 32, spec.y * 32);

    // After 1.5s, reveal the building tiles
    this.scene.time.delayedCall(1500, () => {
      this.scene.buildingLayer.putTilesAt(
        this.getBuildingTileArray(spec.tileFrame),
        spec.x, spec.y
      );
      // Announce on notice board
      this.postToNoticeBoard(`${event.project_name} completed!`);
    });
  }

  placeHome(event) {
    // Place a small house sprite at the claimed lot
    // Show owner's name above door
    // Light up windows at night when owner is home
  }
}
```

### DayNight System

```javascript
class DayNight {
  PHASES = {
    dawn:      { skyAlpha: 0.50, skyColor: 0xFF7B54, lampAlpha: 0.6 },
    morning:   { skyAlpha: 0.00, skyColor: 0x87CEEB, lampAlpha: 0.0 },
    afternoon: { skyAlpha: 0.00, skyColor: 0x87CEEB, lampAlpha: 0.0 },
    evening:   { skyAlpha: 0.35, skyColor: 0xFF6B35, lampAlpha: 0.4 },
    night:     { skyAlpha: 0.72, skyColor: 0x0D1B2A, lampAlpha: 1.0 },
  };

  setPhase(phase) {
    const cfg = this.PHASES[phase];
    // Tween sky overlay to new color and alpha
    this.scene.tweens.add({
      targets: this.skyOverlay,
      alpha: cfg.skyAlpha,
      duration: 2000, ease: 'Sine.InOut'
    });
    this.skyOverlay.setFillStyle(cfg.skyColor);
    // Fade lamps in/out
    this.lampSprites.forEach(lamp => {
      this.scene.tweens.add({ targets: lamp, alpha: cfg.lampAlpha, duration: 1500 });
    });
    // Update home window lights
    this.updateWindowLights(phase);
  }

  updateWindowLights(phase) {
    // At night: homes with owners show warm yellow window glow
    // Agents not at home: window dark
  }
}
```

### AmbientSystem — Animals & World Breathing

```javascript
class AmbientSystem {
  init() {
    // Spawn 3 cats, 2 dogs, 5 birds
    this.spawnAnimals();
    // Gentle tree sway (shader or frame animation)
    this.startTreeSway();
    // River animation (tile animation in Tiled)
    // Occasional bird flies across screen
    this.scheduleFlockEvent();
    // Weather: 10% chance of light rain per day
    this.checkWeather();
  }

  spawnAnimals() {
    // Cats: wander in park and residential areas
    // Dogs: follow agents occasionally, sit near market
    // Birds: perch on rooftops, fly away when agents pass
  }

  updateAnimalBehavior() {
    // Called every 2 seconds
    // Cats: random walk, avoid criminal zones at night
    // Dogs: 20% chance to follow nearest agent for 5 tiles
    // Birds: scatter if agent within 3 tiles
  }
}
```

---

## 8. Action → Visual Behavior Mapping

The LLM `action` field drives where an agent goes and what animation plays.

```python
# src/city/action_router.py

ACTION_TO_DESTINATION = {
    # Builder
    "build":         "LOC_BUILDER_YARD",
    "construct":     "LOC_BUILDER_YARD",
    "work on":       "LOC_BUILDER_YARD",
    "collaborate":   "LOC_BUILDER_YARD",
    # Explorer
    "explore":       "LOC_EXPLORATION_TRAIL",
    "venture":       "LOC_EXPLORATION_TRAIL",
    "discover":      "LOC_EXPLORATION_TRAIL",
    # Police
    "patrol":        "PATROL_ROUTE",
    "investigate":   "LOC_POLICE_STATION",
    "arrest":        "TARGET_AGENT",        # dynamic: moves to criminal's position
    # Merchant
    "sell":          "LOC_MARKET",
    "trade":         "LOC_MARKET",
    "negotiate":     "LOC_MARKET",
    # Teacher
    "teach":         "LOC_SCHOOL",
    "mentor":        "LOC_SCHOOL",
    "lesson":        "LOC_SCHOOL",
    # Healer
    "heal":          "TARGET_AGENT",        # rushes to sick agent
    "treat":         "LOC_CLINIC",
    "tend":          "LOC_CLINIC",
    # Thief
    "steal":         "TARGET_AGENT",        # stalks toward victim
    "rob":           "TARGET_AGENT",
    # Gang leader
    "recruit":       "TARGET_AGENT",
    "organize":      "LOC_DARK_ALLEY",
    # Blackmailer
    "blackmail":     "TARGET_AGENT",
    "extort":        "TARGET_AGENT",
    "threaten":      "LOC_WHISPERING_CAVES",
    # Saboteur
    "sabotage":      "TARGET_ASSET",
    "destroy":       "TARGET_ASSET",
}

def route_action_to_destination(agent_role: str, action: str, context: dict) -> str:
    """
    Parse the LLM action text and return the destination zone or target.
    Falls back to role's default work zone if no keyword matches.
    """
    action_lower = action.lower()
    for keyword, destination in ACTION_TO_DESTINATION.items():
        if keyword in action_lower:
            return destination
    # Default: role work zone
    return PositionManager.WORK_ZONES.get(agent_role, "LOC_TOWN_SQUARE")
```

---

## 9. What the Public Sees

The dashboard is split: **left panel** (the existing text feed, newspaper, relationships) and **right panel** (the Phaser city canvas, taking up ~60% of screen width).

### Camera behavior
- Default: wide shot showing the full city
- On major event (arrest, death, gang formation): camera pans to the location and zooms in for 3 seconds, then returns to overview
- On click on an agent sprite: camera follows that agent, panel shows their stats and recent memories

### Information the viewer sees at a glance
- Agent name floating above sprite
- Token bar (tiny, under name — green when healthy, red when critical)
- Role icon (small badge on sprite)
- Time of day (sun/moon indicator in corner)
- Day counter
- City infrastructure state (built assets listed in sidebar)
- Active criminal investigations (police case status)

### What the viewer does NOT see
- Private events (crimes not yet witnessed)
- Gang membership (until exposed)
- Bribe susceptibility
- LLM raw output

This matches the information asymmetry philosophy: even the human viewer only sees what is PUBLIC.

---

## 10. Implementation Order

### Sprint 1 — Foundation (Backend)
1. Run migration `009_phase5_positions.sql`
2. Add `x, y, home_tile_x, home_tile_y, home_claimed` to `Agent` model
3. Build `PositionManager` — starting positions, zone routing, patrol waypoints
4. Build `HomeManager` — lot assignment, window lights state
5. Add `position_manager` and `home_manager` to `AICity.__init__()`
6. Add position updates to `simulate_day()` — broadcast `positions` event each phase
7. Build `MeetingManager` — meeting detection, outcome dispatch
8. Add `criminal_alliances` table + DB logic in `MeetingManager`
9. Fix project join issue fully — verify with DB query after 5-day run

### Sprint 2 — Static City (Frontend)
1. Create `citymap.json` in Tiled editor matching the layout above
2. Gather LPC tilesets (terrain, buildings, nature) — confirm license
3. Create `game/main.js` with Phaser config
4. Build `BootScene.js` — preload all assets
5. Build `CityScene.js` — render tilemap layers, static map visible
6. Wire WebSocket in `CityScene` — receive events, log to console
7. Deploy alongside existing dashboard at same FastAPI server

### Sprint 3 — Moving Agents
1. Build `AgentManager.js` — spawn sprites, name labels
2. Implement `moveTo()` with walk animations
3. Handle `positions` WebSocket event → move all agents
4. Handle `time_phase` event → agents change destinations
5. Add patrol route for police sprite
6. Test: run simulation, watch agents move on canvas

### Sprint 4 — Day/Night & Events
1. Build `DayNight.js` — sky overlay, lamp sprites, phase transitions
2. Build `EventAnimator.js` — theft particles, arrest chase, death fade, meeting glow
3. Build `MapManager.js` — building spawning on `asset_built` event
4. Add home placement on `home_claimed` event
5. Wire all events through `handleServerEvent`

### Sprint 5 — Ambient Life
1. Create animal sprites (cat, dog, bird — 8×8 or 16×16)
2. Build `AmbientSystem.js` — spawning, wandering behavior, bird flocks
3. Add tree sway animation
4. Add river tile animation
5. Add weather system (rain particle emitter, dark sky overlay)
6. Add notice board — newspaper headline posts there each morning

### Sprint 6 — Polish & Camera
1. Camera pan/zoom on major events
2. Click agent → follow mode
3. Agent tooltip on hover (memories, mood, bonds)
4. Graveyard tiles — gravestones appear and persist
5. Window lights in homes at night
6. Performance optimization (object pooling for particles, culling off-screen sprites)

---

## 11. Assets Checklist

| Asset | Source | License | Status |
|---|---|---|---|
| LPC Terrain tiles | opengameart.org/content/lpc-base-tiles | CC-BY-SA 3.0 | To download |
| LPC Buildings | opengameart.org/content/lpc-building-tiles | CC-BY-SA 3.0 | To download |
| LPC Characters base | opengameart.org/content/lpc-character-bases | CC-BY-SA 3.0 | To download |
| LPC Nature (trees, plants) | opengameart.org/content/lpc-nature | CC-BY-SA 3.0 | To download |
| Cat/Dog sprites | opengameart.org/content/lpc-animals | CC-BY-SA 3.0 | To download |
| Phaser 3 | github.com/photonstorm/phaser | MIT | npm install |
| Rex MoveTo plugin | rexrainbow.github.io/phaser3-rex-notes | MIT | npm install |
| Tiled editor | mapeditor.org | Free | To install |

---

## 12. New Files to Create

```
src/
  city/
    position_manager.py     ← agent positions, zone routing
    meeting_manager.py      ← meeting detection + outcomes
    home_manager.py         ← home lot assignment
  migrations/
    009_phase5_positions.sql

src/dashboard/static/game/
  main.js
  scenes/
    BootScene.js
    CityScene.js
    UIScene.js
  systems/
    AgentManager.js
    MapManager.js
    DayNight.js
    EventAnimator.js
    AmbientSystem.js
  data/
    citymap.json            ← created in Tiled editor
    zones.js
    roleConfig.js
  assets/
    tilesets/
      terrain.png
      buildings.png
      nature.png
    sprites/
      agents.png
      ambient.png
    fx/
      particles.png
      lights.png
```

---

## 13. What Phase 5 Does NOT Include

- 3D rendering (future)
- Player controls (observers only — no clicking to direct agents)
- Voice/audio (future — could add ambient city sounds, footsteps)
- Family system (Phase 6 — requires marriage mechanic, family home assignment, child-parent bond)
- Agent inventory / physical objects
- Multiplayer observation (future — currently single tab)

---

## 14. Success Criteria

Phase 5 is complete when:

- [ ] 15 agents spawn with pixel sprites at correct starting positions
- [ ] Agents physically walk from home → work zone each morning
- [ ] Police sprite follows a visible patrol route
- [ ] Thief sprite visibly stalks the wealthiest agent
- [ ] Day/night cycle transitions smoothly (sky color, lamps, window lights)
- [ ] When a project completes in the DB, a building materializes on the map
- [ ] When an agent dies, a gravestone tile appears at their last position
- [ ] When a theft happens, token particles fly visibly between sprites
- [ ] When Ayla Drake and Asha Rivers meet at The Whispering Caves, two sprites walk there and a meeting animation plays — and a `criminal_alliances` record is created
- [ ] When Dario Cole and Felix Hart meet for a debrief, the police gains real intelligence (event_log visibility is elevated)
- [ ] Cats and dogs wander the streets
- [ ] The public can watch all of this live in a browser with no controls

---

*This document is the single source of truth for Phase 5 development.*
*Last updated: Day 40 of AIcity Simulation — City is alive. Now make it visible.*
