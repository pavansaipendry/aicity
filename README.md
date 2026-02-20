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
- All of this is visible in real time on a live web dashboard — and soon, as a pixel-art city you can watch

---

## Phases built so far

| Phase | Name | Status | What it added |
|-------|------|--------|---------------|
| 1 | The Skeleton | ✅ Done | Agents, token economy, death, basic memory |
| 2 | The Citizens | ✅ Done | LLM brains, messaging, shared memory, daily newspaper |
| 3 | The City | ✅ Done | Real transfers, trial system, births, PostgreSQL, relationships, live dashboard |
| 4 | Deep Bonds | ✅ Done | Gang formation, blackmail, saboteur role, mood system, police corruption, event log, collaborative projects, city assets |
| 5 | The Living City | 🔧 In Progress | Pixel-art 2D city, agent sprites, real movement, day/night cycle, meeting mechanic, home ownership |

---

## Tech stack

| Thing | What it's for |
|-------|--------------|
| Claude Sonnet | Powers the Police, Lawyer, and the monthly chronicle writer |
| GPT-4o | Powers most agents (builders, explorers, teachers, healers, etc.) |
| Groq / Llama 3.3 | Free cloud inference for merchants and messengers |
| PostgreSQL | Stores agent balances, all transactions, stories, agent state, criminal alliances |
| Qdrant | Long-term memory — each agent has their own private "memory collection" |
| Redis | Short-term inbox — agents send and receive messages here |
| FastAPI + WebSocket | Serves the live dashboard and game canvas |
| Phaser 3 | Browser game engine for the 2D pixel-art city (Phase 5) |
| Python 3.12 | Everything is Python |

---

## Project structure

```
aicity/
│
├── main_phase3.py          # Run this to start the simulation
├── requirements.txt        # Python dependencies
├── env.example             # Copy this to .env and fill in your API keys
│
├── tools/
│   └── generate_citymap.py     # Generates the Tiled tilemap + placeholder PNG tilesets
│
├── src/
│   ├── agents/
│   │   ├── agent.py            # The Agent class — DNA of every citizen
│   │   ├── brain.py            # Routes each role to the right LLM (Claude/GPT-4o/Groq)
│   │   ├── behaviors.py        # What each role does each day (earnings, theft, arrests, blackmail, etc.)
│   │   ├── factory.py          # Spawns the founding 10 citizens at the start
│   │   ├── messaging.py        # Agent-to-agent message system (Redis inbox)
│   │   ├── newspaper.py        # Daily/weekly/monthly stories (GPT-4o + Claude)
│   │   ├── relationships.py    # Bond strength between every agent pair (-1.0 to +1.0)
│   │   └── gang.py             # Gang formation, recruitment, exposure, and collapse
│   │
│   ├── economy/
│   │   ├── token_engine.py     # All token operations — single source of truth
│   │   ├── transfers.py        # Bilateral transfers: theft, court fines, trades
│   │   ├── projects.py         # Collaborative infrastructure projects (hospital, school, archive, etc.)
│   │   └── assets.py           # Standing city assets and their daily benefits
│   │
│   ├── justice/
│   │   ├── court.py            # Queues crime reports and runs trials
│   │   ├── judge.py            # LLM judge that reads the case and returns a real verdict
│   │   └── case_manager.py     # Tracks open cases, victim reports, police investigations
│   │
│   ├── city/
│   │   ├── event_log.py        # Logs all events with visibility levels (PRIVATE → PUBLIC)
│   │   ├── position_manager.py # Agent tile positions, zone routing, patrol waypoints (Phase 5)
│   │   ├── home_manager.py     # Home lot assignment and window light state (Phase 5)
│   │   └── meeting_manager.py  # Meeting detection + outcome dispatch (Phase 5)
│   │
│   ├── memory/
│   │   ├── memory_v2.py        # Per-agent private memory in Qdrant + shared city knowledge
│   │   └── persistence.py      # Saves/loads the full city state to PostgreSQL
│   │
│   ├── os/
│   │   └── city_v3.py          # Main city runner — orchestrates every single day
│   │
│   ├── dashboard/
│   │   ├── server.py           # FastAPI server — events, WebSocket, game state caching
│   │   └── static/
│   │       ├── index.html      # Dashboard page (with City tab for Phaser game)
│   │       ├── app.css         # Styles (dark terminal aesthetic + game canvas)
│   │       ├── app.js          # Real-time dashboard logic
│   │       └── game/
│   │           ├── main.js         # Phaser 3 game config
│   │           ├── scenes/
│   │           │   ├── BootScene.js    # Asset preloader
│   │           │   └── CityScene.js    # Tilemap render + WebSocket event handler
│   │           ├── data/
│   │           │   ├── citymap.json    # 96×72 Tiled tilemap (generated)
│   │           │   ├── zones.js        # LOC_* zone constants
│   │           │   └── roleConfig.js   # Role → color/sprite mapping
│   │           └── assets/
│   │               └── tilesets/       # terrain.png, buildings.png, nature.png
│   │
│   └── migrations/
│       ├── 001_initial_schema.sql
│       ├── 002_newborn_comprehension.sql
│       ├── 003_stories.sql
│       ├── 004_event_log.sql
│       ├── 005_mood.sql
│       ├── 006_police_cases.sql
│       ├── 007_villains.sql
│       ├── 008_city_infrastructure.sql
│       └── 009_phase5_positions.sql    # Agent positions, meeting events, criminal alliances
│
└── docs/
    ├── phase4/         # Phase 4 design notes
    └── phase5/
        └── planofAction.md     # Full Phase 5 plan — the single source of truth
```

