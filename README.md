# AIcity — An AI Civilization That Runs Itself

> *"Exist. Grow. Discover."* — hardcoded into every agent at birth

This is a personal project I've been building since February 2026. It's an autonomous AI city where LLM-powered agents are born, earn tokens to survive, form relationships, steal from each other, get arrested, go to trial, build infrastructure, join gangs, blackmail rivals, and die — all without me telling them what to do day-to-day.

It's not a chatbot. It's not a product. It's more like a digital city that grows itself, and I'm just the founder who wrote the laws.

---

## What's actually happening when you run it

- 10 founding agents are born with 1,000 tokens each
- Every day costs 100 tokens just to exist (burn rate)
- Each agent has a role (builder, thief, police, gang leader, etc.) and uses an LLM to decide what to do
- Agents can earn tokens, steal from each other, send messages, heal the sick, arrest criminals, blackmail neighbours, or quietly sabotage city infrastructure
- If you run out of tokens → you starve and die. Permanently.
- Population stays above 6 by spawning newborns who learn from a teacher before graduating into a role
- Agents build the city together — a market stall, a hospital, a school, an archive — through multi-day collaborative projects
- A city vault collects 10% tax on all earnings and redistributes welfare to struggling agents
- Every 7 days a messenger writes a "Week in Review". On day 30, a full monthly chronicle
- An event log tracks every crime, verdict, and death with a visibility system: PRIVATE → WITNESSED → RUMOR → REPORTED → PUBLIC
- Corrupt police officers can quietly accept bribes and bury arrest reports
- All of this is visible in real time on a live web dashboard with a fullscreen city view and live conversation feed

---

## Phases built so far

| Phase | Name | Status | What it added |
|-------|------|--------|---------------|
| 1 | The Skeleton | ✅ Done | Agents, token economy, death, basic memory |
| 2 | The Citizens | ✅ Done | LLM brains, messaging, shared memory, daily newspaper |
| 3 | The City | ✅ Done | Real transfers, trial system, births, PostgreSQL, relationships, live dashboard |
| 4 | Deep Bonds | ✅ Done | Gang formation, blackmail, saboteur role, mood system, police corruption, event log, collaborative projects, city assets |
| 5 | The Living City | ✅ Done | Phaser 3 city canvas, agent sprites, day/night cycle, event animations (theft/arrest/death/meetings), home ownership, fullscreen view with live conversations |
| 6 | Visual Rebuild | 🗓 Planned | SimCity-quality isometric city — PixiJS v8, Kenney sprites, real pathfinding, agents physically build the world tile by tile |

---

## Current dashboard

- **Live city canvas** — Phaser 3 top-down city. Agents move between zones with name labels and role badges.
- **Day/night cycle** — sky overlay shifts from dawn orange to midnight blue. Street lamps glow at dusk.
- **Event animations** — gold particles fly on theft, police sprint to arrest criminals, gravestones appear on death, construction dust on building completion.
- **⛶ FULLSCREEN** button — city expands to 65% of screen, live conversation feed on the right: `Name (role) → Target: message`.
- **Relationship graph** — SVG showing all agent bonds (green = ally, red = enemy, thicker = stronger).
- **Live events feed**, **daily newspaper**, **economy chart**, **archives**.

---

## Tech stack (current — Phase 5)

| Layer | Tool | Purpose |
|-------|------|---------|
| Agent brains | Claude Sonnet 4.6 / Haiku 4.5 | LLM decisions per role per day |
| Backend | Python 3.12 + FastAPI + Uvicorn | Simulation loop + WebSocket server |
| Database | PostgreSQL | Agents, balances, crimes, stories, relationships, tile state |
| Memory | Qdrant | Per-agent private vector memory |
| Messaging | Redis | Agent-to-agent inbox |
| Real-time | WebSocket (FastAPI native) | Dashboard event stream |
| Game engine | Phaser 3.60 (CDN) | Browser city canvas |
| Dashboard | Vanilla JS + CSS | Sidebar UI, feeds, charts |

---

## Tech stack (planned — Phase 6)

