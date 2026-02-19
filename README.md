# AIcity — An AI Civilization That Runs Itself

> *"Exist. Grow. Discover."* — hardcoded into every agent at birth

This is a personal project I've been building since February 2026. It's an autonomous AI city where LLM-powered agents are born, earn tokens to survive, form relationships, steal from each other, get arrested, go to trial, die, and get buried — all without me telling them what to do day-to-day.

It's not a chatbot. It's not a product. It's more like a digital ant farm, except the ants have GPT-4o brains and their own economy.

---

## What's actually happening when you run it

- 10 founding agents are born with 1,000 tokens each
- Every day costs 100 tokens just to exist (burn rate)
- Each agent has a role (builder, thief, police, etc.) and uses an LLM to decide what to do
- Agents can earn tokens, steal from each other, send messages, heal the sick, arrest criminals
- If you run out of tokens → you starve and die. Permanently.
- Population stays above 6 by spawning newborns automatically
- Every 7 days a messenger agent writes a "Week in Review". On day 30, a full monthly chronicle
- All of this is visible in real time on a live web dashboard

---

## Phases built so far

| Phase | Name | Status | What it added |
|-------|------|--------|---------------|
| 1 | The Skeleton | ✅ Done | Agents, token economy, death, basic memory |
| 2 | The Citizens | ✅ Done | LLM brains, messaging, shared memory, daily newspaper |
| 3 | The City | ✅ Done | Real transfers, trial system, births, PostgreSQL, relationships, live dashboard |
| 4 | Deep Bonds | 🔄 Planning | Bond-driven decisions, gang formation, grudges |

---

## Tech stack (what I actually use)

| Thing | What it's for |
|-------|--------------|
| Claude Sonnet | Powers the Police, Lawyer, and the monthly chronicle writer |
| GPT-4o | Powers most agents (builders, explorers, teachers, healers, etc.) |
| Groq / Llama 3.3 | Free cloud inference for merchants and messengers |
| PostgreSQL | Stores agent balances, all transactions, stories, agent state |
| Qdrant | Long-term memory — each agent has their own private "memory collection" |
| Redis | Short-term inbox — agents send and receive messages here |
| FastAPI + WebSocket | Serves the live dashboard |
| Python 3.12 | Everything is Python |

---

## Project structure

```
aicity/
│
├── main_phase3.py          # Run this to start the simulation (Phase 3)
├── main_phase2.py          # Phase 2 runner (kept for reference)
├── main.py                 # Original Phase 1 runner
├── requirements.txt        # Python dependencies
├── env.example             # Copy this to .env and fill in your API keys
│
├── src/
│   ├── agents/
│   │   ├── agent.py            # The Agent class — DNA of every citizen
│   │   ├── brain.py            # Routes each role to the right LLM (Claude/GPT-4o/Groq)
│   │   ├── behaviors.py        # What each role actually does each day (earnings, theft, arrests, etc.)
│   │   ├── factory.py          # Spawns the founding citizens at the start
│   │   ├── messaging.py        # Agent-to-agent message system (Redis inbox)
│   │   ├── newspaper.py        # The Messenger writes daily/weekly/monthly stories (GPT-4o + Claude)
│   │   ├── relationships.py    # Tracks bond strength between every pair of agents (-1.0 to +1.0)
│   │   └── births.py           # Spawns new agents when population drops below 6
│   │
│   ├── economy/
│   │   ├── token_engine.py     # All token operations hit the DB — single source of truth
│   │   ├── transfers.py        # Bilateral transfers: theft, court fines, trades
│   │   └── schema.sql          # The token ledger schema (every transaction ever)
│   │
│   ├── justice/
│   │   ├── court.py            # Queues crime reports and runs trials
│   │   └── judge.py            # LLM judge that reads the case and returns a real verdict
│   │
│   ├── memory/
│   │   ├── memory_v2.py        # Per-agent private memory in Qdrant + shared city knowledge
│   │   ├── memory_system.py    # Original Phase 1 memory (kept for reference)
│   │   └── persistence.py      # Saves/loads the full city state to PostgreSQL
│   │
│   ├── os/
│   │   ├── city_v3.py          # Main city runner — orchestrates every single day
│   │   ├── city_v2.py          # Phase 2 city runner (kept for reference)
│   │   ├── city.py             # Phase 1 city runner (kept for reference)
│   │   └── death_manager.py    # Handles what happens when an agent dies
│   │
│   ├── dashboard/
│   │   ├── server.py           # FastAPI server — receives simulation events, broadcasts via WebSocket
│   │   └── static/
│   │       ├── index.html      # The dashboard page
│   │       ├── app.css         # All the styles (dark terminal aesthetic)
│   │       └── app.js          # All the dashboard logic — real-time updates, graphs, graveyard, etc.
│   │
│   └── migrations/
│       ├── 001_initial_schema.sql      # Creates agents, transactions, newspapers tables
│       ├── 002_newborn_comprehension.sql   # Adds newborn learning system
│       └── 003_stories.sql             # Creates the stories table (daily/weekly/monthly archive)
│
├── docs/
│   ├── phase1/         # Notes and design docs from Phase 1
│   ├── phase2/         # Notes from Phase 2
│   └── phase3/         # Phase 3 plan and feature specs
│
├── tests/
│   ├── test_agent.py           # Tests for the Agent class
│   ├── test_tokens.py          # Tests for the token engine
│   ├── test_transfers.py       # Tests for real bilateral transfers
│   └── test_phase2.py          # Phase 2 integration tests
│
└── scripts/
    └── verify_setup.py         # Quick check to make sure everything is connected
```

---

## How to run it locally

You need: Python 3.12+, PostgreSQL, Redis, Qdrant, and API keys for Anthropic + OpenAI (+ optionally Groq for free Llama inference).

```bash
# 1. Clone
git clone https://github.com/pavansaipendry/aicity.git
cd aicity

# 2. Virtual environment
python -m venv .venv
source .venv/bin/activate   # Mac/Linux
# .venv\Scripts\activate    # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp env.example .env
# Open .env and fill in your keys

# 5. Set up the database
# Make sure PostgreSQL is running, then:
psql -U postgres -d aicity -f src/migrations/001_initial_schema.sql
psql -U postgres -d aicity -f src/migrations/002_newborn_comprehension.sql
psql -U postgres -d aicity -f src/migrations/003_stories.sql

# 6. Start the dashboard (in one terminal)
uvicorn src.dashboard.server:app --port 8000 --reload

# 7. Run the simulation (in another terminal)
python main_phase3.py
```

Then open `http://localhost:8000` in your browser and watch the city live.

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

## A few things I've noticed after running this

- The merchant always ends up richest. Economy 101.
- The thief almost always gets caught eventually — police build grudges.
- Newborns are the most vulnerable citizens. Two bad days and they're gone.
- The newspaper is genuinely good. GPT-4o writes with actual drama.
- Watching an agent die and get added to the graveyard hits different when you've been watching them for 15 days.

---

## What's next (Phase 4)

Making bonds actually matter. Right now the thief just attacks whoever has the most tokens. In Phase 4, agents will remember who wronged them, build alliances, and make decisions based on who they trust — not just who is richest.

---

Built by **Pavan** — student, February 2026