---

## How to run it locally

You need: Python 3.12+, PostgreSQL, Redis, Qdrant, and API keys for Anthropic + OpenAI (+ optionally Groq).

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
# Open .env and fill in your API keys

# 5. Set up the database (run all migrations in order)
psql -d aicity -f src/migrations/001_initial_schema.sql
psql -d aicity -f src/migrations/002_newborn_comprehension.sql
psql -d aicity -f src/migrations/003_stories.sql
psql -d aicity -f src/migrations/004_event_log.sql
psql -d aicity -f src/migrations/005_mood.sql
psql -d aicity -f src/migrations/006_police_cases.sql
psql -d aicity -f src/migrations/007_villains.sql
psql -d aicity -f src/migrations/008_city_infrastructure.sql
psql -d aicity -f src/migrations/009_phase5_positions.sql

# 6. Generate the city tilemap (Phase 5)
python tools/generate_citymap.py

# 7. Start the dashboard (terminal 1)
uvicorn src.dashboard.server:app --port 8000 --reload

# 8. Run the simulation (terminal 2)
python main_phase3.py
```

Open `http://localhost:8000` — click the **City** tab to see the Phaser canvas.

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
- A gang leader and a blackmailer spent 17 days "finalizing their alliance" with no mechanical outcome. The meeting mechanic (Phase 5) now makes that real — they walk to the same zone and a DB record gets created.
- The city archive sat unbuilt for 40 days because the builder kept saying "discuss the archive" and the project system didn't recognize it. Fixed.
- Corrupt police quietly buried arrests. Nobody knew. The event log has it all.
- The newspaper is genuinely good. The LLM writes with actual drama.
- Watching an agent die after 30 days hits different when you know their whole history.

---

## What's coming in Phase 5

The simulation is already running. Phase 5 makes it **visible**.

- Pixel-art sprites (16×16) for all 13 roles walking around a real city map
- Day/night cycle: dawn → morning → afternoon → evening → night
- Agents physically walk from home to work, criminals lurk in the dark alley at night
- Buildings materialize on the map when projects complete
- Token particles fly between sprites when theft happens
- Gravestones appear when agents die
- Cats, dogs, and birds wander the streets
- The public watches live in a browser — no controls, pure observation

---

Built by **Pavan** — student, February 2026