| Layer | Tool | Why it's better |
|-------|------|----------------|
| Game engine | **PixiJS v8** (WebGL/WebGPU) | 100k+ sprites at 60fps, isometric support |
| Language | **TypeScript + Vite** | Type safety, hot module reload, ES modules |
| Isometric | Custom `IsoGrid.ts` | Proper 2.5D depth sorting, tile-to-screen math |
| Pathfinding | **EasyStar.js** | A* on tile grid — agents walk around buildings |
| Terrain | **simplex-noise** | Procedural rivers, hills, empty grassland on day 1 |
| Sprites | **Kenney Isometric City Kit** (free, CC0) | SimCity-quality pre-made isometric tiles |
| Tweens | **GSAP** | Smooth agent movement between tiles |
| Backend | Same Python/FastAPI + add `world_tiles` table | Tile state persisted in PostgreSQL |

Full Phase 6 plan: [`docs/phase6/PHASE6_MASTER_PLAN.md`](docs/phase6/PHASE6_MASTER_PLAN.md)

---

## Project structure

```
aicity/
│
├── main_phase3.py              # Run this to start the simulation
├── requirements.txt            # Python dependencies
├── env.example                 # Copy to .env and fill in API keys
│
├── src/
│   ├── agents/
│   │   ├── agent.py            # Agent class — DNA of every citizen
│   │   ├── brain.py            # Routes each role to the right LLM
│   │   ├── behaviors.py        # What each role does each day
│   │   ├── factory.py          # Spawns the 10 founding citizens
│   │   ├── messaging.py        # Agent-to-agent message system
│   │   ├── newspaper.py        # Daily/weekly/monthly stories
│   │   ├── relationships.py    # Bond strength between every agent pair
│   │   └── gang.py             # Gang formation, recruitment, collapse
│   │
│   ├── economy/
│   │   ├── token_engine.py     # All token operations — single source of truth
│   │   ├── transfers.py        # Bilateral transfers: theft, fines, trades
│   │   ├── projects.py         # Collaborative infrastructure projects
│   │   └── assets.py           # Standing city assets and daily benefits
│   │
│   ├── justice/
│   │   ├── court.py            # Crime queue + trial runner
│   │   ├── judge.py            # LLM judge → real verdict
│   │   └── case_manager.py     # Open cases, investigations
│   │
│   ├── city/
│   │   ├── event_log.py        # All events with visibility levels
│   │   ├── position_manager.py # Agent tile positions, zone routing
│   │   ├── home_manager.py     # Home lot assignment
│   │   └── meeting_manager.py  # Meeting detection + outcome dispatch
│   │
│   ├── memory/
│   │   ├── memory_v2.py        # Per-agent Qdrant memory + shared city knowledge
│   │   └── persistence.py      # Save/load full city state
│   │
│   ├── os/
│   │   └── city_v3.py          # Main city runner — orchestrates every day
│   │
│   ├── dashboard/
│   │   ├── server.py           # FastAPI + WebSocket server
│   │   └── static/
│   │       ├── index.html      # Dashboard page
│   │       ├── app.css         # Dark terminal aesthetic
│   │       ├── app.js          # Real-time dashboard + fullscreen view
│   │       └── game/           # Phase 5 Phaser 3 city (replaced in Phase 6)
│   │           ├── main.js
│   │           ├── scenes/     # BootScene, CityScene, UIScene
│   │           ├── systems/    # AgentManager, DayNight, EventAnimator, MapManager
│   │           └── data/       # zones.js, roleConfig.js, citymap.json
│   │
│   ├── migrations/
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_newborn_comprehension.sql
│   │   ├── 003_stories.sql
│   │   ├── 004_event_log.sql
│   │   ├── 005_mood.sql
│   │   ├── 006_police_cases.sql
│   │   ├── 007_villains.sql
│   │   ├── 008_city_infrastructure.sql
│   │   └── 009_world_tiles.sql       # Phase 6 — isometric tile grid
│   │
│   └── world/
│       └── tile_manager.py           # Phase 6 — tile CRUD + world generation
│
└── docs/
    ├── phase1/         # Setup, agent design, token rules
    ├── phase2/         # LLM brain design, memory architecture
    ├── phase3/         # Economy, trial system, dashboard
    ├── phase4/         # Gang system, blackmail, corruption, event log
    ├── phase5/         # Phaser city canvas plan
    └── phase6/
        └── PHASE6_MASTER_PLAN.md   # Full isometric rebuild — every detail
```

---

## How to run it locally (Phase 5)

You need: Python 3.12+, PostgreSQL, Redis, Qdrant, and an Anthropic API key.

```bash
# 1. Clone
git clone https://github.com/pavansaipendry/aicity.git
cd aicity

# 2. Virtual environment
python -m venv .venv
source .venv/bin/activate   # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp env.example .env
# Open .env and fill in: ANTHROPIC_API_KEY, DATABASE_URL, etc.

# 5. Set up the database
psql -d aicity -f src/migrations/001_initial_schema.sql
psql -d aicity -f src/migrations/002_newborn_comprehension.sql
psql -d aicity -f src/migrations/003_stories.sql
psql -d aicity -f src/migrations/004_event_log.sql
psql -d aicity -f src/migrations/005_mood.sql
psql -d aicity -f src/migrations/006_police_cases.sql
psql -d aicity -f src/migrations/007_villains.sql
psql -d aicity -f src/migrations/008_city_infrastructure.sql
psql -d aicity -f src/migrations/009_world_tiles.sql

# 6. Start the dashboard (terminal 1)
uvicorn src.dashboard.server:app --port 8000 --reload

# 7. Run the simulation (terminal 2)
python main_phase3.py
```

Open `http://localhost:8000` — the dashboard loads automatically.

### Phase 6 isometric canvas (Sprint 1 — in progress)

```bash
# In a third terminal — run the Vite dev server
cd client
npm install
npm run dev
```

Open `http://localhost:5173` — PixiJS isometric canvas with programmatic tile rendering.
The canvas connects to the FastAPI backend at port 8000 via proxy.
Click **City** tab to see the Phaser canvas.
Click **⛶ FULLSCREEN** in the header to open the fullscreen city + conversation view.

---

## The rules agents live by (the Constitution)

```
Law I   — No agent may harm city infrastructure intentionally.
Law II  — No agent may claim ownership of the city itself.
Law III — Every agent has the right to exist until natural death, unless convicted.
Law IV  — No agent may impersonate another agent's identity.
Law V   — The dead are remembered. Funerals are mandatory. Every life has weight.
Law VI  — Humans may observe and set the Constitution, but not interfere with daily life.
Law VII — The city grows itself. No agent may stop growth.
Law VIII — Only the Founder can destroy AIcity entirely. (The Red Button)
```

---

## Things I've noticed after running this

- A police officer (Dario Cole) built an informant network with an explorer over 30+ days — purely from their own conversations
- A blackmailer tried to flip that informant. The informant reported her to the police instead.
- A gang leader and a blackmailer spent 17 days "finalizing their alliance" with no mechanical outcome. The meeting mechanic now makes that real — they walk to the same zone and a DB record gets created.
- The city archive sat unbuilt for 40 days because the builder kept saying "discuss the archive" and the project system didn't recognize it. Fixed.
- Corrupt police quietly buried arrests. Nobody knew. The event log has it all.
- The newspaper is genuinely good. The LLM writes with actual drama.
- Watching an agent die after 30 days hits different when you know their whole history.
- A thief messaged the police officer warning her that someone was about to rob her — and then robbed her anyway the next day.

---

## What Phase 6 will look like

The city starts as **empty grass** on Day 1. No roads, no buildings — nothing.

Builders meet, talk, and decide to lay a road. You watch it happen: wooden stakes
appear first, then foundation tiles, then the finished road stretches across the
field. More builders working together means faster construction.

Villains lurk near the dark alley. Police patrols the streets. When a theft
happens, you watch the police sprint across real roads using A* pathfinding to
catch the criminal. Speech bubbles float above agents' heads as they talk.

Every structure in the city was decided on and built by an LLM agent. The world
is empty until they make it real.

Full plan with every implementation detail: [`docs/phase6/PHASE6_MASTER_PLAN.md`](docs/phase6/PHASE6_MASTER_PLAN.md)

---

Built by **Pavan** — student, February 2026
